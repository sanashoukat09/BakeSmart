import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/review_model.dart';

final reviewServiceProvider = Provider<ReviewService>((ref) {
  return ReviewService(FirebaseFirestore.instance, ref);
});

final productReviewsProvider = StreamProvider.family<List<ReviewModel>, String>((ref, productId) {
  return FirebaseFirestore.instance
      .collection('reviews')
      .where('productId', isEqualTo: productId)
      .orderBy('createdAt', descending: true)
      .snapshots()
      .map((snap) => snap.docs.map((doc) => ReviewModel.fromMap(doc.data(), doc.id)).toList());
});

class ReviewService {
  final FirebaseFirestore _firestore;
  final Ref _ref;

  ReviewService(this._firestore, this._ref);

  Future<void> submitReview({
    required String orderId,
    required String productId,
    required String bakerId,
    required int rating,
    String? reviewText,
  }) async {
    final user = _ref.read(authStateProvider).value;
    if (user == null) throw Exception('Must be logged in to review.');

    // 1. Verify Order status == 'delivered'
    final orderDoc = await _firestore.collection('orders').doc(orderId).get();
    if (!orderDoc.exists) throw Exception('Order not found.');
    final orderMap = orderDoc.data()!;
    if (orderMap['status'] != 'delivered') {
      throw Exception('Order must be delivered before submitting a review.');
    }

    // Customer specific
    if (orderMap['customerId'] != user.uid) {
      throw Exception('You cannot review an order you did not place.');
    }
    
    // Fetch customer details again for safe tracking
    final userDoc = await _firestore.collection('users').doc(user.uid).get();
    final customerName = userDoc.data()?['name'] ?? 'Unknown Customer';

    // 2. Prevent duplication silently
    final existingReviews = await _firestore
        .collection('reviews')
        .where('orderId', isEqualTo: orderId)
        .where('productId', isEqualTo: productId)
        .get();

    if (existingReviews.docs.isNotEmpty) {
      // Review already exists, fail silently
      return;
    }

    final docRef = _firestore.collection('reviews').doc();
    final review = ReviewModel(
      reviewId: docRef.id,
      orderId: orderId,
      productId: productId,
      customerId: user.uid,
      customerName: customerName,
      bakerId: bakerId,
      rating: rating,
      reviewText: reviewText,
      createdAt: DateTime.now(),
    );

    await docRef.set(review.toMap());
  }
}
