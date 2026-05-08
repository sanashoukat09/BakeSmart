import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/cart_item_model.dart';
import '../models/product_model.dart';

final cartProvider = StateNotifierProvider<CartNotifier, List<CartItemModel>>((ref) {
  return CartNotifier();
});

class CartNotifier extends StateNotifier<List<CartItemModel>> {
  CartNotifier() : super([]) {
    _loadCart();
  }

  static const _cartKey = 'bakesmart_cart';

  Future<void> _loadCart() async {
    final prefs = await SharedPreferences.getInstance();
    final cartJson = prefs.getString(_cartKey);
    if (cartJson != null) {
      final List<dynamic> list = json.decode(cartJson);
      state = list.map((item) => CartItemModel.fromMap(item)).toList();
    }
  }

  Future<void> _saveCart() async {
    final prefs = await SharedPreferences.getInstance();
    final cartJson = json.encode(state.map((item) => item.toMap()).toList());
    await prefs.setString(_cartKey, cartJson);
  }

  void addItem(ProductModel product) {
    // Enforce one baker per order
    if (state.isNotEmpty && state.first.bakerId != product.bakerId) {
      // Different baker - clear cart and add new
      state = [
        CartItemModel(
          productId: product.id,
          bakerId: product.bakerId,
          productName: product.name,
          price: product.price,
          imageUrl: product.images.isNotEmpty ? product.images.first : null,
          quantity: 1,
        ),
      ];
    } else {
      final existingIndex = state.indexWhere((item) => item.productId == product.id);
      if (existingIndex != -1) {
        state = [
          for (int i = 0; i < state.length; i++)
            if (i == existingIndex)
              state[i].copyWith(quantity: state[i].quantity + 1)
            else
              state[i]
        ];
      } else {
        state = [
          ...state,
          CartItemModel(
            productId: product.id,
            bakerId: product.bakerId,
            productName: product.name,
            price: product.price,
            imageUrl: product.images.isNotEmpty ? product.images.first : null,
            quantity: 1,
          ),
        ];
      }
    }
    _saveCart();
  }

  void addItemFromModel(CartItemModel newItem) {
    if (state.isNotEmpty && state.first.bakerId != newItem.bakerId) {
      state = [newItem];
    } else {
      final existingIndex = state.indexWhere((item) => item.lineKey == newItem.lineKey);
      if (existingIndex != -1) {
        state = [
          for (int i = 0; i < state.length; i++)
            if (i == existingIndex)
              state[i].copyWith(quantity: state[i].quantity + 1)
            else
              state[i]
        ];
      } else {
        state = [...state, newItem];
      }
    }
    _saveCart();
  }

  void updateQuantity(String productId, int delta) {
    final existingIndex = state.indexWhere((item) => item.productId == productId);
    if (existingIndex == -1) return;
    updateLineQuantity(state[existingIndex].lineKey, delta);
  }

  void updateLineQuantity(String lineKey, int delta) {
    state = [
      for (final item in state)
        if (item.lineKey == lineKey)
          item.copyWith(quantity: (item.quantity + delta).clamp(1, 99))
        else
          item
    ];
    _saveCart();
  }

  void removeItem(String productId) {
    state = state.where((item) => item.productId != productId).toList();
    _saveCart();
  }

  void removeLine(String lineKey) {
    state = state.where((item) => item.lineKey != lineKey).toList();
    _saveCart();
  }

  void clearCart() {
    state = [];
    _saveCart();
  }

  double get totalAmount => state.fold(0, (sum, item) => sum + item.total);
  int get itemCount => state.fold(0, (sum, item) => sum + item.quantity);
}
