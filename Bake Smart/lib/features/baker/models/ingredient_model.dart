import 'package:cloud_firestore/cloud_firestore.dart';

class IngredientModel {
  final String ingredientId;
  final String bakerId;
  final String name;
  final double quantity;
  final String unit; // 'grams', 'kg', 'litres', 'pieces'
  final double lowStockThreshold;
  final DateTime? expiryDate;
  final String status; // 'in_stock', 'low', 'expired', 'out_of_stock'

  IngredientModel({
    required this.ingredientId,
    required this.bakerId,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.lowStockThreshold,
    this.expiryDate,
    required this.status,
  });

  // Automatically recalculates the status based on fields
  static String calculateStatus(double quantity, double lowStockThreshold, DateTime? expiryDate) {
    if (quantity <= 0) {
      return 'out_of_stock';
    }
    
    if (expiryDate != null) {
      // Stripping time for an accurate 'before today' check
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final expiryDay = DateTime(expiryDate.year, expiryDate.month, expiryDate.day);
      if (expiryDay.isBefore(today)) {
        return 'expired';
      }
    }
    
    if (quantity < lowStockThreshold) {
      return 'low';
    }
    
    return 'in_stock';
  }

  IngredientModel copyWith({
    String? ingredientId,
    String? bakerId,
    String? name,
    double? quantity,
    String? unit,
    double? lowStockThreshold,
    DateTime? expiryDate,
    String? status,
  }) {
    return IngredientModel(
      ingredientId: ingredientId ?? this.ingredientId,
      bakerId: bakerId ?? this.bakerId,
      name: name ?? this.name,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      lowStockThreshold: lowStockThreshold ?? this.lowStockThreshold,
      expiryDate: expiryDate ?? this.expiryDate,
      status: status ?? this.status,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'ingredientId': ingredientId,
      'bakerId': bakerId,
      'name': name,
      'quantity': quantity,
      'unit': unit,
      'lowStockThreshold': lowStockThreshold,
      'expiryDate': expiryDate != null ? Timestamp.fromDate(expiryDate!) : null,
      'status': status,
    };
  }

  factory IngredientModel.fromMap(Map<String, dynamic> map, String docId) {
    return IngredientModel(
      ingredientId: map['ingredientId'] ?? docId,
      bakerId: map['bakerId'] ?? '',
      name: map['name'] ?? '',
      quantity: (map['quantity'] ?? 0).toDouble(),
      unit: map['unit'] ?? 'grams',
      lowStockThreshold: (map['lowStockThreshold'] ?? 0).toDouble(),
      expiryDate: (map['expiryDate'] as Timestamp?)?.toDate(),
      status: map['status'] ?? 'in_stock',
    );
  }
}
