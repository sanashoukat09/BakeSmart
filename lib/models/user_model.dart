import 'package:cloud_firestore/cloud_firestore.dart';

class UserModel {
  final String uid;
  final String email;
  final String role; // 'baker' or 'customer'
  final String? displayName;
  final String? photoUrl;
  final bool onboardingComplete;
  final DateTime createdAt;
  final String? fcmToken;

  // Baker-specific fields
  final String? bakeryName;
  final String? location;
  final List<String> specialties;
  final String? bio;
  final List<String> portfolioImages;
  final double rating;
  final int totalReviews;
  final String? contactPhone;
  final String? contactEmail;
  final int dailyOrderCapacity;
  final bool notificationsEnabled;
  final bool newOrderNotif;
  final bool lowStockNotif;
  final bool surplusNotif;

  // Customer-specific fields
  final List<String> dietaryPreferences;
  final List<String> allergens;
  final List<Map<String, dynamic>> savedAddresses;

  UserModel({
    required this.uid,
    required this.email,
    required this.role,
    this.displayName,
    this.photoUrl,
    this.onboardingComplete = false,
    required this.createdAt,
    this.fcmToken,
    // Baker
    this.bakeryName,
    this.location,
    this.specialties = const [],
    this.bio,
    this.portfolioImages = const [],
    this.rating = 0.0,
    this.totalReviews = 0,
    this.contactPhone,
    this.contactEmail,
    this.dailyOrderCapacity = 10,
    this.notificationsEnabled = true,
    this.newOrderNotif = true,
    this.lowStockNotif = true,
    this.surplusNotif = true,
    // Customer
    this.dietaryPreferences = const [],
    this.allergens = const [],
    this.savedAddresses = const [],
  });

  bool get isBaker => role == 'baker';
  bool get isCustomer => role == 'customer';

  factory UserModel.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return UserModel(
      uid: doc.id,
      email: data['email'] ?? '',
      role: data['role'] ?? 'baker',
      displayName: data['displayName'],
      photoUrl: data['photoUrl'],
      onboardingComplete: data['onboardingComplete'] ?? false,
      createdAt: (data['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      fcmToken: data['fcmToken'],
      // Baker
      bakeryName: data['bakeryName'],
      location: data['location'],
      specialties: List<String>.from(data['specialties'] ?? []),
      bio: data['bio'],
      portfolioImages: List<String>.from(data['portfolioImages'] ?? []),
      rating: (data['rating'] ?? 0.0).toDouble(),
      totalReviews: data['totalReviews'] ?? 0,
      contactPhone: data['contactPhone'],
      contactEmail: data['contactEmail'],
      dailyOrderCapacity: data['dailyOrderCapacity'] ?? 10,
      notificationsEnabled: data['notificationsEnabled'] ?? true,
      newOrderNotif: data['newOrderNotif'] ?? true,
      lowStockNotif: data['lowStockNotif'] ?? true,
      surplusNotif: data['surplusNotif'] ?? true,
      // Customer
      dietaryPreferences: List<String>.from(data['dietaryPreferences'] ?? []),
      allergens: List<String>.from(data['allergens'] ?? []),
      savedAddresses:
          List<Map<String, dynamic>>.from(data['savedAddresses'] ?? []),
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'email': email,
      'role': role,
      'displayName': displayName,
      'photoUrl': photoUrl,
      'onboardingComplete': onboardingComplete,
      'createdAt': Timestamp.fromDate(createdAt),
      'fcmToken': fcmToken,
      // Baker
      'bakeryName': bakeryName,
      'location': location,
      'specialties': specialties,
      'bio': bio,
      'portfolioImages': portfolioImages,
      'rating': rating,
      'totalReviews': totalReviews,
      'contactPhone': contactPhone,
      'contactEmail': contactEmail,
      'dailyOrderCapacity': dailyOrderCapacity,
      'notificationsEnabled': notificationsEnabled,
      'newOrderNotif': newOrderNotif,
      'lowStockNotif': lowStockNotif,
      'surplusNotif': surplusNotif,
      // Customer
      'dietaryPreferences': dietaryPreferences,
      'allergens': allergens,
      'savedAddresses': savedAddresses,
    };
  }

  UserModel copyWith({
    String? displayName,
    String? photoUrl,
    bool? onboardingComplete,
    String? fcmToken,
    String? bakeryName,
    String? location,
    List<String>? specialties,
    String? bio,
    List<String>? portfolioImages,
    double? rating,
    int? totalReviews,
    String? contactPhone,
    String? contactEmail,
    int? dailyOrderCapacity,
    bool? notificationsEnabled,
    bool? newOrderNotif,
    bool? lowStockNotif,
    bool? surplusNotif,
    List<String>? dietaryPreferences,
    List<String>? allergens,
    List<Map<String, dynamic>>? savedAddresses,
  }) {
    return UserModel(
      uid: uid,
      email: email,
      role: role,
      displayName: displayName ?? this.displayName,
      photoUrl: photoUrl ?? this.photoUrl,
      onboardingComplete: onboardingComplete ?? this.onboardingComplete,
      createdAt: createdAt,
      fcmToken: fcmToken ?? this.fcmToken,
      bakeryName: bakeryName ?? this.bakeryName,
      location: location ?? this.location,
      specialties: specialties ?? this.specialties,
      bio: bio ?? this.bio,
      portfolioImages: portfolioImages ?? this.portfolioImages,
      rating: rating ?? this.rating,
      totalReviews: totalReviews ?? this.totalReviews,
      contactPhone: contactPhone ?? this.contactPhone,
      contactEmail: contactEmail ?? this.contactEmail,
      dailyOrderCapacity: dailyOrderCapacity ?? this.dailyOrderCapacity,
      notificationsEnabled: notificationsEnabled ?? this.notificationsEnabled,
      newOrderNotif: newOrderNotif ?? this.newOrderNotif,
      lowStockNotif: lowStockNotif ?? this.lowStockNotif,
      surplusNotif: surplusNotif ?? this.surplusNotif,
      dietaryPreferences: dietaryPreferences ?? this.dietaryPreferences,
      allergens: allergens ?? this.allergens,
      savedAddresses: savedAddresses ?? this.savedAddresses,
    );
  }
}
