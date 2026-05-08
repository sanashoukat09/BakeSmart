import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'firestore_service.dart';
import '../providers/auth_provider.dart';

final notificationServiceProvider = Provider((ref) => NotificationService(ref));

class NotificationService {
  final Ref _ref;
  final FirebaseMessaging _fcm = FirebaseMessaging.instance;
  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  NotificationService(this._ref) {
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
