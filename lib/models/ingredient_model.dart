import 'package:cloud_firestore/cloud_firestore.dart';

class IngredientModel {
  final String id;
  final String bakerId;
  final String name;
  final double quantity;
  final String unit; // e.g., 'kg', 'g', 'liters', 'pieces'
  final double unitPrice; // Cost per unit
  final DateTime? expiryDate;
  final double lowStockThreshold;
  final DateTime updatedAt;

  IngredientModel({
    required this.id,
    required this.bakerId,
    required this.name,
    required this.quantity,
    required this.unit,
    this.unitPrice = 0.0,
    this.expiryDate,
    this.lowStockThreshold = 1.0,
    required this.updatedAt,
  });

  bool get isLowStock => quantity <= lowStockThreshold;
  bool get isNearExpiry {
    if (expiryDate == null) return false;
    final threeDaysFromNow = DateTime.now().add(const Duration(days: 3));
    return expiryDate!.isBefore(threeDaysFromNow);
  }

  factory IngredientModel.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return IngredientModel(
      id: doc.id,
      bakerId: data['bakerId'] ?? '',
      name: data['name'] ?? '',
      quantity: (data['quantity'] ?? 0.0).toDouble(),
      unit: data['unit'] ?? '',
      unitPrice: (data['unitPrice'] ?? 0.0).toDouble(),
      expiryDate: (data['expiryDate'] as Timestamp?)?.toDate(),
      lowStockThreshold: (data['lowStockThreshold'] ?? 1.0).toDouble(),
      updatedAt: (data['updatedAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'bakerId': bakerId,
      'name': name,
      'quantity': quantity,
      'unit': unit,
      'unitPrice': unitPrice,
      'expiryDate': expiryDate != null ? Timestamp.fromDate(expiryDate!) : null,
      'lowStockThreshold': lowStockThreshold,
      'updatedAt': Timestamp.fromDate(updatedAt),
    };
  }

  IngredientModel copyWith({
    String? name,
    double? quantity,
    String? unit,
    double? unitPrice,
    DateTime? expiryDate,
    double? lowStockThreshold,
  }) {
    return IngredientModel(
      id: id,
      bakerId: bakerId,
      name: name ?? this.name,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      unitPrice: unitPrice ?? this.unitPrice,
      expiryDate: expiryDate ?? this.expiryDate,
      lowStockThreshold: lowStockThreshold ?? this.lowStockThreshold,
      updatedAt: DateTime.now(),
    );
  }
}
