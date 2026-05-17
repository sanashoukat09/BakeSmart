import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/router/app_router.dart';

abstract class _T {
  static const brown     = Color(0xFFB05E27);
  static const rimLight  = Color(0xFFF2EAE0);
  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const statusPink = Color(0xFFFF6B81);
}

class CustomerBottomNav extends StatelessWidget {
  final int currentIndex;

  const CustomerBottomNav({super.key, required this.currentIndex});

  void _go(BuildContext context, int index) {
    if (index == currentIndex) return;
    switch (index) {
      case 0:
        context.go(AppRoutes.customerHome);
        break;
      case 1:
        context.go(AppRoutes.customerWishlist);
        break;
      case 2:
        context.go(AppRoutes.customerProfile);
        break;
      case 3:
        context.go(AppRoutes.customerCart);
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
          top: BorderSide(color: _T.rimLight, width: 1.5),
        ),
      ),
      child: BottomNavigationBar(
        currentIndex: currentIndex,
        onTap: (index) => _go(context, index),
        backgroundColor: Colors.transparent,
        elevation: 0,
        selectedItemColor: _T.brown,
        unselectedItemColor: const Color(0xFFA8A29E),
        showSelectedLabels: true,
        showUnselectedLabels: true,
        selectedLabelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 11),
        unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 11),
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.home_outlined),
            activeIcon: Icon(Icons.home_rounded),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.favorite_border_rounded),
            activeIcon: Icon(Icons.favorite_rounded),
            label: 'Wishlist',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline_rounded),
            activeIcon: Icon(Icons.person_rounded),
            label: 'Profile',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.shopping_bag_outlined),
            activeIcon: Icon(Icons.shopping_bag_rounded),
            label: 'Cart',
          ),
        ],
      ),
    );
  }
}
