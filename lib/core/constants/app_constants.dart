// ============================================================
// CLOUDINARY CONFIGURATION
// ============================================================
const String cloudinaryCloudName = 'dkhfagiw6';
const String cloudinaryUploadPreset = 'bakesmart_preset';
const String cloudinaryBaseUrl =
    'https://api.cloudinary.com/v1_1/$cloudinaryCloudName/image/upload';

// ============================================================
// APP CONSTANTS
// ============================================================
class AppConstants {
  // App Info
  static const String appName = 'BakeSmart';
  static const String appVersion = '1.0.0';
  static const String baseStorefrontUrl = 'bakesmart.com/store';

  // Theme Colors (Cream & Brown Template)
  static const int backgroundColor = 0xFFFDFCF9;
  static const int cardColor = 0xFFFEF3C7;
  static const int primaryColor = 0xFF78350F;
  static const int secondaryColor = 0xFFD97706;
  static const int textPrimary = 0xFF451A03;
  static const int textSecondary = 0xFF92400E;
  static const int accentColor = 0xFFF59E0B;

  // Firestore Collections
  static const String usersCollection = 'users';
  static const String productsCollection = 'products';
  static const String ingredientsCollection = 'ingredients';
  static const String ordersCollection = 'orders';
  static const String reviewsCollection = 'reviews';
  static const String surplusItemsCollection = 'surplusItems';
  static const String wishlistsCollection = 'wishlists';
  static const String deliverySchedulesCollection = 'deliverySchedules';

  // User Roles
  static const String roleBaker = 'baker';

  // Order Statuses
  static const String orderPlaced = 'placed';
  static const String orderAccepted = 'accepted';
  static const String orderPreparing = 'preparing';
  static const String orderReady = 'ready';
  static const String orderDelivered = 'delivered';
  static const String orderRejected = 'rejected';
  static const String orderCancelled = 'cancelled';

  // Product Categories
  static const List<String> productCategories = [
    'Cakes',
    'Cupcakes',
    'Cookies',
    'Brownies',
    'Pastries',
    'Donuts',
    'Custom Cakes',
    'Beverages',
  ];

  // Dietary Labels
  static const List<String> dietaryLabels = [
    'Eggless',
    'Sugar-Free',
    'Gluten-Free',
    'Nut-Free',
  ];

  // Baker Specialties
  static const List<String> bakerSpecialties = [
    'Wedding Cakes',
    'Birthday Cakes',
    'Cupcakes',
    'Custom Cookies',
    'Pastries',
    'Vegan Bakes',
    'Gluten-Free',
    'Sugar-Free',
    'Breads',
    'Macarons',
  ];
  // Product Constraints
  static const double minProductPrice = 20.0;
  static const double maxProductPrice = 250000.0;
}
