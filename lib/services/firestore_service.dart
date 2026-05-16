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

  Future<void> createUser(UserModel user) async {
    await _db
        .collection(AppConstants.usersCollection)
        .doc(user.uid)
        .set(user.toFirestore());
  }

  Future<UserModel?> getUser(String uid) async {
    final doc = await _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .get();
    if (!doc.exists) return null;
    return UserModel.fromFirestore(doc);
  }

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

  Future<void> updateUser(String uid, Map<String, dynamic> data) async {
    await _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .update(data);
  }

  Future<void> completeOnboarding(String uid, Map<String, dynamic> data) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      ...data,
      'onboardingComplete': true,
    });
  }

  Future<bool> userExists(String uid) async {
    final doc = await _db
        .collection(AppConstants.usersCollection)
        .doc(uid)
        .get();
    return doc.exists;
  }

  Future<bool> isEmailRegistered(String email) async {
    final snapshot = await _db
        .collection(AppConstants.usersCollection)
        .where('email', isEqualTo: email.trim())
        .limit(1)
        .get();
    return snapshot.docs.isNotEmpty;
  }

  Future<UserModel?> getBakerProfile(String bakerId) async {
    return getUser(bakerId);
  }

  Stream<UserModel?> streamBakerProfile(String bakerId) {
    return streamUser(bakerId);
  }

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

  Future<void> addPortfolioImage(String uid, String imageUrl) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      'portfolioImages': FieldValue.arrayUnion([imageUrl]),
    });
  }

  Future<void> removePortfolioImage(String uid, String imageUrl) async {
    await _db.collection(AppConstants.usersCollection).doc(uid).update({
      'portfolioImages': FieldValue.arrayRemove([imageUrl]),
    });
  }

  // ─── PRODUCT OPERATIONS ────────────────────────────────────────

  Future<void> saveProduct(ProductModel product) async {
    if (product.price < AppConstants.minProductPrice ||
        product.price > AppConstants.maxProductPrice) {
      throw Exception(
          'Product price must be between Rs. ${AppConstants.minProductPrice.toInt()} and Rs. ${AppConstants.maxProductPrice.toInt()}.');
    }

    await _db
        .collection(AppConstants.productsCollection)
        .doc(product.id.isEmpty ? null : product.id)
        .set(product.toFirestore(), SetOptions(merge: true));
  }

  Future<void> deleteProduct(String productId) async {
    await _db
        .collection(AppConstants.productsCollection)
        .doc(productId)
        .delete();
  }

  Stream<List<ProductModel>> streamBakerProducts(String bakerId) {
    return _db
        .collection(AppConstants.productsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final products = snapshot.docs
          .map((doc) => ProductModel.fromFirestore(doc))
          .toList();
      products.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return products;
    });
  }

  Stream<List<ProductModel>> streamFeaturedProducts() {
    return _db
        .collection(AppConstants.productsCollection)
        .where('isAvailable', isEqualTo: true)
        .snapshots()
        .map((snapshot) {
      final products = snapshot.docs
          .map((doc) => ProductModel.fromFirestore(doc))
          .toList();
      products.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return products.take(10).toList();
    });
  }

  Future<ProductModel?> getProduct(String productId) async {
    final doc = await _db
        .collection(AppConstants.productsCollection)
        .doc(productId)
        .get();
    if (!doc.exists) return null;
    return ProductModel.fromFirestore(doc);
  }

  Future<void> toggleProductAvailability(
      String productId, bool isAvailable) async {
    await _db
        .collection(AppConstants.productsCollection)
        .doc(productId)
        .update({'isAvailable': isAvailable});
  }

  // ─── INGREDIENT OPERATIONS ────────────────────────────────────

  Future<void> saveIngredient(IngredientModel ingredient) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredient.id.isEmpty ? null : ingredient.id)
        .set(ingredient.toFirestore(), SetOptions(merge: true));
  }

  Future<void> deleteIngredient(String ingredientId) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredientId)
        .delete();
  }

  Stream<List<IngredientModel>> streamBakerIngredients(String bakerId) {
    return _db
        .collection(AppConstants.ingredientsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final ingredients = snapshot.docs
          .map((doc) => IngredientModel.fromFirestore(doc))
          .toList();
      ingredients.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      return ingredients;
    });
  }

  Future<void> updateIngredientQuantity(
      String ingredientId, double newQuantity) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredientId)
        .update({
      'quantity': newQuantity,
      'updatedAt': FieldValue.serverTimestamp(),
    });
  }

  Future<void> decrementIngredientStock(
      String ingredientId, double amount) async {
    await _db
        .collection(AppConstants.ingredientsCollection)
        .doc(ingredientId)
        .update({
      'quantity': FieldValue.increment(-amount),
      'updatedAt': FieldValue.serverTimestamp(),
    });
  }

  // ─── SURPLUS OPERATIONS ────────────────────────────────────────

  Future<void> saveSurplusItem(SurplusItemModel item) async {
    await _db
        .collection(AppConstants.surplusItemsCollection)
        .doc(item.id.isEmpty ? null : item.id)
        .set(item.toFirestore());
  }

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

  Future<void> deactivateSurplus(String surplusId) async {
    await _db
        .collection(AppConstants.surplusItemsCollection)
        .doc(surplusId)
        .update({'active': false});
  }

  Future<void> incrementSurplusQuantity(String surplusId, int amount) async {
    await _db
        .collection(AppConstants.surplusItemsCollection)
        .doc(surplusId)
        .update({
      'quantity': FieldValue.increment(amount),
      'active': true,
    });
  }

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

  Stream<List<OrderModel>> streamBakerOrders(String bakerId) {
    return _db
        .collection(AppConstants.ordersCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final orders = snapshot.docs
          .map((doc) => OrderModel.fromFirestore(doc))
          .toList();
      orders.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return orders;
    });
  }

  Future<void> updateOrderStatus(String orderId, String newStatus) async {
    final order = await getOrder(orderId);
    if (order == null) return;

    await _db
        .collection(AppConstants.ordersCollection)
        .doc(orderId)
        .update({'status': newStatus});

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

  Future<void> setOrderInventoryDeducted(String orderId) async {
    await _db
        .collection(AppConstants.ordersCollection)
        .doc(orderId)
        .update({'inventoryDeducted': true});
  }

  /// Atomically transitions order status and handles inventory side-effects.
  ///
  /// ── INGREDIENT DEDUCTION ───────────────────────────────────────────────────
  /// Triggers ONLY when newStatus == 'preparing' AND inventoryDeducted == false.
  ///
  ///   Why only 'preparing':
  ///     'ready' and 'delivered' are downstream of 'preparing'. Ingredients were
  ///     already deducted when the baker clicked Start Preparing. Triggering again
  ///     on those statuses would double-deduct. The inventoryDeducted flag is a
  ///     safety net but 'preparing'-only is the primary control.
  ///
  ///   Why surplus items are skipped:
  ///     Items with a surplusId are pre-made flash deal products. The baker already
  ///     used ingredients to make them before listing as surplus. There is nothing
  ///     to deduct at order preparation time.
  ///
  /// ── SURPLUS RESTOCK ON CANCELLATION ───────────────────────────────────────
  /// Triggers ONLY when newStatus == 'cancelled' AND inventoryDeducted == false.
  ///
  ///   Why the inventoryDeducted guard:
  ///     If the baker already started preparing (inventoryDeducted = true), the
  ///     physical product exists. The surplus reservation is consumed. The baker
  ///     should manually list the finished product as new surplus — we must NOT
  ///     auto-restock the original reservation because that surplus slot may no
  ///     longer reflect reality (quantity, freshness, etc.).
  ///
  ///   Why only items with a surplusId:
  ///     Regular order items (surplusId = null) have no surplus record to restock.
  ///
  /// ── FIRESTORE RULE: ALL READS BEFORE ALL WRITES ────────────────────────────
  /// All tx.get() calls are completed in Phase 1 before any tx.update() / tx.set()
  /// calls in Phase 2. Interleaving reads and writes inside a transaction causes
  /// the '_command is empty' assertion error.
  Future<void> updateOrderStatusWithAtomicInventory({
    required String orderId,
    required String newStatus,
  }) async {
    await _db.runTransaction((tx) async {

      // ── PHASE 1: ALL READS ──────────────────────────────────────────────────

      final orderRef =
          _db.collection(AppConstants.ordersCollection).doc(orderId);
      final orderSnap = await tx.get(orderRef);

      if (!orderSnap.exists) {
        throw Exception('Order not found: $orderId');
      }

      final order = OrderModel.fromFirestore(orderSnap);

      final shouldDeductIngredients =
          newStatus == AppConstants.orderPreparing && !order.inventoryDeducted;

      final shouldRestockSurplus =
          (newStatus == AppConstants.orderCancelled ||
                  newStatus == AppConstants.orderRejected) &&
              !order.inventoryDeducted;

      // { ingredientId -> { ref, snap, totalToReduce } }
      // Accumulated so a shared ingredient across multiple products is only
      // read once and deducted once with the correct combined total.
      final Map<String, Map<String, dynamic>> ingredientReads = {};

      if (shouldDeductIngredients) {
        for (final item in order.items) {
          // Skip surplus/flash deal items — already made, no ingredients to deduct.
          if (item.surplusId != null && item.surplusId!.isNotEmpty) continue;

          final productRef = _db
              .collection(AppConstants.productsCollection)
              .doc(item.productId);
          final productSnap = await tx.get(productRef);

          if (!productSnap.exists) continue;

          final product = ProductModel.fromFirestore(productSnap);

          for (final entry in product.ingredients.entries) {
            final ingredientId = entry.key;
            final qtyPerUnit = entry.value; // quantity needed per 1 unit of product
            final totalToReduce = qtyPerUnit * item.quantity;

            if (ingredientReads.containsKey(ingredientId)) {
              ingredientReads[ingredientId]!['totalToReduce'] += totalToReduce;
            } else {
              final ingredientRef = _db
                  .collection(AppConstants.ingredientsCollection)
                  .doc(ingredientId);
              final ingredientSnap = await tx.get(ingredientRef);

              ingredientReads[ingredientId] = {
                'ref': ingredientRef,
                'snap': ingredientSnap,
                'totalToReduce': totalToReduce,
              };
            }
          }
        }
      }

      // No surplus reads needed — FieldValue.increment handles restock writes
      // without needing to read current values first.

      // ── PHASE 2: ALL WRITES ─────────────────────────────────────────────────

      if (shouldDeductIngredients) {
        for (final entry in ingredientReads.entries) {
          final snap = entry.value['snap'] as DocumentSnapshot;
          if (!snap.exists) continue; // missing ingredient — skip gracefully

          final ref = entry.value['ref'] as DocumentReference;
          final totalToReduce = entry.value['totalToReduce'] as double;
          final data = snap.data() as Map<String, dynamic>? ?? {};
          final currentQty = (data['quantity'] ?? 0 as num).toDouble();
          final ingredientName = data['name'] ?? 'Unknown Ingredient';

          if (currentQty < totalToReduce) {
            throw Exception(
                'Insufficient stock for $ingredientName. Available: $currentQty, Required: $totalToReduce. Please refill it.');
          }

          tx.update(ref, {
            'quantity': currentQty - totalToReduce,
            'updatedAt': FieldValue.serverTimestamp(),
          });
        }

        // Flip the guard so this block never re-runs on retries or future status changes.
        tx.update(orderRef, {'inventoryDeducted': true});
      }

      if (shouldRestockSurplus) {
        for (final item in order.items) {
          final surplusId = item.surplusId;
          if (surplusId == null || surplusId.isEmpty) continue;

          final surplusRef = _db
              .collection(AppConstants.surplusItemsCollection)
              .doc(surplusId);

          // FieldValue.increment is safe here without a prior read because we are
          // not reading the current value — just applying a delta.
          tx.update(surplusRef, {
            'quantity': FieldValue.increment(item.quantity),
            'active': true,
          });
        }
      }

      // Status update is always the final write.
      tx.update(orderRef, {'status': newStatus});
    });

    // Customer notification — outside transaction (safe to read here).
    final order = await getOrder(orderId);
    if (order == null) return;

    String title = 'Order Update';
    String body = 'Your order #${orderId.substring(0, 8)} is now $newStatus.';

    if (newStatus == AppConstants.orderAccepted) {
      body = 'Your order has been accepted by the baker!';
    } else if (newStatus == AppConstants.orderReady) {
      body = 'Your order is ready for pickup/delivery!';
    } else if (newStatus == AppConstants.orderDelivered) {
      body = 'Enjoy your treats! Your order has been delivered.';
    } else if (newStatus == AppConstants.orderCancelled) {
      body = 'Your order has been cancelled.';
    } else if (newStatus == AppConstants.orderRejected) {
      body = 'Your order has been rejected by the baker.';
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

  /// Creates an order and atomically decrements surplus stock for flash deal items.
  ///
  /// Regular items (surplusId = null) have no stock to check at placement time.
  /// Ingredient deduction happens later when the baker clicks Start Preparing.
  ///
  /// All tx.get() calls happen before any tx.update() / tx.set() calls.
  Future<void> saveOrder(OrderModel order) async {
    await _db.runTransaction((tx) async {

      // ── PHASE 1: ALL READS ──────────────────────────────────────────────────

      // { surplusId -> { ref, snap, requestedQuantity, productName } }
      final Map<String, Map<String, dynamic>> surplusReads = {};

      for (final item in order.items) {
        final surplusId = item.surplusId;
        if (surplusId == null || surplusId.isEmpty) continue;

        if (surplusReads.containsKey(surplusId)) {
          surplusReads[surplusId]!['requestedQuantity'] += item.quantity;
        } else {
          final surplusRef = _db
              .collection(AppConstants.surplusItemsCollection)
              .doc(surplusId);
          final surplusSnap = await tx.get(surplusRef);

          surplusReads[surplusId] = {
            'ref': surplusRef,
            'snap': surplusSnap,
            'requestedQuantity': item.quantity,
            'productName': item.productName,
          };
        }
      }

      // ── PHASE 2: VALIDATE + ALL WRITES ─────────────────────────────────────

      for (final entry in surplusReads.entries) {
        final snap = entry.value['snap'] as DocumentSnapshot;
        final ref = entry.value['ref'] as DocumentReference;
        final requested = entry.value['requestedQuantity'] as int;
        final productName = entry.value['productName'] as String;

        if (!snap.exists) {
          throw Exception(
              'The flash deal for $productName is no longer available.');
        }

        final data = snap.data() as Map<String, dynamic>? ?? {};
        if ((data['active'] ?? false) != true) {
          throw Exception(
              'The flash deal for $productName is no longer available.');
        }

        final available = (data['quantity'] ?? 0) as int;
        if (requested > available) {
          throw Exception(
              'Only $available $productName flash deal item(s) left.');
        }

        final newQuantity = available - requested;
        tx.update(ref, {
          'quantity': newQuantity,
          'active': newQuantity > 0,
        });
      }

      final orderRef =
          _db.collection(AppConstants.ordersCollection).doc(order.id);
      tx.set(orderRef, order.toFirestore());
    });

    // Baker notification — outside transaction.
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

  Future<OrderModel?> getOrder(String orderId) async {
    final doc = await _db
        .collection(AppConstants.ordersCollection)
        .doc(orderId)
        .get();
    if (!doc.exists) return null;
    return OrderModel.fromFirestore(doc);
  }

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

  Future<void> saveReview(ReviewModel review) async {
    final batch = _db.batch();

    final reviewRef =
        _db.collection(AppConstants.reviewsCollection).doc(review.id);
    batch.set(reviewRef, review.toFirestore());

    final orderRef =
        _db.collection(AppConstants.ordersCollection).doc(review.orderId);
    batch.update(orderRef, {'isReviewed': true});

    await batch.commit();

    final reviews = await _db
        .collection(AppConstants.reviewsCollection)
        .where('bakerId', isEqualTo: review.bakerId)
        .get();

    double totalRating = 0;
    for (var doc in reviews.docs) {
      totalRating += (doc.data()['rating'] ?? 0.0).toDouble();
    }
    final double avgRating = totalRating / reviews.docs.length;

    await _db
        .collection(AppConstants.usersCollection)
        .doc(review.bakerId)
        .update({
      'rating': avgRating,
      'totalReviews': reviews.docs.length,
    });
  }

  Stream<List<ReviewModel>> streamBakerReviews(String bakerId) {
    return _db
        .collection(AppConstants.reviewsCollection)
        .where('bakerId', isEqualTo: bakerId)
        .snapshots()
        .map((snapshot) {
      final reviews = snapshot.docs
          .map((doc) => ReviewModel.fromFirestore(doc))
          .toList();
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

  Stream<List<OrderModel>> streamCustomerOrders(String customerId) {
    return _db
        .collection(AppConstants.ordersCollection)
        .where('customerId', isEqualTo: customerId)
        .snapshots()
        .map((snapshot) {
      try {
        final orders = snapshot.docs
            .map((doc) {
              try {
                return OrderModel.fromFirestore(doc);
              } catch (e) {
                print('Error parsing order ${doc.id}: $e');
                return null;
              }
            })
            .where((o) => o != null)
            .cast<OrderModel>()
            .toList();
        orders.sort((a, b) => b.createdAt.compareTo(a.createdAt));
        return orders;
      } catch (e) {
        print('Error in orders stream: $e');
        return <OrderModel>[];
      }
    });
  }

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

  Future<void> addNotification(
      String userId, NotificationModel notification) async {
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
        .snapshots()
        .map((snapshot) {
      try {
        return snapshot.docs
            .map((doc) {
              try {
                return NotificationModel.fromFirestore(doc);
              } catch (e) {
                print('Error parsing notification ${doc.id}: $e');
                return null;
              }
            })
            .where((n) => n != null)
            .cast<NotificationModel>()
            .toList()
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
      } catch (e) {
        print('Error in notifications stream: $e');
        return <NotificationModel>[];
      }
    });
  }

  Future<void> markNotificationAsRead(
      String userId, String notificationId) async {
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