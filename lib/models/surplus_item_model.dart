import 'package:cloud_firestore/cloud_firestore.dart';

class SurplusItemModel {
  final String id;
  final String productId;
  final String bakerId;
  final String name;
  final String? imageUrl;
  final double originalPrice;
  final double discountPrice;
  final int quantity;
  final DateTime createdAt;
  final bool active;

  SurplusItemModel({
    required this.id,
    required this.productId,
    required this.bakerId,
    required this.name,
    this.imageUrl,
    required this.originalPrice,
    required this.discountPrice,
    required this.quantity,
    required this.createdAt,
    this.active = true,
  });

  factory SurplusItemModel.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return SurplusItemModel(
      id: doc.id,
      productId: data['productId'] ?? '',
      bakerId: data['bakerId'] ?? '',
      name: data['name'] ?? data['productName'] ?? '',
      imageUrl: data['imageUrl'] ?? data['productImageUrl'],
      originalPrice: (data['originalPrice'] ?? 0.0).toDouble(),
      discountPrice: (data['discountPrice'] ?? data['discountedPrice'] ?? 0.0).toDouble(),
      quantity: data['quantity'] ?? 0,
      createdAt: (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      active: data['active'] ?? true,
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'productId': productId,
      'bakerId': bakerId,
      'name': name,
      'imageUrl': imageUrl,
      'originalPrice': originalPrice,
      'discountPrice': discountPrice,
      'quantity': quantity,
      'createdAt': Timestamp.fromDate(createdAt),
      'active': active,
    };
  }
}
