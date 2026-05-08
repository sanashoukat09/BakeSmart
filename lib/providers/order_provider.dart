import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/order_model.dart';
 import 'auth_provider.dart';
import '../core/constants/app_constants.dart';

// Stream of orders for the current baker
final bakerOrdersProvider = StreamProvider<List<OrderModel>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null || !user.isBaker) return Stream.value([]);

  return ref.watch(firestoreServiceProvider).streamBakerOrders(user.uid);
});

// Stream of total earnings
final totalEarningsProvider = StreamProvider<double>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null || !user.isBaker) return Stream.value(0.0);

  return ref.watch(firestoreServiceProvider).streamTotalEarnings(user.uid);
});

// Order Notifier for status updates
class OrderNotifier extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;

  OrderNotifier(this._ref) : super(const AsyncValue.data(null));

  Future<void> updateStatus(String orderId, String newStatus) async {
    state = const AsyncValue.loading();
    try {
      final firestore = _ref.read(firestoreServiceProvider);
      
      // Auto-reduce inventory when baker starts preparing or beyond
      final isProductionStage = newStatus == AppConstants.orderPreparing || 
                                newStatus == AppConstants.orderReady || 
                                newStatus == AppConstants.orderDelivered;

      if (isProductionStage) {
        final order = await firestore.getOrder(orderId);
        // Only reduce if it hasn't been deducted yet
        if (order != null && !order.inventoryDeducted) {
          for (var item in order.items) {
            final product = await firestore.getProduct(item.productId);
            if (product != null) {
              for (var entry in product.ingredients.entries) {
                final ingredientId = entry.key;
                final qtyPerUnit = entry.value;
                final totalToReduce = qtyPerUnit * item.quantity;
                await firestore.decrementIngredientStock(ingredientId, totalToReduce);
              }
            }
          }
          // Mark as deducted so we don't do it again
          await firestore.setOrderInventoryDeducted(orderId);
        }
      }

      await firestore.updateOrderStatus(orderId, newStatus);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final orderNotifierProvider =
    StateNotifierProvider<OrderNotifier, AsyncValue<void>>((ref) {
  return OrderNotifier(ref);
});
