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
    // 1. Search Query Match
    final matchesQuery = product.name.toLowerCase().contains(filter.query.toLowerCase()) ||
        product.description.toLowerCase().contains(filter.query.toLowerCase());
    
    // 2. Category Match
    final matchesCategory = filter.category == null || product.category == filter.category;
    
    // 3. Dietary Preferences (Profile + Manual)
    final profileDietary = user?.dietaryPreferences ?? [];
    final manualDietary = filter.dietaryLabels;
    final activeDietary = {...profileDietary, ...manualDietary};
    
    final productLabelsLower = product.dietaryLabels.map((e) => e.toLowerCase().trim()).toSet();
    
    // For Preferences: If user prefers "Vegan", product should ideally be labeled "Vegan".
    // However, we allow products with NO labels to show UNLESS there's an allergy conflict.
    bool matchesPreferences = true;
    if (activeDietary.isNotEmpty) {
      // If user has specific preferences, the product should match AT LEAST ONE of them 
      // if it has any labels at all.
      if (productLabelsLower.isNotEmpty) {
        matchesPreferences = activeDietary.any((pref) => 
          productLabelsLower.contains(pref.toLowerCase().trim())
        );
      }
    }

    // 4. Strict Allergen Filtering (Safety)
    final customerAllergens = user?.allergens ?? [];
    bool matchesAllergens = true;

    // TEMP DEBUG: helps diagnose egg-allergy mismatch from stored values.
    // Only logs in debug mode.
    // ignore: avoid_print
    if (customerAllergens.isNotEmpty) {
      final debugAllergens = customerAllergens.toList();
      // ignore: avoid_print
      print('[DEBUG][store_provider] customerAllergens=$debugAllergens | product=${product.id} labels=${product.dietaryLabels}');
    }

    if (customerAllergens.isNotEmpty) {
      for (final allergenRaw in customerAllergens) {
        final allergen = allergenRaw.toLowerCase().trim();

        bool safeForThisAllergen = true;

        // Egg
        if (allergen.contains('egg')) {
          safeForThisAllergen =
              productLabelsLower.contains('eggless') ||
              productLabelsLower.contains('egg-free') ||
              productLabelsLower.contains('egg free') ||
              productLabelsLower.contains('eggs-free') ||
              productLabelsLower.contains('egg-free-all') ||
              productLabelsLower.contains('egg-free product');
        }
        // Nuts
        else if (allergen.contains('nut')) {
          safeForThisAllergen =
              productLabelsLower.contains('nut-free') ||
              productLabelsLower.contains('nut free') ||
              productLabelsLower.contains('tree nuts-free') ||
              productLabelsLower.contains('tree-nuts-free');
        }
        // Gluten
        else if (allergen.contains('gluten')) {
          safeForThisAllergen =
              productLabelsLower.contains('gluten-free') ||
              productLabelsLower.contains('gluten free');
        }
        // Sugar
        else if (allergen.contains('sugar')) {
          safeForThisAllergen =
              productLabelsLower.contains('sugar-free') ||
              productLabelsLower.contains('sugar free');
        }
        // Dairy / Milk
        else if (allergen.contains('dairy') || allergen.contains('milk')) {
          safeForThisAllergen =
              productLabelsLower.contains('dairy-free') ||
              productLabelsLower.contains('dairy free') ||
              productLabelsLower.contains('vegan');
        }

        // SAFETY RULE: If the product has NO dietary labels at all, 
        // we assume it is UNSAFE for anyone with an active allergy.
        if (productLabelsLower.isEmpty) {
          safeForThisAllergen = false;
        }

        if (!safeForThisAllergen) {
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
