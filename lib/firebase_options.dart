// ⚠️ IMPORTANT — THIS FILE MUST BE REPLACED
//
// Run this command inside your project folder to generate the real file:
//   flutterfire configure --project=bakesmart-5efda
//
// That command will overwrite this file with your real Firebase config.
// Make sure you have the FlutterFire CLI installed:
//   dart pub global activate flutterfire_cli
//
// ─────────────────────────────────────────────────────────────

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) throw UnsupportedError('Web not configured');
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        throw UnsupportedError('Unsupported platform');
    }
  }

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyAQBGu3cMgwB8S4lUdsmc32b6ASqnxZUag',
    appId: '1:74225525286:android:5b595a2663d4ab18183ce7',
    messagingSenderId: '74225525286',
    projectId: 'bakesmart-5efda',
    storageBucket: 'bakesmart-5efda.firebasestorage.app',
  );

  // ─── REPLACE THESE VALUES with output from `flutterfire configure` ───

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'YOUR_IOS_API_KEY',
    appId: 'YOUR_IOS_APP_ID',
    messagingSenderId: 'YOUR_SENDER_ID',
    projectId: 'bakesmart-5efda',
    storageBucket: 'bakesmart-5efda.appspot.com',
    iosClientId: 'YOUR_IOS_CLIENT_ID',
    iosBundleId: 'com.bakesmart.app',
  );
}