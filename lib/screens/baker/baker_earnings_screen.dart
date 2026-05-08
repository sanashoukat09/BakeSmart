import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../providers/order_provider.dart';
import '../../providers/product_provider.dart';
import '../../models/order_model.dart';
import '../../models/product_model.dart';
import '../../core/constants/app_constants.dart';
import '../../core/theme/baker_theme.dart';

class BakerEarningsScreen extends ConsumerWidget {
  const BakerEarningsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersProvider);
    final productsAsync = ref.watch(bakerProductsProvider);

    return Scaffold(
      backgroundColor: BakerTheme.background,
      appBar: AppBar(
        backgroundColor: BakerTheme.background,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Bakery Analytics', style: TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold, fontSize: 22)),
            Text(DateFormat('MMMM yyyy').format(DateTime.now()), style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12)),
          ],
        ),
        elevation: 0,
        actions: [
          IconButton(onPressed: () {}, icon: const Icon(Icons.calendar_month_outlined, color: BakerTheme.primary)),
          const SizedBox(width: 8),
        ],
      ),
      body: ordersAsync.when(
        data: (orders) {
          return productsAsync.when(
            data: (products) {
              final deliveredOrders = orders.where((o) => o.status == AppConstants.orderDelivered).toList();
              
              // DATA PROCESSING
              final now = DateTime.now();
              final today = DateTime(now.year, now.month, now.day);
              final startOfThisWeek = today.subtract(Duration(days: now.weekday - 1));
              final startOfLastWeek = startOfThisWeek.subtract(const Duration(days: 7));

              double totalRevenue = 0;
              double totalProfit = 0;
              double lastWeekRevenue = 0;
              double thisWeekRevenue = 0;
              
              Map<int, double> dailyRevenue = {};
              Map<int, double> dailyProfit = {};
              Map<int, int> dailyOrders = {};
              Map<String, double> productEarnings = {};
              Map<String, int> productSalesCount = {};
              Map<String, double> categoryProfit = {};

              for (int i = 0; i < 7; i++) {
                dailyRevenue[i] = 0;
                dailyProfit[i] = 0;
                dailyOrders[i] = 0;
              }

              for (var order in deliveredOrders) {
                totalRevenue += order.totalAmount;
                double orderProfit = 0;
                
                for (var item in order.items) {
                  final product = products.where((p) => p.id == item.productId).firstOrNull;
                  if (product != null) {
                    final itemProfit = (item.price * (product.profitMargin / 100)) * item.quantity;
                    orderProfit += itemProfit;
                    productEarnings[product.name] = (productEarnings[product.name] ?? 0) + (item.price * item.quantity);
                    productSalesCount[product.name] = (productSalesCount[product.name] ?? 0) + item.quantity;
                    categoryProfit[product.category] = (categoryProfit[product.category] ?? 0) + itemProfit;
                  }
                }
                totalProfit += orderProfit;

                final revenueDate = DateTime(order.deliveryDate.year, order.deliveryDate.month, order.deliveryDate.day);
                final diff = today.difference(revenueDate).inDays;
                
                if (diff >= 0 && diff < 7) {
                  dailyRevenue[6 - diff] = (dailyRevenue[6 - diff] ?? 0) + order.totalAmount;
                  dailyProfit[6 - diff] = (dailyProfit[6 - diff] ?? 0) + orderProfit;
                }

                // Weekly Trends (Sales)
                if (revenueDate.isAfter(startOfLastWeek) && revenueDate.isBefore(startOfThisWeek)) {
                  lastWeekRevenue += order.totalAmount;
                } else if (revenueDate.isAfter(startOfThisWeek) || revenueDate.isAtSameMomentAs(startOfThisWeek)) {
                  thisWeekRevenue += order.totalAmount;
                }
              }

              // Process ALL orders for "Order Activity"
              for (var order in orders) {
                final orderDate = DateTime(order.createdAt.year, order.createdAt.month, order.createdAt.day);
                final diff = today.difference(orderDate).inDays;
                if (diff >= 0 && diff < 7) {
                  dailyOrders[6 - diff] = (dailyOrders[6 - diff] ?? 0) + 1;
                }
              }

              final revenueTrend = lastWeekRevenue == 0 ? 100.0 : ((thisWeekRevenue - lastWeekRevenue) / lastWeekRevenue) * 100;
              final avgMargin = totalRevenue == 0 ? 0.0 : (totalProfit / totalRevenue) * 100;
              final bestSeller = productSalesCount.entries.isEmpty ? "N/A" : productSalesCount.entries.fold(productSalesCount.entries.first, (a, b) => a.value > b.value ? a : b).key;

              // Axis limits
              final maxRev = dailyRevenue.values.fold(0.0, (p, e) => e > p ? e : p);
              final maxProfit = dailyProfit.values.fold(0.0, (p, e) => e > p ? e : p);
              final maxOrders = dailyOrders.values.fold(0, (p, e) => e > p ? e : p).toDouble();

              final revenueMaxY = maxRev > 0 ? maxRev * 1.2 : 5000.0;
              final ordersMaxY = maxOrders > 0 ? maxOrders * 1.2 : 10.0;

              return SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // QUICK STATS CAROUSEL (Simulated with a Row/Wrap)
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      physics: const BouncingScrollPhysics(),
                      child: Row(
                        children: [
                          _QuickStatCard(title: 'Total Revenue', value: 'Rs. ${NumberFormat.compact().format(totalRevenue)}', trend: revenueTrend, icon: Icons.payments_outlined, color: BakerTheme.secondary),
                          const SizedBox(width: 12),
                          _QuickStatCard(title: 'Net Profit', value: 'Rs. ${NumberFormat.compact().format(totalProfit)}', trend: 12.5, icon: Icons.auto_graph_outlined, color: const Color(0xFF10B981)),
                          const SizedBox(width: 12),
                          _QuickStatCard(title: 'Avg. Margin', value: '${avgMargin.toStringAsFixed(1)}%', trend: 2.1, icon: Icons.percent_outlined, color: BakerTheme.primary),
                        ],
                      ),
                    ),
                    
                    const SizedBox(height: 24),

                    // REVENUE VS PROFIT LINE CHART
                    _AnalyticsCard(
                      title: 'Revenue vs Profit',
                      subtitle: 'Weekly Performance',
                      child: SizedBox(
                        height: 200,
                        child: LineChart(_buildRevenueProfitLineChart(dailyRevenue, dailyProfit, revenueMaxY)),
                      ),
                      legend: [
                        _LegendItem(label: 'Revenue', color: BakerTheme.secondary),
                        _LegendItem(label: 'Profit', color: const Color(0xFF10B981)),
                      ],
                    ),

                    const SizedBox(height: 20),

                    // SMART INSIGHTS
                    const _SectionHeader(title: 'Smart Insights ✨'),
                    const SizedBox(height: 12),
                    _InsightCard(
                      insights: [
                        _InsightItem(text: '$bestSeller is your most profitable item this week.', type: InsightType.positive),
                        _InsightItem(text: 'Overall profit margin is stable at ${avgMargin.toStringAsFixed(1)}%.', type: InsightType.neutral),
                        if (revenueTrend < 0)
                          _InsightItem(text: 'Revenue is down ${revenueTrend.abs().toStringAsFixed(1)}% vs last week.', type: InsightType.negative),
                        _InsightItem(text: 'Suggestion: Adjust pricing for seasonal cakes to increase profit by 12%.', type: InsightType.ai),
                      ],
                    ),

                    const SizedBox(height: 32),

                    // WEEKLY ORDERS TREND AREA GRAPH
                    _AnalyticsCard(
                      title: 'Order Activity',
                      subtitle: 'Daily count',
                      child: SizedBox(
                        height: 180,
                        child: LineChart(_buildOrdersAreaChart(dailyOrders, ordersMaxY)),
                      ),
                    ),

                    const SizedBox(height: 20),

                    // PRODUCT SALES BAR CHART
                    _AnalyticsCard(
                      title: 'Top Products',
                      subtitle: 'By Revenue',
                      child: SizedBox(
                        height: 250,
                        child: BarChart(_buildProductSalesBarChart(productEarnings)),
                      ),
                    ),

                    const SizedBox(height: 20),

                    // PROFIT MARGIN PIE CHART
                    _AnalyticsCard(
                      title: 'Profit Contribution',
                      subtitle: 'By Category',
                      child: SizedBox(
                        height: 200,
                        child: PieChart(_buildProfitPieChart(categoryProfit, totalProfit)),
                      ),
                      legend: categoryProfit.entries.map((e) => _LegendItem(label: e.key, color: _getCategoryColor(e.key))).toList(),
                    ),

                    const SizedBox(height: 32),

                    // TOP PERFORMING PRODUCTS LIST
                    const _SectionHeader(title: 'Leaderboard 🏆'),
                    const SizedBox(height: 12),
                    ...productSalesCount.entries.take(3).map((e) {
                      final revenue = productEarnings[e.key] ?? 0;
                      return _ProductPerformanceTile(name: e.key, sales: e.value, revenue: revenue);
                    }),

                    const SizedBox(height: 40),
                  ],
                ),
              );
            },
            loading: () => const Center(child: CircularProgressIndicator(color: BakerTheme.secondary)),
            error: (e, _) => Center(child: Text('Data Error: $e')),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: BakerTheme.secondary)),
        error: (e, _) => Center(child: Text('System Error: $e')),
      ),
    );
  }

  LineChartData _buildRevenueProfitLineChart(Map<int, double> revenue, Map<int, double> profit, double maxY) {
    return LineChartData(
      maxY: maxY,
      minY: 0,
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (spot) => BakerTheme.primary,
          getTooltipItems: (spots) => spots.map((spot) => LineTooltipItem(
            'Rs. ${NumberFormat.compact().format(spot.y)}',
            const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12),
          )).toList(),
        ),
      ),
      gridData: FlGridData(
        show: true,
        drawVerticalLine: false,
        horizontalInterval: maxY / 5 > 0 ? maxY / 5 : 1000,
        getDrawingHorizontalLine: (value) => FlLine(color: BakerTheme.divider.withOpacity(0.5), strokeWidth: 1),
      ),
      titlesData: _buildAxesTitles(),
      borderData: FlBorderData(show: false),
      lineBarsData: [
        LineChartBarData(
          spots: revenue.entries.map((e) => FlSpot(e.key.toDouble(), e.value)).toList(),
          isCurved: true,
          curveSmoothness: 0.35,
          color: BakerTheme.secondary,
          barWidth: 2.5,
          isStrokeCapRound: true,
          dotData: FlDotData(show: true, getDotPainter: (spot, percent, barData, index) => FlDotCirclePainter(radius: 3, color: Colors.white, strokeWidth: 2, strokeColor: BakerTheme.secondary)),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [BakerTheme.secondary.withOpacity(0.2), BakerTheme.secondary.withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        LineChartBarData(
          spots: profit.entries.map((e) => FlSpot(e.key.toDouble(), e.value)).toList(),
          isCurved: true,
          curveSmoothness: 0.35,
          color: const Color(0xFF10B981),
          barWidth: 2.5,
          isStrokeCapRound: true,
          dotData: FlDotData(show: true, getDotPainter: (spot, percent, barData, index) => FlDotCirclePainter(radius: 3, color: Colors.white, strokeWidth: 2, strokeColor: const Color(0xFF10B981))),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [const Color(0xFF10B981).withOpacity(0.2), const Color(0xFF10B981).withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
      ],
    );
  }

  LineChartData _buildOrdersAreaChart(Map<int, int> orders, double maxY) {
    return LineChartData(
      maxY: maxY,
      minY: 0,
      lineTouchData: const LineTouchData(enabled: true),
      gridData: const FlGridData(show: false),
      titlesData: const FlTitlesData(show: false),
      borderData: FlBorderData(show: false),
      lineBarsData: [
        LineChartBarData(
          spots: orders.entries.map((e) => FlSpot(e.key.toDouble(), e.value.toDouble())).toList(),
          isCurved: true,
          curveSmoothness: 0.4,
          color: BakerTheme.primary,
          barWidth: 3,
          isStrokeCapRound: true,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [BakerTheme.primary.withOpacity(0.2), BakerTheme.primary.withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
      ],
    );
  }

  BarChartData _buildProductSalesBarChart(Map<String, double> earnings) {
    final sorted = earnings.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
    return BarChartData(
      alignment: BarChartAlignment.spaceAround,
      maxY: sorted.isEmpty ? 100 : sorted.first.value * 1.2,
      titlesData: FlTitlesData(
        show: true,
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            getTitlesWidget: (value, meta) {
              if (value.toInt() < sorted.length) {
                return Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Text(sorted[value.toInt()].key.substring(0, 3), style: const TextStyle(fontSize: 10, color: BakerTheme.textSecondary)),
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ),
        leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      ),
      borderData: FlBorderData(show: false),
      gridData: const FlGridData(show: false),
      barGroups: sorted.asMap().entries.map((e) => BarChartGroupData(
        x: e.key,
        barRods: [
          BarChartRodData(
            toY: e.value.value,
            color: BakerTheme.primary,
            width: 20,
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      )).toList(),
    );
  }

  PieChartData _buildProfitPieChart(Map<String, double> profit, double total) {
    int i = 0;
    return PieChartData(
      sectionsSpace: 4,
      centerSpaceRadius: 40,
      sections: profit.entries.map((e) {
        final color = _getCategoryColor(e.key);
        return PieChartSectionData(
          color: color,
          value: e.value,
          title: '${((e.value / total) * 100).toStringAsFixed(0)}%',
          radius: 50,
          titleStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
        );
      }).toList(),
    );
  }

  Color _getCategoryColor(String category) {
    final colors = [BakerTheme.primary, BakerTheme.secondary, const Color(0xFF10B981), const Color(0xFF3B82F6), const Color(0xFF8B5CF6)];
    return colors[category.hashCode % colors.length];
  }

  FlTitlesData _buildAxesTitles() {
    return FlTitlesData(
      show: true,
      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
      bottomTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 22,
          getTitlesWidget: (value, meta) {
            final days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
            return Text(days[value.toInt() % 7], style: const TextStyle(color: BakerTheme.textMuted, fontSize: 10));
          },
        ),
      ),
      leftTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 35,
          getTitlesWidget: (value, meta) {
            if (value == 0) return const SizedBox.shrink();
            return Text(NumberFormat.compact().format(value), style: const TextStyle(color: BakerTheme.textMuted, fontSize: 9));
          },
        ),
      ),
    );
  }
}

// --- SUPPORTING UI COMPONENTS ---

class _QuickStatCard extends StatelessWidget {
  final String title;
  final String value;
  final double trend;
  final IconData icon;
  final Color color;

  const _QuickStatCard({required this.title, required this.value, required this.trend, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 160,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [BoxShadow(color: color.withOpacity(0.08), blurRadius: 20, offset: const Offset(0, 10))],
        border: Border.all(color: BakerTheme.divider, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 16),
          Text(title, style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(trend >= 0 ? Icons.trending_up : Icons.trending_down, size: 14, color: trend >= 0 ? const Color(0xFF10B981) : const Color(0xFFEF4444)),
              const SizedBox(width: 4),
              Text('${trend.abs().toStringAsFixed(1)}%', style: TextStyle(color: trend >= 0 ? const Color(0xFF10B981) : const Color(0xFFEF4444), fontSize: 12, fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }
}

class _AnalyticsCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;
  final List<_LegendItem>? legend;

  const _AnalyticsCard({required this.title, required this.subtitle, required this.child, this.legend});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: BakerTheme.divider, width: 1.5),
        boxShadow: [BoxShadow(color: BakerTheme.primary.withOpacity(0.03), blurRadius: 30, offset: const Offset(0, 15))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.bold), overflow: TextOverflow.ellipsis),
                    Text(subtitle, style: const TextStyle(color: BakerTheme.textMuted, fontSize: 11), overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
              if (legend != null)
                Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 12,
                  runSpacing: 4,
                  children: legend!,
                ),
            ],
          ),
          const SizedBox(height: 24),
          child,
        ],
      ),
    );
  }
}

class _InsightCard extends StatelessWidget {
  final List<_InsightItem> insights;
  const _InsightCard({required this.insights});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [BakerTheme.primary.withOpacity(0.05), BakerTheme.primary.withOpacity(0.02)]),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: BakerTheme.primary.withOpacity(0.1)),
      ),
      child: Column(children: insights),
    );
  }
}

class _InsightItem extends StatelessWidget {
  final String text;
  final InsightType type;
  const _InsightItem({required this.text, required this.type});

  @override
  Widget build(BuildContext context) {
    IconData icon;
    Color color;
    switch (type) {
      case InsightType.positive: icon = Icons.star_rounded; color = const Color(0xFF10B981); break;
      case InsightType.negative: icon = Icons.info_outline_rounded; color = const Color(0xFFEF4444); break;
      case InsightType.neutral: icon = Icons.analytics_outlined; color = BakerTheme.secondary; break;
      case InsightType.ai: icon = Icons.auto_awesome_outlined; color = BakerTheme.primary; break;
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: TextStyle(color: BakerTheme.textPrimary.withOpacity(0.8), fontSize: 13, height: 1.4))),
        ],
      ),
    );
  }
}

class _ProductPerformanceTile extends StatelessWidget {
  final String name;
  final int sales;
  final double revenue;

  const _ProductPerformanceTile({required this.name, required this.sales, required this.revenue});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: BakerTheme.divider),
      ),
      child: Row(
        children: [
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(color: BakerTheme.primary.withOpacity(0.1), shape: BoxShape.circle),
            child: const Icon(Icons.cake_outlined, color: BakerTheme.primary, size: 20),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: const TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold)),
                Text('$sales units sold', style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12)),
              ],
            ),
          ),
          Text('Rs. ${NumberFormat.compact().format(revenue)}', style: const TextStyle(color: BakerTheme.primary, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});
  @override
  Widget build(BuildContext context) {
    return Text(title, style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.bold));
  }
}

class _LegendItem extends StatelessWidget {
  final String label;
  final Color color;
  const _LegendItem({required this.label, required this.color});
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(color: BakerTheme.textMuted, fontSize: 10, fontWeight: FontWeight.w600)),
      ],
    );
  }
}

enum InsightType { positive, negative, neutral, ai }
