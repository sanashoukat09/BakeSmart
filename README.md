# BakeSmart — Flutter App Setup Guide

## 📁 Project: bakesmart-5efda | Cloudinary: dkhfagiw6/bakesmart

---

## ✅ Module 1 — COMPLETE (Auth, Onboarding, Profiles)

All files for Module 1 are ready. Follow the steps below to get the app running.

---

## 🚀 Step-by-Step Setup

### Step 1 — Create the Flutter project shell

Open a terminal in `D:\Bake Smart` and run:

```bash
flutter create . --org com.bakesmart --platforms android,ios
```

This generates the native Android/iOS folders. Then copy all files from this
archive INTO `D:\Bake Smart`, overwriting anything that gets replaced.

---

### Step 2 — Connect Firebase

1. Go to: https://console.firebase.google.com/project/bakesmart-5efda/overview
2. Click ⚙️ → **Project Settings** → **Your apps** → Add app → Android
3. Package name: `com.bakesmart.app`
4. Download `google-services.json`
5. Place it at: `D:\Bake Smart\android\app\google-services.json`

For iOS:
1. Add iOS app, Bundle ID: `com.bakesmart.app`
2. Download `GoogleService-Info.plist`
3. Place it at: `D:\Bake Smart\ios\Runner\GoogleService-Info.plist`

---

### Step 3 — Generate firebase_options.dart

Install the FlutterFire CLI (run once):
```bash
dart pub global activate flutterfire_cli
```

Then inside `D:\Bake Smart`:
```bash
flutterfire configure --project=bakesmart-5efda
```

This will replace `lib/firebase_options.dart` with the real config.

---

### Step 4 — Enable Firebase services

In your Firebase console (bakesmart-5efda):

1. **Authentication** → Sign-in method → Enable:
   - Email/Password ✓
   - Google ✓

2. **Firestore Database** → Create database → Start in test mode

3. **Storage** (not needed — using Cloudinary instead) ✓

---

### Step 5 — Install dependencies & run

```bash
cd "D:\Bake Smart"
flutter pub get
flutter run
```

---

### Step 6 — Deploy Firestore rules

```bash
npm install -g firebase-tools
firebase login
firebase deploy --only firestore:rules --project bakesmart-5efda
```

### Step 7 — Deploy Cloud Functions

```bash
cd functions
npm install
cd ..
firebase deploy --only functions --project bakesmart-5efda
```

---

## 📂 Project Structure

```
D:\Bake Smart\
├── lib/
│   ├── main.dart                          ← Entry point
│   ├── firebase_options.dart              ← ⚠️ Replace via flutterfire configure
│   ├── core/
│   │   ├── constants/app_constants.dart   ← Cloudinary + app config
│   │   ├── theme/baker_theme.dart         ← Dark amber theme (baker)
│   │   ├── theme/customer_theme.dart      ← Warm cream theme (customer)
│   │   └── router/app_router.dart         ← go_router navigation
│   ├── models/
│   │   └── user_model.dart               ← Firestore user model
│   ├── services/
│   │   ├── auth_service.dart             ← Firebase Auth
│   │   ├── firestore_service.dart        ← Firestore CRUD
│   │   └── cloudinary_service.dart       ← Image upload
│   ├── providers/
│   │   └── auth_provider.dart            ← Riverpod state
│   └── screens/
│       ├── splash_screen.dart
│       ├── auth/
│       │   ├── login_screen.dart
│       │   ├── register_screen.dart
│       │   └── forgot_password_screen.dart
│       ├── baker/
│       │   ├── baker_onboarding_screen.dart
│       │   ├── baker_dashboard.dart
│       │   └── baker_profile_screen.dart
│       └── customer/
│           ├── customer_onboarding_screen.dart
│           ├── customer_home_screen.dart
│           └── customer_profile_screen.dart
├── functions/
│   ├── index.js                          ← Cloud Functions
│   └── package.json
├── firestore.rules                        ← Security rules
├── firebase.json                          ← Firebase config
└── pubspec.yaml                           ← All dependencies
```

---

## 🎨 UI Design

| Side | Theme | Font | Primary Color |
|------|-------|------|--------------|
| Baker | Dark professional | Space Grotesk | Amber #F59E0B |
| Customer | Light warm | Nunito | Orange-Brown #C2410C |

---

## 📦 Modules Status

| Module | Status | Description |
|--------|--------|-------------|
| 1 | ✅ **DONE** | Auth, Onboarding, Profiles |
| 2 | 🔜 Next | Product & Inventory Management |
| 3 | 🔜 Pending | Cost, Pricing & Surplus |
| 4 | 🔜 Pending | Order Management & Scheduling |
| 5 | 🔜 Pending | Customer Storefront & Cart |
| 6 | 🔜 Pending | Order Tracking & Ratings |
| 10 | 🔜 Pending | Storefront Discovery & Sharing |

---

## ⚠️ Common Issues

**`firebase_options.dart` error** → Run `flutterfire configure --project=bakesmart-5efda`

**Google Sign-In not working** → Add your SHA-1 fingerprint in Firebase console:
```bash
cd android
./gradlew signingReport
```
Copy the SHA1 and add it in Firebase → Project Settings → Your apps → Android app.

**`minSdkVersion` error** → Already set to 23 in `android/app/build.gradle` ✓

**Image picker not working on iOS** → Add to `ios/Runner/Info.plist`:
```xml
<key>NSPhotoLibraryUsageDescription</key>
<string>BakeSmart needs photo access to upload product images</string>
<key>NSCameraUsageDescription</key>
<string>BakeSmart needs camera access to take product photos</string>
```
