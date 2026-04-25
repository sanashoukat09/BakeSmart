# BakeSmart Handover Document

## Section 1 — Project Overview
**Project Name:** BakeSmart
**Subtitle:** An AI-Driven Bakery Management and Customer Marketplace System for Home and Small-Scale Bakers
**Team:** 
- Ramisha Maryam (CIIT/SP23-BCS-077/ISB)
- Sana Shoukat (CIIT/SP23-BCS-082/ISB)
- Zuha Naveed (CIIT/SP23-BCS-104/ISB)
**Supervisor:** Dr. Nusrat Shaheen
**Institution:** COMSATS University Islamabad
**Degree:** Bachelor of Science in Computer Science (2023 to 2027)
**MVP Completion Date:** April 2026
**Platform:** Android Mobile App and Web Admin Panel

---

## Section 2 — Complete Feature List

### 1. Authentication & Security
- **Role-Based Routing**: Automatic redirection to Customer, Baker, or Admin views.
- **Progressive Trust Check**: Immediate suspension detection on app resume.
- **Secure Onboarding**: Dedicated registration for Bakers and Customers.

### 2. Baker Management (Verified Bakers)
- **Inventory Management**: Real-time tracking of ingredients with "Low Stock" and "Expired" alerts.
- **Product Management**: Create and edit listings with automated cost-profit margin calculators.
- **Order Management**: Accept, Reject, and track orders through a custom workflow.
- **Surplus Marketplace**: Ability to mark products as "Surplus" for flash deals.

### 3. Customer Marketplace
- **Intelligent Catalogue**: Searchable product list with filters for tags and availability.
- **Shopping Cart**: Single-baker cart restriction to prevent fulfillment conflicts.
- **Order Tracking**: Visual status progression from "Placed" to "Delivered".
- **Reviews & Ratings**: Feedback system linked to successful deliveries.

### 4. Community Hub
- **Social Feed**: Bakers and Customers can share posts, images, and tips.
- **Engagement**: Real-time likes and threaded comments.
- **Moderation**: Reporting/Flagging system for inappropriate content.

### 5. Notification System
- **Real-time Alerts**: In-app notifications for order updates, comments, and verification status.
- **Unread Badges**: Visual indicators for new activity.

---

## Section 3 — Technology Stack

### Flutter Dependencies (`pubspec.yaml`)
| Dependency | Version | Purpose |
|---|---|---|
| `firebase_core` | ^4.6.0 | Firebase App initialization |
| `firebase_auth` | ^6.3.0 | Identity management and secure login |
| `cloud_firestore` | ^6.2.0 | Real-time NoSQL database for all app data |
| `firebase_storage` | ^13.2.0 | Hosting for product and verification images |
| `flutter_riverpod` | ^3.3.1 | Global state management and dependency injection |
| `cached_network_image`| ^3.4.1 | Image caching and performance optimization |
| `image_picker` | ^1.2.1 | Camera/Gallery access for photo uploads |
| `google_fonts` | ^6.2.1 | Modern typography implementation |
| `intl` | ^0.20.2 | Date and currency formatting |

---

## Section 4 — Architecture Overview
BakeSmart follows a **Feature-First Clean Architecture** pattern.

### Folder Structure
- `lib/core/`: Global configurations and theme.
- `lib/features/`: Modular components (Auth, Baker, Customer, Community, Notifications).
- `lib/shared/`: Reusable UI widgets.
- `services/`: Business logic and Firebase interactions.
- `models/`: Data structures and JSON serialization.

### User Roles & Routing
1. **Customer**: Redirected to `ProductCatalogueScreen`.
2. **Baker**: Redirected to `BakerDashboardScreen`.
3. **Admin**: Restricted from mobile app; prompted to use Web Portal.

---

## Section 5 — Firestore Data Model

| Collection | Key Fields | Description |
|---|---|---|
| `users` | `role`, `verificationStatus`, `bakeryName`, `isSuspended` | Core profile data and role settings. |
| `products` | `bakerId`, `basePrice`, `costPrice`, `images`, `isSurplus` | Bakery items and recipe metadata. |
| `inventory` | `quantity`, `lowStockThreshold`, `expiryDate`, `status` | Baker ingredient tracking. |
| `orders` | `customerId`, `bakerId`, `status`, `statusHistory` | Transactional data and fulfillment tracking. |
| `communityPosts`| `authorId`, `content`, `likedBy`, `isFlagged` | Social hub posts and moderation status. |
| `notifications` | `recipientId`, `title`, `type`, `isRead` | User-specific activity alerts. |

---

## Section 6 — Security Model

### Firestore Rules
- **Role Isolation**: Customers cannot modify products or inventory.
- **Baker Integrity**: Bakers can only edit their own products and inventory.
- **Suspension Guard**: Suspended users are blocked from all write operations.
- **Community Safety**: Authors cannot unflag their own reported posts (Moderator only).

### Storage Rules
- **Private Tiers**: Verification documents are only visible to the owner and Admins.
- **Public Assets**: Product images are globally readable by authenticated users.

---

## Section 7 — Baker Verification System (Progressive Trust)
1. **Stage 1 (Unverified)**: Access to inventory but cannot list products for sale.
2. **Stage 2 (Pending)**: Admin reviews kitchen photos and business details.
3. **Stage 3 (Verified)**: Full selling privileges and "Verified Baker" badge.

---

## Section 8 — Admin Web Panel
The admin panel provides a desktop-optimized interface for:
- **Verification Queue**: Approving/Rejecting baker applications.
- **User Moderation**: Suspending malicious accounts.
- **Content Cleanup**: Reviewing and deleting flagged community posts.
**Access**: [https://bakesmart-app.web.app](https://bakesmart-app.web.app)

---

## Section 9 — Installation Guide
1. Enable "Install from Unknown Sources" in Android settings.
2. Copy `app-release.apk` to your phone.
3. Tap the file to install.

---

## Section 10 — Admin Account Setup
1. Register an account in the app with `admin@bakesmart.com`.
2. Go to Firebase Console → Firestore → `users` collection.
3. Locate the doc for the admin email.
4. Set `role: "admin"`.

---

## Section 11 — Known Limitations
- **Platform**: Android only (iOS not currently supported).
- **Payments**: Cash on Delivery (COD) only; no integrated gateway.
- **Tracking**: Real-time GPS delivery tracking is not implemented.
- **Notifications**: In-app alerts only; Firebase Cloud Messaging (Push) not included in MVP.

---

## Section 12 — Post MVP Roadmap
- **AI Integration**: Recipe optimization and photo-to-instruction conversion.
- **AR Features**: Augmented Reality cake design previews.
- **Cross-Platform**: Support for iOS and Desktop apps.
- **Payment Gateway**: Integration with JazzCash/EasyPaisa.
