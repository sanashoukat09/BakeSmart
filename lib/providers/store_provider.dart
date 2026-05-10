import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/product_model.dart';
import '../models/user_model.dart';
import 'auth_provider.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../core/constants/app_constants.dart';
import 'dart:async';

// Stream of all available products
final allProductsProvider = StreamProvider<List<ProductModel>>((ref) {
  return FirebaseFirestore.instance
      .collection(AppConstants.productsCollection)
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
  final productsAsync = ref.watch(allProductsProvider);
  final products = productsAsync.valueOrNull ?? [];
  final filter = ref.watch(storeFilterProvider);
  final user = ref.watch(currentUserProvider).valueOrNull;

  final filtered = products.where((product) {
    // 0. Availability Match
    if (!product.isAvailable) return false;

    // 1. Search Query Match
    final matchesQuery = product.name.toLowerCase().contains(filter.query.toLowerCase()) ||
        product.description.toLowerCase().contains(filter.query.toLowerCase());
    
    // 2. Category Match (Flexible: handles singular/plural and casing)
    bool matchesCategory = filter.category == null;
    if (filter.category != null) {
      final pCat = product.category.trim().toLowerCase();
      final fCat = filter.category!.trim().toLowerCase();
      matchesCategory = pCat == fCat || 
          pCat == '${fCat}s' || 
          fCat == '${pCat}s' ||
          pCat.replaceAll('s', '') == fCat.replaceAll('s', '');
    }
    
    // Helper to check if a product matches a specific dietary requirement (e.g. Eggless, Sugar-Free)
    bool checkRequirement(String req) {
      if (product.includesAllDietaryLabels) return true;
      if (product.includesNoDietaryLabels) return false;
      
      final label = req.toLowerCase().trim();
      final pLabels = product.dietaryLabels.map((e) => e.toLowerCase().trim()).toList();

      // Egg
      if (label.contains('egg')) {
        return pLabels.contains('eggless') ||
               pLabels.contains('egg-free') ||
               pLabels.contains('egg free') ||
               pLabels.contains('vegan');
      }
      // Nuts
      if (label.contains('nut')) {
        return pLabels.contains('nut-free') ||
               pLabels.contains('nut free') ||
               pLabels.contains('tree nuts-free');
      }
      // Gluten
      if (label.contains('gluten')) {
        return pLabels.contains('gluten-free') ||
               pLabels.contains('gluten free');
      }
      // Sugar
      if (label.contains('sugar')) {
        return pLabels.contains('sugar-free') ||
               pLabels.contains('sugar free');
      }
      // Dairy / Milk
      if (label.contains('dairy') || label.contains('milk')) {
        return pLabels.contains('dairy-free') ||
               pLabels.contains('dairy free') ||
               pLabels.contains('vegan');
      }
      
      // Default direct match
      return pLabels.contains(label);
    }

    // 3. Dietary Preferences (Active UI filters)
    bool matchesPreferences = true;
    if (filter.dietaryLabels.isNotEmpty) {
      for (final pref in filter.dietaryLabels) {
        if (!checkRequirement(pref)) {
          matchesPreferences = false;
          break;
        }
      }
    }

    // 4. Allergen Filtering (Automatic based on user profile)
    final customerAllergens = user?.allergens ?? [];
    bool matchesAllergens = true;

    if (customerAllergens.isNotEmpty) {
      for (final allergen in customerAllergens) {
        if (!checkRequirement(allergen)) {
          matchesAllergens = false;
          break;
        }
      }
    }

    return matchesQuery && matchesCategory && matchesPreferences && matchesAllergens;
  }).toList();

  // Sort by latest first
  filtered.sort((a, b) => b.createdAt.compareTo(a.createdAt));
  
  return filtered;
});

// Featured Bakers (Rated 4.5+)
final featuredBakersProvider = Provider<List<UserModel>>((ref) {
  final bakers = ref.watch(allBakersProvider).valueOrNull ?? [];
  return bakers.where((b) => b.rating >= 4.0).toList();
});
