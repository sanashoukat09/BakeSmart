import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
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

  static const statusGreen = Color(0xFF52B788);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class OrderSuccessScreen extends StatelessWidget {
  const OrderSuccessScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _T.canvas,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Large elegant Success Checkmark
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: _T.statusGreen.withOpacity(0.08),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check_circle_outline_rounded,
                  size: 80,
                  color: _T.statusGreen,
                ),
              ),
              const SizedBox(height: 32),
              const Text(
                'Order Placed Successfully!',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: _T.ink,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Your baker has been notified and will review your order shortly.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: _T.inkMid,
                  height: 1.45,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 48),
              
              ElevatedButton(
                onPressed: () => context.go(AppRoutes.customerHome),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _T.brown,
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 54),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  elevation: 0,
                ),
                child: const Text(
                  'Back to Home',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(height: 16),
              
              TextButton(
                onPressed: () => context.go(AppRoutes.customerOrders),
                child: const Text(
                  'View My Orders',
                  style: TextStyle(
                    color: _T.brown,
                    fontWeight: FontWeight.w800,
                    fontSize: 14.5,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
