// SHARED MODEL — Keep in sync with d:/Bake Smart/lib/features/auth/models/user_model.dart
import 'package:cloud_firestore/cloud_firestore.dart';

class UserModel {
  final String uid;
  final String name;
  final String email;
  final String role; // 'baker', 'customer', 'admin'
  final DateTime createdAt;
  final String? profileImageUrl;

  // Baker specific
  final String? bakeryName;
  final String? bakeryDescription;
  final String? city;
  final String? phone;
  final String? deliveryArea; // Stage 2
  final String? whatsappNumber; // Stage 2
  final String? paymentMethod; // Stage 2
  final String? paymentNumber; // Stage 2
  final String? kitchenPhotoUrl; // Stage 2
  final List<String>? productPhotoUrls; // Stage 2
  final bool hygieneAgreement; // Stage 2
  final bool termsAgreement; // Stage 2
  final DateTime? verificationSubmittedAt; // Stage 2
  
  // STAGE 3 IDENTITY VERIFICATION — To be implemented when payment
  // withdrawal feature is added. Will collect CNIC at that point only,
  // following the same model as JazzCash and EasyPaisa which require
  // CNIC only for financial account activation above threshold amounts.

  final String? verificationStatus; // 'unverified', 'pending', 'verified', 'rejected'
  final String? rejectionReason;
  final bool? verificationBadge;

  // Global specific
  final bool isSuspended;

  // Customer specific
  final List<String>? dietaryPreferences;
  final List<String>? allergies;

  UserModel({
    required this.uid,
    required this.name,
    required this.email,
    required this.role,
    required this.createdAt,
    this.profileImageUrl,
    this.bakeryName,
    this.bakeryDescription,
    this.city,
    this.phone,
    this.deliveryArea,
    this.whatsappNumber,
    this.paymentMethod,
    this.paymentNumber,
    this.kitchenPhotoUrl,
    this.productPhotoUrls,
    this.hygieneAgreement = false,
    this.termsAgreement = false,
    this.verificationSubmittedAt,
    this.verificationStatus,
    this.rejectionReason,
    this.verificationBadge,
    this.isSuspended = false,
    this.dietaryPreferences,
    this.allergies,
  });

  Map<String, dynamic> toMap() {
    return {
      'uid': uid,
      'name': name,
      'email': email,
      'role': role,
      'createdAt': Timestamp.fromDate(createdAt),
      'profileImageUrl': profileImageUrl,
      'isSuspended': isSuspended,
      if (role == 'baker') ...{
        'bakeryName': bakeryName,
        'bakeryDescription': bakeryDescription,
        'city': city,
        'phone': phone,
        'deliveryArea': deliveryArea,
        'whatsappNumber': whatsappNumber,
        'paymentMethod': paymentMethod,
        'paymentNumber': paymentNumber,
        'kitchenPhotoUrl': kitchenPhotoUrl,
        'productPhotoUrls': productPhotoUrls,
        'hygieneAgreement': hygieneAgreement,
        'termsAgreement': termsAgreement,
        'verificationSubmittedAt': verificationSubmittedAt != null ? Timestamp.fromDate(verificationSubmittedAt!) : null,
        'verificationStatus': verificationStatus ?? 'unverified',
        'rejectionReason': rejectionReason,
        'verificationBadge': verificationBadge ?? false,
      },
      if (role == 'customer') ...{
        'dietaryPreferences': dietaryPreferences ?? [],
        'allergies': allergies ?? [],
      }
    };
  }

  factory UserModel.fromMap(Map<String, dynamic> map) {
    return UserModel(
      uid: map['uid'] ?? '',
      name: map['name'] ?? '',
      email: map['email'] ?? '',
      role: map['role'] ?? 'customer',
      createdAt: (map['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
      profileImageUrl: map['profileImageUrl'],
      bakeryName: map['bakeryName'],
      bakeryDescription: map['bakeryDescription'],
      city: map['city'],
      phone: map['phone'],
      deliveryArea: map['deliveryArea'],
      whatsappNumber: map['whatsappNumber'],
      paymentMethod: map['paymentMethod'],
      paymentNumber: map['paymentNumber'],
      kitchenPhotoUrl: map['kitchenPhotoUrl'],
      productPhotoUrls: List<String>.from(map['productPhotoUrls'] ?? []),
      hygieneAgreement: map['hygieneAgreement'] ?? false,
      termsAgreement: map['termsAgreement'] ?? false,
      verificationSubmittedAt: (map['verificationSubmittedAt'] as Timestamp?)?.toDate(),
      verificationStatus: map['verificationStatus'],
      rejectionReason: map['rejectionReason'],
      verificationBadge: map['verificationBadge'],
      isSuspended: map['isSuspended'] ?? false,
      dietaryPreferences: List<String>.from(map['dietaryPreferences'] ?? []),
      allergies: List<String>.from(map['allergies'] ?? []),
    );
  }
}
