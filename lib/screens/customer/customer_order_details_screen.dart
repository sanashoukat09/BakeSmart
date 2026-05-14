import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../providers/customer_order_provider.dart';
import '../../providers/auth_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';

class CustomerOrderDetailsScreen extends ConsumerWidget {
  final String orderId;
  const CustomerOrderDetailsScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(customerOrdersProvider);

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: const Text('Order Tracking'),
        elevation: 0,
      ),
      body: ordersAsync.when(
        data: (orders) {
          final matchingOrders = orders.where((o) => o.id == orderId).toList();
          if (matchingOrders.isEmpty) {
            return const Center(child: Text('Order not found.'));
          }

          return _OrderDetailsBody(order: matchingOrders.first);
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}

class _OrderDetailsBody extends ConsumerStatefulWidget {
  final OrderModel order;
  const _OrderDetailsBody({required this.order});

  @override
  ConsumerState<_OrderDetailsBody> createState() => _OrderDetailsBodyState();
}

class _OrderDetailsBodyState extends ConsumerState<_OrderDetailsBody> {
  bool _isCancelling = false;

  bool get _canCancelOrder => widget.order.status == AppConstants.orderPlaced;

  Future<void> _handleCancelOrder() async {
    if (!_canCancelOrder) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('This order cannot be cancelled at its current stage.')),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text('Cancel Order?'),
        content: const Text('Are you sure you want to cancel this order? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep Order'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel Order', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isCancelling = true);

    try {
      await ref.read(firestoreServiceProvider).updateOrderStatusWithAtomicInventory(
        orderId: widget.order.id,
        newStatus: AppConstants.orderCancelled,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Order cancelled successfully')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error cancelling order: $e')),
      );
    } finally {
      if (mounted) setState(() => _isCancelling = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Order #${widget.order.id.substring(0, 8).toUpperCase()}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
          const SizedBox(height: 8),
          Text(DateFormat('MMM dd, yyyy • hh:mm a').format(widget.order.createdAt), style: const TextStyle(color: Colors.grey)),
          const Divider(height: 48),

          const Text('Track Order', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 24),
          _StatusTimeline(currentStatus: widget.order.status),
          const Divider(height: 48),

          const Text('Items', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 16),
          ...widget.order.items.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${item.quantity}x ${item.productName}'),
                Text('Rs. ${(item.price * item.quantity).toStringAsFixed(0)}'),
              ],
            ),
          )),
          const Divider(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Total Amount', style: TextStyle(fontWeight: FontWeight.bold)),
              Text('Rs. ${widget.order.totalAmount.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Color(0xFFD97706))),
            ],
          ),

          const SizedBox(height: 40),
          if (widget.order.status == AppConstants.orderPlaced)
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: _isCancelling ? null : _handleCancelOrder,
                style: OutlinedButton.styleFrom(foregroundColor: Colors.red, side: const BorderSide(color: Colors.red)),
                child: _isCancelling
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Cancel Order'),
              ),
            ),
          
          if (widget.order.status == AppConstants.orderDelivered && !widget.order.isReviewed)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => context.push('${AppRoutes.customerSubmitReview}/${widget.order.id}'),
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFD97706), foregroundColor: Colors.white),
                child: const Text('Rate & Review'),
              ),
            ),
          
          if (widget.order.isReviewed)
            const Center(
              child: Padding(
                padding: EdgeInsets.only(top: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.check_circle_outline, color: Colors.green, size: 20),
                    SizedBox(width: 8),
                    Text('Order Reviewed', style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _StatusTimeline extends StatelessWidget {
  final String currentStatus;
  const _StatusTimeline({required this.currentStatus});

  @override
  Widget build(BuildContext context) {
    final statuses = [
      AppConstants.orderPlaced,
      AppConstants.orderAccepted,
      AppConstants.orderPreparing,
      AppConstants.orderReady,
      AppConstants.orderDelivered,
    ];

    final labels = [
      'Order Placed',
      'Accepted',
      'Preparing',
      'Ready for Pickup/Delivery',
      'Delivered',
    ];

    int currentIndex = statuses.indexOf(currentStatus);
    if (currentStatus == AppConstants.orderRejected) currentIndex = -1;

    return Column(
      children: List.generate(statuses.length, (i) {
        final isCompleted = i <= currentIndex;
        final isLast = i == statuses.length - 1;

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Column(
              children: [
                Container(
                  width: 24,
                  height: 24,
                  decoration: BoxDecoration(
                    color: isCompleted ? const Color(0xFF10B981) : Colors.grey[200],
                    shape: BoxShape.circle,
                  ),
                  child: isCompleted ? const Icon(Icons.check, size: 14, color: Colors.white) : null,
                ),
                if (!isLast)
                  Container(
                    width: 2,
                    height: 40,
                    color: isCompleted ? const Color(0xFF10B981) : Colors.grey[200],
                  ),
              ],
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    labels[i],
                    style: TextStyle(
                      fontWeight: i == currentIndex ? FontWeight.bold : FontWeight.normal,
                      color: isCompleted ? Colors.black : Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 4),
                  if (i == currentIndex)
                    const Text('Current status', style: TextStyle(fontSize: 11, color: Color(0xFFD97706))),
                ],
              ),
            ),
          ],
        );
      }),
    );
  }
}
