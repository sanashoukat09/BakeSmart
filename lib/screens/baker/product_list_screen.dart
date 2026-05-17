import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/product_provider.dart';
import '../../providers/surplus_provider.dart';
import '../../core/router/app_router.dart';
import '../../models/product_model.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../widgets/baker/baker_bottom_nav.dart';
import '../../core/constants/app_constants.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const taupe     = Color(0xFF6F3C2C);
  static const pink      = Color(0xFFFF8B9F);
  static const pinkL     = Color(0xFFFFF4F5);
  static const copper    = Color(0xFFE67E22);
  static const cream     = Color(0xFFFAF0E6);
  
  static const surface   = Color(0xFFFFFFFF);
  static const surfaceWarm = Color(0xFFFFF9F2);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  // Vibrant accents for status and icons
  static const statusPink = Color(0xFFFF6B81);
  static const statusBrown = Color(0xFFB37E56);
  static const statusCopper = Color(0xFFF39C12);
  static const statusGreen = Color(0xFF52B788);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class ProductListScreen extends ConsumerWidget {
  const ProductListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: _T.canvas,
      bottomNavigationBar: const BakerBottomNav(currentIndex: 1),
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        title: const Text(
          'My Products',
          style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: _T.copper, size: 26),
            onPressed: () => context.push(AppRoutes.bakerAddProduct),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: _CategoryFilterBar(),
        ),
      ),
      body: ref.watch(filteredBakerProductsProvider).when(
        data: (products) {
          if (products.isEmpty) {
            return Center(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 32),
                padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
                decoration: BoxDecoration(
                  color: _T.surfaceWarm,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: _T.surface,
                        shape: BoxShape.circle,
                        boxShadow: _T.shadowSm,
                      ),
                      child: const Icon(Icons.cake_outlined, size: 28, color: _T.inkFaint),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'No products yet', 
                      style: TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () => context.push(AppRoutes.bakerAddProduct),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _T.brown,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('Add Your First Product', style: TextStyle(fontWeight: FontWeight.w800)),
                    ),
                  ],
                ),
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            itemCount: products.length,
            itemBuilder: (context, index) {
              final product = products[index];
              return _ProductCard(product: product);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
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
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: InkWell(
        onTap: () => context.push('${AppRoutes.bakerEditProduct}/${product.id}'),
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: product.images.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: product.images.first,
                        width: 76,
                        height: 76,
                        fit: BoxFit.cover,
                        placeholder: (context, url) => Container(
                          color: _T.surfaceWarm,
                          child: const Center(
                            child: SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: _T.copper),
                            ),
                          ),
                        ),
                        errorWidget: (context, url, error) => Container(
                          color: _T.surfaceWarm,
                          child: const Icon(Icons.error_outline, color: _T.inkFaint),
                        ),
                      )
                    : Container(
                        width: 76,
                        height: 76,
                        color: _T.surfaceWarm,
                        child: const Icon(Icons.image_not_supported_outlined, color: _T.inkFaint),
                      ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      product.name,
                      style: const TextStyle(
                        color: _T.ink,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 6),
                    if (activeSurplus != null)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: _T.pinkL,
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: _T.pink.withOpacity(0.4), width: 1),
                                ),
                                child: Text(
                                  'Rs. ${activeSurplus.discountPrice.toStringAsFixed(0)}',
                                  style: const TextStyle(
                                    color: _T.statusPink,
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                'Rs. ${product.price.toStringAsFixed(0)}',
                                style: const TextStyle(
                                  color: _T.inkMid,
                                  decoration: TextDecoration.lineThrough,
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 5),
                          Text(
                            'Surplus deal: ${activeSurplus.quantity} left',
                            style: const TextStyle(
                              color: _T.statusPink,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      )
                    else
                      Text(
                        'Rs. ${product.price.toStringAsFixed(0)}',
                        style: const TextStyle(
                          color: _T.brown,
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    const SizedBox(height: 5),
                    Text(
                      product.category,
                      style: const TextStyle(
                        color: _T.inkFaint,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                children: [
                  Switch(
                    value: product.isAvailable,
                    onChanged: (val) {
                      ref
                          .read(productNotifierProvider.notifier)
                          .toggleAvailability(product.id, val);
                    },
                    activeColor: _T.statusCopper,
                  ),
                  const Text(
                    'Available',
                    style: TextStyle(color: _T.inkMid, fontSize: 10, fontWeight: FontWeight.w700),
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

class _CategoryFilterBar extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedCategory = ref.watch(bakerCategoryFilterProvider);

    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.only(left: 20),
        itemCount: AppConstants.productCategories.length + 1,
        itemBuilder: (context, i) {
          final isAll = i == 0;
          final cat = isAll ? null : AppConstants.productCategories[i - 1];
          final isSelected = selectedCategory == cat;

          return GestureDetector(
            onTap: () => ref.read(bakerCategoryFilterProvider.notifier).state = cat,
            child: Container(
              margin: const EdgeInsets.only(right: 10),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: isSelected ? _T.brown : Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isSelected ? Colors.transparent : _T.rimLight,
                  width: 1.5,
                ),
              ),
              child: Center(
                child: Text(
                  isAll ? 'All' : cat!,
                  style: TextStyle(
                    color: isSelected ? Colors.white : _T.inkMid,
                    fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
