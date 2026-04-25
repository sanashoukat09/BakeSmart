// SHARED MODEL — Keep in sync with d:/Bake Smart/lib/features/customer/models/cart_item_model.dart

class CartItemModel {
  final String productId;
  final String productName;
  final String coverImageUrl;
  final int quantity;
  final double unitPrice;
  final String bakerId;
  final String bakerName;
  final bool isUnavailableError;

  CartItemModel({
    required this.productId,
    required this.productName,
    required this.coverImageUrl,
    required this.quantity,
    required this.unitPrice,
    required this.bakerId,
    required this.bakerName,
    this.isUnavailableError = false,
  });

  Map<String, dynamic> toMap() {
    return {
      'productId': productId,
      'productName': productName,
      'coverImageUrl': coverImageUrl,
      'quantity': quantity,
      'unitPrice': unitPrice,
      'bakerId': bakerId,
      'bakerName': bakerName,
    };
  }

  factory CartItemModel.fromMap(Map<String, dynamic> map) {
    return CartItemModel(
      productId: map['productId'] ?? '',
      productName: map['productName'] ?? '',
      coverImageUrl: map['coverImageUrl'] ?? '',
      quantity: (map['quantity'] ?? 0).toInt(),
      unitPrice: (map['unitPrice'] ?? 0).toDouble(),
      bakerId: map['bakerId'] ?? '',
      bakerName: map['bakerName'] ?? '',
    );
  }
}
