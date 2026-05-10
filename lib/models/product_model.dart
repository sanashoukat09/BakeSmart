import 'package:cloud_firestore/cloud_firestore.dart';

class ProductModel {
  final String id;
  final String bakerId;
  final String name;
  final String description;
  final double price;
  final String category;
  final List<String> images;
  final List<String> dietaryLabels;

  /// Market-friendly flags for dietary-label completeness.
  /// - includesAllDietaryLabels=true means the product should be treated as safe
  ///   for all recognized dietary labels (e.g. Eggless, Gluten-Free, etc.).
  /// - includesNoDietaryLabels=true means the product has none of the recognized
  ///   dietary labels.
  ///
  /// When a baker selects these, dietaryLabels may be empty.
  final bool includesAllDietaryLabels;
  final bool includesNoDietaryLabels;

  final bool isAvailable;
  final Map<String, double> ingredients; // ingredientId: quantityNeeded
  final Map<String, double> addOns; // label: price
  final double profitMargin; // Percentage, e.g. 30.0 for 30%
  final DateTime createdAt;

  ProductModel({
    required this.id,
    required this.bakerId,
    required this.name,
    required this.description,
    required this.price,
    required this.category,
    required this.images,
    this.dietaryLabels = const [],
    this.includesAllDietaryLabels = false,
    this.includesNoDietaryLabels = false,
    this.isAvailable = true,
    this.ingredients = const {},
    this.addOns = const {},
    this.profitMargin = 30.0,
    required this.createdAt,
  });


  factory ProductModel.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return ProductModel(
      id: doc.id,
      bakerId: data['bakerId'] ?? '',
      name: data['name'] ?? '',
      description: data['description'] ?? '',
      price: (data['price'] ?? 0.0).toDouble(),
      category: data['category'] ?? '',
      images: List<String>.from(data['images'] ?? []),
      dietaryLabels: List<String>.from(data['dietaryLabels'] ?? []),
      includesAllDietaryLabels: data['includesAllDietaryLabels'] ?? false,
      includesNoDietaryLabels: data['includesNoDietaryLabels'] ?? false,
      isAvailable: data['isAvailable'] ?? true,
      ingredients: Map<String, double>.from(
          (data['ingredients'] as Map? ?? {}).map(
        (key, value) => MapEntry(key.toString(), value.toDouble()),
      )),
      addOns: Map<String, double>.from(
          (data['addOns'] as Map? ?? {}).map(
        (key, value) => MapEntry(key.toString(), value.toDouble()),
      )),
      profitMargin: (data['profitMargin'] ?? 30.0).toDouble(),
      createdAt: (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'bakerId': bakerId,
      'name': name,
      'description': description,
      'price': price,
      'category': category,
      'images': images,
      'dietaryLabels': dietaryLabels,
      'includesAllDietaryLabels': includesAllDietaryLabels,
      'includesNoDietaryLabels': includesNoDietaryLabels,
      'isAvailable': isAvailable,
      'ingredients': ingredients,
      'addOns': addOns,
      'profitMargin': profitMargin,
      'createdAt': Timestamp.fromDate(createdAt),
    };
  }

  ProductModel copyWith({
    String? name,
    String? description,
    double? price,
    String? category,
    List<String>? images,
    List<String>? dietaryLabels,
    bool? includesAllDietaryLabels,
    bool? includesNoDietaryLabels,
    bool? isAvailable,
    Map<String, double>? ingredients,
    Map<String, double>? addOns,
    double? profitMargin,
  }) {
    return ProductModel(
      id: id,
      bakerId: bakerId,
      name: name ?? this.name,
      description: description ?? this.description,
      price: price ?? this.price,
      category: category ?? this.category,
      images: images ?? this.images,
      dietaryLabels: dietaryLabels ?? this.dietaryLabels,
      includesAllDietaryLabels:
          includesAllDietaryLabels ?? this.includesAllDietaryLabels,
      includesNoDietaryLabels: includesNoDietaryLabels ?? this.includesNoDietaryLabels,
      isAvailable: isAvailable ?? this.isAvailable,
      ingredients: ingredients ?? this.ingredients,
      addOns: addOns ?? this.addOns,
      profitMargin: profitMargin ?? this.profitMargin,
      createdAt: createdAt,
    );
  }
}
