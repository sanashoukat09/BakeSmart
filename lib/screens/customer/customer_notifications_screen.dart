import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:go_router/go_router.dart';
import '../../providers/notification_provider.dart';
import '../../providers/auth_provider.dart';

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

class CustomerNotificationsScreen extends ConsumerWidget {
  const CustomerNotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notificationsAsync = ref.watch(notificationProvider);
    final user = ref.watch(currentUserProvider).valueOrNull;

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        leadingWidth: 56,
        titleSpacing: 0,
        title: const Text(
          'Notifications',
          style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _T.brown),
          onPressed: () => GoRouter.of(context).pop(),
        ),
        actions: [
          if (notificationsAsync.valueOrNull?.isNotEmpty ?? false)
            Padding(
              padding: const EdgeInsets.only(right: 8.0),
              child: TextButton(
                onPressed: () => _markAllAsRead(user?.uid),
                child: const Text(
                  'Mark all as read', 
                  style: TextStyle(color: _T.copper, fontWeight: FontWeight.w800, fontSize: 13),
                ),
              ),
            ),
        ],
      ),
      body: notificationsAsync.when(
        data: (notifications) {
          if (notifications.isEmpty) {
            return Center(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 32),
                padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
                decoration: BoxDecoration(
                  color: _T.surfaceWarm,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: _T.surface,
                        shape: BoxShape.circle,
                        boxShadow: _T.shadowSm,
                      ),
                      child: const Icon(Icons.notifications_off_outlined, size: 28, color: _T.inkFaint),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'No notifications yet', 
                      style: TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'We will let you know when updates arrive.', 
                      textAlign: TextAlign.center,
                      style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            itemCount: notifications.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final notification = notifications[index];
              return _NotificationTile(notification: notification, userId: user?.uid);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
      ),
    );
  }

  void _markAllAsRead(String? uid) async {
    if (uid == null) return;
    final batch = FirebaseFirestore.instance.batch();
    final snapshot = await FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .collection('notifications')
        .where('isRead', isEqualTo: false)
        .get();

    for (var doc in snapshot.docs) {
      batch.update(doc.reference, {'isRead': true});
    }
    await batch.commit();
  }
}

class _NotificationTile extends StatelessWidget {
  final dynamic notification;
  final String? userId;
  const _NotificationTile({required this.notification, required this.userId});

  @override
  Widget build(BuildContext context) {
    final bool isUnread = !notification.isRead;
    return Container(
      decoration: BoxDecoration(
        color: isUnread ? _T.surfaceWarm : _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isUnread ? _T.pink.withOpacity(0.3) : _T.rimLight, 
          width: 1.5,
        ),
        boxShadow: isUnread ? _T.shadowSm : null,
      ),
      child: ListTile(
        onTap: () {
          if (isUnread && userId != null) {
            FirebaseFirestore.instance
                .collection('users')
                .doc(userId)
                .collection('notifications')
                .doc(notification.id)
                .update({'isRead': true});
          }
        },
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: _getIconColor(notification.type).withOpacity(0.12),
            shape: BoxShape.circle,
          ),
          child: Icon(_getIcon(notification.type), color: _getIconColor(notification.type), size: 22),
        ),
        title: Text(
          notification.title,
          style: TextStyle(
            color: _T.ink,
            fontWeight: isUnread ? FontWeight.w800 : FontWeight.w600,
            fontSize: 14,
            letterSpacing: -0.2,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 5),
            Text(
              notification.body, 
              style: const TextStyle(color: _T.inkMid, fontSize: 13, height: 1.3, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 8),
            Text(
              DateFormat('MMM dd, hh:mm a').format(notification.createdAt),
              style: const TextStyle(color: _T.inkFaint, fontSize: 11, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }

  IconData _getIcon(String? type) {
    switch (type) {
      case 'order': return Icons.shopping_bag_outlined;
      case 'deal': return Icons.local_fire_department_outlined;
      case 'promo': return Icons.campaign_outlined;
      default: return Icons.notifications_outlined;
    }
  }

  Color _getIconColor(String? type) {
    switch (type) {
      case 'order': return _T.statusGreen;
      case 'deal': return _T.statusPink;
      case 'promo': return _T.statusCopper;
      default: return _T.statusBrown;
    }
  }
}
