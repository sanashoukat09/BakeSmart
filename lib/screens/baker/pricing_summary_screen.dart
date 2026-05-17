import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/product_provider.dart';
import '../../providers/pricing_provider.dart';
import '../../models/product_model.dart';

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

class PricingSummaryScreen extends ConsumerWidget {
  const PricingSummaryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final productsAsync = ref.watch(bakerProductsProvider);
    final summary = ref.watch(businessProfitabilityProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        title: const Text(
          'Pricing & Profits', 
          style: TextStyle(fontWeight: FontWeight.w800, color: _T.brown, fontSize: 18),
        ),
        elevation: 0,
      ),
      body: productsAsync.when(
        data: (products) {
          if (products.isEmpty) {
            return const Center(
              child: Text(
                'No products to analyze', 
                style: TextStyle(color: _T.inkMid, fontSize: 14, fontWeight: FontWeight.w600),
              ),
            );
          }

          return SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 40),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Business Summary Card
                _SummaryCard(
                  totalRevenue: summary['totalRevenue'] as double,
                  totalCost: summary['totalCost'] as double,
                  totalProfit: summary['totalProfit'] as double,
                  avgMargin: summary['avgMargin'] as double,
                ),
                const SizedBox(height: 28),
                const Text(
                  'Product Breakdown',
                  style: TextStyle(color: _T.ink, fontSize: 15, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 12),
                ...products.map((p) => _ProductPricingCard(product: p)),
              ],
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final double totalRevenue;
  final double totalCost;
  final double totalProfit;
  final double avgMargin;

  const _SummaryCard({
    required this.totalRevenue,
    required this.totalCost,
    required this.totalProfit,
    required this.avgMargin,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _StatItem(label: 'Total Revenue', value: 'Rs. ${totalRevenue.toStringAsFixed(0)}', color: _T.statusCopper),
              _StatItem(label: 'Avg. Margin', value: '${avgMargin.toStringAsFixed(1)}%', color: _T.statusGreen),
            ],
          ),
          const Divider(color: _T.rimLight, height: 32, thickness: 1.5),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _StatItem(label: 'Total Cost', value: 'Rs. ${totalCost.toStringAsFixed(0)}', color: _T.inkMid),
              _StatItem(label: 'Total Profit', value: 'Rs. ${totalProfit.toStringAsFixed(0)}', color: _T.brown),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatItem({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.w800)),
      ],
    );
  }
}

class _ProductPricingCard extends ConsumerWidget {
  final ProductModel product;
  const _ProductPricingCard({required this.product});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analysis = ref.watch(productCostProvider(product));

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  product.name,
                  style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 14),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: analysis.currentMargin >= product.profitMargin
                      ? _T.statusGreen.withOpacity(0.12)
                      : _T.statusCopper.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '${analysis.currentMargin.toStringAsFixed(1)}% margin',
                  style: TextStyle(
                    color: analysis.currentMargin >= product.profitMargin ? _T.statusGreen : _T.statusCopper,
                    fontSize: 10.5,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _PriceDetail(label: 'Cost', value: 'Rs. ${analysis.baseCost.toStringAsFixed(0)}'),
              _PriceDetail(label: 'Price', value: 'Rs. ${product.price.toStringAsFixed(0)}'),
              _PriceDetail(
                label: 'Suggested',
                value: 'Rs. ${analysis.suggestedPrice.toStringAsFixed(0)}',
                color: _T.brown,
              ),
            ],
          ),
          if (analysis.missingIngredients.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              '⚠️ Missing cost data for ${analysis.missingIngredients.length} ingredients',
              style: const TextStyle(color: _T.statusCopper, fontSize: 11, fontWeight: FontWeight.w700),
            ),
          ],
        ],
      ),
    );
  }
}

class _PriceDetail extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _PriceDetail({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: _T.inkMid, fontSize: 10, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(color: color ?? _T.ink, fontSize: 14, fontWeight: FontWeight.w800)),
      ],
    );
  }
}
