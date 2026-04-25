// SHARED MODEL — Keep in sync with d:/Bake Smart/lib/features/products/models/product_model.dart
import 'package:cloud_firestore/cloud_firestore.dart';

class RecipeIngredient {
  final String ingredientId;
  final String name; 
  final double quantityUsed;
  final double measuredCostPrice;

  RecipeIngredient({
    required this.ingredientId,
    required this.name,
    required this.quantityUsed,
    required this.measuredCostPrice,
  });

  Map<String, dynamic> toMap() {
    return {
      'ingredientId': ingredientId,
      'name': name,
      'quantityUsed': quantityUsed,
      'measuredCostPrice': measuredCostPrice,
    };
  }

  factory RecipeIngredient.fromMap(Map<String, dynamic> map) {
    return RecipeIngredient(
      ingredientId: map['ingredientId'] ?? '',
      name: map['name'] ?? '',
      quantityUsed: (map['quantityUsed'] ?? 0).toDouble(),
      measuredCostPrice: (map['measuredCostPrice'] ?? 0).toDouble(),
    );
  }
}

class ProductModel {
  final String productId;
  final String bakerId;
  final String bakerName;
  final bool bakerIsVerified;
  final String name;
  final String description;
  final String category;
  final List<String> tags;
  final double basePrice;
  final double costPrice;
  final bool isSurplus;
  final double? surplusPrice;
  final List<String> images;
  final bool isAvailable;
  final List<RecipeIngredient> recipeIngredients;
  final DateTime createdAt;
  final DateTime updatedAt;

  ProductModel({
    required this.productId,
    required this.bakerId,
    required this.bakerName,
    required this.bakerIsVerified,
    required this.name,
    required this.description,
    required this.category,
    required this.tags,
    required this.basePrice,
    required this.costPrice,
    this.isSurplus = false,
    this.surplusPrice,
    required this.images,
    this.isAvailable = true,
    required this.recipeIngredients,
    required this.createdAt,
    required this.updatedAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'productId': productId,
      'bakerId': bakerId,
      'bakerName': bakerName,
      'bakerIsVerified': bakerIsVerified,
      'name': name,
      'description': description,
      'category': category,
      'tags': tags,
      'basePrice': basePrice,
      'costPrice': costPrice,
      'isSurplus': isSurplus,
      'surplusPrice': surplusPrice,
      'images': images,
      'isAvailable': isAvailable,
      'recipeIngredients': recipeIngredients.map((x) => x.toMap()).toList(),
      'createdAt': Timestamp.fromDate(createdAt),
      'updatedAt': Timestamp.fromDate(updatedAt),
    };
  }

  factory ProductModel.fromMap(Map<String, dynamic> map, String docId) {
    return ProductModel(
      productId: map['productId'] ?? docId,
      bakerId: map['bakerId'] ?? '',
      bakerName: map['bakerName'] ?? 'Unknown Baker',
      bakerIsVerified: map['bakerIsVerified'] ?? false,
      name: map['name'] ?? '',
      description: map['description'] ?? '',
      category: map['category'] ?? '',
      tags: List<String>.from(map['tags'] ?? []),
      basePrice: (map['basePrice'] ?? 0).toDouble(),
      costPrice: (map['costPrice'] ?? 0).toDouble(),
      isSurplus: map['isSurplus'] ?? false,
      surplusPrice: map['surplusPrice'] != null ? (map['surplusPrice']).toDouble() : null,
      images: List<String>.from(map['images'] ?? []),
      isAvailable: map['isAvailable'] ?? true,
      recipeIngredients: List<RecipeIngredient>.from(
        (map['recipeIngredients'] ?? []).map((x) => RecipeIngredient.fromMap(x)),
      ),
      createdAt: (map['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      updatedAt: (map['updatedAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }
}
