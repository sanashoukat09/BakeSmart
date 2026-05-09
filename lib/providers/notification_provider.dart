import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/notification_model.dart';
import 'auth_provider.dart';
import 'dart:async';

final notificationProvider = StreamProvider<List<NotificationModel>>((ref) {
  final uid = ref.watch(firebaseAuthStateProvider.select((user) => user.value?.uid));

  if (uid == null) {
    return Stream.value([]);
  }

  return ref.watch(firestoreServiceProvider).streamNotifications(uid);
});

final unreadNotificationCountProvider = Provider<int>((ref) {
  final notifications = ref.watch(notificationProvider).valueOrNull ?? [];
  return notifications.where((n) => !n.isRead).length;
});
