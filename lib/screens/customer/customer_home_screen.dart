import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../providers/store_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/surplus_provider.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';
import '../../models/product_model.dart';
import '../../models/cart_item_model.dart';
import '../../providers/notification_provider.dart';
import '../../widgets/customer/customer_bottom_nav.dart';
import '../../widgets/customer/product_card.dart';
import '../../providers/wishlist_provider.dart';
import '../../providers/order_provider.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const pink      = Color(0xFFFF8B9F);
  static const pinkL     = Color(0xFFFFF4F5);
  static const surface   = Color(0xFFFFFFFF);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  static const statusPink = Color(0xFFFF6B81);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

final bestSellingProductsProvider = Provider<List<ProductModel>>((ref) {
  final productsAsync = ref.watch(allProductsProvider);
  final ordersAsync = ref.watch(allOrdersProvider);

  final products = productsAsync.valueOrNull ?? [];
  final orders = ordersAsync.valueOrNull ?? [];

  if (products.isEmpty) return [];

  final Map<String, int> salesCount = {};
  for (final order in orders) {
    if (order.status == 'rejected' || order.status == 'cancelled') continue;
    for (final item in order.items) {
      salesCount[item.productId] = (salesCount[item.productId] ?? 0) + item.quantity;
    }
  }

  // Filter only available products
  final availableProducts = products.where((p) => p.isAvailable).toList();

  // Sort products by sales count descending, fallback to createdAt descending
  availableProducts.sort((a, b) {
    final countA = salesCount[a.id] ?? 0;
    final countB = salesCount[b.id] ?? 0;
    if (countB != countA) {
      return countB.compareTo(countA);
    }
    return b.createdAt.compareTo(a.createdAt);
  });

  return availableProducts.take(5).toList();
});

class CustomerHomeScreen extends ConsumerWidget {
  const CustomerHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bestSellingProducts = ref.watch(bestSellingProductsProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Header Row
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 10),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Welcome',
                          style: TextStyle(
                            color: _T.ink,
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.4,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Discover hand-crafted artisan treats.',
                          style: TextStyle(
                            color: _T.inkMid,
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                    _NotificationBell(),
                  ],
                ),
              ),

              // 2. Capsule Search Field
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                child: Container(
                  decoration: BoxDecoration(
                    color: _T.surface,
                    borderRadius: BorderRadius.circular(30),
                    border: Border.all(color: _T.rimLight, width: 1.5),
                    boxShadow: _T.shadowSm,
                  ),
                  child: TextField(
                    onChanged: (v) {
                      ref.read(storeFilterProvider.notifier).state = ref.read(storeFilterProvider).copyWith(query: v);
                    },
                    style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w700),
                    decoration: const InputDecoration(
                      hintText: 'Search cake, cookies, anything...',
                      hintStyle: TextStyle(color: _T.inkFaint, fontWeight: FontWeight.w600, fontSize: 14),
                      prefixIcon: Icon(Icons.search, color: _T.inkFaint, size: 22),
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 20, vertical: 15),
                    ),
                  ),
                ),
              ),

              // 3. Featured Promo Banner
              const Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                child: _PromoBanner(),
              ),

              // 4. Best Selling section
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 26, 20, 12),
                child: Row(
                  children: const [
                    Text(
                      'Our Best Selling',
                      style: TextStyle(
                        color: _T.ink,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    SizedBox(width: 8),
                    Text(
                      'This week',
                      style: TextStyle(
                        color: _T.inkMid,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),

              SizedBox(
                height: 215,
                child: bestSellingProducts.isEmpty
                    ? const Center(
                        child: Text(
                          'No best selling products available.',
                          style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600),
                        ),
                      )
                    : ListView.builder(
                        scrollDirection: Axis.horizontal,
                        physics: const BouncingScrollPhysics(),
                        padding: const EdgeInsets.only(left: 20),
                        itemCount: bestSellingProducts.length,
                        itemBuilder: (context, i) => _BestSellingCard(product: bestSellingProducts[i]),
                      ),
              ),

              // 6. Explore Categories
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 28, 20, 12),
                child: const Text(
                  'Explore Categories',
                  style: TextStyle(
                    color: _T.ink,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),

              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
                child: GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 16,
                  childAspectRatio: 1.1,
                  children: [
                    _buildCategoryCard(context, ref, 'Beverages', 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Cakes', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Cupcakes', 'https://images.unsplash.com/photo-1576618148400-f54bed99fcfd?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Cookies', 'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Brownies', 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Pastries', 'https://images.unsplash.com/photo-1508737804141-4c3b688e2546?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Donuts', 'https://images.unsplash.com/photo-1551024601-bec78aea704b?auto=format&fit=crop&w=300&q=80'),
                    _buildCategoryCard(context, ref, 'Custom Cakes', 'assets/images/custom_cakes.png'),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: const CustomerBottomNav(currentIndex: 0),
    );
  }

  Widget _buildCategoryCard(BuildContext context, WidgetRef ref, String cat, String imgUrl) {
    return GestureDetector(
      onTap: () {
        context.push('${AppRoutes.customerCategoryProducts}/$cat');
      },
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _T.rimLight, width: 1.2),
          boxShadow: _T.shadowSm,
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(14),
          child: Stack(
            fit: StackFit.expand,
            children: [
              imgUrl.startsWith('assets/')
                  ? Image.asset(
                      imgUrl,
                      fit: BoxFit.cover,
                    )
                  : CachedNetworkImage(
                      imageUrl: imgUrl,
                      fit: BoxFit.cover,
                      placeholder: (context, url) => Container(color: _T.pinkL),
                    ),
              Container(
                color: Colors.black.withOpacity(0.42),
              ),
              Center(
                child: Text(
                  cat,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 18,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BestSellingCard extends ConsumerWidget {
  final ProductModel product;
  const _BestSellingCard({required this.product});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final surplus = ref.watch(activeSurplusByProductProvider)[product.id];
    final hasDeal = surplus != null;
    final price = hasDeal ? surplus.discountPrice : product.price;

    return GestureDetector(
      onTap: () => context.push('${AppRoutes.customerProduct}/${product.id}'),
      child: Container(
        width: 155,
        margin: const EdgeInsets.only(right: 16, bottom: 8, top: 4),
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _T.rimLight, width: 1.2),
          boxShadow: _T.shadowSm,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image + Overlays
            Stack(
              children: [
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(15)),
                  child: product.images.isNotEmpty
                      ? CachedNetworkImage(
                          imageUrl: product.images.first,
                          height: 110,
                          width: double.infinity,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => Container(color: _T.rimLight),
                        )
                      : Container(
                          height: 110,
                          width: double.infinity,
                          color: _T.rimLight,
                          child: const Icon(Icons.cake_outlined, color: _T.inkMid),
                        ),
                ),
                Positioned(
                  top: 6,
                  right: 6,
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
                            size: 15,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
            // Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
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
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Rs. ${price.toStringAsFixed(0)}',
                          style: const TextStyle(
                            color: _T.brown,
                            fontWeight: FontWeight.w800,
                            fontSize: 13.5,
                          ),
                        ),
                        GestureDetector(
                          onTap: () {
                            ref.read(cartProvider.notifier).addItemFromModel(
                              CartItemModel(
                                productId: product.id,
                                bakerId: product.bakerId,
                                productName: product.name,
                                price: price,
                                imageUrl: product.images.isNotEmpty ? product.images.first : '',
                                surplusId: surplus?.id,
                              ),
                            );
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Added ${product.name} to cart'),
                                behavior: SnackBarBehavior.floating,
                                backgroundColor: _T.ink,
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                duration: const Duration(seconds: 1),
                              ),
                            );
                          },
                          child: Container(
                            padding: const EdgeInsets.all(6),
                            decoration: const BoxDecoration(
                              color: _T.brown,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.add_shopping_cart_rounded, color: Colors.white, size: 14),
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

class _NotificationBell extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadCount = ref.watch(unreadNotificationCountProvider);

    return GestureDetector(
      onTap: () => context.push(AppRoutes.customerNotifications),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: _T.rimLight, width: 1.2),
              boxShadow: _T.shadowSm,
            ),
            child: const Icon(Icons.notifications_outlined, color: _T.ink, size: 20),
          ),
          if (unreadCount > 0)
            Positioned(
              right: 0,
              top: 0,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                child: Text(
                  unreadCount > 9 ? '9+' : unreadCount.toString(),
                  style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PromoBanner extends ConsumerWidget {
  const _PromoBanner();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(allProductsProvider).valueOrNull ?? [];
    final activeDealsMap = ref.watch(activeSurplusByProductProvider);

    final productsWithDeals = products.where((p) => activeDealsMap.containsKey(p.id)).toList();

    if (productsWithDeals.isNotEmpty) {
      // Sort by highest discount percentage
      productsWithDeals.sort((a, b) {
        final sA = activeDealsMap[a.id]!;
        final sB = activeDealsMap[b.id]!;
        final pctA = ((a.price - sA.discountPrice) / a.price);
        final pctB = ((b.price - sB.discountPrice) / b.price);
        return pctB.compareTo(pctA);
      });

      final product = productsWithDeals.first;
      final surplus = activeDealsMap[product.id]!;
      final discountPercentage = ((product.price - surplus.discountPrice) / product.price * 100).round();

      return GestureDetector(
        onTap: () => context.push('${AppRoutes.customerProduct}/${product.id}'),
        child: Container(
          height: 145,
          width: double.infinity,
          decoration: BoxDecoration(
            color: _T.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _T.rimLight, width: 1.2),
            boxShadow: _T.shadowSm,
          ),
          child: Row(
            children: [
              const SizedBox(width: 16),
              Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: _T.rimLight, width: 1),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: product.images.isNotEmpty
                      ? CachedNetworkImage(
                          imageUrl: product.images.first,
                          width: 105,
                          height: 105,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => Container(color: _T.rimLight),
                        )
                      : Container(
                          width: 105,
                          height: 105,
                          color: _T.rimLight,
                          child: const Icon(Icons.cake_outlined, color: _T.inkMid),
                        ),
                ),
              ),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: _T.brown.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        'FEATURED DEAL',
                        style: TextStyle(
                          color: _T.brown,
                          fontSize: 9,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.2,
                        ),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      product.name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: _T.ink,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        const Text(
                          'Save ',
                          style: TextStyle(
                            color: _T.inkMid,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          '$discountPercentage% OFF',
                          style: const TextStyle(
                            color: _T.brown,
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
            ],
          ),
        ),
      );
    }

    // Default Fallback Promo Banner
    return Container(
      height: 145,
      width: double.infinity,
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _T.rimLight, width: 1.2),
        boxShadow: _T.shadowSm,
      ),
      child: Row(
        children: [
          const SizedBox(width: 16),
          Container(
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: _T.rimLight, width: 1),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                'https://images.unsplash.com/photo-1519869325930-281384150729?auto=format&fit=crop&w=400&q=80',
                width: 105,
                height: 105,
                fit: BoxFit.cover,
              ),
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _T.brown.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    'SPECIAL PROMO',
                    style: TextStyle(
                      color: _T.brown,
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.2,
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Strawberry Cake Tart',
                  style: TextStyle(
                    color: _T.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    height: 1.2,
                  ),
                ),
                const SizedBox(height: 6),
                const Row(
                  children: [
                    Text(
                      'Save up to ',
                      style: TextStyle(
                        color: _T.inkMid,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      '50% OFF',
                      style: TextStyle(
                        color: _T.brown,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
        ],
      ),
    );
  }
}

