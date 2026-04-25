import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../customer/services/order_service.dart';
import 'order_detail_screen.dart';

class BakerOrdersScreen extends ConsumerWidget {
  const BakerOrdersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        backgroundColor: Colors.brown[50],
        appBar: AppBar(
          title: const Text('Order Management'),
          backgroundColor: Colors.brown,
          foregroundColor: Colors.white,
          bottom: const TabBar(
            indicatorColor: Colors.white,
            labelColor: Colors.white,
            unselectedLabelColor: Colors.white54,
            tabs: [
              Tab(text: 'Pending'),
              Tab(text: 'Active'),
              Tab(text: 'Completed'),
            ],
          ),
        ),
        body: const TabBarView(
          children: [
            _OrdersList(tabFilter: 'pending'),
            _OrdersList(tabFilter: 'active'),
            _OrdersList(tabFilter: 'completed'),
          ],
        ),
      ),
    );
  }
}

class _OrdersList extends ConsumerWidget {
  final String tabFilter;
  const _OrdersList({required this.tabFilter});

  String _formatTimeElapsed(DateTime placedAt) {
    final diff = DateTime.now().difference(placedAt);
    if (diff.inDays > 0) return '${diff.inDays}d ago';
    if (diff.inHours > 0) return '${diff.inHours}h ago';
    if (diff.inMinutes > 0) return '${diff.inMinutes}m ago';
    return 'Just now';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersStreamProvider);

    return ordersAsync.when(
      data: (allOrders) {
        final filteredOrders = allOrders.where((order) {
          switch (tabFilter) {
            case 'pending': return order.status == 'placed';
            case 'active': return ['accepted', 'preparing', 'ready'].contains(order.status);
            case 'completed': return ['delivered', 'rejected'].contains(order.status);
            default: return false;
          }
        }).toList();

        if (filteredOrders.isEmpty) {
          return const Center(child: Text('No orders found.'));
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: filteredOrders.length,
          itemBuilder: (ctx, i) {
            final order = filteredOrders[i];
            
            Widget actionButtons = const SizedBox.shrink();
            if (tabFilter == 'pending') {
              actionButtons = Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(order, 'rejected'),
                      style: OutlinedButton.styleFrom(foregroundColor: Colors.red, side: const BorderSide(color: Colors.red)),
                      child: const Text('Reject'),
                    )
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(order, 'accepted'),
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
                      child: const Text('Accept'),
                    )
                  ),
                ],
              );
            } else if (tabFilter == 'active') {
              String nextLabel = '';
              String nextStatus = '';
              if (order.status == 'accepted') { nextLabel = 'Mark as Preparing'; nextStatus = 'preparing'; }
              if (order.status == 'preparing') { nextLabel = 'Mark as Ready'; nextStatus = 'ready'; }
              if (order.status == 'ready') { nextLabel = 'Mark as Delivered'; nextStatus = 'delivered'; }

              actionButtons = SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(order, nextStatus),
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.brown, foregroundColor: Colors.white),
                  child: Text(nextLabel),
                ),
              );
            }

            return GestureDetector(
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => OrderDetailScreen(order: order))),
              child: Card(
                elevation: 2,
                margin: const EdgeInsets.only(bottom: 16),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(child: Text(order.customerName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
                          Text(_formatTimeElapsed(order.placedAt), style: TextStyle(color: Colors.grey[600], fontSize: 12)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('${order.items.length} items • ${order.fulfillmentType.toUpperCase()}', style: TextStyle(color: Colors.grey[800])),
                      const SizedBox(height: 8),
                      Text('Total: \$${order.totalAmount.toStringAsFixed(2)}', style: const TextStyle(color: Colors.brown, fontWeight: FontWeight.bold)),
                      if (tabFilter != 'completed') const SizedBox(height: 16),
                      actionButtons,
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, s) => Center(child: Text('Error: $e')),
    );
  }
}
