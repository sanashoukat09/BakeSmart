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

  OrderModel copyWith({
    String? orderId,
    String? customerId,
    String? customerName,
    String? bakerId,
    String? bakerName,
    List<CartItemModel>? items,
    double? totalAmount,
    String? status,
    String? fulfillmentType,
    String? deliveryAddress,
    DateTime? estimatedReadyTime,
    DateTime? placedAt,
    DateTime? updatedAt,
    List<OrderStatusEvent>? statusHistory,
  }) {
    return OrderModel(
      orderId: orderId ?? this.orderId,
      customerId: customerId ?? this.customerId,
      customerName: customerName ?? this.customerName,
      bakerId: bakerId ?? this.bakerId,
      bakerName: bakerName ?? this.bakerName,
      items: items ?? this.items,
      totalAmount: totalAmount ?? this.totalAmount,
      status: status ?? this.status,
      fulfillmentType: fulfillmentType ?? this.fulfillmentType,
      deliveryAddress: deliveryAddress ?? this.deliveryAddress,
      estimatedReadyTime: estimatedReadyTime ?? this.estimatedReadyTime,
      placedAt: placedAt ?? this.placedAt,
      updatedAt: updatedAt ?? this.updatedAt,
      statusHistory: statusHistory ?? this.statusHistory,
    );
  }

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
