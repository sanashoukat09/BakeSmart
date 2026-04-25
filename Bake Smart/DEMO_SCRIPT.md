# BakeSmart Demo Script — 10 Minute Supervisor Presentation

## Before the Demo
- Install APK on Android phone (Screen share to projector if possible).
- Open Admin Web Panel in Chrome: https://bakesmart-app.web.app
- Have all test accounts ready (See TEST_ACCOUNTS.md).
- Clear app data for a fresh start.

---

## Minute 1-2: Problem and Solution
**Talk Points:**
- "Home bakers currently manage their entire business via fragmented WhatsApp messages, notebooks, and manual calculations. They lack a unified platform for inventory, costing, and customer discovery."
- "BakeSmart is the solution: A unified mobile ecosystem for bakers to manage their backend and for customers to discover local home-made treats."
- **Action**: Show the app icon and the splash screen.

## Minute 3-4: Customer Experience
**Action**: Login as `customer@bakesmart.com`.
- "The customer journey starts with discovery. Our catalogue uses real-time Firestore filters."
- **Action**: Search for 'Chocolate' and filter by 'Eggless'.
- "Notice the 'Single Baker Cart' rule. We ensure logistics stay simple by preventing multi-bakery orders in one go."
- **Action**: Add a cake to cart and proceed to the Checkout screen. Show the delivery/pickup toggle.

## Minute 5-6: Baker Experience (Backend)
**Action**: Login as `baker@bakesmart.com`.
- "Bakers have a powerful dashboard. Here they can see their 'Low Stock' ingredients automatically calculated."
- **Action**: Tap 'Inventory'. Show a 'Low Stock' badge.
- "We also have a built-in cost calculator. When adding a product, BakeSmart calculates the profit margin based on ingredient prices."
- **Action**: Open 'Add Product'. Show the margin percentage updating as you change the price.

## Minute 7-8: The Order Lifecycle
**Action**: Login back as Customer, place the order. Then login as Baker.
- "Real-time notifications are the heartbeat of the app."
- **Action**: Show the notification tray in the Baker app.
- "As the baker accepts and prepares the order, the customer's tracking screen updates instantly without a refresh."
- **Action**: Update status to 'Ready'. Switch to Customer phone and show the visual stepper updating.

## Minute 9: Community and Trust
- "To build a brand, bakers need community. Our hub allows sharing and engagement."
- **Action**: Show the Community Hub feed. Like a post.
- "We use a Progressive Trust model. Only verified bakers get the trust badge, which prevents fraud."
- **Action**: Show the 'Verified Baker' badge on a post.

## Minute 10: Admin Web Panel & Moderation
**Action**: Switch to the laptop/Chrome view.
- "Finally, the Admin Portal ensures the platform stays safe."
- **Action**: Show the 'Verification Queue'. 
- "Admins can review kitchen photos submitted by bakers before granting selling privileges."
- **Action**: Show a 'Flagged Post' in moderation and explain the suspension system.

---

## Closing Points
- **Architecture**: Built using Clean Architecture and Riverpod for scalability.
- **Cost**: Zero operational cost on the Firebase Free Tier.
- **Scalability**: Ready for Phase 2 AI features like recipe optimization and AR design previews.
