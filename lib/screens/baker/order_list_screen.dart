import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../providers/order_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';
import '../../core/theme/baker_theme.dart';


class OrderListScreen extends ConsumerWidget {
  const OrderListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersProvider);

    return Scaffold(
      backgroundColor: BakerTheme.background,

      appBar: AppBar(
        backgroundColor: BakerTheme.background,
        title: const Text('Orders', style: TextStyle(fontWeight: FontWeight.bold, color: BakerTheme.textPrimary)),

        elevation: 0,
      ),
      body: ordersAsync.when(
        data: (orders) {
          if (orders.isEmpty) {
            return const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.receipt_long_outlined, color: Color(0xFF484F58), size: 64),
                  SizedBox(height: 16),
                  Text('No orders yet', style: TextStyle(color: BakerTheme.textSecondary)),

                ],
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: orders.length,
            itemBuilder: (context, index) {
              final order = orders[index];
              return _OrderCard(order: order);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFFF59E0B))),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}

class _OrderCard extends StatelessWidget {
  final OrderModel order;
  const _OrderCard({required this.order});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: order.status == AppConstants.orderPlaced ? BakerTheme.secondary.withOpacity(0.5) : BakerTheme.divider,
          width: order.status == AppConstants.orderPlaced ? 2 : 1,
        ),

      ),
      child: InkWell(
        onTap: () => context.push('${AppRoutes.bakerOrderDetails}/${order.id}'),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Order #${order.id.substring(0, 8).toUpperCase()}',
                    style: const TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold),

                  ),
                  _StatusBadge(status: order.status),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                order.customerName,
                style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),

              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.calendar_today_outlined, color: Color(0xFF8B949E), size: 14),
                  const SizedBox(width: 6),
                  Text(
                    'Delivery: ${DateFormat('MMM dd, hh:mm a').format(order.deliveryDate)}',
                    style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 13),

                  ),
                ],
              ),
              const Divider(color: BakerTheme.divider, height: 24),

              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${order.items.length} items',
                    style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 13),

                  ),
                  Text(
                    'Rs. ${order.totalAmount.toStringAsFixed(0)}',
                    style: const TextStyle(color: BakerTheme.secondary, fontSize: 16, fontWeight: FontWeight.bold),

                  ),
                ],
              ),
              if (order.capacityWarning) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 16),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'Daily capacity warning',
                          style: TextStyle(color: Colors.orange, fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    Color color;
    String label = status.toUpperCase();

    switch (status) {
      case AppConstants.orderPlaced:
        color = const Color(0xFFF59E0B);
        label = 'NEW';
        break;
      case AppConstants.orderAccepted:
        color = const Color(0xFF3B82F6);
        break;
      case AppConstants.orderPreparing:
        color = const Color(0xFF8B5CF6);
        break;
      case AppConstants.orderReady:
        color = const Color(0xFF10B981);
        break;
      case AppConstants.orderDelivered:
        color = const Color(0xFF484F58);
        break;
      case AppConstants.orderRejected:
        color = const Color(0xFFEF4444);
        break;
      default:
        color = const Color(0xFF8B949E);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold),
      ),
    );
  }
}
