import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../customer/services/order_service.dart';
import 'package:intl/intl.dart';

// OrderDetailScreen now accepts only orderId instead of a full OrderModel
// snapshot. This prevents stale data from the navigation moment from ever
// being displayed — the screen derives all state exclusively from the live
// bakerOrdersStreamProvider stream.
class OrderDetailScreen extends ConsumerWidget {
  final String orderId;
  const OrderDetailScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersStreamProvider);

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: Text('Order ${orderId.substring(0, 6)}'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
      ),
      body: ordersAsync.when(
        data: (allOrders) {
          // Safely look up the live order by ID from the stream.
          // If the order is no longer in the stream (e.g. deleted), show a
          // friendly error rather than crashing.
          final matches = allOrders.where((o) => o.orderId == orderId);
          if (matches.isEmpty) {
            return const Center(child: Text('Order not found.'));
          }
          final activeOrder = matches.first;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildCustomerCard(activeOrder),
                const SizedBox(height: 16),
                _buildItemsList(activeOrder),
                const SizedBox(height: 16),
                _buildStatusActionBox(context, ref, activeOrder),
                const SizedBox(height: 16),
                _buildTimeline(activeOrder),
              ],
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, s) => const Center(child: Text('Error loading live order')),
      ),
    );
  }

  Widget _buildCustomerCard(activeOrder) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Customer Details', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const Divider(),
            Text('Name: ${activeOrder.customerName}', style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 8),
            Text('Fulfillment: ${activeOrder.fulfillmentType.toUpperCase()}', style: TextStyle(color: Colors.brown[700], fontWeight: FontWeight.bold)),
            if (activeOrder.fulfillmentType == 'delivery' && activeOrder.deliveryAddress != null) ...[
              const SizedBox(height: 8),
              Text('Address: ${activeOrder.deliveryAddress}'),
            ]
          ],
        ),
      ),
    );
  }

  Widget _buildItemsList(activeOrder) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Order Items', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const Divider(),
            ...activeOrder.items.map((item) => Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(child: Text('${item.quantity}x ${item.productName}')),
                  Text('\$${(item.unitPrice * item.quantity).toStringAsFixed(2)}'),
                ],
              ),
            )),
            const Divider(),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Total:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                Text('\$${activeOrder.totalAmount.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.brown)),
              ],
            )
          ],
        ),
      ),
    );
  }

  Widget _buildStatusActionBox(BuildContext context, WidgetRef ref, activeOrder) {
    // All button logic is driven by activeOrder.status from the live stream.
    // No local variable. No optimistic state.
    if (activeOrder.status == 'placed') {
      return Row(
        children: [
          Expanded(child: OutlinedButton(
            onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(activeOrder, 'rejected'),
            style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Reject'),
          )),
          const SizedBox(width: 16),
          Expanded(child: ElevatedButton(
            onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(activeOrder, 'accepted'),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
            child: const Text('Accept'),
          )),
        ],
      );
    }

    String nextLabel = '';
    String nextStatus = '';
    if (activeOrder.status == 'accepted') { nextLabel = 'Mark as Preparing'; nextStatus = 'preparing'; }
    else if (activeOrder.status == 'preparing') { nextLabel = 'Mark as Ready'; nextStatus = 'ready'; }
    else if (activeOrder.status == 'ready') { nextLabel = 'Mark as Delivered'; nextStatus = 'delivered'; }

    if (nextLabel.isEmpty) return const SizedBox.shrink();

    return ElevatedButton(
      onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(activeOrder, nextStatus),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 16),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
      ),
      child: Text(nextLabel, style: const TextStyle(fontSize: 16)),
    );
  }

  Widget _buildTimeline(activeOrder) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Status History', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const Divider(),
            ...activeOrder.statusHistory.map((history) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  const Icon(Icons.history, size: 16, color: Colors.grey),
                  const SizedBox(width: 8),
                  Text(history.status.toUpperCase(), style: const TextStyle(fontWeight: FontWeight.bold)),
                  const Spacer(),
                  Text(DateFormat('MMM dd, hh:mm a').format(history.timestamp), style: const TextStyle(color: Colors.grey, fontSize: 12)),
                ],
              ),
            )),
          ],
        ),
      ),
    );
  }
}
