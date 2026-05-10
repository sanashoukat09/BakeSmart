import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/store_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/product_provider.dart'; // For cloudinaryServiceProvider
import '../../providers/surplus_provider.dart';
import '../../core/utils/share_util.dart';
import '../../models/product_model.dart';
import '../../models/cart_item_model.dart';
import '../../models/review_model.dart';
import '../../providers/auth_provider.dart';

class CustomerProductDetailsScreen extends ConsumerStatefulWidget {
  final String productId;
  const CustomerProductDetailsScreen({super.key, required this.productId});

  @override
  ConsumerState<CustomerProductDetailsScreen> createState() => _CustomerProductDetailsScreenState();
}

class _CustomerProductDetailsScreenState extends ConsumerState<CustomerProductDetailsScreen> {
  final List<String> _selectedAddOns = [];
  final List<File> _referencePhotos = [];
  bool _isUploading = false;

  double _calculateTotalPrice(ProductModel product, {double? basePrice}) {
    double total = basePrice ?? product.price;
    for (var label in _selectedAddOns) {
      total += product.addOns[label] ?? 0.0;
    }
    return total;
  }

  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.gallery, imageQuality: 70);
    if (picked != null) {
      setState(() => _referencePhotos.add(File(picked.path)));
    }
  }

  Future<void> _addToCart(ProductModel product, {double? basePrice, dynamic surplus}) async {
    setState(() => _isUploading = true);
    try {
      List<String> photoUrls = [];
      if (_referencePhotos.isNotEmpty) {
        photoUrls = await ref.read(cloudinaryServiceProvider).uploadMultipleImages(
          imageFiles: _referencePhotos,
          folder: 'customer_references',
        );
      }

      final cartItem = CartItemModel(
        productId: product.id,
        bakerId: product.bakerId,
        productName: product.name,
        price: _calculateTotalPrice(product, basePrice: basePrice),
        imageUrl: product.images.isNotEmpty ? product.images.first : null,
        maxQuantity: surplus?.quantity,
        surplusId: surplus?.id,
        selectedAddOns: _selectedAddOns,
        referencePhotos: photoUrls,
      );

      // Custom addItem logic for specialized CartItem
      final success = ref.read(cartProvider.notifier).addItemFromModel(cartItem);

      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Added to cart with customizations!')),
          );
          Navigator.pop(context);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Cannot add more! Only ${surplus.quantity} available in this deal.'),
              backgroundColor: const Color(0xFFDC2626),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final productsAsync = ref.watch(allProductsProvider);
    final surplusByProduct = ref.watch(activeSurplusByProductProvider);

    return productsAsync.when(
      data: (products) {
        final product = products.firstWhere((p) => p.id == widget.productId);
        final surplus = surplusByProduct[product.id];
        final basePrice = surplus?.discountPrice ?? product.price;
        final totalPrice = _calculateTotalPrice(product, basePrice: basePrice);

        return Scaffold(
          backgroundColor: Colors.white,
          body: CustomScrollView(
            slivers: [
              SliverAppBar(
                expandedHeight: 350,
                pinned: true,
                actions: [
                  IconButton(
                    icon: const Icon(Icons.share_outlined),
                    onPressed: () => ShareUtil.shareProduct(
                      productName: product.name,
                      productId: product.id,
                      bakerName: 'BakeSmart Baker', // Could fetch actual name if needed
                    ),
                  ),
                ],
                flexibleSpace: FlexibleSpaceBar(
                  background: product.images.isNotEmpty
                      ? CachedNetworkImage(imageUrl: product.images.first, fit: BoxFit.cover)
                      : Container(color: const Color(0xFFFEF3C7)),
                ),
              ),
              
              // Allergen Warning
              _buildAllergenWarning(product),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(product.name, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Text(
                            'Rs. ${totalPrice.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontSize: 20,
                              color: surplus != null
                                  ? const Color(0xFFDC2626)
                                  : const Color(0xFFD97706),
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          if (surplus != null) ...[
                            const SizedBox(width: 10),
                            Text(
                              'Rs. ${product.price.toStringAsFixed(0)}',
                              style: const TextStyle(
                                color: Colors.grey,
                                decoration: TextDecoration.lineThrough,
                              ),
                            ),
                          ],
                        ],
                      ),
                      if (surplus != null) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF2F2),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFFFECACA)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.flash_on, color: Color(0xFFDC2626), size: 18),
                              const SizedBox(width: 8),
                              Text(
                                'FLASH DEAL: ${surplus.quantity} item${surplus.quantity > 1 ? "s" : ""} left',
                                style: const TextStyle(
                                  color: Color(0xFFDC2626),
                                  fontWeight: FontWeight.w800,
                                  fontSize: 13,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                      const SizedBox(height: 16),
                      Text(product.description, style: const TextStyle(color: Colors.grey, height: 1.5)),
                      const SizedBox(height: 32),
                      _ProductReviews(productId: product.id),
                      
                      if (product.addOns.isNotEmpty) ...[
                        const SizedBox(height: 32),
                        const Text('Customizations', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 12),
                        ...product.addOns.entries.map((e) => CheckboxListTile(
                          title: Text(e.key),
                          subtitle: Text('+ Rs. ${e.value.toStringAsFixed(0)}'),
                          value: _selectedAddOns.contains(e.key),
                          activeColor: const Color(0xFFD97706),
                          contentPadding: EdgeInsets.zero,
                          onChanged: (val) {
                            setState(() {
                              if (val!) _selectedAddOns.add(e.key);
                              else _selectedAddOns.remove(e.key);
                            });
                          },
                        )),
                      ],

                      const SizedBox(height: 32),
                      const Text('Reference Photos (Optional)', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      const Text('Upload photos for custom designs or messages', style: TextStyle(color: Colors.grey, fontSize: 12)),
                      const SizedBox(height: 12),
                      SizedBox(
                        height: 80,
                        child: ListView(
                          scrollDirection: Axis.horizontal,
                          children: [
                            GestureDetector(
                              onTap: _pickImage,
                              child: Container(
                                width: 80,
                                decoration: BoxDecoration(color: const Color(0xFFFEF3C7), borderRadius: BorderRadius.circular(12)),
                                child: const Icon(Icons.add_a_photo, color: Color(0xFFD97706)),
                              ),
                            ),
                            ..._referencePhotos.map((f) => Padding(
                              padding: const EdgeInsets.only(left: 8),
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(12),
                                child: Image.file(f, width: 80, height: 80, fit: BoxFit.cover),
                              ),
                            )),
                          ],
                        ),
                      ),
                      const SizedBox(height: 100),
                    ],
                  ),
                ),
              ),
            ],
          ),
          bottomSheet: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: Colors.white, boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 10, offset: const Offset(0, -4))]),
            child: SafeArea(
              child: ElevatedButton(
                onPressed: _isUploading
                    ? null
                    : () => _addToCart(product, basePrice: basePrice, surplus: surplus),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFD97706),
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 56),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                child: _isUploading 
                  ? const CircularProgressIndicator(color: Colors.white)
                  : const Text('Add to Cart', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
          ),
        );
      },
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(body: Center(child: Text('Error: $e'))),
    );
  }

  Widget _buildAllergenWarning(ProductModel product) {
    final user = ref.watch(currentUserProvider).valueOrNull;
    if (user == null || user.allergens.isEmpty) return const SliverToBoxAdapter(child: SizedBox.shrink());

    final List<String> conflicts = [];
    for (var allergen in user.allergens) {
      // Market-friendly flags take precedence.
      if (product.includesAllDietaryLabels == true) {
        continue;
      }

      if (product.includesNoDietaryLabels == true) {
        conflicts.add(allergen);
        continue;
      }

      bool isSafe = false;
      if (allergen == 'Nuts' && product.dietaryLabels.contains('Nut-Free')) isSafe = true;
      if (allergen == 'Gluten' && product.dietaryLabels.contains('Gluten-Free')) isSafe = true;
      if (allergen == 'Eggs' && product.dietaryLabels.contains('Eggless')) isSafe = true;
      if (allergen == 'Sugar' && product.dietaryLabels.contains('Sugar-Free')) isSafe = true;

      // If we don't have a "Free" label for this allergen, assume it might be present
      if (!isSafe) conflicts.add(allergen);
    }

    if (conflicts.isEmpty) return const SliverToBoxAdapter(child: SizedBox.shrink());

    return SliverToBoxAdapter(
      child: Container(
        margin: const EdgeInsets.fromLTRB(24, 16, 24, 0),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFFFEF2F2),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFFECACA)),
        ),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, color: Color(0xFFDC2626), size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Allergen Warning!',
                    style: TextStyle(color: Color(0xFF991B1B), fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  Text(
                    'This product may contain: ${conflicts.join(", ")} which matches your allergen profile.',
                    style: const TextStyle(color: Color(0xFFB91C1C), fontSize: 12),
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

class _ProductReviews extends ConsumerWidget {
  final String productId;

  const _ProductReviews({required this.productId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return StreamBuilder<List<ReviewModel>>(
      stream: ref.read(firestoreServiceProvider).streamProductReviews(productId),
      builder: (context, snapshot) {
        final reviews = snapshot.data ?? [];
        if (reviews.isEmpty) {
          return const SizedBox.shrink();
        }

        final avgRating =
            reviews.fold<double>(0, (sum, review) => sum + review.rating) /
                reviews.length;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text(
                  'Reviews',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.star_rounded, color: Colors.amber, size: 18),
                Text(
                  '${avgRating.toStringAsFixed(1)} (${reviews.length})',
                  style: const TextStyle(
                    color: Color(0xFFD97706),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...reviews.take(5).map((review) => _ReviewTile(review: review)),
            const SizedBox(height: 8),
          ],
        );
      },
    );
  }
}

class _ReviewTile extends StatelessWidget {
  final ReviewModel review;

  const _ReviewTile({required this.review});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFDFCF9),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFEF3C7)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  review.customerName,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Row(
                children: List.generate(
                  5,
                  (index) => Icon(
                    index < review.rating.round()
                        ? Icons.star_rounded
                        : Icons.star_outline_rounded,
                    color: Colors.amber,
                    size: 16,
                  ),
                ),
              ),
            ],
          ),
          if (review.comment.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              review.comment,
              style: const TextStyle(color: Colors.grey, height: 1.4),
            ),
          ],
        ],
      ),
    );
  }
}
