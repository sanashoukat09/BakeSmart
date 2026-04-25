// SHARED MODEL — Keep in sync with d:/Bake Smart/lib/features/customer/models/order_model.dart
import 'package:cloud_firestore/cloud_firestore.dart';
import 'cart_item_model.dart';

class OrderStatusEvent {
  final String status;
  final DateTime timestamp;

  OrderStatusEvent({required this.status, required this.timestamp});

  Map<String, dynamic> toMap() {
    return {
      'status': status,
      'timestamp': Timestamp.fromDate(timestamp),
    };
  }

  factory OrderStatusEvent.fromMap(Map<String, dynamic> map) {
    return OrderStatusEvent(
      status: map['status'] ?? 'placed',
      timestamp: (map['timestamp'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }
}

class OrderModel {
  final String orderId;
  final String customerId;
  final String customerName;
  final String bakerId;
  final String bakerName;
  final List<CartItemModel> items;
  final double totalAmount;
  final String status; // 'placed', 'accepted', 'rejected', 'preparing', 'ready', 'delivered'
  final String fulfillmentType; // 'delivery', 'pickup'
  final String? deliveryAddress;
  final DateTime? estimatedReadyTime;
  final DateTime placedAt;
  final DateTime updatedAt;
  final List<OrderStatusEvent> statusHistory;

  OrderModel({
    required this.orderId,
    required this.customerId,
    required this.customerName,
    required this.bakerId,
    required this.bakerName,
    required this.items,
    required this.totalAmount,
    required this.status,
    required this.fulfillmentType,
    this.deliveryAddress,
    this.estimatedReadyTime,
    required this.placedAt,
    required this.updatedAt,
    required this.statusHistory,
  });

  Map<String, dynamic> toMap() {
    return {
      'orderId': orderId,
      'customerId': customerId,
      'customerName': customerName,
      'bakerId': bakerId,
      'bakerName': bakerName,
      'items': items.map((x) => x.toMap()).toList(),
      'totalAmount': totalAmount,
      'status': status,
      'fulfillmentType': fulfillmentType,
      'deliveryAddress': deliveryAddress,
      'estimatedReadyTime': estimatedReadyTime != null ? Timestamp.fromDate(estimatedReadyTime!) : null,
      'placedAt': Timestamp.fromDate(placedAt),
      'updatedAt': Timestamp.fromDate(updatedAt),
      'statusHistory': statusHistory.map((x) => x.toMap()).toList(),
    };
  }

  factory OrderModel.fromMap(Map<String, dynamic> map, String docId) {
    return OrderModel(
      orderId: map['orderId'] ?? docId,
      customerId: map['customerId'] ?? '',
      customerName: map['customerName'] ?? 'Unknown Customer',
      bakerId: map['bakerId'] ?? '',
      bakerName: map['bakerName'] ?? 'Unknown Baker',
      items: List<CartItemModel>.from((map['items'] ?? []).map((x) => CartItemModel.fromMap(x))),
      totalAmount: (map['totalAmount'] ?? 0).toDouble(),
      status: map['status'] ?? 'placed',
      fulfillmentType: map['fulfillmentType'] ?? 'pickup',
      deliveryAddress: map['deliveryAddress'],
      estimatedReadyTime: (map['estimatedReadyTime'] as Timestamp?)?.toDate(),
      placedAt: (map['placedAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      updatedAt: (map['updatedAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      statusHistory: List<OrderStatusEvent>.from((map['statusHistory'] ?? []).map((x) => OrderStatusEvent.fromMap(x))),
    );
  }
}
