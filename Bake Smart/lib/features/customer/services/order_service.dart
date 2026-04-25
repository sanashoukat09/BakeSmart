import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/order_model.dart';
import '../models/cart_item_model.dart';

import '../../notifications/models/notification_model.dart';
import '../../notifications/services/notification_service.dart';

final orderServiceProvider = Provider<OrderService>((ref) {
  return OrderService(FirebaseFirestore.instance, ref);
});

final bakerOrdersStreamProvider = StreamProvider<List<OrderModel>>((ref) {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return const Stream.empty();
  return FirebaseFirestore.instance
      .collection('orders')
      .where('bakerId', isEqualTo: user.uid)
      .snapshots()
      .map((snap) {
        final list = snap.docs.map((doc) => OrderModel.fromMap(doc.data(), doc.id)).toList();
        list.sort((a, b) => b.placedAt.compareTo(a.placedAt));
        return list;
      });
});

final customerOrdersStreamProvider = StreamProvider<List<OrderModel>>((ref) {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return const Stream.empty();
  return FirebaseFirestore.instance
      .collection('orders')
      .where('customerId', isEqualTo: user.uid)
      .snapshots()
      .map((snap) {
        final list = snap.docs.map((doc) => OrderModel.fromMap(doc.data(), doc.id)).toList();
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

    // Fetch customer details to embed directly into order natively
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

    final batch = _firestore.batch();
    
    // Write 1: Set order
    batch.set(docRef, order.toMap());

    // Write 2: Notify Baker
    _ref.read(notificationServiceProvider).sendNotificationWithBatch(
      batch,
      recipientId: order.bakerId,
      title: 'New Order Received! 🥐',
      body: '$customerName placed an order for ${items.length} items.',
      type: NotificationType.orderUpdate,
      referenceId: order.orderId,
    );

    await batch.commit();
    return docRef.id;
  }

  Future<void> updateOrderStatus(OrderModel order, String newStatus, {DateTime? estimatedReadyTime}) async {
    final now = DateTime.now();
    final newEvent = {
        'status': newStatus,
        'timestamp': Timestamp.fromDate(now),
    };
    
    final batch = _firestore.batch();
    final docRef = _firestore.collection('orders').doc(order.orderId);

    final updates = {
      'status': newStatus,
      'updatedAt': Timestamp.fromDate(now),
      'statusHistory': FieldValue.arrayUnion([newEvent]),
    };
    
    if (estimatedReadyTime != null) {
      updates['estimatedReadyTime'] = Timestamp.fromDate(estimatedReadyTime);
    }

    batch.update(docRef, updates);

    // Notify Customer
    String body = 'Your order status is now: $newStatus';
    if (newStatus == 'accepted') body = 'Baker has accepted your order!';
    if (newStatus == 'ready') body = 'Your order is ready for ${order.fulfillmentType}!';

    _ref.read(notificationServiceProvider).sendNotificationWithBatch(
      batch,
      recipientId: order.customerId,
      title: 'Order Tracking Update',
      body: body,
      type: NotificationType.orderUpdate,
      referenceId: order.orderId,
    );

    await batch.commit();
  }

  // Validates items against firestore to ensure isAvailable == true
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
