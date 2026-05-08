import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../providers/auth_provider.dart';
import '../../core/constants/app_constants.dart';
import '../../core/theme/baker_theme.dart';


class BakerDashboard extends ConsumerStatefulWidget {
  const BakerDashboard({super.key});

  @override
  ConsumerState<BakerDashboard> createState() => _BakerDashboardState();
}

class _BakerDashboardState extends ConsumerState<BakerDashboard> {
  int _currentIndex = 0;

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
          bottomNavigationBar: Container(
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(
                top: BorderSide(color: BakerTheme.divider, width: 1.5),

              ),
            ),
            child: BottomNavigationBar(
              currentIndex: _currentIndex,
              onTap: (i) {
                setState(() => _currentIndex = i);
                if (i == 1) context.push(AppRoutes.bakerProducts);
                if (i == 2) context.push(AppRoutes.bakerOrders);
                if (i == 3) context.push(AppRoutes.bakerEarnings);
                if (i == 4) context.push(AppRoutes.bakerProfile);
              },
              backgroundColor: Colors.transparent,
              elevation: 0,
              selectedItemColor: BakerTheme.primary,

              unselectedItemColor: const Color(0xFFA8A29E),
              showSelectedLabels: true,
              showUnselectedLabels: true,
              type: BottomNavigationBarType.fixed,
              items: const [
                BottomNavigationBarItem(
                  icon: Icon(Icons.dashboard_outlined),
                  activeIcon: Icon(Icons.dashboard),
                  label: 'Dashboard',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.inventory_2_outlined),
                  activeIcon: Icon(Icons.inventory_2),
                  label: 'Products',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.receipt_long_outlined),
                  activeIcon: Icon(Icons.receipt_long),
                  label: 'Orders',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.bar_chart_outlined),
                  activeIcon: Icon(Icons.bar_chart),
                  label: 'Analytics',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.person_outline),
                  activeIcon: Icon(Icons.person),
                  label: 'Profile',
                ),
              ],
            ),
          ),
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
    final bakerySlug = (user.bakeryName ?? 'bakery')
        .toLowerCase()
        .replaceAll(RegExp(r'\s+'), '-')
        .replaceAll(RegExp(r'[^a-z0-9-]'), '');
    final storefrontUrl = '$bakerySlug/bakesmart.com';

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
                  value: '0',
                  icon: Icons.receipt_long_outlined,
                  color: BakerTheme.secondary,
                  onTap: () => context.push(AppRoutes.bakerEarnings),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _StatCard(
                  label: 'Products',
                  value: '0',
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
                  value: 'Rs. 0',
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

          // Recent orders placeholder
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
                        color: BakerTheme.textSecondary, fontWeight: FontWeight.w700)),

              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: BakerTheme.divider, width: 1.5),

            ),
            child: Center(
              child: Column(
                children: [
                  const Icon(Icons.receipt_long_outlined,
                      color: BakerTheme.divider, size: 48),

                  const SizedBox(height: 12),
                  const Text(
                    'No orders yet',
                    style: TextStyle(
                      color: BakerTheme.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),

                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Orders will appear here once customers start ordering.',
                    textAlign: TextAlign.center,
                    style:
                        const TextStyle(color: BakerTheme.textSecondary, fontSize: 13),

                  ),
                ],
              ),
            ),
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
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: BakerTheme.divider.withOpacity(0.4),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: BakerTheme.divider, width: 1.5),
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: BakerTheme.divider),
              ),
              child: Icon(icon, color: BakerTheme.primary, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    value,
                    style: const TextStyle(
                      color: BakerTheme.textPrimary,
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    label,
                    style: const TextStyle(
                      color: BakerTheme.textSecondary,
                      fontSize: 13,
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
