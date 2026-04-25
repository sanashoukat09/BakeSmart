import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';

import '../models/notification_model.dart';
import '../services/notification_service.dart';
import '../../auth/services/auth_provider.dart';
import '../../customer/models/order_model.dart';
import '../../customer/screens/order_tracking_screen.dart';
import '../../community/models/community_post_model.dart';
import '../../community/screens/post_detail_screen.dart';
import '../../baker/screens/seller_verification_screen.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    // Mark all as read when opening the screen
    Future.microtask(() {
      final user = ref.read(authStateProvider).value;
      if (user != null) {
        ref.read(notificationServiceProvider).markAllAsRead(user.uid);
      }
    });
  }

  Future<void> _handleNavigation(NotificationModel notification) async {
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    
    // Show loading overlay or indicator if needed, but simple async fetch is fine
    try {
      if (notification.type == NotificationType.orderUpdate) {
        final doc = await FirebaseFirestore.instance
            .collection('orders')
            .doc(notification.referenceId)
            .get();
        
        if (doc.exists && mounted) {
          final order = OrderModel.fromMap(doc.data()!, doc.id);
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => OrderTrackingScreen(order: order)),
          );
        } else {
          scaffoldMessenger.showSnackBar(const SnackBar(content: Text('Order not found')));
        }
      } else if (notification.type == NotificationType.verificationUpdate) {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const SellerVerificationScreen()),
        );
      } else if (notification.type == NotificationType.newComment) {
        final doc = await FirebaseFirestore.instance
            .collection('communityPosts')
            .doc(notification.referenceId)
            .get();
            
        final user = ref.read(authStateProvider).value;
        
        if (doc.exists && user != null && mounted) {
          final post = CommunityPostModel.fromMap(doc.data()!, doc.id);
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => PostDetailScreen(post: post, currentUserId: user.uid),
            ),
          );
        } else {
          scaffoldMessenger.showSnackBar(const SnackBar(content: Text('Post not found')));
        }
      }
    } catch (e) {
      if (mounted) {
        scaffoldMessenger.showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final notificationsAsync = ref.watch(notificationsStreamProvider);

    return Scaffold(
      backgroundColor: const Color(0xFFFDF8F5),
      appBar: AppBar(
        title: const Text('Notifications', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: notificationsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator(color: Colors.brown)),
        error: (e, _) => Center(child: Text('Error: $e')),
        data: (notifications) {
          if (notifications.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.notifications_none_outlined, size: 80, color: Colors.brown.withOpacity(0.2)),
                  const SizedBox(height: 16),
                  const Text(
                    'No notifications yet',
                    style: TextStyle(fontSize: 18, color: Colors.grey, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: notifications.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final notification = notifications[index];
              return _NotificationCard(
                notification: notification,
                onTap: () => _handleNavigation(notification),
              );
            },
          );
        },
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  final NotificationModel notification;
  final VoidCallback onTap;

  const _NotificationCard({required this.notification, required this.onTap});

  IconData _getIcon() {
    switch (notification.type) {
      case NotificationType.orderUpdate:
        return Icons.shopping_bag_outlined;
      case NotificationType.verificationUpdate:
        return Icons.verified_user_outlined;
      case NotificationType.newComment:
        return Icons.chat_bubble_outline_rounded;
    }
  }

  Color _getColor() {
    switch (notification.type) {
      case NotificationType.orderUpdate:
        return Colors.blue;
      case NotificationType.verificationUpdate:
        return Colors.green;
      case NotificationType.newComment:
        return Colors.orange;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: notification.isRead ? Colors.transparent : Colors.brown.withOpacity(0.1)),
      ),
      color: notification.isRead ? Colors.white : const Color(0xFFFBE9E7),
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: _getColor().withOpacity(0.1),
          child: Icon(_getIcon(), color: _getColor(), size: 20),
        ),
        title: Text(
          notification.title,
          style: TextStyle(
            fontWeight: notification.isRead ? FontWeight.normal : FontWeight.bold,
            fontSize: 15,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(notification.body, style: TextStyle(color: Colors.grey[700], fontSize: 13)),
            const SizedBox(height: 4),
            Text(
              DateFormat('MMM d, h:mm a').format(notification.createdAt),
              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
            ),
          ],
        ),
        trailing: notification.isRead 
          ? null 
          : Container(width: 8, height: 8, decoration: const BoxDecoration(color: Colors.brown, shape: BoxShape.circle)),
      ),
    );
  }
}
