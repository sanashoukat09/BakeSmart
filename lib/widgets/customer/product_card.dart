import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/product_model.dart';
import '../../providers/surplus_provider.dart';
import '../../providers/store_provider.dart';
import '../../providers/cart_provider.dart';
import '../../models/cart_item_model.dart';
import '../../providers/wishlist_provider.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const surface   = Color(0xFFFFFFFF);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  static const statusPink = Color(0xFFFF6B81);
  static const statusRed   = Color(0xFFE74C3C);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: ink.withOpacity(0.03), blurRadius: 12, offset: const Offset(0, 4)),
  ];
}

class ProductCard extends ConsumerWidget {
  final ProductModel product;
  final VoidCallback onTap;

  const ProductCard({super.key, required this.product, required this.onTap});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final surplus = ref.watch(activeSurplusByProductProvider)[product.id];
    final hasDeal = surplus != null;
    final bakers = ref.watch(allBakersProvider).valueOrNull ?? [];
    final baker = bakers.cast<dynamic>().firstWhere((b) => b.uid == product.bakerId, orElse: () => null);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _T.rimLight, width: 1.2),
          boxShadow: _T.shadowSm,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image Section
            Expanded(
              flex: 5,
              child: ClipRRect(
                borderRadius: const BorderRadius.vertical(top: Radius.circular(15)),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    product.images.isNotEmpty
                        ? CachedNetworkImage(
                            imageUrl: product.images.first,
                            width: double.infinity,
                            fit: BoxFit.cover,
                            placeholder: (context, url) =>
                                Container(color: _T.rimLight),
                          )
                        : Container(
                            color: _T.rimLight,
                            child: const Icon(Icons.cake_outlined, color: _T.inkMid, size: 24),
                          ),
                    if (hasDeal)
                      Positioned(
                        top: 8,
                        left: 8,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: _T.brown,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Text(
                            'SPECIAL DEAL',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 8,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.2,
                            ),
                          ),
                        ),
                      ),
                    Positioned(
                      top: 8,
                      right: 8,
                      child: Consumer(
                        builder: (context, ref, child) {
                          final wishlist = ref.watch(wishlistProvider);
                          final isFav = wishlist.contains(product.id);
                          return GestureDetector(
                            onTap: () {
                              final added = ref.read(wishlistProvider.notifier).toggleWishlist(product.id);
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    added ? '${product.name} added to wishlist' : '${product.name} removed from wishlist',
                                  ),
                                  behavior: SnackBarBehavior.floating,
                                  backgroundColor: _T.ink,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                  duration: const Duration(seconds: 1),
                                ),
                              );
                            },
                            child: Container(
                              padding: const EdgeInsets.all(5),
                              decoration: const BoxDecoration(
                                color: Colors.white,
                                shape: BoxShape.circle,
                                boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 4)],
                              ),
                              child: Icon(
                                isFav ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                                color: _T.statusPink,
                                size: 16,
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Info Section
            Expanded(
              flex: 5,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      product.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: _T.ink,
                        fontWeight: FontWeight.w800,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 2),
                    if (hasDeal)
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              'Rs. ${surplus!.discountPrice.toStringAsFixed(0)}',
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: _T.brown,
                                fontWeight: FontWeight.w800,
                                fontSize: 13.5,
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              'Rs. ${product.price.toStringAsFixed(0)}',
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: _T.inkFaint,
                                decoration: TextDecoration.lineThrough,
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      )
                    else
                      Text(
                        'Rs. ${product.price.toStringAsFixed(0)}',
                        style: const TextStyle(
                          color: _T.brown,
                          fontWeight: FontWeight.w800,
                          fontSize: 13.5,
                        ),
                      ),
                    const Divider(color: _T.rimLight, height: 10, thickness: 1),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                baker?.bakeryName ?? 'Home Bakery',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: _T.inkMid,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Row(
                                children: [
                                  const Icon(Icons.star_rounded, color: Colors.amber, size: 12),
                                  const SizedBox(width: 2),
                                  Text(
                                    baker?.rating.toStringAsFixed(1) ?? '4.8',
                                    style: const TextStyle(
                                      color: _T.inkMid,
                                      fontSize: 10.5,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                        GestureDetector(
                          onTap: () {
                            ref.read(cartProvider.notifier).addItemFromModel(
                              CartItemModel(
                                productId: product.id,
                                bakerId: product.bakerId,
                                productName: product.name,
                                price: hasDeal ? surplus!.discountPrice : product.price,
                                imageUrl: product.images.isNotEmpty ? product.images.first : '',
                                surplusId: surplus?.id,
                              ),
                            );
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Added ${product.name} to cart'),
                                duration: const Duration(milliseconds: 1500),
                                behavior: SnackBarBehavior.floating,
                                backgroundColor: _T.ink,
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                            );
                          },
                          child: Container(
                            padding: const EdgeInsets.all(6),
                            decoration: const BoxDecoration(
                              color: _T.brown,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(
                              Icons.add_shopping_cart_rounded,
                              color: Colors.white,
                              size: 14,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
