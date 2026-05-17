import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../providers/store_provider.dart';
import '../../services/notification_service.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../widgets/customer/product_card.dart';

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
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

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
          backgroundColor: _T.canvas,
          body: CustomScrollView(
            physics: const BouncingScrollPhysics(),
            slivers: [
              // Cover & Bio Header
              SliverAppBar(
                expandedHeight: 250,
                pinned: true,
                backgroundColor: _T.brown,
                leading: IconButton(
                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                  onPressed: () => context.pop(),
                ),
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
                        Container(color: const Color(0xFFFFECE0)), // Soft peach fallback
                      Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [Colors.black.withOpacity(0.65), Colors.transparent],
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
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 22,
                                      fontWeight: FontWeight.w900,
                                      letterSpacing: -0.3,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Row(
                                    children: [
                                      const Icon(Icons.star_rounded, color: Colors.amber, size: 18),
                                      const SizedBox(width: 4),
                                      Text(
                                        '${baker.rating.toStringAsFixed(1)} (${baker.totalReviews} review${baker.totalReviews != 1 ? "s" : ""})',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 13.5,
                                          fontWeight: FontWeight.w800,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
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
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'About the Baker', 
                        style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: _T.ink),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        baker.bio ?? 'Passionate baker creating delicious treats for your special moments.',
                        style: const TextStyle(
                          color: _T.inkMid,
                          height: 1.5,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: baker.specialties.map((s) => Chip(
                          label: Text(
                            s, 
                            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: _T.brown),
                          ),
                          backgroundColor: const Color(0xFFFFECE0),
                          side: BorderSide.none,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        )).toList(),
                      ),
                      const Divider(height: 48, color: _T.rimLight, thickness: 1.5),
                      const Text(
                        'Our Products', 
                        style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: _T.ink),
                      ),
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
      loading: () => const Scaffold(
        backgroundColor: _T.canvas,
        body: Center(child: CircularProgressIndicator(color: _T.brown)),
      ),
      error: (e, _) => Scaffold(
        backgroundColor: _T.canvas,
        body: Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusRed))),
      ),
    );
  }
}
