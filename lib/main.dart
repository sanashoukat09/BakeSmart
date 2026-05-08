import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/router/app_router.dart';
import 'core/theme/baker_theme.dart';
import 'providers/auth_provider.dart';
import 'services/notification_service.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Set preferred orientations
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Initialize Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  runApp(
    const ProviderScope(
      child: BakeSmartApp(),
    ),
  );
}

class BakeSmartApp extends ConsumerWidget {
  const BakeSmartApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    // Initialize Notifications
    ref.read(notificationServiceProvider).init();

    return MaterialApp.router(
      title: 'BakeSmart',
      debugShowCheckedModeBanner: false,
      theme: BakerTheme.theme,
      routerConfig: router,
    );
  }
}
