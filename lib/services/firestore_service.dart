import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user_model.dart';
import '../models/product_model.dart';
import '../models/ingredient_model.dart';
import '../models/surplus_item_model.dart';
import '../models/order_model.dart';
import '../models/review_model.dart';
import '../models/notification_model.dart';
import '../core/constants/app_constants.dart';
import 'package:uuid/uuid.dart';

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

  // Check if email is already registered
  Future<bool> isEmailRegistered(String email) async {
    final snapshot = await _db
        .collection(AppConstants.usersCollection)
        .where('email', isEqualTo: email.trim())
        .limit(1)
        .get();
    return snapshot.docs.isNotEmpty;
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

  // Increment surplus quantity (e.g. on cancellation)
  Future<void> incrementSurplusQuantity(String surplusId, int amount) async {
    await _db
        .collection(AppConstants.surplusItemsCollection)
        .doc(surplusId)
        .update({
      'quantity': FieldValue.increment(amount),
      'active': true,
    });
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
    final order = await getOrder(orderId);
    if (order == null) return;

    await _db
        .collection(AppConstants.ordersCollection)
        .doc(orderId)
        .update({'status': newStatus});

    // Notify Customer
    String title = 'Order Update';
    String body = 'Your order #${orderId.substring(0, 8)} is now $newStatus.';
    
    if (newStatus == AppConstants.orderAccepted) {
      body = 'Your order has been accepted by the baker!';
    } else if (newStatus == AppConstants.orderReady) {
      body = 'Your order is ready for pickup/delivery!';
    } else if (newStatus == AppConstants.orderDelivered) {
      body = 'Enjoy your treats! Your order has been delivered.';
    }

    await addNotification(
      order.customerId,
      NotificationModel(
        id: const Uuid().v4(),
        title: title,
        body: body,
        createdAt: DateTime.now(),
        type: 'order',
        relatedId: orderId,
      ),
    );
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
      if (item.surplusId != null && item.surplusId!.isNotEmpty) {
        final surplusDoc = await _db
            .collection(AppConstants.surplusItemsCollection)
            .doc(item.surplusId)
            .get();

        if (!surplusDoc.exists || !(surplusDoc.data()?['active'] ?? false)) {
          throw Exception(
            'The flash deal for ${item.productName} is no longer available.',
          );
        }

        final available = surplusDoc.data()?['quantity'] ?? 0;
        if (item.quantity > available) {
          throw Exception(
            'Only $available ${item.productName} flash deal item(s) left.',
          );
        }

        batch.update(surplusDoc.reference, {
          'quantity': available - item.quantity,
          'active': (available - item.quantity) > 0,
        });
      }
    }

    batch.set(
      _db.collection(AppConstants.ordersCollection).doc(order.id),
      order.toFirestore(),
    );
    await batch.commit();

    // Notify Baker of new order
    await addNotification(
      order.bakerId,
      NotificationModel(
        id: const Uuid().v4(),
        title: 'New Order Received! 🎂',
        body: 'You have a new order from ${order.customerName}.',
        createdAt: DateTime.now(),
        type: 'order',
        relatedId: order.id,
      ),
    );
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
  // ─── NOTIFICATION OPERATIONS ──────────────────────────────────
  
  Future<void> addNotification(String userId, NotificationModel notification) async {
    await _db
        .collection(AppConstants.usersCollection)
        .doc(userId)
        .collection('notifications')
        .doc(notification.id)
        .set(notification.toMap());
  }

  Stream<List<NotificationModel>> streamNotifications(String userId) {
    return _db
        .collection(AppConstants.usersCollection)
        .doc(userId)
        .collection('notifications')
        .orderBy('createdAt', descending: true)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => NotificationModel.fromFirestore(doc))
            .toList());
  }

  Future<void> markNotificationAsRead(String userId, String notificationId) async {
    await _db
        .collection(AppConstants.usersCollection)
        .doc(userId)
        .collection('notifications')
        .doc(notificationId)
        .update({'isRead': true});
  }

  Future<void> markAllNotificationsAsRead(String userId) async {
    final batch = _db.batch();
    final unread = await _db
        .collection(AppConstants.usersCollection)
        .doc(userId)
        .collection('notifications')
        .where('isRead', isEqualTo: false)
        .get();

    for (var doc in unread.docs) {
      batch.update(doc.reference, {'isRead': true});
    }
    await batch.commit();
  }
}
