import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/product_model.dart';
import '../models/user_model.dart';
import 'auth_provider.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../core/constants/app_constants.dart';

// Stream of all available products
final allProductsProvider = StreamProvider<List<ProductModel>>((ref) {
  return FirebaseFirestore.instance
      .collection(AppConstants.productsCollection)
      .where('isAvailable', isEqualTo: true)
      .snapshots()
      .map((snapshot) => snapshot.docs
          .map((doc) => ProductModel.fromFirestore(doc))
          .toList());
});

// Stream of all bakers
final allBakersProvider = StreamProvider<List<UserModel>>((ref) {
  return FirebaseFirestore.instance
      .collection(AppConstants.usersCollection)
      .where('role', isEqualTo: AppConstants.roleBaker)
      .snapshots()
      .map((snapshot) => snapshot.docs
          .map((doc) => UserModel.fromFirestore(doc))
          .toList());
});

// Search and Filter State
class StoreFilter {
  static const Object _unset = Object();

  final String query;
  final String? category;
  final List<String> dietaryLabels;

  StoreFilter({
    this.query = '',
    this.category,
    this.dietaryLabels = const [],
  });

  StoreFilter copyWith({
    String? query,
    Object? category = _unset,
    List<String>? dietaryLabels,
  }) {
    return StoreFilter(
      query: query ?? this.query,
      category: identical(category, _unset) ? this.category : category as String?,
      dietaryLabels: dietaryLabels ?? this.dietaryLabels,
    );
  }
}

final storeFilterProvider = StateProvider<StoreFilter>((ref) => StoreFilter());

// Filtered Products
final filteredProductsProvider = Provider<List<ProductModel>>((ref) {
  final products = ref.watch(allProductsProvider).valueOrNull ?? [];
  final filter = ref.watch(storeFilterProvider);
  final user = ref.watch(currentUserProvider).valueOrNull;

  // Base preferences from user profile
  final userDietary = user?.dietaryPreferences ?? [];

  return products.where((product) {
    final matchesQuery = product.name.toLowerCase().contains(filter.query.toLowerCase()) ||
        product.description.toLowerCase().contains(filter.query.toLowerCase());
    
    final matchesCategory = filter.category == null || product.category == filter.category;
    
    // Auto-filter by user's saved dietary profile + any manual filters
    final activeDietary = {...userDietary, ...filter.dietaryLabels};
    final matchesDietary = activeDietary.isEmpty ||
        activeDietary.every((label) => product.dietaryLabels.contains(label));

    return matchesQuery && matchesCategory && matchesDietary;
  }).toList();
});

// Featured Bakers (Rated 4.5+)
final featuredBakersProvider = Provider<List<UserModel>>((ref) {
  final bakers = ref.watch(allBakersProvider).valueOrNull ?? [];
  return bakers.where((b) => b.rating >= 4.0).toList();
});
