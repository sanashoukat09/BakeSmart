import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../customer/models/order_model.dart';
import '../../customer/services/order_service.dart';
import '../../customer/services/cart_service.dart';
import 'write_review_screen.dart';
import 'cart_screen.dart';

class OrderTrackingScreen extends ConsumerWidget {
  final OrderModel order;
  const OrderTrackingScreen({super.key, required this.order});

  void _handleReorder(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reorder this?'),
        content: const Text('This will replace any items currently in your cart with items from this order. Continue?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: Colors.grey)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              final cartNotifier = ref.read(cartProvider.notifier);
              cartNotifier.clearCart();
              for (var item in order.items) {
                cartNotifier.addItem(item);
              }
              Navigator.push(context, MaterialPageRoute(builder: (_) => const CartScreen()));
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.brown, foregroundColor: Colors.white),
            child: const Text('Yes, Reorder'),
          )
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(title: Text('Order ${order.orderId.substring(0,6)}'), backgroundColor: Colors.brown, foregroundColor: Colors.white),
      body: Consumer(
        builder: (ctx, watchRef, _) {
          final ordersAsync = watchRef.watch(customerOrdersStreamProvider);
          return ordersAsync.when(
            data: (orders) {
              final activeOrder = orders.firstWhere((o) => o.orderId == order.orderId, orElse: () => order);
              
              if (activeOrder.status == 'rejected') {
                return _buildRejectedView(context, ref, activeOrder);
              }

              return SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildStepper(activeOrder),
                    const SizedBox(height: 32),
                    if (activeOrder.estimatedReadyTime != null) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(color: Colors.brown[50], borderRadius: BorderRadius.circular(12)),
                        child: Row(
                          children: [
                            const Icon(Icons.access_time, color: Colors.brown),
                            const SizedBox(width: 8),
                            Text('Estimated: ${TimeOfDay.fromDateTime(activeOrder.estimatedReadyTime!).format(context)}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.brown)),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                    ],
                    _buildItemsReviewList(context, activeOrder),
                  ],
                ),
              );
            },
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e,s) => Center(child: Text('Error: $e')),
          );
        }
      ),
    );
  }

  Widget _buildStepper(OrderModel activeOrder) {
    int currentStep = 0;
    switch(activeOrder.status) {
      case 'placed': currentStep = 0; break;
      case 'accepted': currentStep = 1; break;
      case 'preparing': currentStep = 2; break;
      case 'ready': currentStep = 3; break;
      case 'delivered': currentStep = 4; break;
    }

    final steps = ['Placed', 'Accepted', 'Preparing', 'Ready', 'Delivered'];

    return Stepper(
      currentStep: currentStep,
      physics: const NeverScrollableScrollPhysics(),
      steps: steps.asMap().entries.map((entry) {
        final idx = entry.key;
        final title = entry.value;
        final isActive = idx <= currentStep;
        return Step(
          title: Text(title, style: TextStyle(fontWeight: isActive ? FontWeight.bold : FontWeight.normal, color: isActive ? Colors.brown : Colors.grey)),
          content: const SizedBox.shrink(),
          isActive: isActive,
          state: idx < currentStep ? StepState.complete : idx == currentStep ? StepState.editing : StepState.indexed,
        );
      }).toList(),
      controlsBuilder: (context, details) => const SizedBox.shrink(),
    );
  }

  Widget _buildRejectedView(BuildContext context, WidgetRef ref, OrderModel activeOrder) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cancel, color: Colors.red, size: 80),
            const SizedBox(height: 24),
            const Text('Order Rejected', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.red)),
            const SizedBox(height: 16),
            const Text('Unfortunately, the baker could not accept this order at this time.', textAlign: TextAlign.center, style: TextStyle(fontSize: 16)),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () => _handleReorder(context, ref),
              icon: const Icon(Icons.refresh),
              label: const Text('Reorder Items'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                backgroundColor: Colors.brown,
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildItemsReviewList(BuildContext context, OrderModel activeOrder) {
    final isDelivered = activeOrder.status == 'delivered';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Items', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        ...activeOrder.items.map((item) => Card(
          elevation: 1,
          margin: const EdgeInsets.only(bottom: 12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${item.quantity}x ${item.productName}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      Text('\$${item.unitPrice.toStringAsFixed(2)} each', style: TextStyle(color: Colors.grey[600])),
                    ],
                  ),
                ),
                if (isDelivered)
                  OutlinedButton.icon(
                    onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WriteReviewScreen(order: activeOrder, itemToReview: item))),
                    icon: const Icon(Icons.star_border, size: 18),
                    label: const Text('Review'),
                    style: OutlinedButton.styleFrom(foregroundColor: Colors.orange, side: const BorderSide(color: Colors.orange)),
                  ),
              ],
            ),
          ),
        )),
      ]
    );
  }
}
