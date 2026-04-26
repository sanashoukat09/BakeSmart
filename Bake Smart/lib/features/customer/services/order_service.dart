import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/order_model.dart';
import '../models/cart_item_model.dart';

import '../../notifications/models/notification_model.dart';
import '../../notifications/services/notification_service.dart';

final orderServiceProvider = Provider<OrderService>((ref) {
  return OrderService(FirebaseFirestore.instance, ref);
});

// Uses FirebaseAuth.instance.currentUser directly — NOT ref.watch(authStateProvider).
// Watching authStateProvider caused the stream to be torn down and recreated on
// every Firebase Auth token refresh, which made Firestore serve from local cache
// first (showing stale status), then correct from the server ~2 seconds later.
final bakerOrdersStreamProvider = StreamProvider<List<OrderModel>>((ref) {
  final uid = FirebaseAuth.instance.currentUser?.uid;
  if (uid == null) return const Stream.empty();

  return FirebaseFirestore.instance
      .collection('orders')
      .where('bakerId', isEqualTo: uid)
      .snapshots()
      .map((snap) {
        final list = snap.docs
            .map((doc) => OrderModel.fromMap(doc.data(), doc.id))
            .toList();
        list.sort((a, b) => b.placedAt.compareTo(a.placedAt));
        return list;
      });
});

final customerOrdersStreamProvider = StreamProvider<List<OrderModel>>((ref) {
  final uid = FirebaseAuth.instance.currentUser?.uid;
  if (uid == null) return const Stream.empty();

  return FirebaseFirestore.instance
      .collection('orders')
      .where('customerId', isEqualTo: uid)
      .snapshots()
      .map((snap) {
        final list = snap.docs
            .map((doc) => OrderModel.fromMap(doc.data(), doc.id))
            .toList();
        list.sort((a, b) => b.placedAt.compareTo(a.placedAt));
        return list;
      });
});


class OrderService {
  final FirebaseFirestore _firestore;
  final Ref _ref;

  OrderService(this._firestore, this._ref);

  Future<String> placeOrder({
    required List<CartItemModel> items,
    required double totalAmount,
    required String fulfillmentType,
    required String? deliveryAddress,
  }) async {
    final user = _ref.read(authStateProvider).value;
    if (user == null) throw Exception('Must be logged in to place an order.');
    if (items.isEmpty) throw Exception('Cart is empty.');

    final userDoc = await _firestore.collection('users').doc(user.uid).get();
    if (!userDoc.exists) throw Exception('User Document Missing.');
    final customerName = userDoc.data()?['name'] ?? 'Unknown Customer';

    const status = 'placed';
    final docRef = _firestore.collection('orders').doc();
    final now = DateTime.now();

    final order = OrderModel(
      orderId: docRef.id,
      customerId: user.uid,
      customerName: customerName,
      bakerId: items.first.bakerId,
      bakerName: items.first.bakerName,
      items: items,
      totalAmount: totalAmount,
      fulfillmentType: fulfillmentType,
      deliveryAddress: deliveryAddress,
      status: status,
      placedAt: now,
      updatedAt: now,
      statusHistory: [OrderStatusEvent(status: status, timestamp: now)],
    );

    // Write order first.
    await docRef.set(order.toMap());

    // Notify baker separately — if this fails the order is already placed.
    try {
      await _ref.read(notificationServiceProvider).sendNotification(
        recipientId: order.bakerId,
        title: 'New Order Received! 🥐',
        body: '$customerName placed an order for ${items.length} items.',
        type: NotificationType.orderUpdate,
        referenceId: order.orderId,
      );
    } catch (e) {
      // Notification failure is non-fatal — the order is already committed.
    }

    return docRef.id;
  }

  /// Updates the order status in Firestore.
  /// CRITICAL: The order status write and the customer notification are now
  /// TWO SEPARATE writes. Previously they were in the same batch — if the
  /// notification write failed (e.g. missing index, rules error), the ENTIRE
  /// batch would fail and Firestore would revert the local cache, making the
  /// order snap back to 'placed' after ~2 seconds. Now only the order write
  /// is critical; the notification is best-effort.
  Future<void> updateOrderStatus(
    OrderModel order,
    String newStatus, {
    DateTime? estimatedReadyTime,
  }) async {
    final now = DateTime.now();
    final newEvent = {
      'status': newStatus,
      'timestamp': Timestamp.fromDate(now),
    };

    final docRef = _firestore.collection('orders').doc(order.orderId);

    final updates = <String, dynamic>{
      'status': newStatus,
      'updatedAt': Timestamp.fromDate(now),
      'statusHistory': FieldValue.arrayUnion([newEvent]),
    };

    if (estimatedReadyTime != null) {
      updates['estimatedReadyTime'] = Timestamp.fromDate(estimatedReadyTime);
    }

    // Write 1 — ORDER STATUS. This must succeed. If it throws, the caller
    // will catch it and show the user an error message.
    await docRef.update(updates);

    // Write 2 — CUSTOMER NOTIFICATION. Best-effort. A failure here does NOT
    // revert the order status because it is a separate write.
    try {
      String body = 'Your order status is now: $newStatus';
      if (newStatus == 'accepted') body = 'Baker has accepted your order!';
      if (newStatus == 'ready') {
        body = 'Your order is ready for ${order.fulfillmentType}!';
      }

      await _ref.read(notificationServiceProvider).sendNotification(
        recipientId: order.customerId,
        title: 'Order Tracking Update',
        body: body,
        type: NotificationType.orderUpdate,
        referenceId: order.orderId,
      );
    } catch (e) {
      // Notification failure is non-fatal — the status update is committed.
    }
  }

  Future<List<String>> validateCartAvailability(List<CartItemModel> items) async {
    List<String> unavailableProductIds = [];
    for (var item in items) {
      final doc = await _firestore.collection('products').doc(item.productId).get();
      if (!doc.exists) {
        unavailableProductIds.add(item.productId);
      } else {
        final data = doc.data();
        final isAvailable = data?['isAvailable'] ?? false;
        if (!isAvailable) {
          unavailableProductIds.add(item.productId);
        }
      }
    }
    return unavailableProductIds;
  }
}
