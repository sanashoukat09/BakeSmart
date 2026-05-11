import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../screens/auth/login_screen.dart';
import '../../screens/auth/register_screen.dart';
import '../../screens/auth/forgot_password_screen.dart';
import '../../screens/baker/baker_onboarding_screen.dart';
import '../../screens/baker/baker_dashboard.dart';
import '../../screens/baker/baker_profile_screen.dart';
import '../../screens/baker/ai_assistant_screen.dart';
import '../../screens/baker/product_list_screen.dart';
import '../../screens/baker/add_edit_product_screen.dart';
import '../../screens/baker/inventory_screen.dart';
import '../../screens/baker/add_edit_ingredient_screen.dart';
import '../../screens/baker/pricing_summary_screen.dart';
import '../../screens/baker/surplus_management_screen.dart';
import '../../screens/baker/order_list_screen.dart';
import '../../screens/baker/order_details_screen.dart';
import '../../screens/baker/baker_earnings_screen.dart';
import '../../screens/splash_screen.dart';
import '../../screens/customer/customer_onboarding_screen.dart';
import '../../screens/customer/customer_home_screen.dart';
import '../../screens/customer/customer_profile_screen.dart';
import '../../screens/customer/baker_storefront_screen.dart';
import '../../screens/customer/customer_product_details_screen.dart';
import '../../screens/customer/cart_screen.dart';
import '../../screens/customer/checkout_screen.dart';
import '../../screens/customer/order_success_screen.dart';
import '../../screens/customer/customer_orders_screen.dart';
import '../../screens/customer/customer_order_details_screen.dart';
import '../../screens/customer/submit_review_screen.dart';
import '../../screens/customer/surplus_deals_screen.dart';
import '../../screens/customer/customer_notifications_screen.dart';

// Route names
class AppRoutes {
  static const splash = '/';
  static const login = '/login';
  static const register = '/register';
  static const forgotPassword = '/forgot-password';

  // Baker routes
  static const bakerOnboarding = '/baker/onboarding';
  static const bakerDashboard = '/baker/dashboard';
  static const bakerProfile = '/baker/profile';
  static const bakerProducts = '/baker/products';
  static const bakerAddProduct = '/baker/products/add';
  static const bakerEditProduct = '/baker/products/edit';
  static const bakerInventory = '/baker/inventory';
  static const bakerAddIngredient = '/baker/inventory/add';
  static const bakerEditIngredient = '/baker/inventory/edit';
  static const bakerPricing = '/baker/pricing';
  static const bakerSurplus = '/baker/surplus';
  static const bakerOrders = '/baker/orders';
  static const bakerOrderDetails = '/baker/orders/details';
  static const bakerEarnings = '/baker/earnings';
  static const bakerNotifications = '/baker/notifications';
  static const bakerAiAssistant = '/baker/ai-assistant';

  // Customer routes
  static const customerOnboarding = '/customer/onboarding';
  static const customerHome = '/customer/home';
  static const customerProfile = '/customer/profile';
  static const customerStore = '/customer/store';
  static const customerProduct = '/customer/product';
  static const customerCart = '/customer/cart';
  static const customerCheckout = '/customer/checkout';
  static const customerOrderSuccess = '/customer/order-success';
  static const customerOrders = '/customer/orders';
  static const customerOrderDetails = '/customer/orders/details';
  static const customerSubmitReview = '/customer/submit-review';
  static const customerSurplus = '/customer/surplus-deals';
  static const customerNotifications = '/customer/notifications';
}

final routerProvider = Provider<GoRouter>((ref) {
  // Use ref.read instead of ref.watch to ensure this provider only runs ONCE.
  // This keeps the GoRouter instance stable across the entire app lifecycle.
  final notifier = ref.read(routerNotifierProvider);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: notifier,
    redirect: (context, state) => notifier.redirect(context, state),
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.register,
        builder: (context, state) => const RegisterScreen(),
      ),
      GoRoute(
        path: AppRoutes.forgotPassword,
        builder: (context, state) => const ForgotPasswordScreen(),
      ),
      // Baker routes
      GoRoute(
        path: AppRoutes.bakerOnboarding,
        builder: (context, state) => const BakerOnboardingScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerDashboard,
        builder: (context, state) => const BakerDashboard(),
      ),
      GoRoute(
        path: AppRoutes.bakerProfile,
        builder: (context, state) => const BakerProfileScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerProducts,
        builder: (context, state) => const ProductListScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerAddProduct,
        builder: (context, state) => const AddEditProductScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.bakerEditProduct}/:id',
        builder: (context, state) => AddEditProductScreen(
          productId: state.pathParameters['id'],
        ),
      ),
      GoRoute(
        path: AppRoutes.bakerInventory,
        builder: (context, state) => const InventoryScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerAddIngredient,
        builder: (context, state) => const AddEditIngredientScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.bakerEditIngredient}/:id',
        builder: (context, state) => AddEditIngredientScreen(
          ingredientId: state.pathParameters['id'],
        ),
      ),
      GoRoute(
        path: AppRoutes.bakerPricing,
        builder: (context, state) => const PricingSummaryScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerSurplus,
        builder: (context, state) => const SurplusManagementScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerOrders,
        builder: (context, state) => const OrderListScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.bakerOrderDetails}/:id',
        builder: (context, state) => OrderDetailsScreen(
          orderId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: AppRoutes.bakerEarnings,
        builder: (context, state) => const BakerEarningsScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerNotifications,
        builder: (context, state) => const CustomerNotificationsScreen(),
      ),
      GoRoute(
        path: AppRoutes.bakerAiAssistant,
        builder: (context, state) => const AiAssistantScreen(),
      ),
      // Customer routes
      GoRoute(
        path: AppRoutes.customerOnboarding,
        builder: (context, state) => const CustomerOnboardingScreen(),
      ),
      GoRoute(
        path: AppRoutes.customerHome,
        builder: (context, state) => const CustomerHomeScreen(),
      ),
      GoRoute(
        path: AppRoutes.customerProfile,
        builder: (context, state) => const CustomerProfileScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.customerStore}/:id',
        builder: (context, state) => BakerStorefrontScreen(
          bakerId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '${AppRoutes.customerProduct}/:id',
        builder: (context, state) => CustomerProductDetailsScreen(
          productId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: AppRoutes.customerCart,
        builder: (context, state) => const CartScreen(),
      ),
      GoRoute(
        path: AppRoutes.customerCheckout,
        builder: (context, state) => const CheckoutScreen(),
      ),
      GoRoute(
        path: AppRoutes.customerOrderSuccess,
        builder: (context, state) => const OrderSuccessScreen(),
      ),
      GoRoute(
        path: AppRoutes.customerOrders,
        builder: (context, state) => const CustomerOrdersScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.customerOrderDetails}/:id',
        builder: (context, state) => CustomerOrderDetailsScreen(
          orderId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '${AppRoutes.customerSubmitReview}/:orderId',
        builder: (context, state) => SubmitReviewScreen(
          orderId: state.pathParameters['orderId']!,
        ),
      ),
      GoRoute(
        path: AppRoutes.customerSurplus,
        builder: (context, state) => const SurplusDealsScreen(),
      ),
      GoRoute(
        path: AppRoutes.customerNotifications,
        builder: (context, state) => const CustomerNotificationsScreen(),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Text('Page not found: ${state.error}'),
      ),
    ),
  );
});

final routerNotifierProvider = Provider<RouterNotifier>((ref) {
  return RouterNotifier(ref);
});

class RouterNotifier extends ChangeNotifier {
  final Ref _ref;

  RouterNotifier(this._ref) {
    _ref.listen(firebaseAuthStateProvider, (_, __) => notifyListeners());
    _ref.listen(
      currentUserProvider.select((userAsync) {
        final user = userAsync.valueOrNull;
        if (user == null) return null;
        return '${user.role}_${user.onboardingComplete}';
      }),
      (_, __) => notifyListeners(),
    );
  }

  String? redirect(BuildContext context, GoRouterState state) {
    final authState = _ref.read(firebaseAuthStateProvider);
    final currentUser = _ref.read(currentUserProvider);

    final isAuthLoading = authState.isLoading;
    final isUserLoading = authState.valueOrNull != null && currentUser.isLoading;

    if (isAuthLoading || isUserLoading) return null;

    final firebaseUser = authState.valueOrNull;
    final isLoggedIn = firebaseUser != null;
    final isAuthRoute = state.matchedLocation == AppRoutes.login ||
        state.matchedLocation == AppRoutes.register ||
        state.matchedLocation == AppRoutes.forgotPassword ||
        state.matchedLocation == AppRoutes.splash;

    final user = currentUser.valueOrNull;

    // DEFENSIVE: If already on a role-appropriate screen, do NOT redirect anywhere.
    // This stops the "jump to dashboard" when profile data (like notifications) updates.
    if (user != null) {
      if (user.isBaker && state.matchedLocation.startsWith('/baker')) {
        return null;
      }
      if (user.isCustomer && state.matchedLocation.startsWith('/customer')) {
        return null;
      }
    }

    if (state.matchedLocation == AppRoutes.splash) {
      if (!isLoggedIn) return AppRoutes.login;
      if (user != null) {
        if (user.isBaker) {
          return user.onboardingComplete
              ? AppRoutes.bakerDashboard
              : AppRoutes.bakerOnboarding;
        } else {
          return user.onboardingComplete
              ? AppRoutes.customerHome
              : AppRoutes.customerOnboarding;
        }
      }
      if (!currentUser.isLoading) return AppRoutes.login;
      return null;
    }

    if (!isLoggedIn && !isAuthRoute) return AppRoutes.login;
    if (!isLoggedIn) return null;
    if (user == null) return null;

    if (isAuthRoute) {
      if (user.isBaker) {
        return user.onboardingComplete
            ? AppRoutes.bakerDashboard
            : AppRoutes.bakerOnboarding;
      } else {
        return user.onboardingComplete
            ? AppRoutes.customerHome
            : AppRoutes.customerOnboarding;
      }
    }

    if (state.matchedLocation.startsWith('/baker') && !user.isBaker) {
      return AppRoutes.customerHome;
    }
    if (state.matchedLocation.startsWith('/customer') && !user.isCustomer) {
      return AppRoutes.bakerDashboard;
    }

    return null;
  }
}

// Helper to make GoRouter work with Riverpod streams
class GoRouterRefreshStream extends ChangeNotifier {
  GoRouterRefreshStream(Stream<dynamic> stream) {
    notifyListeners();
    _subscription = stream.listen((_) => notifyListeners());
  }
  late final dynamic _subscription;

  @override
  void dispose() {
    _subscription.cancel();
    super.dispose();
  }
}
