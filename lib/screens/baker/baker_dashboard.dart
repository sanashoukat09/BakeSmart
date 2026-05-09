import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../providers/auth_provider.dart';
import '../../providers/order_provider.dart';
import '../../providers/product_provider.dart';
import '../../core/constants/app_constants.dart';
import '../../core/theme/baker_theme.dart';
import '../../widgets/baker/baker_bottom_nav.dart';


class BakerDashboard extends ConsumerStatefulWidget {
  const BakerDashboard({super.key});

  @override
  ConsumerState<BakerDashboard> createState() => _BakerDashboardState();
}

class _BakerDashboardState extends ConsumerState<BakerDashboard> {
  @override
  Widget build(BuildContext context) {
    final userAsync = ref.watch(currentUserProvider);

    return userAsync.when(
      loading: () => const Scaffold(
        backgroundColor: BakerTheme.background,

        body: Center(
            child: CircularProgressIndicator(color: BakerTheme.secondary)),

      ),
      error: (e, _) => Scaffold(
        backgroundColor: BakerTheme.background,

        body: Center(child: Text('Error: $e')),
      ),
      data: (user) {
        if (user == null) return const SizedBox.shrink();

        return Scaffold(
          backgroundColor: BakerTheme.background,

          appBar: AppBar(
            backgroundColor: BakerTheme.background,

            elevation: 0,
            toolbarHeight: 80,
            title: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: BakerTheme.divider, width: 1.5),

                  ),
                  child: const Center(
                    child: Icon(Icons.bakery_dining_rounded,
                        color: BakerTheme.primary, size: 28),

                  ),
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'BakeSmart',
                      style: TextStyle(
                        color: BakerTheme.textPrimary,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.5,
                      ),

                    ),
                    Text(
                      user.bakeryName ?? 'Your Bakery',
                      style: const TextStyle(
                        color: BakerTheme.textSecondary,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),

                    ),
                  ],
                ),
              ],
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined,
                    color: BakerTheme.textSecondary),

                onPressed: () {},
              ),
              const SizedBox(width: 8),
            ],
          ),
          body: _DashboardHome(user: user),
          bottomNavigationBar: const BakerBottomNav(currentIndex: 0),
        );
      },
    );
  }
}

class _DashboardHome extends ConsumerWidget {
  final dynamic user;
  const _DashboardHome({required this.user});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bakerOrdersProvider);
    final productsAsync = ref.watch(bakerProductsProvider);
    final earningsAsync = ref.watch(totalEarningsProvider);

    final bakerySlug = (user.bakeryName ?? 'bakery')
        .toLowerCase()
        .replaceAll(RegExp(r'\s+'), '-')
        .replaceAll(RegExp(r'[^a-z0-9-]'), '');
    final storefrontUrl = '$bakerySlug/bakesmart.com';

    final today = DateTime.now();
    final todaysOrders = ordersAsync.valueOrNull?.where((o) =>
            o.createdAt.year == today.year &&
            o.createdAt.month == today.month &&
            o.createdAt.day == today.day) ??
        [];
    final productCount = productsAsync.valueOrNull?.length ?? 0;
    final totalEarnings = earningsAsync.valueOrNull ?? 0.0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Greeting
          RichText(
            text: TextSpan(
              text: 'Good day, ',
              style: const TextStyle(
                color: BakerTheme.textPrimary,
                fontSize: 24,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
              ),

              children: [
                TextSpan(
                  text: '${user.displayName?.split(' ').first ?? 'Baker'} 👋',
                  style: const TextStyle(
                    color: BakerTheme.textSecondary,
                    fontWeight: FontWeight.w800,
                  ),

                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Stats row
          Row(
            children: [
              Expanded(
                child: _StatCard(
                  label: "Today's Orders",
                  value: todaysOrders.length.toString(),
                  icon: Icons.receipt_long_outlined,
                  color: BakerTheme.secondary,
                  onTap: () => context.push(AppRoutes.bakerEarnings),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _StatCard(
                  label: 'Products',
                  value: productCount.toString(),
                  icon: Icons.cake_outlined,
                  color: const Color(0xFF10B981),
                  onTap: () => context.push(AppRoutes.bakerProducts),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _StatCard(
                  label: 'Rating',
                  value: user.rating > 0 ? user.rating.toStringAsFixed(1) : '—',
                  icon: Icons.star_outline,
                  color: const Color(0xFF818CF8),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _StatCard(
                  label: 'Earnings',
                  value: 'Rs. ${NumberFormat.compact().format(totalEarnings)}',
                  icon: Icons.account_balance_wallet_outlined,
                  color: const Color(0xFFF97316),
                  onTap: () => context.push(AppRoutes.bakerEarnings),
                ),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // Quick actions
          const Text(
            'Quick Actions',
            style: TextStyle(
              color: BakerTheme.textPrimary,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),

          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _QuickAction(
                icon: Icons.add_circle_outline,
                label: 'Add Product',
                color: const Color(0xFF16A34A), // Green
                onTap: () => context.push(AppRoutes.bakerAddProduct),
              ),
              const SizedBox(width: 12),
              _QuickAction(
                icon: Icons.receipt_long_outlined,
                label: 'View Orders',
                color: const Color(0xFFEA580C), // Orange
                onTap: () => context.push(AppRoutes.bakerOrders),
              ),
              const SizedBox(width: 12),
              _QuickAction(
                icon: Icons.kitchen_outlined,
                label: 'Inventory',
                color: const Color(0xFF7C3AED), // Purple
                onTap: () => context.push(AppRoutes.bakerInventory),
              ),
              const SizedBox(width: 12),
              _QuickAction(
                icon: Icons.local_offer_outlined,
                label: 'Surplus',
                color: const Color(0xFF7F1D1D), // Maroon
                onTap: () => context.push(AppRoutes.bakerSurplus),
              ),
            ],
          ),

          const SizedBox(height: 24),
          // Storefront URL
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: BakerTheme.divider.withOpacity(0.5),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: BakerTheme.divider, width: 1.5),

            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Your Storefront',
                  style: TextStyle(
                    color: BakerTheme.textPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),

                ),
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE7E5E4).withOpacity(0.3),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(
                    child: Text(
                      storefrontUrl,
                      style: const TextStyle(
                        color: BakerTheme.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),

                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: _ActionChip(
                        icon: Icons.copy_rounded,
                        label: 'Copy',
                        onTap: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('Storefront URL copied!')),
                          );
                        },
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _ActionChip(
                        icon: Icons.share_rounded,
                        label: 'Share',
                        onTap: () => ShareUtil.shareStore(
                          bakerName: user.bakeryName ?? 'Your Bakery',
                          bakerId: user.uid,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _ActionChip(
                        icon: Icons.camera_alt_outlined,
                        label: 'Socials',
                        onTap: () {},
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Recent orders
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Recent Orders',
                style: TextStyle(
                  color: BakerTheme.textPrimary,
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
              TextButton(
                onPressed: () => context.push(AppRoutes.bakerOrders),
                child: const Text('View all',
                    style: TextStyle(
                        color: BakerTheme.textSecondary,
                        fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ordersAsync.when(
            data: (orders) {
              if (orders.isEmpty) {
                return Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: BakerTheme.divider, width: 1.5),
                  ),
                  child: const Center(
                    child: Column(
                      children: [
                        Icon(Icons.receipt_long_outlined,
                            color: BakerTheme.divider, size: 48),
                        SizedBox(height: 12),
                        Text(
                          'No orders yet',
                          style: TextStyle(
                            color: BakerTheme.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        SizedBox(height: 4),
                        Text(
                          'Orders will appear here once customers start ordering.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              color: BakerTheme.textSecondary, fontSize: 13),
                        ),
                      ],
                    ),
                  ),
                );
              }

              final recentOrders = orders.toList()
                ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
              final top3 = recentOrders.take(3).toList();

              return Column(
                children: top3.map((order) {
                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: BakerTheme.divider, width: 1.5),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 45,
                          height: 45,
                          decoration: BoxDecoration(
                            color: BakerTheme.primary.withOpacity(0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.shopping_bag_outlined,
                              color: BakerTheme.primary, size: 20),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                order.customerName,
                                style: const TextStyle(
                                    color: BakerTheme.textPrimary,
                                    fontWeight: FontWeight.w800,
                                    fontSize: 15),
                              ),
                              Text(
                                '${order.items.length} items • Rs. ${order.totalAmount}',
                                style: const TextStyle(
                                    color: BakerTheme.textSecondary,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: _getStatusColor(order.status).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            order.status.toUpperCase(),
                            style: TextStyle(
                                color: _getStatusColor(order.status),
                                fontSize: 10,
                                fontWeight: FontWeight.w800),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              );
            },
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text('Error: $e'),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        decoration: BoxDecoration(
          color: BakerTheme.divider.withOpacity(0.4),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: BakerTheme.divider, width: 1.5),
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: BakerTheme.divider),
              ),
              child: Icon(icon, color: BakerTheme.primary, size: 18),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    value,
                    style: const TextStyle(
                      color: BakerTheme.textPrimary,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    label,
                    style: const TextStyle(
                      color: BakerTheme.textSecondary,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Column(
          children: [
            Container(
              height: 70,
              width: double.infinity,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: Colors.white, size: 28),
            ),
            const SizedBox(height: 8),
            Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                height: 1.1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ActionChip(
      {required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFFD4A373).withOpacity(0.6),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Center(
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}

Color _getStatusColor(String status) {
  switch (status.toLowerCase()) {
    case 'pending':
    case 'placed':
      return const Color(0xFFF59E0B);
    case 'preparing':
      return const Color(0xFF3B82F6);
    case 'ready':
      return const Color(0xFF10B981);
    case 'delivered':
      return const Color(0xFF059669);
    case 'cancelled':
      return const Color(0xFFEF4444);
    default:
      return BakerTheme.textSecondary;
  }
}
