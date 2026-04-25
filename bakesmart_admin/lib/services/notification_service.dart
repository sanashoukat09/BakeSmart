import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'auth_provider.dart';
import '../models/notification_model.dart';

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService(ref.watch(firestoreProvider));
});

class NotificationService {
  final FirebaseFirestore _firestore;

  NotificationService(this._firestore);

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
}
