import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../products/models/product_model.dart';
import '../models/cart_item_model.dart';
import '../services/cart_service.dart';
import '../services/review_service.dart';
import 'package:intl/intl.dart';
import 'package:cached_network_image/cached_network_image.dart';

class ProductDetailScreen extends ConsumerStatefulWidget {
  final ProductModel product;
  const ProductDetailScreen({super.key, required this.product});

  @override
  ConsumerState<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends ConsumerState<ProductDetailScreen> {
  int _quantity = 1;
  int _currentImageIndex = 0;

  void _addToCart() {
    final cartService = ref.read(cartProvider.notifier);
    
    if (!cartService.canAddItem(widget.product.bakerId)) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Start a new cart?'),
          content: Text('Your cart has items from another baker. Adding this item will clear your current cart. Do you want to continue?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Keep Current Cart', style: TextStyle(color: Colors.grey)),
            ),
            ElevatedButton(
              onPressed: () {
                cartService.clearCart();
                _performAdd();
                Navigator.pop(ctx);
              },
              style: ElevatedButton.styleFrom(backgroundColor: Colors.brown, foregroundColor: Colors.white),
              child: const Text('Clear & Add'),
            ),
          ],
        ),
      );
    } else {
      _performAdd();
    }
  }

  void _performAdd() {
    final priceToUse = widget.product.isSurplus && widget.product.surplusPrice != null
        ? widget.product.surplusPrice!
        : widget.product.basePrice;

    final cartItem = CartItemModel(
      productId: widget.product.productId,
      productName: widget.product.name,
      coverImageUrl: widget.product.images.isNotEmpty ? widget.product.images.first : '',
      quantity: _quantity,
      unitPrice: priceToUse,
      bakerId: widget.product.bakerId,
      bakerName: widget.product.bakerName,
    );

    ref.read(cartProvider.notifier).addItem(cartItem);
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Added to cart!'), duration: Duration(seconds: 1)));
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final reviewsAsync = ref.watch(productReviewsProvider(widget.product.productId));
    
    final priceToDisplay = widget.product.isSurplus && widget.product.surplusPrice != null 
        ? widget.product.surplusPrice! 
        : widget.product.basePrice;

    double avgRating = 0;
    int reviewCount = 0;
    if (reviewsAsync.hasValue && reviewsAsync.value!.isNotEmpty) {
      final reviews = reviewsAsync.value!;
      reviewCount = reviews.length;
      avgRating = reviews.fold(0.0, (sum, r) => sum + r.rating) / reviewCount;
    }

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: Text(widget.product.name),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: Colors.brown,
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Gallery
            SizedBox(
              height: 300,
              child: Stack(
                children: [
                  widget.product.images.isNotEmpty
                      ? PageView.builder(
                          itemCount: widget.product.images.length,
                          onPageChanged: (idx) => setState(() => _currentImageIndex = idx),
                          itemBuilder: (ctx, i) => CachedNetworkImage(
                            imageUrl: widget.product.images[i],
                            fit: BoxFit.cover,
                            width: double.infinity,
                            placeholder: (context, url) => Container(color: Colors.grey[200]),
                            errorWidget: (context, url, error) => const Icon(Icons.error),
                          ),
                        )
                      : Container(color: Colors.grey[200], child: const Center(child: Icon(Icons.image, size: 80, color: Colors.grey))),
                  
                  // Gradient & Dots
                  if (widget.product.images.length > 1)
                    Positioned(
                      bottom: 0, left: 0, right: 0,
                      child: Container(
                        height: 50,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.bottomCenter,
                            end: Alignment.topCenter,
                            colors: [Colors.black.withOpacity(0.6), Colors.transparent],
                          )
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: List.generate(widget.product.images.length, (idx) {
                            return Container(
                              margin: const EdgeInsets.symmetric(horizontal: 4),
                              width: _currentImageIndex == idx ? 10 : 6,
                              height: _currentImageIndex == idx ? 10 : 6,
                              decoration: BoxDecoration(shape: BoxShape.circle, color: _currentImageIndex == idx ? Colors.white : Colors.white54),
                            );
                          }),
                        ),
                      ),
                    ),
                ],
              ),
            ),

            // Content
            Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(widget.product.name, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                            if (reviewCount > 0)
                              Row(
                                children: [
                                  const Icon(Icons.star, color: Colors.orange, size: 16),
                                  const SizedBox(width: 4),
                                  Text(avgRating.toStringAsFixed(1), style: const TextStyle(fontWeight: FontWeight.bold)),
                                  Text(' ($reviewCount)', style: const TextStyle(color: Colors.grey)),
                                ],
                              ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text('\$${priceToDisplay.toStringAsFixed(2)}', style: const TextStyle(fontSize: 24, color: Colors.brown, fontWeight: FontWeight.bold)),
                          if (widget.product.isSurplus && widget.product.surplusPrice != null)
                            Text('\$${widget.product.basePrice.toStringAsFixed(2)}', style: const TextStyle(fontSize: 14, decoration: TextDecoration.lineThrough, color: Colors.grey)),
                        ],
                      )
                    ],
                  ),
                  const SizedBox(height: 12),
                  
                  // Baker info
                  Row(
                    children: [
                      const Icon(Icons.store, color: Colors.grey, size: 20),
                      const SizedBox(width: 8),
                      Text(widget.product.bakerName, style: TextStyle(color: Colors.grey[800], fontSize: 16)),
                      if (widget.product.bakerIsVerified) ...[
                        const SizedBox(width: 4),
                        const Icon(Icons.verified, color: Colors.blue, size: 18),
                      ]
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Tags
                  if (widget.product.tags.isNotEmpty) ...[
                    Wrap(
                      spacing: 8, runSpacing: 8,
                      children: widget.product.tags.map((t) => Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(color: Colors.brown[50], borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.brown[200]!)),
                        child: Text(t, style: TextStyle(color: Colors.brown[700], fontSize: 12)),
                      )).toList(),
                    ),
                    const SizedBox(height: 24),
                  ],

                  Text(widget.product.description, style: const TextStyle(fontSize: 16, height: 1.5, color: Colors.black87)),
                  const SizedBox(height: 32),

                  // Quantity Selector
                  Row(
                    children: [
                      const Text('Quantity', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500)),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.remove_circle_outline),
                        onPressed: () {
                          if (_quantity > 1) setState(() => _quantity--);
                        },
                      ),
                      Text('$_quantity', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                      IconButton(
                        icon: const Icon(Icons.add_circle_outline),
                        onPressed: () => setState(() => _quantity++),
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),

                  // Add Button
                  ElevatedButton(
                    onPressed: _addToCart,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      backgroundColor: Colors.brown,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      minimumSize: const Size(double.infinity, 50),
                    ),
                    child: Text('Add to Cart - \$${(priceToDisplay * _quantity).toStringAsFixed(2)}', style: const TextStyle(fontSize: 18)),
                  ),
                  
                  const SizedBox(height: 32),
                  const Divider(),
                  const SizedBox(height: 16),
                  const Text('Reviews & Ratings', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  
                  reviewsAsync.when(
                    data: (reviews) {
                      if (reviews.isEmpty) {
                        return const Text('No reviews yet. Be the first to try this!', style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic));
                      }
                      
                      return Column(
                        children: reviews.map((r) => Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(r.customerName, style: const TextStyle(fontWeight: FontWeight.bold)),
                                  Text(DateFormat('MMM dd, yyyy').format(r.createdAt), style: TextStyle(color: Colors.grey[600], fontSize: 12)),
                                ],
                              ),
                              Row(
                                children: List.generate(5, (index) => Icon(
                                  index < r.rating ? Icons.star : Icons.star_border,
                                  color: Colors.orange,
                                  size: 14,
                                )),
                              ),
                              if (r.reviewText != null && r.reviewText!.isNotEmpty) ...[
                                const SizedBox(height: 8),
                                Text(r.reviewText!),
                              ]
                            ],
                          ),
                        )).toList(),
                      );
                    },
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (e,s) => const Text('Failed to load reviews.'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
