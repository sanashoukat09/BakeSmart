import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/surplus_provider.dart';
import '../../widgets/customer/surplus_card.dart';
import '../../core/router/app_router.dart';

class SurplusDealsScreen extends ConsumerWidget {
  const SurplusDealsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final surplusAsync = ref.watch(allSurplusProvider);

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      appBar: AppBar(
        backgroundColor: const Color(0xFFDC2626),
        title: const Text('Flash Deals', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        iconTheme: const IconThemeData(color: Colors.white),
        elevation: 0,
      ),
      body: surplusAsync.when(
        data: (items) {
          if (items.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.flash_off_rounded, size: 80, color: Color(0xFFFEF3C7)),
                  const SizedBox(height: 16),
                  const Text('No flash deals available right now.', style: TextStyle(color: Colors.grey)),
                  const SizedBox(height: 8),
                  const Text('Check back later for fresh surplus items!', style: TextStyle(color: Colors.grey, fontSize: 12)),
                ],
              ),
            );
          }

          return GridView.builder(
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
        loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFFDC2626))),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}
