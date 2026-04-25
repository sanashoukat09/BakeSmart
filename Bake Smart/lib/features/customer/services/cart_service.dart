import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/cart_item_model.dart';

class CartNotifier extends Notifier<List<CartItemModel>> {
  @override
  List<CartItemModel> build() => [];

  // Check if we can safely add an item without a baker mismatch
  bool canAddItem(String incomingBakerId) {
    if (state.isEmpty) return true;
    return state.first.bakerId == incomingBakerId;
  }

  void addItem(CartItemModel item) {
    // If different baker, caller should have checked `canAddItem` and cleared if needed.
    // We enforce strictly:
    if (state.isNotEmpty && state.first.bakerId != item.bakerId) {
      throw Exception('Cart cannot contain items from multiple bakers.');
    }

    final existingIndex = state.indexWhere((i) => i.productId == item.productId);
    if (existingIndex >= 0) {
      final existingItem = state[existingIndex];
      final mutatedList = List<CartItemModel>.from(state);
      mutatedList[existingIndex] = existingItem.copyWith(
        quantity: existingItem.quantity + item.quantity,
      );
      state = mutatedList;
    } else {
      state = [...state, item];
    }
  }

  void updateQuantity(String productId, int modifier) {
    final existingIndex = state.indexWhere((i) => i.productId == productId);
    if (existingIndex >= 0) {
      final existingItem = state[existingIndex];
      final newQty = existingItem.quantity + modifier;

      if (newQty <= 0) {
        removeItem(productId);
      } else {
        final mutatedList = List<CartItemModel>.from(state);
        mutatedList[existingIndex] = existingItem.copyWith(quantity: newQty);
        state = mutatedList;
      }
    }
  }

  void setItemUnavailableError(String productId, bool hasError) {
    final existingIndex = state.indexWhere((i) => i.productId == productId);
    if (existingIndex >= 0) {
      final existingItem = state[existingIndex];
      final mutatedList = List<CartItemModel>.from(state);
      mutatedList[existingIndex] = existingItem.copyWith(isUnavailableError: hasError);
      state = mutatedList;
    }
  }

  void removeItem(String productId) {
    state = state.where((i) => i.productId != productId).toList();
  }

  void clearCart() {
    state = [];
  }

  double get subtotal {
    return state.fold(0.0, (sum, item) => sum + (item.unitPrice * item.quantity));
  }
  
  int get totalItemCount {
    return state.fold(0, (sum, item) => sum + item.quantity);
  }
}

final cartProvider = NotifierProvider<CartNotifier, List<CartItemModel>>(() {
  return CartNotifier();
});
