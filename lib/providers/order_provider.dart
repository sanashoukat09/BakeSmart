import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/order_model.dart';
import 'auth_provider.dart';
import '../core/constants/app_constants.dart';

// Stream of orders for the current baker
final bakerOrdersProvider = StreamProvider<List<OrderModel>>((ref) {
  final uid = ref.watch(currentUserProvider.select((user) => user.valueOrNull?.uid));
  final isBaker = ref.watch(currentUserProvider.select((user) => user.valueOrNull?.isBaker ?? false));

  if (uid == null || !isBaker) return Stream.value([]);

  return ref.watch(firestoreServiceProvider).streamBakerOrders(uid);
});

// Stream of total earnings
final totalEarningsProvider = StreamProvider<double>((ref) {
  final uid = ref.watch(currentUserProvider.select((user) => user.valueOrNull?.uid));
  final isBaker = ref.watch(currentUserProvider.select((user) => user.valueOrNull?.isBaker ?? false));

  if (uid == null || !isBaker) return Stream.value(0.0);

  return ref.watch(firestoreServiceProvider).streamTotalEarnings(uid);
});

// Order Notifier for status updates
class OrderNotifier extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;

  OrderNotifier(this._ref) : super(const AsyncValue.data(null));

  Future<void> updateStatus(String orderId, String newStatus) async {
    state = const AsyncValue.loading();
    try {
      final firestore = _ref.read(firestoreServiceProvider);

      final isProductionStage = newStatus == AppConstants.orderPreparing ||
          newStatus == AppConstants.orderReady ||
          newStatus == AppConstants.orderDelivered;

      final isCancellation = newStatus == AppConstants.orderCancelled ||
          newStatus == AppConstants.orderRejected;

      if (isCancellation) {
        final order = await firestore.getOrder(orderId);
        if (order == null) {
          throw Exception('Order not found.');
        }
        if (newStatus == AppConstants.orderCancelled && order.status != AppConstants.orderPlaced) {
          throw Exception('Only orders in the placed state can be cancelled.');
        }
        if (newStatus == AppConstants.orderRejected && order.status != AppConstants.orderPlaced) {
          throw Exception('Only orders in the placed state can be rejected.');
        }
      }

      // Atomic inventory handling is now delegated to FirestoreService.
      if (isProductionStage || isCancellation) {
        await firestore.updateOrderStatusWithAtomicInventory(
          orderId: orderId,
          newStatus: newStatus,
        );
      } else {
        await firestore.updateOrderStatus(orderId, newStatus);
      }

      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      // Let the UI show an alert/snackbar with the real error message.
      throw e;
    }
  }
}

final orderNotifierProvider =
    StateNotifierProvider<OrderNotifier, AsyncValue<void>>((ref) {
  return OrderNotifier(ref);
});

final allOrdersProvider = StreamProvider<List<OrderModel>>((ref) {
  return ref.watch(firestoreServiceProvider).streamAllOrders();
});
