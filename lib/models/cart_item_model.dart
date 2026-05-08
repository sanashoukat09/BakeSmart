class CartItemModel {
  final String productId;
  final String bakerId;
  final String productName;
  final double price;
  final String? imageUrl;
  final int quantity;
  final int? maxQuantity;
  final List<String> selectedAddOns;
  final List<String> referencePhotos;
  final String? surplusId;

  CartItemModel({
    required this.productId,
    required this.bakerId,
    required this.productName,
    required this.price,
    this.imageUrl,
    this.quantity = 1,
    this.maxQuantity,
    this.selectedAddOns = const [],
    this.referencePhotos = const [],
    this.surplusId,
  });

  String get lineKey {
    final addOns = [...selectedAddOns]..sort();
    final photos = [...referencePhotos]..sort();
    return [
      productId,
      bakerId,
      price.toStringAsFixed(2),
      surplusId ?? '',
      addOns.join('|'),
      photos.join('|'),
    ].join('::');
  }

  CartItemModel copyWith({
    int? quantity,
    int? maxQuantity,
    List<String>? selectedAddOns,
    List<String>? referencePhotos,
    String? surplusId,
  }) {
    return CartItemModel(
      productId: productId,
      bakerId: bakerId,
      productName: productName,
      price: price,
      imageUrl: imageUrl,
      quantity: quantity ?? this.quantity,
      maxQuantity: maxQuantity ?? this.maxQuantity,
      selectedAddOns: selectedAddOns ?? this.selectedAddOns,
      referencePhotos: referencePhotos ?? this.referencePhotos,
      surplusId: surplusId ?? this.surplusId,
    );
  }

  double get total => price * quantity;

  Map<String, dynamic> toMap() {
    return {
      'productId': productId,
      'bakerId': bakerId,
      'productName': productName,
      'price': price,
      'imageUrl': imageUrl,
      'quantity': quantity,
      'maxQuantity': maxQuantity,
      'selectedAddOns': selectedAddOns,
      'referencePhotos': referencePhotos,
      'surplusId': surplusId,
    };
  }

  factory CartItemModel.fromMap(Map<String, dynamic> map) {
    return CartItemModel(
      productId: map['productId'] ?? '',
      bakerId: map['bakerId'] ?? '',
      productName: map['productName'] ?? '',
      price: (map['price'] ?? 0.0).toDouble(),
      imageUrl: map['imageUrl'],
      quantity: map['quantity'] ?? 1,
      maxQuantity: map['maxQuantity'],
      selectedAddOns: List<String>.from(map['selectedAddOns'] ?? []),
      referencePhotos: List<String>.from(map['referencePhotos'] ?? []),
      surplusId: map['surplusId'],
    );
  }
}
