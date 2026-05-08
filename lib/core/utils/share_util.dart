import 'package:share_plus/share_plus.dart';
import '../constants/app_constants.dart';

class ShareUtil {
  static const String _baseUrl = 'https://bakesmart.app'; // Placeholder for deep linking

  static void shareStore({required String bakerName, required String bakerId}) {
    final bakerySlug = bakerName
        .toLowerCase()
        .replaceAll(RegExp(r'\s+'), '-')
        .replaceAll(RegExp(r'[^a-z0-9-]'), '');
    final String url = '$bakerySlug/bakesmart.com';
    final String message = 'Check out $bakerName on BakeSmart! Freshly baked treats delivered to your door. 🍰\n\nView Store: $url';
    
    Share.share(message);
  }

  static void shareProduct({required String productName, required String productId, required String bakerName}) {
    final bakerySlug = bakerName
        .toLowerCase()
        .replaceAll(RegExp(r'\s+'), '-')
        .replaceAll(RegExp(r'[^a-z0-9-]'), '');
    final String url = '$bakerySlug/bakesmart.com';
    final String message = 'You have to see this $productName from $bakerName on BakeSmart! 😍\n\nOrder here: $url';
    
    Share.share(message);
  }

  static void inviteFriend() {
    const String message = 'Join me on BakeSmart! The best place to find home-baked treats and manage your bakery. 🧁\n\nDownload now: $_baseUrl';
    
    Share.share(message);
  }
}
