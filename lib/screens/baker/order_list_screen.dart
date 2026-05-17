import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../providers/order_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';
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

class OrderListScreen extends ConsumerWidget {
  const OrderListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      bottomNavigationBar: const BakerBottomNav(currentIndex: 2),
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: false,
        title: const Text(
          'Orders', 
          style: TextStyle(fontWeight: FontWeight.w800, color: _T.brown, fontSize: 18),
        ),
      ),
      body: ordersAsync.when(
        data: (orders) {
          if (orders.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      color: _T.pinkL,
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: _T.pink.withOpacity(0.2), width: 1.5),
                    ),
                    child: const Icon(Icons.receipt_long_outlined, color: _T.copper, size: 32),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'No orders yet', 
                    style: TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Active bakery orders will appear here.', 
                    style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            itemCount: orders.length,
            itemBuilder: (context, index) {
              final order = orders[index];
              return _OrderCard(order: order);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
      ),
    );
  }
}

class _OrderCard extends StatelessWidget {
  final OrderModel order;
  const _OrderCard({required this.order});

  @override
  Widget build(BuildContext context) {
    final sc = _statusConfig(order.status);
    final oId = order.id;
    final displayId = oId.length > 4 ? oId.substring(oId.length - 4).toUpperCase() : oId.toUpperCase();

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: order.status == AppConstants.orderPlaced ? _T.pink.withOpacity(0.5) : _T.rimLight,
          width: order.status == AppConstants.orderPlaced ? 2 : 1.5,
        ),
        boxShadow: _T.shadowSm,
      ),
      child: InkWell(
        onTap: () => context.push('${AppRoutes.bakerOrderDetails}/${order.id}'),
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // POS style left box
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: _T.surfaceWarm,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: _T.rimLight),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          '#',
                          style: TextStyle(color: _T.copper, fontSize: 10, fontWeight: FontWeight.w800),
                        ),
                        Text(
                          displayId,
                          style: const TextStyle(color: _T.brown, fontSize: 14, fontWeight: FontWeight.w800),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 14),

                  // Middle info block
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          order.customerName,
                          style: const TextStyle(
                            color: _T.ink,
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.2,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            const Icon(Icons.calendar_today_outlined, color: _T.inkMid, size: 12),
                            const SizedBox(width: 4),
                            Text(
                              'Delivery: ${DateFormat('MMM dd, hh:mm a').format(order.deliveryDate)}',
                              style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  // Sleek Status Badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: sc.color.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      sc.label,
                      style: TextStyle(
                        color: sc.color,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.6,
                      ),
                    ),
                  ),
                ],
              ),
              const Divider(color: _T.rimLight, height: 24, thickness: 1),

              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${order.items.length} item${order.items.length == 1 ? '' : 's'}',
                    style: const TextStyle(color: _T.taupe, fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                  Text(
                    'Rs. ${order.totalAmount.toStringAsFixed(0)}',
                    style: const TextStyle(color: _T.copper, fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                ],
              ),
              if (order.capacityWarning) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: _T.pinkL.withOpacity(0.6),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _T.pink.withOpacity(0.2)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.warning_amber_rounded, color: _T.copper, size: 16),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Daily capacity limit reached warning',
                          style: TextStyle(color: _T.taupe, fontSize: 12, fontWeight: FontWeight.w700),
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

class _StatusConfig {
  final Color color;
  final String label;
  const _StatusConfig(this.color, this.label);
}

_StatusConfig _statusConfig(String status) {
  switch (status.toLowerCase()) {
    case 'pending':
    case 'placed':   return const _StatusConfig(_T.statusCopper,  'NEW');
    case 'accepted': return const _StatusConfig(_T.statusBrown,   'ACCEPTED');
    case 'preparing':return const _StatusConfig(_T.statusBrown,   'PREPARING');
    case 'ready':    return const _StatusConfig(_T.statusGreen,   'READY');
    case 'delivered':return const _StatusConfig(_T.statusGreen,   'DELIVERED');
    case 'cancelled':
    case 'rejected':  return const _StatusConfig(_T.statusPink,    'REJECTED');
    default:         return const _StatusConfig(_T.inkMid, 'UNKNOWN');
  }
}
