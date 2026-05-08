import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'firestore_service.dart';
import '../providers/auth_provider.dart';

final notificationServiceProvider = Provider((ref) => NotificationService(ref));

class NotificationService {
  final Ref _ref;
  final FirebaseMessaging _fcm = FirebaseMessaging.instance;

  NotificationService(this._ref);

  Future<void> init() async {
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
  }

  void _updateToken(String token) {
    final user = _ref.read(currentUserProvider).valueOrNull;
    if (user != null) {
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
