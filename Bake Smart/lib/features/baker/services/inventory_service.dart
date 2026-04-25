import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/ingredient_model.dart';

final inventoryServiceProvider = Provider<InventoryService>((ref) {
  return InventoryService(ref.watch(firestoreProvider));
});

final inventoryStreamProvider = StreamProvider<List<IngredientModel>>((ref) {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return const Stream.empty();

  final firestore = ref.watch(firestoreProvider);
  return firestore
      .collection('inventory')
      .where('bakerId', isEqualTo: user.uid)
      .snapshots()
      .map((snapshot) {
    return snapshot.docs
        .map((doc) => IngredientModel.fromMap(doc.data(), doc.id))
        .toList();
  });
});

class InventoryService {
  final FirebaseFirestore _firestore;

  InventoryService(this._firestore);

  Future<void> addIngredient(IngredientModel ingredient) async {
    final docRef = _firestore.collection('inventory').doc();
    final updatedIngredient = ingredient.copyWith(ingredientId: docRef.id);
    await docRef.set(updatedIngredient.toMap());
  }

  Future<void> updateIngredient(IngredientModel ingredient) async {
    await _firestore
        .collection('inventory')
        .doc(ingredient.ingredientId)
        .update(ingredient.toMap());
  }

  Future<void> updateQuantity(IngredientModel ingredient, double adjustment) async {
    double newQuantity = ingredient.quantity + adjustment;
    if (newQuantity < 0) newQuantity = 0;

    final newStatus = IngredientModel.calculateStatus(
      newQuantity,
      ingredient.lowStockThreshold,
      ingredient.expiryDate,
    );

    final updatedIngredient = ingredient.copyWith(
      quantity: newQuantity,
      status: newStatus,
    );

    await updateIngredient(updatedIngredient);
  }

  Future<void> deleteIngredient(String ingredientId) async {
    await _firestore.collection('inventory').doc(ingredientId).delete();
  }
}
