import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/product_provider.dart';
import '../../providers/pricing_provider.dart';
import '../../models/product_model.dart';
import '../../core/theme/baker_theme.dart';


class PricingSummaryScreen extends ConsumerWidget {
  const PricingSummaryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final productsAsync = ref.watch(bakerProductsProvider);
    final summary = ref.watch(businessProfitabilityProvider);

    return Scaffold(
      backgroundColor: BakerTheme.background,

      appBar: AppBar(
        backgroundColor: BakerTheme.background,
        title: const Text('Pricing & Profits', style: TextStyle(fontWeight: FontWeight.bold, color: BakerTheme.textPrimary)),
        elevation: 0,

      ),
      body: productsAsync.when(
        data: (products) {
          if (products.isEmpty) {
            return Center(child: Text('No products to analyze', style: TextStyle(color: BakerTheme.textSecondary)));

          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
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
                const SizedBox(height: 24),
                const Text(
                  'Product Breakdown',
                  style: TextStyle(color: BakerTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.bold),

                ),
                const SizedBox(height: 12),
                ...products.map((p) => _ProductPricingCard(product: p)),
              ],
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFFF59E0B))),
        error: (e, _) => Center(child: Text('Error: $e')),
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
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: BakerTheme.divider),

      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _StatItem(label: 'Total Revenue', value: 'Rs. ${totalRevenue.toStringAsFixed(0)}', color: BakerTheme.textPrimary),
              _StatItem(label: 'Avg. Margin', value: '${avgMargin.toStringAsFixed(1)}%', color: Colors.green),

            ],
          ),
          const Divider(color: BakerTheme.divider, height: 32),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _StatItem(label: 'Total Cost', value: 'Rs. ${totalCost.toStringAsFixed(0)}', color: BakerTheme.textSecondary),
              _StatItem(label: 'Total Profit', value: 'Rs. ${totalProfit.toStringAsFixed(0)}', color: BakerTheme.secondary),

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
        Text(label, style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12)),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
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
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: BakerTheme.divider),

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
                  style: const TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold),

                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: analysis.currentMargin >= product.profitMargin
                      ? Colors.green.withOpacity(0.1)
                      : Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '${analysis.currentMargin.toStringAsFixed(1)}% margin',
                  style: TextStyle(
                    color: analysis.currentMargin >= product.profitMargin ? Colors.green : Colors.orange,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _PriceDetail(label: 'Cost', value: 'Rs. ${analysis.baseCost.toStringAsFixed(0)}'),
              _PriceDetail(label: 'Price', value: 'Rs. ${product.price.toStringAsFixed(0)}'),
              _PriceDetail(
                label: 'Suggested',
                value: 'Rs. ${analysis.suggestedPrice.toStringAsFixed(0)}',
                color: BakerTheme.secondary,
              ),

            ],
          ),
          if (analysis.missingIngredients.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              '⚠️ Missing cost data for ${analysis.missingIngredients.length} ingredients',
              style: const TextStyle(color: Colors.orange, fontSize: 10),
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
        Text(label, style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 10)),
        Text(value, style: TextStyle(color: color ?? BakerTheme.textPrimary, fontSize: 14, fontWeight: FontWeight.w600)),
      ],
    );

  }
}
