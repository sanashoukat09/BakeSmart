import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/product_provider.dart';
import '../../providers/surplus_provider.dart';
import '../../core/router/app_router.dart';
import '../../models/product_model.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../core/theme/baker_theme.dart';


class ProductListScreen extends ConsumerWidget {
  const ProductListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final productsAsync = ref.watch(bakerProductsProvider);

    return Scaffold(
      backgroundColor: BakerTheme.background,

      appBar: AppBar(
        backgroundColor: BakerTheme.background,
        title: const Text(
          'My Products',
          style: TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold),
        ),

        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: Color(0xFFF59E0B)),
            onPressed: () => context.push(AppRoutes.bakerAddProduct),
          ),
        ],
      ),
      body: productsAsync.when(
        data: (products) {
          if (products.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.cake_outlined,
                      color: Color(0xFF484F58), size: 64),
                  const SizedBox(height: 16),
                  const Text(
                    'No products yet',
                    style: TextStyle(color: BakerTheme.textPrimary, fontSize: 18),

                  ),
                  const SizedBox(height: 8),
                  ElevatedButton(
                    onPressed: () => context.push(AppRoutes.bakerAddProduct),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: BakerTheme.secondary,
                      foregroundColor: Colors.white,

                    ),
                    child: const Text('Add Your First Product'),
                  ),
                ],
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: products.length,
            itemBuilder: (context, index) {
              final product = products[index];
              return _ProductCard(product: product);
            },
          );
        },
        loading: () => const Center(
            child: CircularProgressIndicator(color: Color(0xFFF59E0B))),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}

class _ProductCard extends ConsumerWidget {
  final ProductModel product;
  const _ProductCard({required this.product});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final surplusItems = ref.watch(bakerSurplusProvider).valueOrNull ?? [];
    final surplus = surplusItems
        .where((item) => item.productId == product.id && item.quantity > 0)
        .toList();
    surplus.sort((a, b) => a.discountPrice.compareTo(b.discountPrice));
    final activeSurplus = surplus.isNotEmpty ? surplus.first : null;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: BakerTheme.divider),

      ),
      child: InkWell(
        onTap: () => context.push('${AppRoutes.bakerEditProduct}/${product.id}'),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: product.images.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: product.images.first,
                        width: 80,
                        height: 80,
                        fit: BoxFit.cover,
                        placeholder: (context, url) => Container(
                          color: BakerTheme.background,

                          child: const Center(
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                        errorWidget: (context, url, error) => Container(
                          color: BakerTheme.background,

                          child: const Icon(Icons.error),
                        ),
                      )
                    : Container(
                        width: 80,
                        height: 80,
                        color: BakerTheme.background,

                        child: const Icon(Icons.image_not_supported,
                            color: Color(0xFF484F58)),
                      ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      product.name,
                      style: const TextStyle(
                        color: BakerTheme.textPrimary,

                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    if (activeSurplus != null)
                      Row(
                        children: [
                          Text(
                            'Rs. ${activeSurplus.discountPrice.toStringAsFixed(0)}',
                            style: const TextStyle(
                              color: Colors.red,
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Rs. ${product.price.toStringAsFixed(0)}',
                            style: const TextStyle(
                              color: Color(0xFF8B949E),
                              decoration: TextDecoration.lineThrough,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      )
                    else
                      Text(
                        'Rs. ${product.price.toStringAsFixed(0)}',
                        style: const TextStyle(
                          color: BakerTheme.secondary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    if (activeSurplus != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        'Surplus deal: ${activeSurplus.quantity} left',
                        style: const TextStyle(
                          color: Colors.red,
                          fontSize: 11,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                    const SizedBox(height: 4),
                    Text(
                      product.category,
                      style: const TextStyle(
                        color: Color(0xFF8B949E),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                children: [
                  Switch(
                    value: product.isAvailable,
                    onChanged: (val) {
                      ref
                          .read(productNotifierProvider.notifier)
                          .toggleAvailability(product.id, val);
                    },
                    activeColor: const Color(0xFFF59E0B),
                  ),
                  const Text(
                    'Available',
                    style: TextStyle(color: Color(0xFF8B949E), fontSize: 10),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
