import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/models/user_model.dart';
import '../../auth/services/auth_provider.dart';
import '../../community/screens/community_hub_screen.dart';
import '../../notifications/screens/notifications_screen.dart';
import '../../notifications/services/notification_service.dart';
import 'inventory_screen.dart';
import 'products_screen.dart';
import 'baker_orders_screen.dart';
import 'seller_verification_screen.dart';

class BakerDashboardScreen extends ConsumerWidget {
  final UserModel userModel;
  
  const BakerDashboardScreen({super.key, required this.userModel});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadCountAsync = ref.watch(unreadNotificationsCountProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Baker Dashboard'),
        actions: [
          Stack(
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_none_rounded),
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
              ),
              unreadCountAsync.when(
                data: (count) => count > 0 
                  ? Positioned(
                      right: 8,
                      top: 8,
                      child: Container(
                        padding: const EdgeInsets.all(2),
                        decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(10)),
                        constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                        child: Text('$count', style: const TextStyle(color: Colors.white, fontSize: 10), textAlign: TextAlign.center),
                      ),
                    )
                  : const SizedBox.shrink(),
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
              ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authControllerProvider).signOut(),
          ),
        ],
      ),
      body: Column(
        children: [
          _VerificationBanner(status: userModel.verificationStatus ?? 'unverified', reason: userModel.rejectionReason),
          Expanded(
            child: Center(
              child: SingleChildScrollView(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Welcome, ${userModel.bakeryName ?? userModel.name}!',
                          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                        ),
                        if (userModel.verificationStatus == 'verified')
                          const Padding(
                            padding: EdgeInsets.only(left: 8.0),
                            child: Icon(Icons.verified, color: Colors.green, size: 24),
                          ),
                      ],
                    ),
                    const SizedBox(height: 32),
                    ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const InventoryScreen()),
                        );
                      },
                      icon: const Icon(Icons.inventory),
                      label: const Text('Manage Inventory'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                        backgroundColor: Colors.brown,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const ProductsScreen()),
                        );
                      },
                      icon: const Icon(Icons.cake),
                      label: const Text('Manage Products'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                        backgroundColor: Colors.brown,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const BakerOrdersScreen()),
                        );
                      },
                      icon: const Icon(Icons.receipt_long),
                      label: const Text('Manage Orders'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                        backgroundColor: Colors.brown,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const CommunityHubScreen()),
                        );
                      },
                      icon: const Icon(Icons.people_alt_rounded),
                      label: const Text('Community Hub'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                        backgroundColor: const Color(0xFF00897B),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _VerificationBanner extends StatelessWidget {
  final String status;
  final String? reason;
  
  const _VerificationBanner({required this.status, this.reason});

  @override
  Widget build(BuildContext context) {
    if (status == 'verified') return const SizedBox.shrink();

    Color bgColor;
    Color textColor;
    IconData icon;
    String message;
    VoidCallback? onTap;

    switch (status) {
      case 'pending':
        bgColor = Colors.blueGrey[50]!;
        textColor = Colors.blueGrey[700]!;
        icon = Icons.hourglass_top_rounded;
        message = 'Your verification is under review. You will be notified within 24 to 48 hours. Product listing is disabled until approved.';
        break;
      case 'rejected':
        bgColor = Colors.red[50]!;
        textColor = Colors.red[900]!;
        icon = Icons.error_outline_rounded;
        message = 'Verification not approved. Reason: ${reason ?? "Please check your details"}. Tap to resubmit.';
        onTap = () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SellerVerificationScreen()));
        break;
      case 'unverified':
      default:
        bgColor = Colors.orange[50]!;
        textColor = Colors.orange[900]!;
        icon = Icons.info_outline_rounded;
        message = 'You are not yet verified as a seller. Tap here to apply and start listing your products.';
        onTap = () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SellerVerificationScreen()));
        break;
    }

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        color: bgColor,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Icon(icon, color: textColor, size: 22),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                message,
                style: TextStyle(color: textColor, fontWeight: FontWeight.w600, fontSize: 13),
              ),
            ),
            if (onTap != null) Icon(Icons.arrow_forward_ios, color: textColor, size: 14),
          ],
        ),
      ),
    );
  }
}
