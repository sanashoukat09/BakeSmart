# SRS Updates & Development Deviations

This document tracks changes made during the development of BakeSmart that differ from the original Software Requirements Specification (SRS).

## 1. Features Added (Beyond SRS)
- **Automated Profit Margin Calculator**: Originally planned as a manual input, we implemented a real-time calculator that links Product Price to Ingredient Cost.
- **Progressive Trust Security Rules**: Added granular Firestore rules to prevent author-self-flagging and enforced 'Suspended' state at the database level.
- **Image Caching Layer**: Added `cached_network_image` to improve app performance on low-bandwidth connections, which wasn't a functional requirement but was necessary for UX.

## 2. Features Modified from Original SRS
- **Baker Verification**: The original SRS suggested a simple checkbox. We implemented a 3-stage model (Unverified -> Pending -> Verified) with mandatory photo uploads (Kitchen and Products) for improved safety.
- **Cart Management**: Modified to enforce "Single Baker Cart" to simplify fulfillment logistics for the MVP, rather than allowing multi-bakery split orders.
- **Inventory Status**: Status is now dynamically calculated (`in_stock`, `low`, `expired`, `out_of_stock`) based on date and quantity, rather than being a static manual toggle.

## 3. Features Deferred to Phase 2 (Future)
- **AI-Powered Recipe Assistant**: Deferred due to complexity and the need for a curated Pakistani-bakery dataset.
- **AR Product Previews**: Moved to Phase 2 to ensure core marketplace stability first.
- **Push Notifications (FCM)**: Replaced with real-time in-app notifications for MVP to reduce initial setup complexity and potential configuration errors on supervisor devices.
- **Integrated Payment Gateway**: Deferred to Phase 3; Cash on Delivery (COD) is used for MVP as per local home-baker preferences.

## 4. Technical Design Decisions
- **State Management**: Chose **Riverpod** over Provider/Bloc for its better handling of asynchronous data streams (Firestore snapshots) and safety.
- **Database Architecture**: Denormalized certain fields (e.g., `bakerName` inside `ProductModel`) to minimize read-costs and improve catalogue scroll speed.
- **Navigation**: Implemented a "Cold Start Suspension Check" in `AuthChecker` to ensure banned users are kicked out immediately upon opening the app.
