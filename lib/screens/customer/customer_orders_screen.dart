import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../providers/customer_order_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';
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
  static const statusGreen = Color(0xFF52B788);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class CustomerOrdersScreen extends ConsumerWidget {
  const CustomerOrdersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(customerOrdersProvider);

    return DefaultTabController(
      length: 2,
      child: Scaffold(
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
            'My Orders',
            style: TextStyle(
              color: _T.ink,
              fontWeight: FontWeight.w800,
              fontSize: 19,
            ),
          ),
          bottom: const PreferredSize(
            preferredSize: Size.fromHeight(48),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TabBar(
                isScrollable: true,
                labelColor: _T.brown,
                unselectedLabelColor: _T.inkMid,
                indicatorColor: _T.brown,
                indicatorWeight: 3,
                labelStyle: TextStyle(fontWeight: FontWeight.w800, fontSize: 14.5),
                unselectedLabelStyle: TextStyle(fontWeight: FontWeight.w600, fontSize: 14.5),
                tabs: [
                  Tab(text: 'Active Orders'),
                  Tab(text: 'Past Orders'),
                ],
              ),
            ),
          ),
        ),
        body: ordersAsync.when(
          data: (orders) {
            final activeOrders = orders.where((o) => o.status != AppConstants.orderDelivered && o.status != AppConstants.orderRejected).toList();
            final pastOrders = orders.where((o) => o.status == AppConstants.orderDelivered || o.status == AppConstants.orderRejected).toList();

            return TabBarView(
              physics: const BouncingScrollPhysics(),
              children: [
                _OrderList(orders: activeOrders),
                _OrderList(orders: pastOrders),
              ],
            );
          },
          loading: () => const Center(child: CircularProgressIndicator(color: _T.brown)),
          error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusRed))),
        ),
      ),
    );
  }
}

class _OrderList extends StatelessWidget {
  final List<OrderModel> orders;
  const _OrderList({required this.orders});

  @override
  Widget build(BuildContext context) {
    if (orders.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: _T.inkFaint.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.receipt_long_outlined, size: 64, color: _T.inkFaint),
            ),
            const SizedBox(height: 20),
            const Text(
              'No orders here', 
              style: TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 6),
            const Text(
              'Your active and past treats will show up here.',
              style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      itemCount: orders.length,
      itemBuilder: (context, i) => _OrderCard(order: orders[i]),
    );
  }
}

class _OrderCard extends StatelessWidget {
  final OrderModel order;
  const _OrderCard({required this.order});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push('${AppRoutes.customerOrderDetails}/${order.id}'),
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Order #${order.id.substring(0, 8).toUpperCase()}',
                          style: const TextStyle(
                            color: _T.ink,
                            fontWeight: FontWeight.w800,
                            fontSize: 14.5,
                          ),
                        ),
                        _StatusBadge(status: order.status),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      '${order.items.length} item${order.items.length > 1 ? "s" : ""} • Rs. ${order.totalAmount.toStringAsFixed(0)}',
                      style: const TextStyle(
                        color: _T.statusPink,
                        fontWeight: FontWeight.w800,
                        fontSize: 13.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        const Icon(Icons.access_time_rounded, color: _T.inkFaint, size: 14),
                        const SizedBox(width: 6),
                        Text(
                          'Delivery: ${DateFormat('MMM dd, hh:mm a').format(order.deliveryDate)}',
                          style: const TextStyle(
                            color: _T.inkMid,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right_rounded, color: _T.inkFaint),
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
    switch (status) {
      case AppConstants.orderPlaced:
        color = _T.brown;
        break;
      case AppConstants.orderAccepted:
        color = const Color(0xFF3B82F6);
        break;
      case AppConstants.orderPreparing:
        color = const Color(0xFF8B5CF6);
        break;
      case AppConstants.orderReady:
        color = _T.statusGreen;
        break;
      case AppConstants.orderDelivered:
        color = _T.statusGreen;
        break;
      case AppConstants.orderRejected:
        color = _T.statusRed;
        break;
      default:
        color = Colors.grey;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(
          color: color,
          fontSize: 9.5,
          fontWeight: FontWeight.w900,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
