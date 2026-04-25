import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/auth_provider.dart';
import 'login_screen.dart';
import '../../baker/screens/baker_dashboard_screen.dart';
import '../../customer/screens/product_catalogue_screen.dart';

// TO CREATE AN ADMIN ACCOUNT:
// 1. Register a normal account in the app
// 2. Go to Firebase Console → Firestore → users collection
// 3. Find the document for that user
// 4. Change the role field from 'baker' or 'customer' to 'admin'
// 5. The user will be routed to AdminDashboard on next login

class AuthChecker extends ConsumerStatefulWidget {
  const AuthChecker({super.key});

  @override
  ConsumerState<AuthChecker> createState() => _AuthCheckerState();
}

class _AuthCheckerState extends ConsumerState<AuthChecker> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _checkSuspensionStatus();
    }
  }

  Future<void> _checkSuspensionStatus() async {
    final user = ref.read(authStateProvider).value;
    if (user == null) return;

    // Refresh user data from Firestore
    final userData = await ref.read(userDataProvider.future);
    if (userData != null && userData.isSuspended) {
      _handleSuspension();
    }
  }

  void _handleSuspension() {
    if (!mounted) return;
    ref.read(authControllerProvider).signOut();
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text('Account Suspended'),
        content: const Text('Your account has been suspended. Please contact support for assistance.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);

    return authState.when(
      data: (user) {
        if (user == null) {
          return const LoginScreen();
        }

        final userDataAsync = ref.watch(userDataProvider);

        return userDataAsync.when(
          data: (userData) {
            if (userData == null) {
              // Usually happens if Auth user exists but Firestore doc is missing
              WidgetsBinding.instance.addPostFrameCallback((_) {
                ref.read(authControllerProvider).signOut();
              });
              return const Scaffold(
                body: Center(
                  child: Padding(
                    padding: EdgeInsets.all(24.0),
                    child: Text('User profile not found. Please try registering again.', textAlign: TextAlign.center),
                  ),
                ),
              );
            }

            // Cold start suspension check
            if (userData.isSuspended) {
              WidgetsBinding.instance.addPostFrameCallback((_) => _handleSuspension());
              return const Scaffold(
                body: Center(child: CircularProgressIndicator()),
              );
            }
            
            switch (userData.role) {
              case 'admin':
                // Admins are not allowed in the mobile app
                return Scaffold(
                  body: Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.admin_panel_settings, size: 80, color: Colors.brown),
                          const SizedBox(height: 24),
                          const Text(
                            'Web Portal Required',
                            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.brown),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'Administrative functions are only available via the web dashboard. Please log in at bakesmart-app.web.app',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Colors.grey),
                          ),
                          const SizedBox(height: 32),
                          ElevatedButton(
                            onPressed: () => ref.read(authControllerProvider).signOut(),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.brown,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 16),
                            ),
                            child: const Text('Back to Login'),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              case 'baker':
                return BakerDashboardScreen(userModel: userData);
              case 'customer':
              default:
                return const ProductCatalogueScreen();
            }
          },
          loading: () => const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          ),
          error: (e, trace) => Scaffold(
            body: Center(child: Text('Error loading user data: $e')),
          ),
        );
      },
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (e, trace) => Scaffold(
        body: Center(child: Text('Auth Error: $e')),
      ),
    );
  }
}
