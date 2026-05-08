import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/order_provider.dart';
import '../../models/order_model.dart';
import '../../core/constants/app_constants.dart';
import '../../core/theme/baker_theme.dart';


class OrderDetailsScreen extends ConsumerWidget {
  final String orderId;
  const OrderDetailsScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersProvider);

    return Scaffold(
      backgroundColor: BakerTheme.background,

      appBar: AppBar(
        backgroundColor: BakerTheme.background,
        title: const Text('Order Details', style: TextStyle(color: BakerTheme.textPrimary)),
        elevation: 0,
        iconTheme: const IconThemeData(color: BakerTheme.textPrimary),

      ),
      body: ordersAsync.when(
        data: (orders) {
          final order = orders.firstWhere((o) => o.id == orderId);
          return _OrderDetailsBody(order: order);
        },
        loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFFF59E0B))),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}

class _OrderDetailsBody extends ConsumerWidget {
  final OrderModel order;
  const _OrderDetailsBody({required this.order});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isUpdating = ref.watch(orderNotifierProvider).isLoading;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header info
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Order #${order.id.substring(0, 8).toUpperCase()}',
                      style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 13)),
                  const SizedBox(height: 4),
                  Text(DateFormat('MMM dd, yyyy • hh:mm a').format(order.createdAt),
                      style: const TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold)),

                ],
              ),
              _StatusBadge(status: order.status),
            ],
          ),
          const SizedBox(height: 24),

          // Status Actions
          if (order.status != AppConstants.orderDelivered && order.status != AppConstants.orderRejected) ...[
            const Text('Update Status', style: TextStyle(color: BakerTheme.textSecondary, fontSize: 12, fontWeight: FontWeight.bold)),

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
                Text(order.customerName, style: const TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold)),
                Text(order.customerPhone, style: const TextStyle(color: BakerTheme.textSecondary)),
                const SizedBox(height: 8),
                Text('Delivery Address:', style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12)),
                Text(order.deliveryAddress, style: const TextStyle(color: BakerTheme.textPrimary)),

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
                    Text(order.customerNote!, style: const TextStyle(color: BakerTheme.textPrimary)),

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
                            borderRadius: BorderRadius.circular(8),
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
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: BakerTheme.divider),

            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Total Amount', style: TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold)),
                Text('Rs. ${order.totalAmount.toStringAsFixed(0)}',
                    style: const TextStyle(color: BakerTheme.secondary, fontSize: 20, fontWeight: FontWeight.bold)),

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
          color: const Color(0xFF10B981),
          onTap: () => _update(ref, AppConstants.orderAccepted),
          isUpdating: isUpdating,
        ),
        const SizedBox(width: 12),
        _ActionButton(
          label: 'Reject',
          color: const Color(0xFFEF4444),
          onTap: () => _update(ref, AppConstants.orderRejected),
          isUpdating: isUpdating,
          outlined: true,
        ),
      ];
    } else if (order.status == AppConstants.orderAccepted) {
      actions = [
        _ActionButton(
          label: 'Start Preparing',
          color: const Color(0xFF8B5CF6),
          onTap: () => _update(ref, AppConstants.orderPreparing),
          isUpdating: isUpdating,
        ),
      ];
    } else if (order.status == AppConstants.orderPreparing) {
      actions = [
        _ActionButton(
          label: 'Mark as Ready',
          color: const Color(0xFF10B981),
          onTap: () => _update(ref, AppConstants.orderReady),
          isUpdating: isUpdating,
        ),
      ];
    } else if (order.status == AppConstants.orderReady) {
      actions = [
        _ActionButton(
          label: 'Confirm Delivery',
          color: const Color(0xFF3B82F6),
          onTap: () => _update(ref, AppConstants.orderDelivered),
          isUpdating: isUpdating,
        ),
      ];
    }

    return Row(children: actions);
  }

  void _update(WidgetRef ref, String status) {
    ref.read(orderNotifierProvider.notifier).updateStatus(order.id, status);
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
                  side: BorderSide(color: color),
                  foregroundColor: color,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                child: Text(label),
              )
            : ElevatedButton(
                onPressed: isUpdating ? null : onTap,
                style: ElevatedButton.styleFrom(
                  backgroundColor: color,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                child: isUpdating ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : Text(label),
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
            Icon(icon, color: BakerTheme.textSecondary, size: 16),
            const SizedBox(width: 8),
            Text(title, style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12, fontWeight: FontWeight.bold)),

          ],
        ),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: BakerTheme.divider),

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
            child: Text('${item.quantity}x ${item.productName}', style: const TextStyle(color: BakerTheme.textPrimary)),

          ),
          Text('Rs. ${(item.price * item.quantity).toStringAsFixed(0)}', style: const TextStyle(color: BakerTheme.textSecondary)),

        ],
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
      case AppConstants.orderPlaced: color = const Color(0xFFF59E0B); break;
      case AppConstants.orderAccepted: color = const Color(0xFF3B82F6); break;
      case AppConstants.orderPreparing: color = const Color(0xFF8B5CF6); break;
      case AppConstants.orderReady: color = const Color(0xFF10B981); break;
      case AppConstants.orderDelivered: color = const Color(0xFF484F58); break;
      case AppConstants.orderRejected: color = const Color(0xFFEF4444); break;
      default: color = const Color(0xFF8B949E);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(20), border: Border.all(color: color.withOpacity(0.3))),
      child: Text(status.toUpperCase(), style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
    );
  }
}
