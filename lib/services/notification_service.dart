import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'firestore_service.dart';
import '../providers/auth_provider.dart';
import '../models/notification_model.dart';
import 'dart:async';

final notificationServiceProvider = Provider((ref) => NotificationService(ref));

class NotificationService {
  final Ref _ref;
  final FirebaseMessaging _fcm = FirebaseMessaging.instance;
  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();
  StreamSubscription? _notificationSubscription;
  DateTime? _initTime;

  NotificationService(this._ref) {
    _initTime = DateTime.now();
    _listenToAuth();
  }

  void _listenToAuth() {
    _ref.listen(currentUserProvider, (prev, next) async {
      final user = next.valueOrNull;
      if (user != null) {
        String? token = await _fcm.getToken();
        if (token != null) {
          _updateToken(token);
        }
        _listenToFirestoreNotifications(user.uid);
      } else {
        _notificationSubscription?.cancel();
        _notificationSubscription = null;
      }
    });
  }

  void _listenToFirestoreNotifications(String uid) {
    _notificationSubscription?.cancel();
    
    // Listen for new notifications in Firestore
    _notificationSubscription = FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .collection('notifications')
        .where('createdAt', isGreaterThan: _initTime)
        .snapshots()
        .listen((snapshot) {
      for (var change in snapshot.docChanges) {
        if (change.type == DocumentChangeType.added) {
          try {
            final notification = NotificationModel.fromFirestore(change.doc);
            // Only show if it's not already read and it's new
            if (!notification.isRead) {
              showLocalNotification(
                title: notification.title,
                body: notification.body,
              );
            }
          } catch (e) {
            print('Error parsing live notification: $e');
          }
        }
      }
    });
  }

  Future<void> init() async {
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidInit);
    await _localNotifications.initialize(initSettings);

    await _localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(
          const AndroidNotificationChannel(
            'bakesmart_alerts',
            'BakeSmart Alerts',
            description: 'Order, inventory, and status alerts',
            importance: Importance.high,
          ),
        );

    // Request permission for iOS
    NotificationSettings settings = await _fcm.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      // Get the token
      String? token = await _fcm.getToken();
      if (token != null) {
        _updateToken(token);
      }
    }

    // Listen to token refreshes
    _fcm.onTokenRefresh.listen(_updateToken);

    FirebaseMessaging.onMessage.listen((message) {
      final notification = message.notification;
      final title = notification?.title ?? message.data['title'];
      final body = notification?.body ?? message.data['body'];
      if (title == null || body == null) return;
      showLocalNotification(title: title, body: body);
    });
  }

  Future<void> showLocalNotification({
    required String title,
    required String body,
  }) async {
    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        'bakesmart_alerts',
        'BakeSmart Alerts',
        channelDescription: 'Order, inventory, and status alerts',
        importance: Importance.high,
        priority: Priority.high,
      ),
    );

    await _localNotifications.show(
      DateTime.now().millisecondsSinceEpoch ~/ 1000,
      title,
      body,
      details,
    );
  }

  void _updateToken(String token) {
    final user = _ref.read(currentUserProvider).valueOrNull;
    if (user != null && user.fcmToken != token) {
      _ref.read(firestoreServiceProvider).updateUser(user.uid, {
        'fcmToken': token,
      });
    }
  }

  Future<void> subscribeToBaker(String bakerId) async {
    await _fcm.subscribeToTopic('surplus_$bakerId');
  }

  Future<void> unsubscribeFromBaker(String bakerId) async {
    await _fcm.unsubscribeFromTopic('surplus_$bakerId');
  }
}
