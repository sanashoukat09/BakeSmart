import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../providers/order_provider.dart';
import '../../providers/product_provider.dart';
import '../../providers/auth_provider.dart';
import '../../models/order_model.dart';
import '../../models/product_model.dart';
import '../../models/review_model.dart';
import '../../core/constants/app_constants.dart';
import '../../widgets/baker/baker_bottom_nav.dart';

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

enum AnalyticsRange { week, month }

class BakerEarningsScreen extends ConsumerStatefulWidget {
  const BakerEarningsScreen({super.key});

  @override
  ConsumerState<BakerEarningsScreen> createState() =>
      _BakerEarningsScreenState();
}

class _BakerEarningsScreenState extends ConsumerState<BakerEarningsScreen> {
  AnalyticsRange _range = AnalyticsRange.week;

  @override
  Widget build(BuildContext context) {
    final ordersAsync = ref.watch(bakerOrdersProvider);
    final productsAsync = ref.watch(bakerProductsProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      bottomNavigationBar: const BakerBottomNav(currentIndex: 3),
      appBar: AppBar(
        backgroundColor: _T.canvas,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Bakery Analytics', 
              style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
            ),
            const SizedBox(height: 2),
            Text(
              _range == AnalyticsRange.week ? 'Weekly report' : DateFormat('MMMM yyyy').format(DateTime.now()), 
              style: const TextStyle(color: _T.inkMid, fontSize: 11, fontWeight: FontWeight.w600),
            ),
          ],
        ),
        elevation: 0,
        actions: [
          _DateRangeSelector(
            currentRange: _range,
            onChanged: (value) => setState(() => _range = value),
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: ordersAsync.when(
        data: (orders) {
          return productsAsync.when(
            data: (products) {
              final now = DateTime.now();
              final today = DateTime(now.year, now.month, now.day);
              final periodStart = _range == AnalyticsRange.week
                  ? today.subtract(Duration(days: now.weekday - 1))
                  : DateTime(now.year, now.month, 1);
              final previousPeriodStart = _range == AnalyticsRange.week
                  ? periodStart.subtract(const Duration(days: 7))
                  : DateTime(now.year, now.month - 1, 1);
              final previousPeriodEnd = periodStart;
              final bucketCount = _range == AnalyticsRange.week ? 7 : 5;

              final deliveredOrders = orders.where((order) {
                if (order.status != AppConstants.orderDelivered) return false;
                return !order.deliveryDate.isBefore(periodStart);
              }).toList();

              // DATA PROCESSING
              double totalRevenue = 0;
              double totalProfit = 0;
              double previousRevenue = 0;
              double previousProfit = 0;

              Map<int, double> dailyRevenue = {};
              Map<int, double> dailyProfit = {};
              // FE-1: received/completed/rejected counts per bucket
              final Map<int, int> dailyOrdersReceived = {};
              final Map<int, int> dailyOrdersCompleted = {};
              final Map<int, int> dailyOrdersRejected = {};
              // legacy total activity
              Map<int, int> dailyOrders = {};
              Map<String, double> productEarnings = {};
              Map<String, int> productSalesCount = {};
              Map<String, double> categoryProfit = {};

              for (int i = 0; i < bucketCount; i++) {
                dailyRevenue[i] = 0;
                dailyProfit[i] = 0;
                dailyOrders[i] = 0;

                dailyOrdersReceived[i] = 0;
                dailyOrdersCompleted[i] = 0;
                dailyOrdersRejected[i] = 0;
              }

              for (var order in deliveredOrders) {
                totalRevenue += order.totalAmount;
                double orderProfit = _estimateOrderProfit(order, products);
                
                for (var item in order.items) {
                  final productMatches =
                      products.where((p) => p.id == item.productId);
                  final product =
                      productMatches.isEmpty ? null : productMatches.first;
                  if (product != null) {
                    productEarnings[product.name] = (productEarnings[product.name] ?? 0) + (item.price * item.quantity);
                    productSalesCount[product.name] = (productSalesCount[product.name] ?? 0) + item.quantity;
                    final itemProfit = _estimateItemProfit(item, product);
                    categoryProfit[product.category] = (categoryProfit[product.category] ?? 0) + itemProfit;
                  }
                }
                totalProfit += orderProfit;

                final revenueDate = DateTime(order.deliveryDate.year, order.deliveryDate.month, order.deliveryDate.day);
                final bucket = _bucketIndex(revenueDate, periodStart, bucketCount);
                if (bucket != null) {
                  dailyRevenue[bucket] = (dailyRevenue[bucket] ?? 0) + order.totalAmount;
                  dailyProfit[bucket] = (dailyProfit[bucket] ?? 0) + orderProfit;
                }
              }

              for (final order in orders.where((o) => o.status == AppConstants.orderDelivered)) {
                final date = DateTime(order.deliveryDate.year, order.deliveryDate.month, order.deliveryDate.day);
                if (!date.isBefore(previousPeriodStart) && date.isBefore(previousPeriodEnd)) {
                  previousRevenue += order.totalAmount;
                  previousProfit += _estimateOrderProfit(order, products);
                }
              }

              // Process ALL orders for "Order Activity"
              for (var order in orders) {
                final orderDate = DateTime(order.createdAt.year, order.createdAt.month, order.createdAt.day);
                if (!orderDate.isBefore(periodStart)) {
                  final bucket = _bucketIndex(orderDate, periodStart, bucketCount);
                  if (bucket != null) {
                    dailyOrders[bucket] = (dailyOrders[bucket] ?? 0) + 1;

                    final isRejected = order.status == AppConstants.orderRejected;
                    final isCompleted = order.status == AppConstants.orderDelivered;
                    final isReceived = !isRejected && !isCompleted;

                    if (isRejected) {
                      dailyOrdersRejected[bucket] = (dailyOrdersRejected[bucket] ?? 0) + 1;
                    } else if (isCompleted) {
                      dailyOrdersCompleted[bucket] = (dailyOrdersCompleted[bucket] ?? 0) + 1;
                    } else if (isReceived) {
                      dailyOrdersReceived[bucket] = (dailyOrdersReceived[bucket] ?? 0) + 1;
                    }
                  }
                }
              }

              final revenueTrend = previousRevenue == 0
                  ? (totalRevenue > 0 ? 100.0 : 0.0)
                  : ((totalRevenue - previousRevenue) / previousRevenue) * 100;
              final profitTrend = previousProfit == 0
                  ? (totalProfit > 0 ? 100.0 : 0.0)
                  : ((totalProfit - previousProfit) / previousProfit) * 100;
              final avgMargin = totalRevenue == 0 ? 0.0 : (totalProfit / totalRevenue) * 100;
              final bestSeller = productSalesCount.entries.isEmpty ? "N/A" : productSalesCount.entries.fold(productSalesCount.entries.first, (a, b) => a.value > b.value ? a : b).key;

              // FE-3: Peak day + peak time (from order.createdAt within selected range)
              final Map<int, int> peakHourCounts = <int, int>{};
              final Map<int, int> peakWeekdayCounts = <int, int>{}; // 1..7 (Mon..Sun) using Dart weekday (Mon=1)
              for (int i = 0; i < 24; i++) {
                peakHourCounts[i] = 0;
              }
              // Dart weekday: 1 Mon .. 7 Sun
              for (int wd = 1; wd <= 7; wd++) {
                peakWeekdayCounts[wd] = 0;
              }

              for (final order in orders) {
                final created = order.createdAt;
                if (created.isBefore(periodStart)) continue;
                final bucket = _bucketIndex(DateTime(created.year, created.month, created.day), periodStart, bucketCount);
                if (bucket == null) continue;

                peakHourCounts[created.hour] = (peakHourCounts[created.hour] ?? 0) + 1;
                peakWeekdayCounts[created.weekday] = (peakWeekdayCounts[created.weekday] ?? 0) + 1;
              }

              final peakHour = peakHourCounts.entries.isEmpty
                  ? null
                  : peakHourCounts.entries.reduce((a, b) => a.value >= b.value ? a : b).key;

              final peakWeekdayNumber = peakWeekdayCounts.entries.isEmpty
                  ? null
                  : peakWeekdayCounts.entries.reduce((a, b) => a.value >= b.value ? a : b).key;

              final peakWeekdayLabel = peakWeekdayNumber == null
                  ? 'N/A'
                  : const <int, String>{
                      1: 'Mon',
                      2: 'Tue',
                      3: 'Wed',
                      4: 'Thu',
                      5: 'Fri',
                      6: 'Sat',
                      7: 'Sun',
                    }[peakWeekdayNumber] ??
                      'N/A';

              final peakTimeLabel = peakHour == null
                  ? 'N/A'
                  : '${peakHour.toString().padLeft(2, '0')}:00';

              // Axis limits
              final maxRev = dailyRevenue.values.fold(0.0, (p, e) => e > p ? e : p);
              final maxOrders = dailyOrders.values.fold(0, (p, e) => e > p ? e : p).toDouble();

              final revenueMaxY = maxRev > 0 ? maxRev * 1.2 : 5000.0;
              final ordersMaxY = maxOrders > 0 ? maxOrders * 1.2 : 10.0;

              return SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 40),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // QUICK STATS CAROUSEL
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      physics: const BouncingScrollPhysics(),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          children: [
                            _QuickStatCard(
                              title: 'Total Revenue', 
                              value: 'Rs. ${NumberFormat.compact().format(totalRevenue)}', 
                              trend: revenueTrend, 
                              icon: Icons.payments_outlined, 
                              color: _T.statusCopper,
                            ),
                            const SizedBox(width: 12),
                            _QuickStatCard(
                              title: 'Net Profit', 
                              value: 'Rs. ${NumberFormat.compact().format(totalProfit)}', 
                              trend: profitTrend, 
                              icon: Icons.auto_graph_outlined, 
                              color: _T.statusGreen,
                            ),
                            const SizedBox(width: 12),
                            _QuickStatCard(
                              title: 'Avg. Margin', 
                              value: '${avgMargin.toStringAsFixed(1)}%', 
                              trend: 0, 
                              icon: Icons.percent_outlined, 
                              color: _T.brown,
                            ),
                          ],
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 24),

                    // REVENUE VS PROFIT LINE CHART
                    _AnalyticsCard(
                      title: 'Revenue vs Profit',
                      subtitle: _range == AnalyticsRange.week ? 'Weekly performance' : 'Monthly performance',
                      legend: const [
                        _LegendItem(label: 'Revenue', color: _T.statusCopper),
                        _LegendItem(label: 'Profit', color: _T.statusGreen),
                      ],
                      child: SizedBox(
                        height: 200,
                        child: LineChart(_buildRevenueProfitLineChart(dailyRevenue, dailyProfit, revenueMaxY)),
                      ),
                    ),

                    const SizedBox(height: 24),

                    // SMART INSIGHTS
                    const _SectionHeader(title: 'Smart Insights ✨'),
                    const SizedBox(height: 12),
                    _InsightCard(
                      insights: [
                        _InsightItem(text: '$bestSeller is your most profitable item this week.', type: InsightType.positive),
                        _InsightItem(text: 'Overall profit margin is stable at ${avgMargin.toStringAsFixed(1)}%.', type: InsightType.neutral),
                        _InsightItem(
                          text: 'Peak order time: $peakWeekdayLabel at $peakTimeLabel.',
                          type: InsightType.positive,
                        ),
                        if (revenueTrend < 0)
                          _InsightItem(text: 'Revenue is down ${revenueTrend.abs().toStringAsFixed(1)}% vs last week.', type: InsightType.negative),
                        const _InsightItem(text: 'Suggestion: Adjust pricing for seasonal cakes to increase profit by 12%.', type: InsightType.ai),
                      ],
                    ),

                    const SizedBox(height: 24),

                    // WEEKLY ORDERS TREND AREA GRAPH
                    _AnalyticsCard(
                      title: 'Order Activity',
                      subtitle: _range == AnalyticsRange.week ? 'Received / Completed / Rejected (by day)' : 'Received / Completed / Rejected (by bucket)',
                      legend: const [
                        _LegendItem(label: 'Received', color: _T.statusCopper),
                        _LegendItem(label: 'Completed', color: _T.statusGreen),
                        _LegendItem(label: 'Rejected', color: _T.statusPink),
                      ],
                      child: SizedBox(
                        height: 180,
                        child: LineChart(
                          _buildOrdersAreaChart(
                            dailyOrdersReceived,
                            dailyOrdersCompleted,
                            dailyOrdersRejected,
                            ordersMaxY,
                          ),
                        ),
                      ),
                    ),

                    const SizedBox(height: 24),

                    // PRODUCT SALES BAR CHART
                    _AnalyticsCard(
                      title: 'Top Products',
                      subtitle: 'By Revenue',
                      child: SizedBox(
                        height: 250,
                        child: BarChart(_buildProductSalesBarChart(productEarnings)),
                      ),
                    ),

                    const SizedBox(height: 24),

                    // PROFIT MARGIN PIE CHART
                    _AnalyticsCard(
                      title: 'Profit Contribution',
                      subtitle: 'By Category',
                      legend: categoryProfit.entries.map((e) => _LegendItem(label: e.key, color: _getCategoryColor(e.key))).toList(),
                      child: SizedBox(
                        height: 200,
                        child: PieChart(_buildProfitPieChart(categoryProfit, totalProfit)),
                      ),
                    ),

                    const SizedBox(height: 24),

                    // Reviews leaderboard (all-time)
                    _ReviewsLeaderboardSection(
                      products: products,
                    ),

                    const SizedBox(height: 24),

                    // TOP PERFORMING PRODUCTS LIST
                    const _SectionHeader(title: 'Leaderboard 🏆'),
                    const SizedBox(height: 12),
                    ...(productSalesCount.entries.toList()
                          ..sort((a, b) => b.value.compareTo(a.value)))
                        .take(3)
                        .map((e) {
                      final revenue = productEarnings[e.key] ?? 0;
                      return _ProductPerformanceTile(name: e.key, sales: e.value, revenue: revenue);
                    }),
                  ],
                ),
              );
            },
            loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
            error: (e, _) => Center(child: Text('Data Error: $e', style: const TextStyle(color: _T.statusPink))),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
        error: (e, _) => Center(child: Text('System Error: $e', style: const TextStyle(color: _T.statusPink))),
      ),
    );
  }

  LineChartData _buildRevenueProfitLineChart(Map<int, double> revenue, Map<int, double> profit, double maxY) {
    return LineChartData(
      maxY: maxY,
      minY: 0,
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (spot) => _T.brown,
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
        getDrawingHorizontalLine: (value) => FlLine(color: _T.rimLight.withOpacity(0.5), strokeWidth: 1),
      ),
      titlesData: _buildAxesTitles(),
      borderData: FlBorderData(show: false),
      lineBarsData: [
        LineChartBarData(
          spots: revenue.entries.map((e) => FlSpot(e.key.toDouble(), e.value)).toList(),
          isCurved: true,
          curveSmoothness: 0.35,
          color: _T.statusCopper,
          barWidth: 2.5,
          isStrokeCapRound: true,
          dotData: FlDotData(show: true, getDotPainter: (spot, percent, barData, index) => FlDotCirclePainter(radius: 3, color: Colors.white, strokeWidth: 2, strokeColor: _T.statusCopper)),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [_T.statusCopper.withOpacity(0.12), _T.statusCopper.withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        LineChartBarData(
          spots: profit.entries.map((e) => FlSpot(e.key.toDouble(), e.value)).toList(),
          isCurved: true,
          curveSmoothness: 0.35,
          color: _T.statusGreen,
          barWidth: 2.5,
          isStrokeCapRound: true,
          dotData: FlDotData(show: true, getDotPainter: (spot, percent, barData, index) => FlDotCirclePainter(radius: 3, color: Colors.white, strokeWidth: 2, strokeColor: _T.statusGreen)),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [_T.statusGreen.withOpacity(0.12), _T.statusGreen.withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
      ],
    );
  }

  LineChartData _buildOrdersAreaChart(
    Map<int, int> received,
    Map<int, int> completed,
    Map<int, int> rejected,
    double maxY,
  ) {
    return LineChartData(
      maxY: maxY,
      minY: 0,
      lineTouchData: const LineTouchData(enabled: true),
      gridData: const FlGridData(show: false),
      titlesData: const FlTitlesData(show: false),
      borderData: FlBorderData(show: false),
      lineBarsData: [
        LineChartBarData(
          spots: received.entries
              .map((e) => FlSpot(e.key.toDouble(), e.value.toDouble()))
              .toList(),
          isCurved: true,
          curveSmoothness: 0.4,
          color: _T.statusCopper,
          barWidth: 3,
          isStrokeCapRound: true,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [_T.statusCopper.withOpacity(0.12), _T.statusCopper.withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        LineChartBarData(
          spots: completed.entries
              .map((e) => FlSpot(e.key.toDouble(), e.value.toDouble()))
              .toList(),
          isCurved: true,
          curveSmoothness: 0.4,
          color: _T.statusGreen,
          barWidth: 3,
          isStrokeCapRound: true,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [_T.statusGreen.withOpacity(0.12), _T.statusGreen.withOpacity(0.0)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        LineChartBarData(
          spots: rejected.entries
              .map((e) => FlSpot(e.key.toDouble(), e.value.toDouble()))
              .toList(),
          isCurved: true,
          curveSmoothness: 0.4,
          color: _T.statusPink,
          barWidth: 3,
          isStrokeCapRound: true,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [_T.statusPink.withOpacity(0.12), _T.statusPink.withOpacity(0.0)],
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
                  child: Text(
                    sorted[value.toInt()].key.substring(0, 3), 
                    style: const TextStyle(fontSize: 10, color: _T.inkMid, fontWeight: FontWeight.w600),
                  ),
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
            color: _T.brown,
            width: 20,
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      )).toList(),
    );
  }

  PieChartData _buildProfitPieChart(Map<String, double> profit, double total) {
    return PieChartData(
      sectionsSpace: 4,
      centerSpaceRadius: 40,
      sections: total <= 0
          ? [
              PieChartSectionData(
                color: _T.rimLight,
                value: 1,
                title: '0%',
                radius: 50,
                titleStyle: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              )
            ]
          : profit.entries.map((e) {
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

  int? _bucketIndex(DateTime date, DateTime periodStart, int bucketCount) {
    final diff = date.difference(periodStart).inDays;
    if (diff < 0) return null;
    if (_range == AnalyticsRange.week) {
      return diff < bucketCount ? diff : null;
    }
    final index = diff ~/ 7;
    return index < bucketCount ? index : bucketCount - 1;
  }

  double _estimateOrderProfit(OrderModel order, List<ProductModel> products) {
    double profit = 0;
    for (final item in order.items) {
      final matches = products.where((product) => product.id == item.productId);
      if (matches.isEmpty) continue;
      profit += _estimateItemProfit(item, matches.first);
    }
    return profit;
  }

  double _estimateItemProfit(OrderItem item, ProductModel product) {
    final estimatedUnitCost = product.price * (1 - (product.profitMargin / 100));
    return (item.price - estimatedUnitCost) * item.quantity;
  }

  Color _getCategoryColor(String category) {
    final colors = [_T.brown, _T.statusCopper, _T.statusGreen, _T.statusPink, _T.taupe];
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
            final labels = _range == AnalyticsRange.week
                ? ['M', 'T', 'W', 'T', 'F', 'S', 'S']
                : ['W1', 'W2', 'W3', 'W4', 'W5'];
            final index = value.toInt();
            if (index < 0 || index >= labels.length) {
              return const SizedBox.shrink();
            }
            return Text(
              labels[index], 
              style: const TextStyle(color: _T.inkMid, fontSize: 10, fontWeight: FontWeight.w600),
            );
          },
        ),
      ),
      leftTitles: AxisTitles(
        sideTitles: SideTitles(
          showTitles: true,
          reservedSize: 35,
          getTitlesWidget: (value, meta) {
            if (value == 0) return const SizedBox.shrink();
            return Text(
              NumberFormat.compact().format(value), 
              style: const TextStyle(color: _T.inkMid, fontSize: 9, fontWeight: FontWeight.w600),
            );
          },
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  SUPPORTING UI COMPONENTS
// ════════════════════════════════════════════════════════════════════════════

class _DateRangeSelector extends StatelessWidget {
  final AnalyticsRange currentRange;
  final ValueChanged<AnalyticsRange> onChanged;

  const _DateRangeSelector({required this.currentRange, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 10),
      padding: const EdgeInsets.symmetric(horizontal: 4),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _T.rimLight, width: 1.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _RangeButton(
            label: 'Week',
            isSelected: currentRange == AnalyticsRange.week,
            onTap: () => onChanged(AnalyticsRange.week),
          ),
          _RangeButton(
            label: 'Month',
            isSelected: currentRange == AnalyticsRange.month,
            onTap: () => onChanged(AnalyticsRange.month),
          ),
        ],
      ),
    );
  }
}

class _RangeButton extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _RangeButton({required this.label, required this.isSelected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? _T.brown : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : _T.inkMid,
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

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
      width: 150,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: _T.shadowSm,
        border: Border.all(color: _T.rimLight, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(10)),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 14),
          Text(title, style: const TextStyle(color: _T.inkMid, fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(trend >= 0 ? Icons.trending_up : Icons.trending_down, size: 14, color: trend >= 0 ? _T.statusGreen : _T.statusPink),
              const SizedBox(width: 4),
              Text(
                '${trend.abs().toStringAsFixed(1)}%', 
                style: TextStyle(color: trend >= 0 ? _T.statusGreen : _T.statusPink, fontSize: 11, fontWeight: FontWeight.w800),
              ),
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
        color: _T.surface,
        borderRadius: BorderRadius.circular(24),
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
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title, 
                      style: const TextStyle(color: _T.ink, fontSize: 15.5, fontWeight: FontWeight.w800), 
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle, 
                      style: const TextStyle(color: _T.inkMid, fontSize: 11, fontWeight: FontWeight.w600), 
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              if (legend != null)
                Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  runSpacing: 4,
                  children: legend!,
                ),
            ],
          ),
          const SizedBox(height: 20),
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
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _T.surfaceWarm,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
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
      case InsightType.positive: 
        icon = Icons.star_rounded; 
        color = _T.statusGreen; 
        break;
      case InsightType.negative: 
        icon = Icons.info_outline_rounded; 
        color = _T.statusPink; 
        break;
      case InsightType.neutral: 
        icon = Icons.analytics_outlined; 
        color = _T.statusCopper; 
        break;
      case InsightType.ai: 
        icon = Icons.auto_awesome_outlined; 
        color = _T.brown; 
        break;
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text, 
              style: const TextStyle(color: _T.ink, fontSize: 13, height: 1.4, fontWeight: FontWeight.w600),
            ),
          ),
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
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Row(
        children: [
          Container(
            width: 40, height: 40,
            decoration: const BoxDecoration(color: _T.surfaceWarm, shape: BoxShape.circle),
            child: const Icon(Icons.cake_outlined, color: _T.brown, size: 20),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name, 
                  style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 14),
                ),
                const SizedBox(height: 2),
                Text(
                  '$sales units sold', 
                  style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          Text(
            'Rs. ${NumberFormat.compact().format(revenue)}', 
            style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 14),
          ),
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
    return Text(
      title, 
      style: const TextStyle(color: _T.ink, fontSize: 15, fontWeight: FontWeight.w800),
    );
  }
}

class _LegendItem extends StatelessWidget {
  final String label;
  final Color color;
  const _LegendItem({required this.label, required this.color});
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 4),
        Text(
          label, 
          style: const TextStyle(color: _T.inkMid, fontSize: 10, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

enum InsightType { positive, negative, neutral, ai }

class _ReviewsLeaderboardSection extends StatelessWidget {
  final List<ProductModel> products;
  const _ReviewsLeaderboardSection({required this.products});

  @override
  Widget build(BuildContext context) {
    return _ReviewsLeaderboardBody(products: products);
  }
}

class _ReviewsLeaderboardBody extends ConsumerWidget {
  final List<ProductModel> products;
  const _ReviewsLeaderboardBody({required this.products});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentUser = ref.watch(currentUserProvider).valueOrNull;
    final bakerId = currentUser?.uid;

    if (bakerId == null) return const SizedBox.shrink();

    return StreamBuilder<List<ReviewModel>>(
      stream: ref.read(firestoreServiceProvider).streamBakerReviews(bakerId),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator(color: _T.copper));
        }
        final reviews = snapshot.data ?? [];
        if (reviews.isEmpty) {
          return const _EmptyReviewsSection();
        }

        // Aggregate: productId -> {count, ratingSum}
        final Map<String, int> reviewCountByProduct = {};
        final Map<String, double> ratingSumByProduct = {};
        final Map<String, double> avgRatingByProduct = {};

        for (final review in reviews) {
          final pids = review.productIds;
          if (pids.isEmpty) continue;

          for (final pid in pids) {
            final key = pid;
            reviewCountByProduct[key] = (reviewCountByProduct[key] ?? 0) + 1;
            ratingSumByProduct[key] = (ratingSumByProduct[key] ?? 0) + review.rating;
          }
        }

        for (final entry in reviewCountByProduct.entries) {
          final pid = entry.key;
          final count = entry.value;
          final sum = ratingSumByProduct[pid] ?? 0.0;
          avgRatingByProduct[pid] = count == 0 ? 0.0 : (sum / count);
        }

        // Most reviewed: top 3 by count
        final mostReviewed = reviewCountByProduct.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value));

        // Highest rated: top 3 by avg rating, tie-break by count
        final highestRated = avgRatingByProduct.entries.toList()
          ..sort((a, b) {
            final av = a.value;
            final bv = b.value;
            final cmp = bv.compareTo(av);
            if (cmp != 0) return cmp;
            final ac = reviewCountByProduct[a.key] ?? 0;
            final bc = reviewCountByProduct[b.key] ?? 0;
            return bc.compareTo(ac);
          });

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionHeader(title: 'Reviews & Ratings ⭐'),
            const SizedBox(height: 12),

            _ReviewsAnalyticsCard(
              title: 'Most Reviewed',
              subtitle: 'Top products by review volume',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: mostReviewed.take(3).map((e) {
                  final pid = e.key;
                  final count = e.value;
                  final avg = avgRatingByProduct[pid] ?? 0.0;
                  final name = products.firstWhere((p) => p.id == pid, orElse: () => ProductModel(id: pid, bakerId: '', name: pid, description: '', price: 0, category: '', images: const [], dietaryLabels: const [], ingredients: const {}, addOns: const {}, isAvailable: true, profitMargin: 0, createdAt: DateTime.fromMillisecondsSinceEpoch(0))).name;

                  return _ProductReviewRow(
                    title: name,
                    subtitle: '$count reviews • ${avg.toStringAsFixed(1)}★',
                  );
                }).toList(),
              ),
            ),

            const SizedBox(height: 16),

            _ReviewsAnalyticsCard(
              title: 'Highest Rated',
              subtitle: 'Top products by average rating',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: highestRated.take(3).map((e) {
                  final pid = e.key;
                  final avg = e.value;
                  final count = reviewCountByProduct[pid] ?? 0;
                  final name = products.firstWhere((p) => p.id == pid, orElse: () => ProductModel(id: pid, bakerId: '', name: pid, description: '', price: 0, category: '', images: const [], dietaryLabels: const [], ingredients: const {}, addOns: const {}, isAvailable: true, profitMargin: 0, createdAt: DateTime.fromMillisecondsSinceEpoch(0))).name;

                  return _ProductReviewRow(
                    title: name,
                    subtitle: '$count reviews • ${avg.toStringAsFixed(1)}★',
                  );
                }).toList(),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _EmptyReviewsSection extends StatelessWidget {
  const _EmptyReviewsSection();

  @override
  Widget build(BuildContext context) {
    return const _ReviewsAnalyticsCard(
      title: 'Reviews & Ratings ⭐',
      subtitle: 'No reviews yet',
      child: SizedBox.shrink(),
    );
  }
}

class _ReviewsAnalyticsCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;
  const _ReviewsAnalyticsCard({
    required this.title,
    required this.subtitle,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: _T.ink, fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          Text(subtitle, style: const TextStyle(color: _T.inkMid, fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _ProductReviewRow extends StatelessWidget {
  final String title;
  final String subtitle;

  const _ProductReviewRow({
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 13.5)),
          const SizedBox(height: 3),
          Text(subtitle, style: const TextStyle(color: _T.inkMid, fontSize: 11.5, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
