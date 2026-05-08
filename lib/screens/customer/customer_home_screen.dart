import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/store_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/surplus_provider.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';
import '../../widgets/customer/product_card.dart';
import '../../widgets/customer/baker_card.dart';
import '../../widgets/customer/surplus_card.dart';

class CustomerHomeScreen extends ConsumerWidget {
  const CustomerHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(filteredProductsProvider);
    final featuredBakersAsync = ref.watch(allBakersProvider); // Use all for now
    final filter = ref.watch(storeFilterProvider);
    final cartItems = ref.watch(cartProvider);

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9), // Warm off-white
      body: CustomScrollView(
        slivers: [
          // App Bar with Search
          SliverAppBar(
            expandedHeight: 180,
            floating: false,
            pinned: true,
            backgroundColor: const Color(0xFFFDFCF9),
            elevation: 0,
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                padding: const EdgeInsets.fromLTRB(20, 60, 20, 20),
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    colors: [Color(0xFFFEF3C7), Color(0xFFFDFCF9)],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Find your favorite',
                              style: TextStyle(fontSize: 16, color: Color(0xFF92400E)),
                            ),
                            Text(
                              'Bakery Delights',
                              style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFF451A03)),
                            ),
                          ],
                        ),
                        Transform.translate(
                          offset: const Offset(12, 0),
                          child: IconButton(
                            icon: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: const BoxDecoration(
                                  color: Colors.white, shape: BoxShape.circle),
                              child: const Icon(Icons.person,
                                  color: Color(0xFFD97706)),
                            ),
                            onPressed: () => context.push(AppRoutes.customerProfile),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(60),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                child: TextField(
                  onChanged: (v) => ref.read(storeFilterProvider.notifier).state = filter.copyWith(query: v),
                  decoration: InputDecoration(
                    hintText: 'Search cakes, cookies...',
                    prefixIcon: const Icon(Icons.search, color: Color(0xFFD97706)),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(15),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Flash Deals Section
          _FlashDealsSection(),

          // Categories
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 20, 20, 12),
                  child: Text('Categories', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF451A03))),
                ),
                SizedBox(
                  height: 45,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.only(left: 20),
                    itemCount: AppConstants.productCategories.length + 1,
                    itemBuilder: (context, i) {
                      final isAll = i == 0;
                      final cat = isAll ? null : AppConstants.productCategories[i - 1];
                      final isSelected = filter.category == cat;

                      return GestureDetector(
                        onTap: () => ref.read(storeFilterProvider.notifier).state = filter.copyWith(category: cat),
                        child: Container(
                          margin: const EdgeInsets.only(right: 10),
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          decoration: BoxDecoration(
                            color: isSelected ? const Color(0xFFD97706) : Colors.white,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: isSelected ? Colors.transparent : const Color(0xFFFEF3C7)),
                          ),
                          child: Center(
                            child: Text(
                              isAll ? 'All' : cat!,
                              style: TextStyle(
                                color: isSelected ? Colors.white : const Color(0xFF92400E),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),

          // Featured Bakers
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 24, 20, 12),
                  child: Text('Featured Bakers', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF451A03))),
                ),
                SizedBox(
                  height: 190,
                  child: featuredBakersAsync.when(
                    data: (bakers) => ListView.builder(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.only(left: 20),
                      itemCount: bakers.length,
                      itemBuilder: (context, i) => BakerCard(
                        baker: bakers[i],
                        onTap: () => context.push('${AppRoutes.customerStore}/${bakers[i].uid}'),
                      ),
                    ),
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (_, __) => const SizedBox.shrink(),
                  ),
                ),
              ],
            ),
          ),

          // Product Grid
          const SliverToBoxAdapter(
            child: Padding(
              padding: EdgeInsets.fromLTRB(20, 24, 20, 12),
              child: Text('Fresh from the Oven', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF451A03))),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 0.72,
                mainAxisSpacing: 16,
                crossAxisSpacing: 16,
              ),
              delegate: SliverChildBuilderDelegate(
                (context, i) => ProductCard(
                  product: products[i],
                  onTap: () => context.push('${AppRoutes.customerProduct}/${products[i].id}'),
                ),
                childCount: products.length,
              ),
            ),
          ),
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
        ],
      ),
      floatingActionButton: cartItems.isNotEmpty
          ? FloatingActionButton.extended(
              onPressed: () => context.push(AppRoutes.customerCart),
              backgroundColor: const Color(0xFFD97706),
              icon: const Icon(Icons.shopping_cart, color: Colors.white),
              label: Text('${ref.read(cartProvider.notifier).itemCount} items', style: const TextStyle(color: Colors.white)),
            )
          : null,
    );
  }
}

class _FlashDealsSection extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final surplusAsync = ref.watch(allSurplusProvider);

    return surplusAsync.when(
      data: (items) {
        if (items.isEmpty) return const SliverToBoxAdapter(child: SizedBox.shrink());

        return SliverToBoxAdapter(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 32, 20, 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Flash Deals 🔥', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFFDC2626))),
                    TextButton(
                      onPressed: () => context.push(AppRoutes.customerSurplus),
                      child: const Text('View All', style: TextStyle(color: Color(0xFFD97706))),
                    ),
                  ],
                ),
              ),
              SizedBox(
                height: 220,
                child: ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  scrollDirection: Axis.horizontal,
                  itemCount: items.length,
                  itemBuilder: (context, i) => Container(
                    width: 180,
                    margin: const EdgeInsets.symmetric(horizontal: 8),
                    child: SurplusCard(
                      item: items[i],
                      onTap: () => context.push('${AppRoutes.customerProduct}/${items[i].productId}'),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
      loading: () => const SliverToBoxAdapter(child: SizedBox.shrink()),
      error: (_, __) => const SliverToBoxAdapter(child: SizedBox.shrink()),
    );
  }
}
