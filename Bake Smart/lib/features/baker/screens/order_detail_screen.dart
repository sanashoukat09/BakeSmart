import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../customer/models/order_model.dart';
import '../../customer/services/order_service.dart';
import 'package:intl/intl.dart';

class OrderDetailScreen extends ConsumerWidget {
  final OrderModel order;
  const OrderDetailScreen({super.key, required this.order});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // We observe the stream to keep the order document auto-updated on this screen
    final ordersAsync = ref.watch(bakerOrdersStreamProvider);

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(title: Text('Order ${order.orderId.substring(0, 6)}'), backgroundColor: Colors.brown, foregroundColor: Colors.white),
      body: ordersAsync.when(
        data: (allOrders) {
          final activeOrder = allOrders.firstWhere((o) => o.orderId == order.orderId, orElse: () => order);
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
        error: (e,s) => const Center(child: Text('Error loading live order')),
      )
    );
  }

  Widget _buildCustomerCard(OrderModel o) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Customer Details', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const Divider(),
            Text('Name: ${o.customerName}', style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 8),
            Text('Fulfillment: ${o.fulfillmentType.toUpperCase()}', style: TextStyle(color: Colors.brown[700], fontWeight: FontWeight.bold)),
            if (o.fulfillmentType == 'delivery' && o.deliveryAddress != null) ...[
              const SizedBox(height: 8),
              Text('Address: ${o.deliveryAddress}'),
            ]
          ],
        ),
      ),
    );
  }

  Widget _buildItemsList(OrderModel o) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Order Items', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const Divider(),
            ...o.items.map((item) => Padding(
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
                Text('\$${o.totalAmount.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.brown)),
              ],
            )
          ],
        ),
      ),
    );
  }

  Widget _buildStatusActionBox(BuildContext context, WidgetRef ref, OrderModel o) {
    String nextLabel = '';
    String nextStatus = '';
    
    if (o.status == 'placed') {
      return Row(
        children: [
          Expanded(child: OutlinedButton(onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(o, 'rejected'), style: OutlinedButton.styleFrom(foregroundColor: Colors.red), child: const Text('Reject'))),
          const SizedBox(width: 16),
          Expanded(child: ElevatedButton(onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(o, 'accepted'), style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white), child: const Text('Accept'))),
        ],
      );
    } else if (o.status == 'accepted') { nextLabel = 'Mark as Preparing'; nextStatus = 'preparing'; }
    else if (o.status == 'preparing') { nextLabel = 'Mark as Ready'; nextStatus = 'ready'; }
    else if (o.status == 'ready') { nextLabel = 'Mark as Delivered'; nextStatus = 'delivered'; }
    
    if (nextLabel.isEmpty) return const SizedBox.shrink();

    return ElevatedButton(
      onPressed: () => ref.read(orderServiceProvider).updateOrderStatus(o, nextStatus),
      style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16), backgroundColor: Colors.brown, foregroundColor: Colors.white),
      child: Text(nextLabel, style: const TextStyle(fontSize: 16)),
    );
  }

  Widget _buildTimeline(OrderModel o) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Status History', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const Divider(),
            ...o.statusHistory.map((history) => Padding(
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
