import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/surplus_provider.dart';
import '../../widgets/customer/surplus_card.dart';
import '../../core/router/app_router.dart';

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

class SurplusDealsScreen extends ConsumerWidget {
  const SurplusDealsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final surplusAsync = ref.watch(allSurplusProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _T.ink),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'Flash Deals',
          style: TextStyle(
            color: _T.ink,
            fontWeight: FontWeight.w800,
            fontSize: 19,
          ),
        ),
      ),
      body: surplusAsync.when(
        data: (items) {
          if (items.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: _T.statusPink.withOpacity(0.06),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.flash_off_rounded,
                      size: 72,
                      color: _T.statusPink,
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'No flash deals available right now.',
                    style: TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Check back later for fresh surplus items!',
                    style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            );
          }

          return GridView.builder(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.all(20),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              childAspectRatio: 0.68,
              mainAxisSpacing: 16,
              crossAxisSpacing: 16,
            ),
            itemCount: items.length,
            itemBuilder: (context, i) => SurplusCard(
              item: items[i],
              onTap: () {
                context.push('${AppRoutes.customerProduct}/${items[i].productId}');
              },
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.brown)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusRed))),
      ),
    );
  }
}
