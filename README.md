# BakeSmart — Flutter App Setup Guide

## 📁 Project: bakesmart-5efda | Cloudinary: dkhfagiw6/bakesmart

---

## ✅ Module 1 — COMPLETE (Auth, Onboarding, Profiles)

All files for Module 1 are ready. Follow the steps below to get the app running.

---

## Module 6 — Local 3D Event Designer

Phase 8 connects the customer Flutter app to the self-hosted service in
`bakesmart_ai/`. Signed-in customers can enter their space, location, event,
theme, cake picture reference and decoration budget; open the combined
interactive 3D scene; and save, reopen, regenerate, share or delete the result.

The recommendation request uses BakeSmart's own locally trained checkpoint. It
does not call Gemini, OpenAI or another external inference service. The cake
picture is selected on the phone but is currently retained only as a reference
name—the procedural renderer does not upload or reconstruct the photograph.

Start the Python service before running the Flutter app:

```powershell
cd bakesmart_ai
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The default Android-emulator URL is `http://10.0.2.2:8000`. For a physical
phone, use the laptop's IPv4 address while both devices are on the same Wi-Fi:

```powershell
flutter run --dart-define=BAKESMART_AI_BASE_URL=http://192.168.1.10:8000
```

Deploy the updated Firestore rules before using saved designs. The rules keep
each `eventDesigns` record private to its authenticated owner. Sharing uses the
real interactive viewer URL and never makes the Firestore input record public.
Because the no-cost setup is self-hosted, a shared viewer link works only while
the BakeSmart Python service is running and reachable from the recipient's
device. A private Wi-Fi address is not an internet-wide public link.

Validate the Flutter integration on a machine with the Flutter SDK installed:

```powershell
flutter analyze
flutter test test/models/event_design_model_test.dart
```

### Phase 9 — AR compatibility and device fallback

Phase 9 checks Android's motion-tracking camera feature locally through
`PackageManager` as a conservative AR-hardware signal.
Camera and AR features are optional in the manifest, so phones without AR can
still install BakeSmart. The check does not install, query or require Google Play
Services for AR.

The result screen follows this fixed order:

1. Show `Open in AR` only when the phone reports AR camera hardware **and** the
   BakeSmart response contains `ar_supported=true` with a real `ar_url`.
2. Otherwise show `Open Interactive 3D View` when `viewer_3d_url` exists.
3. Otherwise show `Concept preview—not to scale` with no fake button.

The current procedural backend intentionally returns no AR URL, so Phase 9 uses
the interactive 3D viewer on both unsupported devices and AR-capable devices.
Hardware detection uses Android's documented
[`FEATURE_CAMERA_AR`](https://developer.android.com/reference/android/content/pm/PackageManager#FEATURE_CAMERA_AR)
flag, available from API level 28.

### Phase 10 — Venue evidence and clearance-aware placement

Customers now select a required wide venue photo and may add a second angle.
The photos are sent only to the self-hosted BakeSmart service, analysed in
memory, and discarded. A free local Pillow/NumPy analyser reports resolution,
orientation, lighting, contrast, sharpness and horizontal structural cues. It
uses no external model, pretrained weights or inference API.

The analyser deliberately does **not** claim that it has identified doors,
windows, furniture, outlets or exact dimensions. Customers enter measured room
dimensions, an optional known reference length, and the coordinates and sizes
of visible obstacles, then confirm the obstacle map. BakeSmart evaluates three
focal positions, preserves at least 0.90 m of circulation in front of the
setup, and returns:

- the suggested focal centre measured from the left edge;
- available front clearance and any blocking obstacle labels;
- high, medium or low evidence confidence;
- separate confirmed facts and remaining assumptions.

When evidence is incomplete, the result stays labelled
`Concept preview—not to scale` and requires manual venue review. No uploaded
venue photo is added to the training dataset or persisted by Phase 10.

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
| 6 | ✅ **Phase 10 complete** | Local venue-photo evidence, measured obstacle-aware placement, 3D fallback, save and sharing |
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
