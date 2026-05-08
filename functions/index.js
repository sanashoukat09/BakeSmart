const functions = require('firebase-functions');
const admin = require('firebase-admin');

admin.initializeApp();
const db = admin.firestore();

// ─────────────────────────────────────────────────────────────
// Module 2 — Reduce ingredient stock when order is placed
// ─────────────────────────────────────────────────────────────
exports.onOrderPlaced = functions.firestore
  .document('orders/{orderId}')
  .onCreate(async (snap, context) => {
    const order = snap.data();
    if (!order || !order.items) return;

    const batch = db.batch();

    for (const item of order.items) {
      if (!item.productId || !item.quantity) continue;

      // Get product to find linked ingredients
      const productDoc = await db.collection('products').doc(item.productId).get();
      if (!productDoc.exists) continue;

      const product = productDoc.data();
      if (!product.ingredients) continue;

      // ingredients is a Map: { ingredientId: quantityNeeded }
      for (const [ingredientId, quantityNeeded] of Object.entries(product.ingredients)) {
        const ingRef = db.collection('ingredients').doc(ingredientId);
        const reduction = quantityNeeded * item.quantity;

        batch.update(ingRef, {
          quantity: admin.firestore.FieldValue.increment(-reduction),
          updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        });
      }
    }

    await batch.commit();
    console.log(`Ingredient stock updated for order ${context.params.orderId}`);
  });

// ─────────────────────────────────────────────────────────────
// Module 3 — Auto-remove surplus when stock hits 0
// ─────────────────────────────────────────────────────────────
exports.onIngredientUpdated = functions.firestore
  .document('ingredients/{ingredientId}')
  .onUpdate(async (change, context) => {
    const after = change.after.data();
    if (after.quantity > 0) return;

    // Find surplus items using this ingredient's baker
    const surplusSnap = await db.collection('surplusItems')
      .where('bakerId', '==', after.bakerId)
      .get();

    const batch = db.batch();
    surplusSnap.forEach(doc => {
      batch.update(doc.ref, { active: false, removedAt: admin.firestore.FieldValue.serverTimestamp() });
    });

    await batch.commit();
  });

// ─────────────────────────────────────────────────────────────
// Module 6 — Update baker rating when a review is written
// ─────────────────────────────────────────────────────────────
exports.onReviewCreated = functions.firestore
  .document('reviews/{reviewId}')
  .onCreate(async (snap, context) => {
    const review = snap.data();
    if (!review || !review.bakerId || !review.rating) return;

    const reviewsSnap = await db.collection('reviews')
      .where('bakerId', '==', review.bakerId)
      .get();

    if (reviewsSnap.empty) return;

    let total = 0;
    reviewsSnap.forEach(doc => {
      total += doc.data().rating || 0;
    });
    const avg = total / reviewsSnap.size;

    await db.collection('users').doc(review.bakerId).update({
      rating: parseFloat(avg.toFixed(1)),
      totalReviews: reviewsSnap.size,
    });

    console.log(`Baker ${review.bakerId} rating updated to ${avg.toFixed(1)}`);
  });

// ─────────────────────────────────────────────────────────────
// Module 4 — Check daily capacity conflict on order accept
// ─────────────────────────────────────────────────────────────
exports.checkCapacityOnAccept = functions.firestore
  .document('orders/{orderId}')
  .onUpdate(async (change, context) => {
    const before = change.before.data();
    const after = change.after.data();

    // Only trigger when status changes to 'accepted'
    if (before.status === after.status || after.status !== 'accepted') return;

    const bakerId = after.bakerId;
    const deliveryDate = after.deliveryDate;

    if (!bakerId || !deliveryDate) return;

    // Count accepted orders for same baker on same delivery date
    const ordersSnap = await db.collection('orders')
      .where('bakerId', '==', bakerId)
      .where('deliveryDate', '==', deliveryDate)
      .where('status', 'in', ['accepted', 'preparing', 'ready'])
      .get();

    const bakerDoc = await db.collection('users').doc(bakerId).get();
    const capacity = bakerDoc.data()?.dailyOrderCapacity || 10;

    if (ordersSnap.size > capacity) {
      // Flag the order with a capacity warning
      await change.after.ref.update({
        capacityWarning: true,
        capacityWarningMessage: `You have ${ordersSnap.size} orders on ${deliveryDate}, exceeding your daily capacity of ${capacity}.`,
      });
    }
  });
