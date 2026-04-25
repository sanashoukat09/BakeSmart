import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/notification_model.dart';

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService(ref.watch(firestoreProvider));
});

final unreadNotificationsCountProvider = StreamProvider<int>((ref) {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return Stream.value(0);

  return ref.watch(firestoreProvider)
      .collection('notifications')
      .where('recipientId', isEqualTo: user.uid)
      .where('isRead', isEqualTo: false)
      .snapshots()
      .map((snapshot) => snapshot.docs.length);
});

final notificationsStreamProvider = StreamProvider<List<NotificationModel>>((ref) {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return Stream.value([]);

  return ref.watch(firestoreProvider)
      .collection('notifications')
      .where('recipientId', isEqualTo: user.uid)
      .orderBy('createdAt', descending: true)
      .snapshots()
      .map((snapshot) => snapshot.docs
          .map((doc) => NotificationModel.fromMap(doc.data(), doc.id))
          .toList());
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

  /// Mark all notifications as read for a specific user in a batch
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
