import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/ingredient_model.dart';
import 'auth_provider.dart';

// Stream of ingredients for the current baker
final bakerIngredientsProvider = StreamProvider<List<IngredientModel>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null || !user.isBaker) return Stream.value([]);

  return ref.watch(firestoreServiceProvider).streamBakerIngredients(user.uid);
});

// Low stock ingredients
final lowStockIngredientsProvider = Provider<List<IngredientModel>>((ref) {
  final ingredients = ref.watch(bakerIngredientsProvider).valueOrNull ?? [];
  return ingredients.where((i) => i.isLowStock).toList();
});

// Near expiry ingredients
final nearExpiryIngredientsProvider = Provider<List<IngredientModel>>((ref) {
  final ingredients = ref.watch(bakerIngredientsProvider).valueOrNull ?? [];
  return ingredients.where((i) => i.isNearExpiry).toList();
});

// Inventory Notifier for CRUD actions
class InventoryNotifier extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;

  InventoryNotifier(this._ref) : super(const AsyncValue.data(null));

  Future<void> saveIngredient(IngredientModel ingredient) async {
    state = const AsyncValue.loading();
    try {
      await _ref.read(firestoreServiceProvider).saveIngredient(ingredient);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> deleteIngredient(String ingredientId) async {
    state = const AsyncValue.loading();
    try {
      await _ref.read(firestoreServiceProvider).deleteIngredient(ingredientId);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> updateQuantity(String ingredientId, double newQuantity) async {
    try {
      await _ref
          .read(firestoreServiceProvider)
          .updateIngredientQuantity(ingredientId, newQuantity);
    } catch (e) {
      // Handle error
    }
  }
}

final inventoryNotifierProvider =
    StateNotifierProvider<InventoryNotifier, AsyncValue<void>>((ref) {
  return InventoryNotifier(ref);
});
