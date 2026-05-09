import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../providers/store_provider.dart';
import '../../services/notification_service.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../widgets/customer/product_card.dart';

class BakerStorefrontScreen extends ConsumerWidget {
  final String bakerId;
  const BakerStorefrontScreen({super.key, required this.bakerId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bakersAsync = ref.watch(allBakersProvider);
    final productsAsync = ref.watch(allProductsProvider);

    return bakersAsync.when(
      data: (bakers) {
        final baker = bakers.firstWhere((b) => b.uid == bakerId);
        final bakerProducts = productsAsync.valueOrNull?.where((p) => p.bakerId == bakerId).toList() ?? [];

        return Scaffold(
          backgroundColor: const Color(0xFFFDFCF9),
          body: CustomScrollView(
            slivers: [
              // Cover & Bio
              SliverAppBar(
                expandedHeight: 250,
                pinned: true,
                backgroundColor: const Color(0xFFD97706),
                actions: [
                  IconButton(
                    icon: const Icon(Icons.share_outlined, color: Colors.white),
                    onPressed: () => ShareUtil.shareStore(
                      bakerName: baker.bakeryName ?? 'Home Bakery',
                      bakerId: baker.uid,
                    ),
                  ),
                ],
                flexibleSpace: FlexibleSpaceBar(
                  background: Stack(
                    fit: StackFit.expand,
                    children: [
                      if (baker.portfolioImages.isNotEmpty)
                        CachedNetworkImage(
                          imageUrl: baker.portfolioImages.first,
                          fit: BoxFit.cover,
                        )
                      else
                        Container(color: const Color(0xFFFEF3C7)),
                      Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [Colors.black.withOpacity(0.6), Colors.transparent],
                            begin: Alignment.bottomCenter,
                            end: Alignment.topCenter,
                          ),
                        ),
                      ),
                      Positioned(
                        bottom: 20,
                        left: 20,
                        right: 20,
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    baker.bakeryName ?? 'Home Bakery',
                                    style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
                                  ),
                                  const SizedBox(height: 4),
                                  Row(
                                    children: [
                                      const Icon(Icons.star_rounded, color: Colors.amber, size: 18),
                                      const SizedBox(width: 4),
                                      Text(
                                        '${baker.rating.toStringAsFixed(1)} (${baker.totalReviews} reviews)',
                                        style: const TextStyle(color: Colors.white, fontSize: 14),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                            // Notification button removed as per user request

                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // About Section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('About the Baker', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF451A03))),
                      const SizedBox(height: 8),
                      Text(
                        baker.bio ?? 'Passionate baker creating delicious treats for your special moments.',
                        style: const TextStyle(color: Color(0xFF92400E), height: 1.5),
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 8,
                        children: baker.specialties.map((s) => Chip(
                          label: Text(s, style: const TextStyle(fontSize: 11)),
                          backgroundColor: const Color(0xFFFEF3C7),
                          side: BorderSide.none,
                        )).toList(),
                      ),
                      const Divider(height: 40, color: Color(0xFFFEF3C7)),
                      const Text('Our Products', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF451A03))),
                    ],
                  ),
                ),
              ),

              // Products Grid
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
                      product: bakerProducts[i],
                      onTap: () => context.push('${AppRoutes.customerProduct}/${bakerProducts[i].id}'),
                    ),
                    childCount: bakerProducts.length,
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 50)),
            ],
          ),
        );
      },
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(body: Center(child: Text('Error: $e'))),
    );
  }
}
