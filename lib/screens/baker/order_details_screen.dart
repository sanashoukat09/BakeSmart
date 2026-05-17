import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/order_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';

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

class OrderDetailsScreen extends ConsumerWidget {
  final String orderId;
  const OrderDetailsScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        title: const Text(
          'Order Details', 
          style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        elevation: 0,
        iconTheme: const IconThemeData(color: _T.brown),
      ),
      body: ordersAsync.when(
        data: (orders) {
          final order = orders.firstWhere((o) => o.id == orderId);
          return _OrderDetailsBody(order: order);
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
      ),
    );
  }
}

class _OrderDetailsBody extends ConsumerWidget {
  final OrderModel order;
  const _OrderDetailsBody({required this.order});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sc = _statusConfig(order.status);
    final isUpdating = ref.watch(orderNotifierProvider).isLoading;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header info card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _T.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _T.rimLight, width: 1.5),
              boxShadow: _T.shadowSm,
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Order #${order.id.substring(0, 8).toUpperCase()}',
                      style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      DateFormat('MMM dd, yyyy • hh:mm a').format(order.createdAt),
                      style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 15),
                    ),
                  ],
                ),
                // Status Badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
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
          ),
          const SizedBox(height: 24),

          // Status Actions
          if (order.status != AppConstants.orderDelivered && order.status != AppConstants.orderRejected) ...[
            const Text(
              'Update Status', 
              style: TextStyle(color: _T.taupe, fontSize: 12, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _StatusActions(order: order, isUpdating: isUpdating),
            const SizedBox(height: 24),
          ],

          // Customer Info
          _InfoSection(
            title: 'Customer Details',
            icon: Icons.person_outline,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  order.customerName, 
                  style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 16),
                ),
                const SizedBox(height: 4),
                Text(
                  order.customerPhone, 
                  style: const TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600, fontSize: 13),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Delivery Address:', 
                  style: TextStyle(color: _T.inkFaint, fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.3),
                ),
                const SizedBox(height: 4),
                Text(
                  order.deliveryAddress, 
                  style: const TextStyle(color: _T.ink, fontSize: 14, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Order Items
          _InfoSection(
            title: 'Items',
            icon: Icons.shopping_basket_outlined,
            child: Column(
              children: order.items.map((item) => _OrderItemRow(item: item)).toList(),
            ),
          ),
          const SizedBox(height: 20),

          // Customization
          if (order.customerNote != null || order.referencePhotos.isNotEmpty)
            _InfoSection(
              title: 'Customization Notes',
              icon: Icons.edit_note_outlined,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (order.customerNote != null)
                    Text(
                      order.customerNote!, 
                      style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
                    ),
                  if (order.referencePhotos.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    SizedBox(
                      height: 100,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        itemCount: order.referencePhotos.length,
                        itemBuilder: (context, i) => Container(
                          margin: const EdgeInsets.only(right: 8),
                          width: 100,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: _T.rimLight, width: 1.5),
                            image: DecorationImage(image: NetworkImage(order.referencePhotos[i]), fit: BoxFit.cover),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          const SizedBox(height: 20),

          // Total
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _T.pinkL.withOpacity(0.4),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _T.pink.withOpacity(0.2), width: 1.5),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Total Amount', 
                  style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 15),
                ),
                Text(
                  'Rs. ${order.totalAmount.toStringAsFixed(0)}',
                  style: const TextStyle(color: _T.statusGreen, fontSize: 20, fontWeight: FontWeight.w900),
                ),
              ],
            ),
          ),
          const SizedBox(height: 40),
        ],
      ),
    );
  }
}

class _StatusActions extends ConsumerWidget {
  final OrderModel order;
  final bool isUpdating;
  const _StatusActions({required this.order, required this.isUpdating});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    List<Widget> actions = [];

    if (order.status == AppConstants.orderPlaced) {
      actions = [
        _ActionButton(
          label: 'Accept Order',
          color: _T.statusGreen,
          onTap: () => _update(context, ref, AppConstants.orderAccepted),
          isUpdating: isUpdating,
        ),
        const SizedBox(width: 12),
        _ActionButton(
          label: 'Reject',
          color: _T.statusPink,
          onTap: () => _update(context, ref, AppConstants.orderRejected),
          isUpdating: isUpdating,
          outlined: true,
        ),
      ];
    } else if (order.status == AppConstants.orderAccepted) {
      actions = [
        _ActionButton(
          label: 'Start Preparing',
          color: _T.copper,
          onTap: () => _update(context, ref, AppConstants.orderPreparing),
          isUpdating: isUpdating,
        ),
      ];
    } else if (order.status == AppConstants.orderPreparing) {
      actions = [
        _ActionButton(
          label: 'Mark as Ready',
          color: _T.statusGreen,
          onTap: () => _update(context, ref, AppConstants.orderReady),
          isUpdating: isUpdating,
        ),
      ];
    } else if (order.status == AppConstants.orderReady) {
      actions = [
        _ActionButton(
          label: 'Confirm Delivery',
          color: _T.brown,
          onTap: () => _update(context, ref, AppConstants.orderDelivered),
          isUpdating: isUpdating,
        ),
      ];
    }

    return Row(children: actions);
  }

  Future<void> _update(BuildContext context, WidgetRef ref, String status) async {
    try {
      await ref.read(orderNotifierProvider.notifier).updateStatus(order.id, status);
    } catch (e) {
      final message = e is Exception ? e.toString() : e.toString();
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message.replaceFirst('Exception: ', '')),
          backgroundColor: _T.statusPink,
        ),
      );
    }
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onTap;
  final bool isUpdating;
  final bool outlined;

  const _ActionButton({
    required this.label,
    required this.color,
    required this.onTap,
    required this.isUpdating,
    this.outlined = false,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: SizedBox(
        height: 48,
        child: outlined
            ? OutlinedButton(
                onPressed: isUpdating ? null : onTap,
                style: OutlinedButton.styleFrom(
                  side: BorderSide(color: color, width: 1.5),
                  foregroundColor: color,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
              )
            : ElevatedButton(
                onPressed: isUpdating ? null : onTap,
                style: ElevatedButton.styleFrom(
                  backgroundColor: color,
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: isUpdating 
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) 
                  : Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
              ),
      ),
    );
  }
}

class _InfoSection extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;

  const _InfoSection({required this.title, required this.icon, required this.child});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: _T.copper, size: 16),
            const SizedBox(width: 8),
            Text(
              title, 
              style: const TextStyle(color: _T.brown, fontSize: 12.5, fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: _T.surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _T.rimLight, width: 1.5),
            boxShadow: _T.shadowSm,
          ),
          child: child,
        ),
      ],
    );
  }
}

class _OrderItemRow extends StatelessWidget {
  final OrderItem item;
  const _OrderItemRow({required this.item});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Text(
              '${item.quantity}x ${item.productName}', 
              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w700),
            ),
          ),
          Text(
            'Rs. ${(item.price * item.quantity).toStringAsFixed(0)}', 
            style: const TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600),
          ),
        ],
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
