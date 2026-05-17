import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/router/app_router.dart';
import 'core/theme/baker_theme.dart';
import 'screens/splash_screen.dart';
import 'services/notification_service.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'firebase_options.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  debugPrint("Handling a background message: ${message.messageId}");
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await dotenv.load(fileName: ".env");

  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Warm up the rendering engine just before starting the app
  WidgetsBinding.instance.scheduleWarmUpFrame();

  runApp(
    const ProviderScope(
      child: BakeSmartApp(),
    ),
  );
}

class BakeSmartApp extends ConsumerStatefulWidget {
  const BakeSmartApp({super.key});

  @override
  ConsumerState<BakeSmartApp> createState() => _BakeSmartAppState();
}

class _BakeSmartAppState extends ConsumerState<BakeSmartApp> with WidgetsBindingObserver {
  bool _showSplashOverlay = false;
  double _overlayOpacity = 0.0;
  bool _isFirstLaunch = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    // Initialize notifications only once when the app starts
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(notificationServiceProvider).init();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (_isFirstLaunch) {
        _isFirstLaunch = false;
        return;
      }

      setState(() {
        _showSplashOverlay = true;
        _overlayOpacity = 1.0;
      });

      // After 2800ms of display time (intro + float), fade it out
      Future.delayed(const Duration(milliseconds: 2800), () {
        if (!mounted) return;
        setState(() {
          _overlayOpacity = 0.0;
        });

        // Fully remove from stack after opacity fade (400ms)
        Future.delayed(const Duration(milliseconds: 400), () {
          if (!mounted) return;
          setState(() {
            _showSplashOverlay = false;
          });
        });
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    return Directionality(
      textDirection: TextDirection.ltr,
      child: Stack(
        children: [
          MaterialApp.router(
            title: 'BakeSmart',
            debugShowCheckedModeBanner: false,
            theme: BakerTheme.theme,
            routerConfig: router,
          ),
          if (_showSplashOverlay)
            AnimatedOpacity(
              opacity: _overlayOpacity,
              duration: const Duration(milliseconds: 400),
              curve: Curves.easeInOut,
              child: const SplashScreen(),
            ),
        ],
      ),
    );
  }
}