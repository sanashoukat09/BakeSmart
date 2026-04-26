import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../customer/services/order_service.dart';
import 'order_detail_screen.dart';

// BakerOrdersScreen is a ConsumerStatefulWidget so that the TabController
// is created once in initState() and NEVER recreated on stream rebuilds.
// Previously it was a ConsumerWidget, which meant every Firestore emission
// triggered build(), re-creating DefaultTabController and resetting to tab 0.
// Track which order IDs are currently being updated to show a processing indicator
final orderProcessingProvider = StateProvider.family<bool, String>((ref, orderId) => false);

class BakerOrdersScreen extends ConsumerStatefulWidget {
  const BakerOrdersScreen({super.key});

  @override
  ConsumerState<BakerOrdersScreen> createState() => _BakerOrdersScreenState();
}

class _BakerOrdersScreenState extends ConsumerState<BakerOrdersScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: const Text('Order Management'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white54,
          tabs: const [
            Tab(text: 'Pending'),
            Tab(text: 'Active'),
            Tab(text: 'Completed'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _OrdersList(tabFilter: 'pending'),
          _OrdersList(tabFilter: 'active'),
          _OrdersList(tabFilter: 'completed'),
        ],
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

            final isProcessing = ref.watch(orderProcessingProvider(order.orderId));

            // Helper: await the status update and show any error as a snackbar.
            Future<void> doUpdate(String newStatus) async {
              ref.read(orderProcessingProvider(order.orderId).notifier).state = true;
              try {
                await ref.read(orderServiceProvider).updateOrderStatus(order, newStatus);
              } catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx).showSnackBar(
                    SnackBar(
                      content: Text('Failed to update order: $e'),
                      backgroundColor: Colors.red[700],
                    ),
                  );
                }
              } finally {
                ref.read(orderProcessingProvider(order.orderId).notifier).state = false;
              }
            }

            if (isProcessing) {
              actionButtons = const Center(
                child: Padding(
                  padding: EdgeInsets.symmetric(vertical: 8.0),
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              );
            } else if (order.status == 'placed') {
              actionButtons = Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => doUpdate('rejected'),
                      style: OutlinedButton.styleFrom(foregroundColor: Colors.red, side: const BorderSide(color: Colors.red)),
                      child: const Text('Reject'),
                    )
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => doUpdate('accepted'),
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
                      child: const Text('Accept'),
                    )
                  ),
                ],
              );
            } else if (['accepted', 'preparing', 'ready'].contains(order.status)) {
              String nextLabel = '';
              String nextStatus = '';
              if (order.status == 'accepted') { nextLabel = 'Mark as Preparing'; nextStatus = 'preparing'; }
              if (order.status == 'preparing') { nextLabel = 'Mark as Ready'; nextStatus = 'ready'; }
              if (order.status == 'ready') { nextLabel = 'Mark as Delivered'; nextStatus = 'delivered'; }

              actionButtons = SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => doUpdate(nextStatus),
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.brown, foregroundColor: Colors.white),
                  child: Text(nextLabel),
                ),
              );
            }

            return GestureDetector(
              // Pass only orderId — OrderDetailScreen will look up the live
              // order from the stream instead of using a stale snapshot.
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => OrderDetailScreen(orderId: order.orderId))),
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
