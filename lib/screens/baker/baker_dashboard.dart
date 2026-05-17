import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../providers/auth_provider.dart';
import '../../providers/order_provider.dart';
import '../../providers/product_provider.dart';
import '../../providers/notification_provider.dart';
import '../../widgets/baker/baker_bottom_nav.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS  —  every pixel traces back to the splash screen palette
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFDFCF9);
  static const brown     = Color(0xFF8B5A2B);
  static const taupe     = Color(0xFF5D4037);
  static const pink      = Color(0xFFFFB6C1);
  static const pinkL     = Color(0xFFFFF0F2);
  static const copper    = Color(0xFFB8794C);
  static const cream     = Color(0xFFF9F5F0);
  
  static const surface   = Color(0xFFFFFFFF);
  static const surfaceWarm = Color(0xFFFBF8F4);
  static const rimLight  = Color(0xFFEFEBE4);

  static const ink       = Color(0xFF5D4037);
  static const inkMid    = Color(0xFF8B7971);
  static const inkFaint  = Color(0xFFCFC4BC);

  // Soft accents for status and icons
  static const statusPink = Color(0xFFE598A4);
  static const statusBrown = Color(0xFF9E7E6E);
  static const statusCopper = Color(0xFFC08962);
  static const statusGreen = Color(0xFF87A18E);

  // Premium Gradients
  static const espresso  = Color(0xFF5D4037); // Matches splash screen secondary taupe
  static const espressoL = Color(0xFF8B5A2B); // Matches splash screen primary brown
  static const gEspresso = LinearGradient(
    colors: [espressoL, espresso],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );

  static const gPink = LinearGradient(
    colors: [Color(0xFFFFD1D8), Color(0xFFFFB6C1)],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );
  static const gCopper = LinearGradient(
    colors: [Color(0xFFD9A07E), Color(0xFFB8794C)],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );
  static const gGreen = LinearGradient(
    colors: [Color(0xFFB9D4B5), Color(0xFF87A18E)],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );
  static const gBrown = LinearGradient(
    colors: [Color(0xFFC7B19D), Color(0xFF9E7E6E)],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
  static List<BoxShadow> shadowMd = [
    BoxShadow(color: brown.withOpacity(0.06), blurRadius: 20, offset: const Offset(0, 8)),
  ];
  static List<BoxShadow> shadowPinkLuminous = [
    BoxShadow(color: pink.withOpacity(0.4), blurRadius: 16, offset: const Offset(0, 6)),
  ];
  static List<BoxShadow> shadowEspresso = [
    BoxShadow(color: espresso.withOpacity(0.3), blurRadius: 20, offset: const Offset(0, 8)),
  ];


  static const r12 = BorderRadius.all(Radius.circular(12));
  static const r16 = BorderRadius.all(Radius.circular(16));
  static const r20 = BorderRadius.all(Radius.circular(20));
  static const r24 = BorderRadius.all(Radius.circular(24));
}

// ════════════════════════════════════════════════════════════════════════════
//  ROOT SCREEN
// ════════════════════════════════════════════════════════════════════════════

class BakerDashboard extends ConsumerStatefulWidget {
  const BakerDashboard({super.key});

  @override
  ConsumerState<BakerDashboard> createState() => _BakerDashboardState();
}

class _BakerDashboardState extends ConsumerState<BakerDashboard> {
  @override
  Widget build(BuildContext context) {
    final userAsync = ref.watch(currentUserProvider);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.dark.copyWith(statusBarColor: Colors.transparent),
      child: userAsync.when(
        loading: () => const Scaffold(
          backgroundColor: _T.canvas,
          body: Center(child: _CopperLoader()),
        ),
        error: (e, _) => Scaffold(
          backgroundColor: _T.canvas,
          body: Center(child: Text('Error: $e')),
        ),
        data: (user) {
          if (user == null) return const SizedBox.shrink();
          return Scaffold(
            backgroundColor: _T.canvas,
            body: _DashboardBody(user: user),
            bottomNavigationBar: const BakerBottomNav(currentIndex: 0),
          );
        },
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  BODY — custom scroll view with a pinned header
// ════════════════════════════════════════════════════════════════════════════

class _DashboardBody extends ConsumerWidget {
  final dynamic user;
  const _DashboardBody({required this.user});

  String get _firstName => user.displayName?.split(' ').first ?? 'Baker';
  String get _greeting {
    final h = DateTime.now().hour;
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync   = ref.watch(bakerOrdersProvider);
    final productsAsync = ref.watch(bakerProductsProvider);
    final earningsAsync = ref.watch(totalEarningsProvider);
    final unreadCount   = ref.watch(unreadNotificationCountProvider);

    final today = DateTime.now();
    final todayOrders = ordersAsync.valueOrNull?.where((o) =>
        o.createdAt.year  == today.year  &&
        o.createdAt.month == today.month &&
        o.createdAt.day   == today.day).toList() ?? [];
    final productCount  = productsAsync.valueOrNull?.length ?? 0;
    final totalEarnings = earningsAsync.valueOrNull  ?? 0.0;

    return CustomScrollView(
      physics: const BouncingScrollPhysics(),
      slivers: [

        // ── Sticky header ─────────────────────────────────────────────────
        SliverPersistentHeader(
          pinned: true,
          delegate: _HeaderDelegate(
            user: user,
            unreadCount: unreadCount,
            topPadding: MediaQuery.of(context).padding.top,
          ),
        ),

        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
          sliver: SliverList(
            delegate: SliverChildListDelegate([

              // ── Hero greeting card ───────────────────────────────────────
              _HeroCard(
                greeting: _greeting,
                firstName: _firstName,
                bakeryName: user.bakeryName,
              ),
              const SizedBox(height: 28),

              // ── Quick Actions ────────────────────────────────────────────
              const _Label('Quick Actions'),
              const SizedBox(height: 14),
              _QuickActionsRow(),
              const SizedBox(height: 28),

              // ── Stats Overview ───────────────────────────────────────────
              const _Label('Overview'),
              const SizedBox(height: 14),
              _StatsRow(
                todayCount: todayOrders.length,
                productCount: productCount,
                rating: user.rating ?? 0.0,
                earnings: totalEarnings,
              ),
              const SizedBox(height: 28),

              // ── AI Assistant ─────────────────────────────────────────────
              _AiCard(),
              const SizedBox(height: 28),

              // ── Storefront ───────────────────────────────────────────────
              _Label('Your Storefront'),
              const SizedBox(height: 14),
              _StorefrontCard(user: user),
              const SizedBox(height: 28),

              // ── Recent orders ────────────────────────────────────────────
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const _Label('Recent Orders'),
                  GestureDetector(
                    onTap: () => context.push(AppRoutes.bakerOrders),
                    child: const Text(
                      'See all →',
                      style: TextStyle(
                        color: _T.copper,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _RecentOrdersList(ordersAsync: ordersAsync),

            ]),
          ),
        ),
      ],
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  PINNED HEADER DELEGATE
// ════════════════════════════════════════════════════════════════════════════

class _HeaderDelegate extends SliverPersistentHeaderDelegate {
  final dynamic user;
  final int unreadCount;
  final double topPadding;
  const _HeaderDelegate({required this.user, required this.unreadCount, required this.topPadding});

  @override double get minExtent => kToolbarHeight + 20 + topPadding;
  @override double get maxExtent => kToolbarHeight + 20 + topPadding;

  @override
  bool shouldRebuild(_HeaderDelegate old) =>
      old.unreadCount != unreadCount || old.user != user;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Container(
      color: _T.canvas.withOpacity(0.95),
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        left: 20,
        right: 20,
        bottom: 8,
      ),
      child: Row(
        children: [
          // Minimalist Logomark
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: _T.pinkL,
              borderRadius: BorderRadius.circular(13),
              border: Border.all(color: _T.pink, width: 1.5),
            ),
            child: const Icon(Icons.bakery_dining_rounded, color: _T.brown, size: 22),
          ),
          const SizedBox(width: 11),

          // Brand name
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'BakeSmart',
                style: TextStyle(
                  color: _T.brown,
                  fontSize: 19,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                  fontFamily: 'serif',
                  height: 1.1,
                ),
              ),
              Text(
                user.bakeryName ?? 'Your Bakery',
                style: const TextStyle(
                  color: _T.taupe,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w400,
                  letterSpacing: 0.2,
                ),
              ),
            ],
          ),

          const Spacer(),

          // Notification button
          GestureDetector(
            onTap: () => Navigator.of(context)
                .pushNamed(AppRoutes.bakerNotifications),
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: _T.surface,
                    borderRadius: BorderRadius.circular(13),
                    border: Border.all(color: _T.rimLight, width: 1.5),
                    boxShadow: _T.shadowSm,
                  ),
                  child: const Icon(
                    Icons.notifications_outlined,
                    color: _T.brown,
                    size: 21,
                  ),
                ),
                if (unreadCount > 0)
                  Positioned(
                    top: -4,
                    right: -4,
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        color: _T.pink,
                        shape: BoxShape.circle,
                        border: Border.all(color: _T.canvas, width: 2),
                      ),
                      child: Center(
                        child: Text(
                          unreadCount > 9 ? '9+' : '$unreadCount',
                          style: const TextStyle(
                            color: _T.brown,
                            fontSize: 9,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  HERO GREETING CARD  —  full-width espresso banner, mirrors splash dark card
// ════════════════════════════════════════════════════════════════════════════

class _HeroCard extends StatelessWidget {
  final String greeting;
  final String firstName;
  final String? bakeryName;
  const _HeroCard({
    required this.greeting,
    required this.firstName,
    required this.bakeryName,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      clipBehavior: Clip.antiAlias, // Important for background rings
      decoration: BoxDecoration(
        gradient: _T.gPink,
        borderRadius: _T.r24,
        boxShadow: _T.shadowPinkLuminous,
      ),
      child: Stack(
        children: [
          // Background decorative rings for depth
          Positioned(
            right: -40,
            top: -40,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _T.surface.withOpacity(0.2),
              ),
            ),
          ),
          Positioned(
            right: 40,
            bottom: -50,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _T.surface.withOpacity(0.15),
              ),
            ),
          ),

          // Main Content
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
            child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Subtle label
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _T.surface.withOpacity(0.6),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: _T.surface, width: 1.5),
                  ),
                  child: Text(
                    DateFormat('EEEE, d MMM').format(DateTime.now()),
                    style: const TextStyle(
                      color: _T.taupe,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.3,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '$greeting,',
                  style: TextStyle(
                    color: _T.taupe.withOpacity(0.8),
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '$firstName 👋',
                  style: const TextStyle(
                    color: _T.brown,
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                    fontFamily: 'serif',
                    height: 1.1,
                  ),
                ),
                if (bakeryName != null) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Container(
                        width: 6,
                        height: 6,
                        decoration: const BoxDecoration(
                          color: _T.surface,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 7),
                      Text(
                        bakeryName!,
                        style: const TextStyle(
                          color: _T.taupe,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          // Micro-animated floating icon
          const _FloatingHeroIcon(),
        ],
      ),
      ),
      ],
      ),
    );
  }
}

class _FloatingHeroIcon extends StatefulWidget {
  const _FloatingHeroIcon();
  @override
  State<_FloatingHeroIcon> createState() => _FloatingHeroIconState();
}

class _FloatingHeroIconState extends State<_FloatingHeroIcon> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 3200),
  )..repeat();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, child) {
        final floatY = -math.sin(_ctrl.value * 2 * math.pi) * 8.0;
        return Transform.translate(
          offset: Offset(0, floatY),
          child: child,
        );
      },
      child: Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          color: _T.surface.withOpacity(0.6),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _T.surface, width: 2),
          boxShadow: [
            BoxShadow(
              color: _T.brown.withOpacity(0.08),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: const Icon(Icons.cake_rounded, color: _T.brown, size: 32),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  STATS ROW  —  2×2 grid of metric tiles
// ════════════════════════════════════════════════════════════════════════════

class _StatsRow extends StatelessWidget {
  final int todayCount;
  final int productCount;
  final double rating;
  final double earnings;

  const _StatsRow({
    required this.todayCount,
    required this.productCount,
    required this.rating,
    required this.earnings,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(children: [
          Expanded(child: _StatTile(
            label: "Today's Orders",
            value: '$todayCount',
            icon: Icons.receipt_long_rounded,
            gradient: _T.gCopper,
            onTap: () => context.push(AppRoutes.bakerOrders),
          )),
          const SizedBox(width: 14),
          Expanded(child: _StatTile(
            label: 'Products',
            value: '$productCount',
            icon: Icons.cake_rounded,
            gradient: _T.gGreen,
            onTap: () => context.push(AppRoutes.bakerProducts),
          )),
        ]),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: _StatTile(
            label: 'Rating',
            value: rating > 0 ? rating.toStringAsFixed(1) : '—',
            icon: Icons.star_rounded,
            gradient: _T.gPink,
          )),
          const SizedBox(width: 14),
          Expanded(child: _StatTile(
            label: 'Total Earned',
            value: 'Rs. ${NumberFormat.compact().format(earnings)}',
            icon: Icons.account_balance_wallet_rounded,
            gradient: _T.gBrown,
            onTap: () => context.push(AppRoutes.bakerEarnings),
          )),
        ]),
      ],
    );
  }
}

class _StatTile extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final LinearGradient gradient;
  final VoidCallback? onTap;

  const _StatTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.gradient,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        clipBehavior: Clip.antiAlias, // For watermark
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: _T.r20,
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: Stack(
          children: [
            // Professional Watermark Icon
            Positioned(
              right: -12,
              bottom: -12,
              child: Transform.rotate(
                angle: -0.2, // Slight tilt for dynamism
                child: Icon(
                  icon,
                  size: 72,
                  color: gradient.colors.first.withOpacity(0.06),
                ),
              ),
            ),
            
            // Content
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Luminous Icon pill
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                gradient: gradient,
                borderRadius: BorderRadius.circular(11),
                boxShadow: [
                  BoxShadow(
                    color: gradient.colors.last.withOpacity(0.4),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Icon(icon, color: Colors.white, size: 20),
            ),
            const SizedBox(height: 14),
            Text(
              value,
              style: const TextStyle(
                color: _T.brown,
                fontSize: 22,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
                height: 1.0,
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Expanded(
                  child: Text(
                    label,
                    style: const TextStyle(
                      color: _T.taupe,
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (onTap != null)
                  const Icon(Icons.arrow_forward_ios_rounded,
                      size: 10, color: _T.inkFaint),
              ],
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

// ════════════════════════════════════════════════════════════════════════════
//  AI ASSISTANT CARD  —  warm surface card, NOT dark (page already has hero)
// ════════════════════════════════════════════════════════════════════════════

class _AiCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push(AppRoutes.bakerAiAssistant),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: _T.r20,
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: Row(
          children: [
            // Icon matching minimalist theme
            Container(
              width: 54,
              height: 54,
              decoration: BoxDecoration(
                color: _T.pinkL,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: _T.pink, width: 1.5),
              ),
              child: const Icon(Icons.auto_awesome_rounded,
                  color: _T.brown, size: 26),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'AI Photo Assistant',
                    style: TextStyle(
                      color: _T.brown,
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.2,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Analyze photos for instructions & recipes',
                    style: TextStyle(
                      color: _T.taupe,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w500,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            // Arrow chip
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: _T.surfaceWarm,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _T.rimLight),
              ),
              child: const Icon(Icons.arrow_forward_rounded,
                  color: _T.brown, size: 18),
            ),
          ],
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  QUICK ACTIONS
// ════════════════════════════════════════════════════════════════════════════

class _QuickActionsRow extends StatelessWidget {
  static const _items = [
    _QAItem(Icons.add_rounded,            'Add\nProduct', _T.gGreen, AppRoutes.bakerAddProduct),
    _QAItem(Icons.receipt_long_rounded,   'Orders',       _T.gCopper, AppRoutes.bakerOrders),
    _QAItem(Icons.kitchen_rounded,        'Inventory',    _T.gBrown, AppRoutes.bakerInventory),
    _QAItem(Icons.local_offer_rounded,    'Surplus',      _T.gPink, AppRoutes.bakerSurplus),
  ];

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(_items.length, (i) {
        final item = _items[i];
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: i < _items.length - 1 ? 12 : 0),
            child: GestureDetector(
              onTap: () => context.push(item.route),
              child: Column(
                children: [
                  Container(
                    height: 62,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      gradient: item.gradient,
                      borderRadius: _T.r16,
                      boxShadow: [
                        BoxShadow(
                          color: item.gradient.colors.last.withOpacity(0.35),
                          blurRadius: 12,
                          offset: const Offset(0, 5),
                        ),
                      ],
                    ),
                    child: Icon(item.icon, color: Colors.white, size: 26),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    item.label,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: _T.taupe,
                      fontSize: 10.5,
                      fontWeight: FontWeight.w700,
                      height: 1.25,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }
}

class _QAItem {
  final IconData icon;
  final String label;
  final LinearGradient gradient;
  final String route;
  const _QAItem(this.icon, this.label, this.gradient, this.route);
}

// ════════════════════════════════════════════════════════════════════════════
//  STOREFRONT CARD
// ════════════════════════════════════════════════════════════════════════════

class _StorefrontCard extends StatelessWidget {
  final dynamic user;
  const _StorefrontCard({required this.user});

  @override
  Widget build(BuildContext context) {
    final slug = (user.bakeryName ?? 'bakery')
        .toLowerCase()
        .replaceAll(RegExp(r'\s+'), '-')
        .replaceAll(RegExp(r'[^a-z0-9-]'), '');
    final url = '$slug.bakesmart.com';

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: _T.r24,
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: _T.pinkL,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.pink.withOpacity(0.3)),
                ),
                child: const Icon(Icons.storefront_rounded, color: _T.copper, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          decoration: const BoxDecoration(color: _T.statusGreen, shape: BoxShape.circle),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'LIVE STOREFRONT',
                          style: TextStyle(
                            color: _T.taupe.withOpacity(0.6),
                            fontSize: 10.5,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.8,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      url,
                      style: const TextStyle(
                        color: _T.brown,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.2,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(child: _SFLightButton(
                icon: Icons.copy_rounded,
                label: 'Copy Link',
                onTap: () => ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('Store URL copied to clipboard'),
                    backgroundColor: _T.brown,
                    behavior: SnackBarBehavior.floating,
                    shape: RoundedRectangleBorder(borderRadius: _T.r12),
                    margin: const EdgeInsets.all(16),
                  ),
                ),
              )),
              const SizedBox(width: 12),
              Expanded(child: _SFLightButton(
                icon: Icons.share_rounded,
                label: 'Share Store',
                onTap: () => ShareUtil.shareStore(
                  bakerName: user.bakeryName ?? 'Your Bakery',
                  bakerId: user.uid,
                ),
              )),
            ],
          ),
        ],
      ),
    );
  }
}

class _SFLightButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _SFLightButton({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: _T.surfaceWarm,
          borderRadius: _T.r16,
          border: Border.all(color: _T.rimLight, width: 1.5),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: _T.copper, size: 16),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(
                color: _T.taupe,
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  RECENT ORDERS LIST
// ════════════════════════════════════════════════════════════════════════════

class _RecentOrdersList extends StatelessWidget {
  final AsyncValue ordersAsync;
  const _RecentOrdersList({required this.ordersAsync});

  @override
  Widget build(BuildContext context) {
    return ordersAsync.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 24),
        child: Center(child: _CopperLoader()),
      ),
      error: (e, _) => Text('Error: $e',
          style: const TextStyle(color: _T.statusPink)),
      data: (orders) {
        if (orders == null || (orders as List).isEmpty) {
          return _EmptyOrders();
        }
        final sorted = [...orders]
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
        final top3 = sorted.take(3).toList();
        return Column(
          children: top3
              .map<Widget>((o) => _OrderTile(order: o))
              .toList(),
        );
      },
    );
  }
}

class _EmptyOrders extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 24),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: _T.r20,
        border: Border.all(color: _T.rimLight, width: 1.5),
      ),
      child: Column(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: _T.surfaceWarm,
              borderRadius: BorderRadius.circular(17),
            ),
            child: const Icon(Icons.receipt_long_outlined,
                color: _T.inkFaint, size: 28),
          ),
          const SizedBox(height: 16),
          const Text(
            'No orders yet',
            style: TextStyle(
              color: _T.ink,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Orders will appear here once\ncustomers start ordering.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: _T.inkMid,
              fontSize: 13,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }
}

class _OrderTile extends StatelessWidget {
  final dynamic order;
  const _OrderTile({required this.order});

  @override
  Widget build(BuildContext context) {
    final sc = _statusConfig(order.status);
    final oId = order.id.toString();
    final displayId = oId.length > 4 ? oId.substring(oId.length - 4).toUpperCase() : oId.toUpperCase();

    return GestureDetector(
      onTap: () =>
          context.push('${AppRoutes.bakerOrderDetails}/${order.id}'),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: _T.r20,
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: Row(
          children: [
            // Industrial Order Hash
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: _T.surfaceWarm,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: _T.rimLight),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text(
                    '#',
                    style: TextStyle(color: _T.copper, fontSize: 10, fontWeight: FontWeight.w800),
                  ),
                  Text(
                    displayId,
                    style: const TextStyle(color: _T.brown, fontSize: 14, fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),

            // Order Details
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    order.customerName,
                    style: const TextStyle(
                      color: _T.ink,
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.2,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${order.items.length} item${order.items.length == 1 ? '' : 's'}  •  Rs. ${order.totalAmount}',
                    style: const TextStyle(
                      color: _T.taupe,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),

            // Sleek Status Badge
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
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  SHARED SMALL WIDGETS
// ════════════════════════════════════════════════════════════════════════════

class _Label extends StatelessWidget {
  final String label;
  const _Label(this.label, {super.key});

  @override
  Widget build(BuildContext context) => Text(
    label,
    style: const TextStyle(
      color: _T.ink,
      fontSize: 17,
      fontWeight: FontWeight.w800,
      letterSpacing: -0.3,
    ),
  );
}

class _CopperLoader extends StatelessWidget {
  const _CopperLoader();

  @override
  Widget build(BuildContext context) => const SizedBox(
    width: 28,
    height: 28,
    child: CircularProgressIndicator(
      color: _T.copper,
      strokeWidth: 2.5,
    ),
  );
}

// ════════════════════════════════════════════════════════════════════════════
//  STATUS CONFIG HELPER
// ════════════════════════════════════════════════════════════════════════════

class _StatusConfig {
  final Color color;
  final String label;
  const _StatusConfig(this.color, this.label);
}

_StatusConfig _statusConfig(String status) {
  switch (status.toLowerCase()) {
    case 'pending':
    case 'placed':   return const _StatusConfig(_T.statusCopper,  'PLACED');
    case 'preparing':return const _StatusConfig(_T.statusBrown,   'PREPARING');
    case 'ready':    return const _StatusConfig(_T.statusGreen,   'READY');
    case 'delivered':return const _StatusConfig(_T.statusGreen,   'DELIVERED');
    case 'cancelled':return const _StatusConfig(_T.statusPink,    'CANCELLED');
    default:         return const _StatusConfig(_T.inkMid, 'UNKNOWN');
  }
}