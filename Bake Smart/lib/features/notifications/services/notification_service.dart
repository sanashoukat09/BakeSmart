import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/notification_model.dart';

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService(ref.watch(firestoreProvider));
});

final unreadNotificationsCountProvider = StreamProvider<int>((ref) {
  final uid = FirebaseAuth.instance.currentUser?.uid;
  if (uid == null) return Stream.value(0);

  // Only filter by recipientId — no compound query, no index required.
  // We count unread client-side to avoid needing a composite index.
  return ref.watch(firestoreProvider)
      .collection('notifications')
      .where('recipientId', isEqualTo: uid)
      .snapshots()
      .map((snapshot) =>
          snapshot.docs.where((d) => d.data()['isRead'] == false).length);
});

final notificationsStreamProvider = StreamProvider<List<NotificationModel>>((ref) {
  final uid = FirebaseAuth.instance.currentUser?.uid;
  if (uid == null) return Stream.value([]);

  // No orderBy on the server — sort client-side to avoid requiring a
  // composite index on (recipientId, createdAt). This index can be added
  // later via Firebase Console for better performance at scale.
  return ref.watch(firestoreProvider)
      .collection('notifications')
      .where('recipientId', isEqualTo: uid)
      .snapshots()
      .map((snapshot) {
        final list = snapshot.docs
            .map((doc) => NotificationModel.fromMap(doc.data(), doc.id))
            .toList();
        // Sort newest-first client-side.
        list.sort((a, b) => b.createdAt.compareTo(a.createdAt));
        return list;
      });
});

class NotificationService {
  final FirebaseFirestore _firestore;

  NotificationService(this._firestore);

  /// Helper to send a notification as part of an existing batch
  void sendNotificationWithBatch(
    WriteBatch batch, {
    required String recipientId,
    required String title,
    required String body,
    required NotificationType type,
    required String referenceId,
  }) {
    final docRef = _firestore.collection('notifications').doc();
    final notification = NotificationModel(
      notificationId: docRef.id,
      recipientId: recipientId,
      title: title,
      body: body,
      type: type,
      referenceId: referenceId,
      createdAt: DateTime.now(),
    );
    batch.set(docRef, notification.toMap());
  }

  /// Send a standalone notification (not in a batch)
  Future<void> sendNotification({
    required String recipientId,
    required String title,
    required String body,
    required NotificationType type,
    required String referenceId,
  }) async {
    final docRef = _firestore.collection('notifications').doc();
    final notification = NotificationModel(
      notificationId: docRef.id,
      recipientId: recipientId,
      title: title,
      body: body,
      type: type,
      referenceId: referenceId,
      createdAt: DateTime.now(),
    );
    await docRef.set(notification.toMap());
  }

  /// Mark all notifications as read for a specific user
  Future<void> markAllAsRead(String userId) async {
    final query = await _firestore
        .collection('notifications')
        .where('recipientId', isEqualTo: userId)
        .where('isRead', isEqualTo: false)
        .get();

    if (query.docs.isEmpty) return;

    final batch = _firestore.batch();
    for (var doc in query.docs) {
      batch.update(doc.reference, {'isRead': true});
    }
    await batch.commit();
  }

  /// Mark a single notification as read
  Future<void> markAsRead(String notificationId) async {
    await _firestore
        .collection('notifications')
        .doc(notificationId)
        .update({'isRead': true});
  }
}
