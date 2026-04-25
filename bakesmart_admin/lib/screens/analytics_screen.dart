import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:math' as math;
import '../services/admin_service.dart';

class AnalyticsScreen extends ConsumerWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analyticsAsync = ref.watch(adminAnalyticsProvider);

    return analyticsAsync.when(
      data: (stats) => SingleChildScrollView(
        padding: const EdgeInsets.all(40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 24,
              runSpacing: 24,
              children: [
                _buildKPICard('Total Orders', '${stats.totalOrders}', Icons.shopping_bag_outlined, Colors.purple),
                _buildKPICard('Total Revenue', 'PKR ${stats.totalRevenue.toStringAsFixed(0)}', Icons.payments_outlined, Colors.green),
                _buildKPICard('Popular Product', stats.mostOrderedProduct, Icons.star_outline, Colors.orange),
                _buildKPICard('New Users (7d)', '${stats.newUsersLast7Days}', Icons.person_add_outlined, Colors.blue),
              ],
            ),
            const SizedBox(height: 48),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  flex: 3,
                  child: _buildSection(
                    title: 'Orders per Day (Last 7 Days)',
                    child: SizedBox(
                      height: 250,
                      child: CustomPaint(
                        painter: _BarChartPainter(stats.ordersLast7Days),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 32),
                Expanded(
                  flex: 2,
                  child: _buildSection(
                    title: 'Top 5 Bakers',
                    child: stats.topBakers.isEmpty 
                      ? const Center(child: Text('No data recorded for this week', style: TextStyle(color: Colors.grey)))
                      : Column(
                          children: stats.topBakers.map((b) => _buildBakerRow(b.name, b.orderCount)).toList(),
                        ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
    );
  }

  Widget _buildKPICard(String title, String value, IconData icon, Color color) {
    return Container(
      width: 300,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFEEEEEE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 16),
          Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(title, style: TextStyle(color: Colors.grey[600])),
        ],
      ),
    );
  }

  Widget _buildSection({required String title, required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFEEEEEE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 32),
          child,
        ],
      ),
    );
  }

  Widget _buildBakerRow(String name, int count) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: Colors.brown[50], 
            child: Text(name[0], style: const TextStyle(color: Colors.brown, fontSize: 13, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 16),
          Expanded(child: Text(name, style: const TextStyle(fontWeight: FontWeight.w500))),
          Text('$count orders', style: const TextStyle(color: Colors.grey, fontSize: 13)),
        ],
      ),
    );
  }
}

class _BarChartPainter extends CustomPainter {
  final List<int> data;
  _BarChartPainter(this.data);

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;
    
    final paint = Paint()
      ..color = Colors.brown[300]!
      ..style = PaintingStyle.fill;

    final maxVal = data.reduce(math.max).toDouble() + 5;
    final spacing = size.width / (data.length * 2 + 1);
    final barWidth = spacing;

    for (int i = 0; i < data.length; i++) {
      final barHeight = (data[i] / maxVal) * size.height;
      final x = spacing + (i * 2 * spacing);
      final y = size.height - barHeight;

      canvas.drawRRect(
        RRect.fromRectAndCorners(
          Rect.fromLTWH(x, y, barWidth, barHeight),
          topLeft: const Radius.circular(4),
          topRight: const Radius.circular(4),
        ),
        paint,
      );

      // Label
      final tp = TextPainter(
        text: TextSpan(text: '${data[i]}', style: const TextStyle(color: Colors.brown, fontSize: 10, fontWeight: FontWeight.bold)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(x + (barWidth - tp.width) / 2, y - 15));
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
