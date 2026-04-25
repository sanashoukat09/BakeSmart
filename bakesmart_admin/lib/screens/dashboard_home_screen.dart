import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../services/admin_service.dart';

class DashboardHomeScreen extends ConsumerWidget {
  const DashboardHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analyticsAsync = ref.watch(adminAnalyticsProvider);
    final pendingVerifications = ref.watch(verificationQueueProvider);
    final recentOrders = ref.watch(recentOrdersProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          analyticsAsync.when(
            data: (stats) => Wrap(
              spacing: 24,
              runSpacing: 24,
              children: [
                _buildStatCard(
                  'Total Bakers',
                  '${stats.totalBakers}',
                  Icons.store_outlined,
                  Colors.blue,
                ),
                _buildStatCard(
                  'Total Customers',
                  '${stats.totalCustomers}',
                  Icons.people_outline,
                  Colors.green,
                ),
                _buildStatCard(
                  'Orders (Today)',
                  '${stats.ordersToday}',
                  Icons.receipt_long_outlined,
                  Colors.orange,
                ),
                pendingVerifications.when(
                  data: (list) => _buildStatCard(
                    'Pending Verifications',
                    '${list.length}',
                    Icons.verified_user_outlined,
                    list.isNotEmpty ? Colors.red : Colors.grey,
                    showBadge: list.isNotEmpty,
                  ),
                  loading: () => _buildStatCard('Pending Verifications', '...', Icons.verified_user_outlined, Colors.grey),
                  error: (_, __) => _buildStatCard('Pending Verifications', 'Error', Icons.error_outline, Colors.red),
                ),
              ],
            ),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text('Error loading stats: $e'),
          ),
          const SizedBox(height: 48),
          const Text(
            'Recent Orders',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          recentOrders.when(
            data: (orders) => Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFEEEEEE)),
              ),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: const Color(0xFFEEEEEE)),
                child: DataTable(
                  headingRowHeight: 56,
                  dataRowMinHeight: 64,
                  dataRowMaxHeight: 64,
                  columns: const [
                    DataColumn(label: Text('Baker Name', style: TextStyle(fontWeight: FontWeight.bold))),
                    DataColumn(label: Text('Customer', style: TextStyle(fontWeight: FontWeight.bold))),
                    DataColumn(label: Text('Amount', style: TextStyle(fontWeight: FontWeight.bold))),
                    DataColumn(label: Text('Date', style: TextStyle(fontWeight: FontWeight.bold))),
                    DataColumn(label: Text('Status', style: TextStyle(fontWeight: FontWeight.bold))),
                  ],
                  rows: orders.map((order) => DataRow(cells: [
                    DataCell(Text(order.bakerName)),
                    DataCell(Text(order.customerName)),
                    DataCell(Text('PKR ${order.totalAmount.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w600))),
                    DataCell(Text(DateFormat('MMM dd, hh:mm a').format(order.placedAt))),
                    DataCell(_buildStatusChip(order.status)),
                  ])).toList(),
                ),
              ),
            ),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text('Error loading orders: $e'),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color, {bool showBadge = false}) {
    return Container(
      width: 260,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFEEEEEE)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 28),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  title,
                  style: TextStyle(color: Colors.grey[600], fontSize: 13),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          if (showBadge)
            Container(
              width: 10,
              height: 10,
              decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
            ),
        ],
      ),
    );
  }

  Widget _buildStatusChip(String status) {
    Color color;
    switch (status) {
      case 'delivered': color = Colors.green; break;
      case 'accepted': color = Colors.blue; break;
      case 'ready': color = Colors.purple; break;
      case 'rejected': color = Colors.red; break;
      default: color = Colors.orange;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold),
      ),
    );
  }
}
