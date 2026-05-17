import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../providers/cart_provider.dart';
import '../../core/router/app_router.dart';
import '../../widgets/customer/customer_bottom_nav.dart';

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

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: ink.withOpacity(0.03), blurRadius: 16, offset: const Offset(0, 4)),
  ];
}

class CartScreen extends ConsumerWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cartItems = ref.watch(cartProvider);
    final cartNotifier = ref.read(cartProvider.notifier);

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          'Cart',
          style: TextStyle(
            color: _T.ink,
            fontSize: 18,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.2,
          ),
        ),
        actions: [
          if (cartItems.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined, color: _T.inkMid, size: 24),
              onPressed: () => _confirmClear(context, cartNotifier),
            ),
        ],
      ),
      body: cartItems.isEmpty
          ? const _EmptyCart()
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Playful subheader
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your Cart',
                        style: TextStyle(
                          color: _T.ink,
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.4,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        'Review your items before proceeding to checkout.',
                        style: TextStyle(
                          color: _T.inkMid,
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                
                // Cart Items List
                Expanded(
                  child: ListView.builder(
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    itemCount: cartItems.length,
                    itemBuilder: (context, i) => _CartItemTile(item: cartItems[i], notifier: cartNotifier),
                  ),
                ),
                _CartSummary(total: cartNotifier.totalAmount),
              ],
            ),
      bottomNavigationBar: const CustomerBottomNav(currentIndex: 3),
    );
  }

  void _confirmClear(BuildContext context, CartNotifier notifier) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _T.canvas,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Clear Cart?', style: TextStyle(color: _T.ink, fontWeight: FontWeight.w800)),
        content: const Text('Are you sure you want to remove all items from your cart?', style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w500)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel', style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w700)),
          ),
          TextButton(
            onPressed: () {
              notifier.clearCart();
              Navigator.pop(context);
            },
            child: const Text('Clear All', style: TextStyle(color: _T.statusRed, fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}

class _EmptyCart extends StatelessWidget {
  const _EmptyCart();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: _T.rimLight.withOpacity(0.5),
                shape: BoxShape.circle,
                border: Border.all(color: _T.rimLight, width: 1.5),
              ),
              child: const Icon(
                Icons.shopping_basket_outlined,
                size: 64,
                color: _T.inkMid,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'Your Cart is Empty',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                color: _T.ink,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.2,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Browse our menu to discover and add delicious treats to your cart.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: _T.inkMid,
                fontWeight: FontWeight.w500,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => context.go(AppRoutes.customerHome),
              style: ElevatedButton.styleFrom(
                backgroundColor: _T.brown,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 36, vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              child: const Text(
                'Browse Items',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CartItemTile extends StatelessWidget {
  final dynamic item; // CartItemModel
  final CartNotifier notifier;

  const _CartItemTile({required this.item, required this.notifier});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _T.rimLight, width: 1.2),
        boxShadow: _T.shadowSm,
      ),
      child: Row(
        children: [
          // White Frame Item Photo
          Container(
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _T.rimLight, width: 1),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: item.imageUrl != null && item.imageUrl!.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: item.imageUrl!,
                      width: 76,
                      height: 76,
                      fit: BoxFit.cover,
                      placeholder: (context, url) => Container(color: _T.rimLight),
                    )
                  : Container(
                      width: 76,
                      height: 76,
                      color: _T.rimLight,
                      child: const Icon(Icons.cake_outlined, color: _T.inkMid, size: 24),
                    ),
            ),
          ),
          const SizedBox(width: 14),
          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.productName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: _T.ink),
                ),
                if (item.selectedAddOns.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 3),
                    child: Text(
                      'Extra: ${item.selectedAddOns.join(", ")}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11, color: _T.inkMid, fontWeight: FontWeight.w600),
                    ),
                  ),
                const SizedBox(height: 8),
                Text(
                  'Rs. ${item.price.toStringAsFixed(0)}',
                  style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 14),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // Actions: Delete & Quantity pickers
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              IconButton(
                icon: const Icon(Icons.delete_outline_rounded, color: _T.inkMid, size: 20),
                onPressed: () => notifier.removeLine(item.lineKey),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  _QtyBtn(icon: Icons.remove, onTap: () => notifier.updateLineQuantity(item.lineKey, -1)),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    child: Text(
                      '${item.quantity}',
                      style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: _T.ink),
                    ),
                  ),
                  _QtyBtn(icon: Icons.add, onTap: () => notifier.updateLineQuantity(item.lineKey, 1)),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QtyBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _QtyBtn({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(5),
        decoration: BoxDecoration(
          color: Colors.white,
          shape: BoxShape.circle,
          border: Border.all(color: _T.rimLight, width: 1.2),
        ),
        child: Icon(icon, size: 12, color: _T.ink),
      ),
    );
  }
}

class _CartSummary extends StatelessWidget {
  final double total;
  const _CartSummary({required this.total});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 28),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        border: Border(top: BorderSide(color: _T.rimLight, width: 1.5)),
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Total Amount',
                  style: TextStyle(color: _T.ink, fontSize: 15, fontWeight: FontWeight.w700),
                ),
                Text(
                  'Rs. ${total.toStringAsFixed(0)}',
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: _T.brown),
                ),
              ],
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () => context.push(AppRoutes.customerCheckout),
              style: ElevatedButton.styleFrom(
                backgroundColor: _T.brown,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 50),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              child: const Text('Proceed to Checkout', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            ),
          ],
        ),
      ),
    );
  }
}
