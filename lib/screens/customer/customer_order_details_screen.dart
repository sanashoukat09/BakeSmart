import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../providers/customer_order_provider.dart';
import '../../providers/auth_provider.dart';
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

class CustomerOrderDetailsScreen extends ConsumerWidget {
  final String orderId;
  const CustomerOrderDetailsScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(customerOrdersProvider);

    return Scaffold(
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
          'Order Tracking',
          style: TextStyle(
            color: _T.ink,
            fontWeight: FontWeight.w800,
            fontSize: 19,
          ),
        ),
      ),
      body: ordersAsync.when(
        data: (orders) {
          final matchingOrders = orders.where((o) => o.id == orderId).toList();
          if (matchingOrders.isEmpty) {
            return const Center(
              child: Text(
                'Order not found.', 
                style: TextStyle(color: _T.ink, fontWeight: FontWeight.bold),
              ),
            );
          }

          return _OrderDetailsBody(order: matchingOrders.first);
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.brown)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusRed))),
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
        backgroundColor: _T.canvas,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: const Text(
          'Cancel Order?', 
          style: TextStyle(color: _T.ink, fontWeight: FontWeight.w800),
        ),
        content: const Text(
          'Are you sure you want to cancel this order? This action cannot be undone.',
          style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep Order', style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.bold)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel Order', style: TextStyle(color: _T.statusRed, fontWeight: FontWeight.bold)),
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
        const SnackBar(content: Text('Order cancelled successfully ✓')),
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
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Order ID Card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _T.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _T.rimLight, width: 1.5),
              boxShadow: _T.shadowSm,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Order #${widget.order.id.substring(0, 8).toUpperCase()}',
                      style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17, color: _T.ink),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: widget.order.status == AppConstants.orderCancelled || widget.order.status == AppConstants.orderRejected
                            ? _T.statusRed.withOpacity(0.08)
                            : _T.statusGreen.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        widget.order.status.toUpperCase(),
                        style: TextStyle(
                          color: widget.order.status == AppConstants.orderCancelled || widget.order.status == AppConstants.orderRejected
                              ? _T.statusRed
                              : _T.statusGreen,
                          fontSize: 9,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  DateFormat('MMM dd, yyyy • hh:mm a').format(widget.order.createdAt),
                  style: const TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600, fontSize: 13),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Track Order Section
          const Text(
            'Track Order', 
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: _T.ink),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _T.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _T.rimLight, width: 1.5),
              boxShadow: _T.shadowSm,
            ),
            child: _StatusTimeline(currentStatus: widget.order.status),
          ),
          const SizedBox(height: 24),

          // Items Summary Section
          const Text(
            'Items Summary', 
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: _T.ink),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _T.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _T.rimLight, width: 1.5),
              boxShadow: _T.shadowSm,
            ),
            child: Column(
              children: [
                ...widget.order.items.map((item) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${item.quantity}x ${item.productName}',
                        style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w700, fontSize: 14),
                      ),
                      Text(
                        'Rs. ${(item.price * item.quantity).toStringAsFixed(0)}',
                        style: const TextStyle(color: _T.inkMid, fontWeight: FontWeight.w700, fontSize: 14),
                      ),
                    ],
                  ),
                )),
                const Divider(color: _T.rimLight, thickness: 1.5, height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Total Amount', 
                      style: TextStyle(fontWeight: FontWeight.w900, color: _T.ink, fontSize: 14.5),
                    ),
                    Text(
                      'Rs. ${widget.order.totalAmount.toStringAsFixed(0)}',
                      style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 18, color: _T.statusPink),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 36),
          if (widget.order.status == AppConstants.orderPlaced)
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: _isCancelling ? null : _handleCancelOrder,
                style: OutlinedButton.styleFrom(
                  foregroundColor: _T.statusRed,
                  side: const BorderSide(color: _T.statusRed, width: 1.5),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                child: _isCancelling
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: _T.statusRed))
                    : const Text('Cancel Order', style: TextStyle(fontWeight: FontWeight.w800)),
              ),
            ),
          
          if (widget.order.status == AppConstants.orderDelivered && !widget.order.isReviewed)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => context.push('${AppRoutes.customerSubmitReview}/${widget.order.id}'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _T.brown, 
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  elevation: 0,
                ),
                child: const Text('Rate & Review', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
              ),
            ),
          
          if (widget.order.isReviewed)
            Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: _T.statusGreen.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.check_circle_outline_rounded, color: _T.statusGreen, size: 20),
                    SizedBox(width: 8),
                    Text('Order Reviewed ✓', style: TextStyle(color: _T.statusGreen, fontWeight: FontWeight.w800, fontSize: 13.5)),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 40),
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
    if (currentStatus == AppConstants.orderRejected || currentStatus == AppConstants.orderCancelled) currentIndex = -1;

    return Column(
      children: List.generate(statuses.length, (i) {
        final isCompleted = i <= currentIndex && currentIndex != -1;
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
                    color: isCompleted ? _T.statusGreen : _T.rimLight,
                    shape: BoxShape.circle,
                  ),
                  child: isCompleted ? const Icon(Icons.check, size: 14, color: Colors.white) : null,
                ),
                if (!isLast)
                  Container(
                    width: 2,
                    height: 40,
                    color: isCompleted ? _T.statusGreen : _T.rimLight,
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
                      fontWeight: i == currentIndex ? FontWeight.w800 : FontWeight.w600,
                      color: isCompleted ? _T.ink : _T.inkMid,
                      fontSize: 13.5,
                    ),
                  ),
                  const SizedBox(height: 4),
                  if (i == currentIndex)
                    const Text(
                      'Current status', 
                      style: TextStyle(fontSize: 11, color: _T.statusPink, fontWeight: FontWeight.w800),
                    ),
                ],
              ),
            ),
          ],
        );
      }),
    );
  }
}
