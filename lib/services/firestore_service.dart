import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user_model.dart';
import '../models/product_model.dart';
import '../models/ingredient_model.dart';
import '../models/surplus_item_model.dart';
import '../models/order_model.dart';
import '../models/review_model.dart';
import '../core/constants/app_constants.dart';

class FirestoreService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  // ─── USER OPERATIONS ──────────────────────────────────────────

  // Create user document
  Future<void> createUser(UserModel user) async {
    await _db
        .collection(AppConstants.usersCollection)
        .doc(user.uid)
        .set(user.toFirestore());
  }

  // Get user by UID (one-time)
  Future<UserModel?> getUser(String uid) async {
    final doc = await _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .get();
    if (!doc.exists) return null;
    return UserModel.fromFirestore(doc);
  }

  // Stream user document (real-time)
  Stream<UserModel?> streamUser(String uid) {
    return _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .snapshots()
        .map((doc) {
      if (!doc.exists) return null;
      return UserModel.fromFirestore(doc);
    });
  }

  // Update user fields
  Future<void> updateUser(String uid, Map<String, dynamic> data) async {
    await _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .update(data);
  }

  // Complete onboarding
  Future<void> completeOnboarding(
      String uid, Map<String, dynamic> data) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      ...data,
      'onboardingComplete': true,
    });
  }

  // Check if user exists
  Future<bool> userExists(String uid) async {
    final doc = await _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .get();
    return doc.exists;
  }

  // Get baker public profile by ID
  Future<UserModel?> getBakerProfile(String bakerId) async {
    return getUser(bakerId);
  }

  // Stream baker profile
  Stream<UserModel?> streamBakerProfile(String bakerId) {
    return streamUser(bakerId);
  }

  // Update notification preferences
  Future<void> updateNotificationPrefs(String uid,
      {required bool enabled,
      required bool newOrder,
      required bool lowStock,
      required bool surplus}) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      'notificationsEnabled': enabled,
      'newOrderNotif': newOrder,
      'lowStockNotif': lowStock,
      'surplusNotif': surplus,
    });
  }

  // Add portfolio image URL
  Future<void> addPortfolioImage(String uid, String imageUrl) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      'portfolioImages': FieldValue.arrayUnion([imageUrl]),
    });
  }

  // Remove portfolio image URL
  Future<void> removePortfolioImage(String uid, String imageUrl) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      'portfolioImages': FieldValue.arrayRemove([imageUrl]),
    });
  }

  // ─── PRODUCT OPERATIONS ────────────────────────────────────────

  // Create or update product
  Future<void> saveProduct(ProductModel product) async {
    await _db
        .collection(AppConstants.productsCollection)
        .doc(product.id.isEmpty ? null : product.id)
        .set(product.toFirestore(), SetOptions(merge: true));
  }

  // Delete product
  Future<void> deleteProduct(String productId) async {
    await _db.collection(AppConstants.productsCollection).doc(productId).delete();
  }

  // Stream products for a specific baker
  Stream<List<ProductModel>> streamBakerProducts(String bakerId) {
    return _db
        .collection(AppConstants.productsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final products = snapshot.docs
          .map((doc) => ProductModel.fromFirestore(doc))
          .toList();
      // Sort in memory
      products.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return products;
    });
  }

  // Get single product
  Future<ProductModel?> getProduct(String productId) async {
    final doc = await _db.collection(AppConstants.productsCollection).doc(productId).get();
    if (!doc.exists) return null;
    return ProductModel.fromFirestore(doc);
  }

  // Toggle product availability
  Future<void> toggleProductAvailability(String productId, bool isAvailable) async {
    await _db
        .collection(AppConstants.productsCollection)
        .doc(productId)
        .update({'isAvailable': isAvailable});
  }

  // ─── INGREDIENT OPERATIONS ────────────────────────────────────

  // Create or update ingredient
  Future<void> saveIngredient(IngredientModel ingredient) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredient.id.isEmpty ? null : ingredient.id)
        .set(ingredient.toFirestore(), SetOptions(merge: true));
  }

  // Delete ingredient
  Future<void> deleteIngredient(String ingredientId) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredientId)
        .delete();
  }

  // Stream ingredients for a specific baker
  Stream<List<IngredientModel>> streamBakerIngredients(String bakerId) {
    return _db
        .collection(AppConstants.ingredientsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final ingredients = snapshot.docs
          .map((doc) => IngredientModel.fromFirestore(doc))
          .toList();
      // Sort in memory
      ingredients.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      return ingredients;
    });
  }

  // Update ingredient quantity
  Future<void> updateIngredientQuantity(String ingredientId, double newQuantity) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredientId)
        .update({
      'quantity': newQuantity,
      'updatedAt': FieldValue.serverTimestamp(),
    });
  }

  // Decrement ingredient stock
  Future<void> decrementIngredientStock(String ingredientId, double amount) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredientId)
        .update({
      'quantity': FieldValue.increment(-amount),
      'updatedAt': FieldValue.serverTimestamp(),
    });
  }

  // ─── SURPLUS OPERATIONS ────────────────────────────────────────

  // Create surplus item
  Future<void> saveSurplusItem(SurplusItemModel item) async {
    await _db
        .collection(AppConstants.surplusItemsCollection)
        .doc(item.id.isEmpty ? null : item.id)
        .set(item.toFirestore());
  }

  // Stream active surplus items for a specific baker
  Stream<List<SurplusItemModel>> streamBakerSurplus(String bakerId) {
    return _db
        .collection(AppConstants.surplusItemsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .where('active', isEqualTo: true)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => SurplusItemModel.fromFirestore(doc))
            .toList());
  }

  // Deactivate surplus item
  Future<void> deactivateSurplus(String surplusId) async {
    await _db
        .collection(AppConstants.surplusItemsCollection)
        .doc(surplusId)
        .update({'active': false});
  }

  // Stream all active surplus items for discovery
  Stream<List<SurplusItemModel>> streamAllSurplus() {
    return _db
        .collection(AppConstants.surplusItemsCollection)
        .where('active', isEqualTo: true)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => SurplusItemModel.fromFirestore(doc))
            .toList());
  }

  // ─── ORDER OPERATIONS ──────────────────────────────────────────

  // Stream orders for a specific baker
  Stream<List<OrderModel>> streamBakerOrders(String bakerId) {
    return _db
        .collection(AppConstants.ordersCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final orders = snapshot.docs
          .map((doc) => OrderModel.fromFirestore(doc))
          .toList();
      // Sort in memory
      orders.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return orders;
    });
  }

  // Update order status
  Future<void> updateOrderStatus(String orderId, String newStatus) async {
    await _db
        .collection(AppConstants.ordersCollection)
        .doc(orderId)
        .update({'status': newStatus});
  }

  // Mark inventory as deducted
  Future<void> setOrderInventoryDeducted(String orderId) async {
    await _db
        .collection(AppConstants.ordersCollection)
        .doc(orderId)
        .update({'inventoryDeducted': true});
  }

  // Create new order
  Future<void> saveOrder(OrderModel order) async {
    final batch = _db.batch();

    for (final item in order.items) {
      final surplusSnapshot = await _db
          .collection(AppConstants.surplusItemsCollection)
          .where('productId', isEqualTo: item.productId)
          .where('active', isEqualTo: true)
          .limit(1)
          .get();
      if (surplusSnapshot.docs.isEmpty) continue;

      final surplusDoc = surplusSnapshot.docs.first;
      final available = surplusDoc.data()['quantity'] ?? 0;
      if (item.quantity > available) {
        throw Exception(
          'Only $available ${item.productName} flash deal item(s) left.',
        );
      }

      batch.update(surplusDoc.reference, {
        'quantity': available - item.quantity,
        'active': available - item.quantity > 0,
      });
    }

    batch.set(
      _db.collection(AppConstants.ordersCollection).doc(order.id),
      order.toFirestore(),
    );
    await batch.commit();
  }

  // Get single order
  Future<OrderModel?> getOrder(String orderId) async {
    final doc = await _db.collection(AppConstants.ordersCollection).doc(orderId).get();
    if (!doc.exists) return null;
    return OrderModel.fromFirestore(doc);
  }

  // Get order count for a specific date (Capacity Check)
  Future<int> getOrdersCountForDate(String bakerId, DateTime date) async {
    final startOfDay = DateTime(date.year, date.month, date.day);
    final endOfDay = DateTime(date.year, date.month, date.day, 23, 59, 59);

    final snapshot = await _db
        .collection(AppConstants.ordersCollection)
        .where('bakerId', isEqualTo: bakerId)
        .where('deliveryDate', isGreaterThanOrEqualTo: startOfDay)
        .where('deliveryDate', isLessThanOrEqualTo: endOfDay)
        .get();

    return snapshot.docs.where((doc) {
      final status = doc.data()['status'];
      return status != AppConstants.orderRejected;
    }).length;
  }

  // ─── REVIEW OPERATIONS ──────────────────────────────────────────

  // Save review and update baker's rating (simple version)
  Future<void> saveReview(ReviewModel review) async {
    final batch = _db.batch();
    
    // Save review
    final reviewRef = _db.collection(AppConstants.reviewsCollection).doc(review.id);
    batch.set(reviewRef, review.toFirestore());

    // Mark order as reviewed
    final orderRef = _db.collection(AppConstants.ordersCollection).doc(review.orderId);
    batch.update(orderRef, {'isReviewed': true});

    await batch.commit();

    // Update baker rating (aggregate)
    final reviews = await _db
        .collection(AppConstants.reviewsCollection)
        .where('bakerId', isEqualTo: review.bakerId)
        .get();

    double totalRating = 0;
    for (var doc in reviews.docs) {
      totalRating += (doc.data()['rating'] ?? 0.0).toDouble();
    }
    double avgRating = totalRating / reviews.docs.length;

    await _db.collection(AppConstants.usersCollection).doc(review.bakerId).update({
      'rating': avgRating,
      'totalReviews': reviews.docs.length,
    });
  }

  // Stream reviews for a baker
  Stream<List<ReviewModel>> streamBakerReviews(String bakerId) {
    return _db
        .collection(AppConstants.reviewsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final reviews = snapshot.docs
          .map((doc) => ReviewModel.fromFirestore(doc))
          .toList();
      // Sort in memory
      reviews.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return reviews;
    });
  }

  Stream<List<ReviewModel>> streamProductReviews(String productId) {
    return _db
        .collection(AppConstants.reviewsCollection)
        .where('productIds', arrayContains: productId)
        .snapshots()
        .map((snapshot) {
      final reviews = snapshot.docs
          .map((doc) => ReviewModel.fromFirestore(doc))
          .toList();
      reviews.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return reviews;
    });
  }

  // Stream customer's orders
  Stream<List<OrderModel>> streamCustomerOrders(String customerId) {
    return _db
        .collection(AppConstants.ordersCollection)
        .where('customerId', isEqualTo: customerId)
        .snapshots()
        .map((snapshot) {
      final orders = snapshot.docs
          .map((doc) => OrderModel.fromFirestore(doc))
          .toList();
      // Sort in memory
      orders.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return orders;
    });
  }

  // Get earnings summary (simple calculation from delivered orders)
  Stream<double> streamTotalEarnings(String bakerId) {
    return _db
        .collection(AppConstants.ordersCollection)
        .where('bakerId', isEqualTo: bakerId)
        .where('status', isEqualTo: AppConstants.orderDelivered)
        .snapshots()
        .map((snapshot) {
      double total = 0;
      for (var doc in snapshot.docs) {
        total += (doc.data()['totalAmount'] ?? 0.0).toDouble();
      }
      return total;
    });
  }
}
