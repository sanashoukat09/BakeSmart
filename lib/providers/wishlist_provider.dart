import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final wishlistProvider = StateNotifierProvider<WishlistNotifier, List<String>>((ref) {
  return WishlistNotifier();
});

class WishlistNotifier extends StateNotifier<List<String>> {
  WishlistNotifier() : super([]) {
    _loadWishlist();
  }

  static const _wishlistKey = 'bakesmart_wishlist';

  Future<void> _loadWishlist() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList(_wishlistKey);
    if (list != null) {
      state = list;
    }
  }

  Future<void> _saveWishlist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_wishlistKey, state);
  }

  bool toggleWishlist(String productId) {
    final exists = state.contains(productId);
    if (exists) {
      state = state.where((id) => id != productId).toList();
    } else {
      state = [...state, productId];
    }
    _saveWishlist();
    return !exists; // returns true if added, false if removed
  }

  bool isWishlisted(String productId) {
    return state.contains(productId);
  }
}
