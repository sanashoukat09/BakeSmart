import 'package:cloud_firestore/cloud_firestore.dart';

class OrderModel {
  final String id;
  final String customerId;
  final String bakerId;
  final List<OrderItem> items;
  final double totalAmount;
  final String status; // placed, accepted, preparing, ready, delivered, rejected
  final DateTime createdAt;
  final DateTime deliveryDate;
  final String? customerNote;
  final List<String> referencePhotos;
  final String deliveryAddress;
  final String customerName;
  final String customerPhone;
  final bool capacityWarning;
  final String? capacityWarningMessage;
  final bool inventoryDeducted;
  final String paymentMethod;

  OrderModel({
    required this.id,
    required this.customerId,
    required this.bakerId,
    required this.items,
    required this.totalAmount,
    required this.status,
    required this.createdAt,
    required this.deliveryDate,
    this.customerNote,
    this.referencePhotos = const [],
    required this.deliveryAddress,
    required this.customerName,
    required this.customerPhone,
    this.capacityWarning = false,
    this.capacityWarningMessage,
    this.inventoryDeducted = false,
    this.paymentMethod = 'COD',
  });

  factory OrderModel.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return OrderModel(
      id: doc.id,
      customerId: data['customerId'] ?? '',
      bakerId: data['bakerId'] ?? '',
      items: (data['items'] as List? ?? [])
          .map((item) => OrderItem.fromMap(item))
          .toList(),
      totalAmount: (data['totalAmount'] ?? 0.0).toDouble(),
      status: data['status'] ?? 'placed',
      createdAt: (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      deliveryDate: (data['deliveryDate'] as Timestamp?)?.toDate() ?? DateTime.now(),
      customerNote: data['customerNote'],
      referencePhotos: List<String>.from(data['referencePhotos'] ?? []),
      deliveryAddress: data['deliveryAddress'] ?? '',
      customerName: data['customerName'] ?? '',
      customerPhone: data['customerPhone'] ?? '',
      capacityWarning: data['capacityWarning'] ?? false,
      capacityWarningMessage: data['capacityWarningMessage'],
      inventoryDeducted: data['inventoryDeducted'] ?? false,
      paymentMethod: data['paymentMethod'] ?? 'COD',
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'customerId': customerId,
      'bakerId': bakerId,
      'items': items.map((i) => i.toMap()).toList(),
      'totalAmount': totalAmount,
      'status': status,
      'createdAt': Timestamp.fromDate(createdAt),
      'deliveryDate': Timestamp.fromDate(deliveryDate),
      'customerNote': customerNote,
      'referencePhotos': referencePhotos,
      'deliveryAddress': deliveryAddress,
      'customerName': customerName,
      'customerPhone': customerPhone,
      'capacityWarning': capacityWarning,
      'capacityWarningMessage': capacityWarningMessage,
      'inventoryDeducted': inventoryDeducted,
      'paymentMethod': paymentMethod,
    };
  }
}

class OrderItem {
  final String productId;
  final String productName;
  final int quantity;
  final double price;
  final String? imageUrl;
  final List<String> selectedAddOns;

  OrderItem({
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.price,
    this.imageUrl,
    this.selectedAddOns = const [],
  });

  factory OrderItem.fromMap(Map<String, dynamic> map) {
    return OrderItem(
      productId: map['productId'] ?? '',
      productName: map['productName'] ?? '',
      quantity: map['quantity'] ?? 0,
      price: (map['price'] ?? 0.0).toDouble(),
      imageUrl: map['imageUrl'],
      selectedAddOns: List<String>.from(map['selectedAddOns'] ?? []),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'productId': productId,
      'productName': productName,
      'quantity': quantity,
      'price': price,
      'imageUrl': imageUrl,
      'selectedAddOns': selectedAddOns,
    };
  }
}
