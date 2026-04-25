import 'package:cloud_firestore/cloud_firestore.dart';

class ReviewModel {
  final String reviewId;
  final String orderId;
  final String productId;
  final String customerId;
  final String customerName;
  final String bakerId;
  final int rating;
  final String? reviewText;
  final DateTime createdAt;

  ReviewModel({
    required this.reviewId,
    required this.orderId,
    required this.productId,
    required this.customerId,
    required this.customerName,
    required this.bakerId,
    required this.rating,
    this.reviewText,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'reviewId': reviewId,
      'orderId': orderId,
      'productId': productId,
      'customerId': customerId,
      'customerName': customerName,
      'bakerId': bakerId,
      'rating': rating,
      'reviewText': reviewText,
      'createdAt': Timestamp.fromDate(createdAt),
    };
  }

  factory ReviewModel.fromMap(Map<String, dynamic> map, String docId) {
    return ReviewModel(
      reviewId: map['reviewId'] ?? docId,
      orderId: map['orderId'] ?? '',
      productId: map['productId'] ?? '',
      customerId: map['customerId'] ?? '',
      customerName: map['customerName'] ?? 'Unknown',
      bakerId: map['bakerId'] ?? '',
      rating: (map['rating'] ?? 5).toInt(),
      reviewText: map['reviewText'],
      createdAt: (map['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }
}
