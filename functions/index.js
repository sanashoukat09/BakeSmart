const functions = require('firebase-functions');
const admin = require('firebase-admin');

admin.initializeApp();
const db = admin.firestore();

async function sendToUser(userId, title, body, data = {}) {
  if (!userId) return;
  const userDoc = await db.collection('users').doc(userId).get();
  if (!userDoc.exists) return;

  const user = userDoc.data();
  if (user.notificationsEnabled === false || !user.fcmToken) return;

  try {
    await admin.messaging().send({
      token: user.fcmToken,
      notification: { title, body },
      data: Object.fromEntries(
        Object.entries(data).map(([key, value]) => [key, String(value)])
      ),
    });
  } catch (error) {
    console.error(`Failed to send notification to ${userId}`, error);
  }
}

// ─────────────────────────────────────────────────────────────
// Module 2 — Reduce ingredient stock when order is placed
// ─────────────────────────────────────────────────────────────
exports.onOrderPlaced = functions.firestore
  .document('orders/{orderId}')
  .onCreate(async (snap, context) => {
    const order = snap.data();
    if (!order || !order.items) return;

    await sendToUser(
      order.bakerId,
      'New order received',
      `${order.customerName || 'A customer'} placed an order for Rs. ${order.totalAmount || 0}.`,
      { type: 'new_order', orderId: context.params.orderId }
    );
    console.log(`Baker notified for order ${context.params.orderId}`);
  });

exports.onOrderStatusChanged = functions.firestore
  .document('orders/{orderId}')
  .onUpdate(async (change, context) => {
    const before = change.before.data();
    const after = change.after.data();
    if (!before || !after || before.status === after.status) return;

    await sendToUser(
      after.customerId,
      'Order status updated',
      `Your order is now ${after.status}.`,
      { type: 'order_status', orderId: context.params.orderId, status: after.status }
    );
  });

// ─────────────────────────────────────────────────────────────
// Module 3 — Auto-remove surplus when stock hits 0
// ─────────────────────────────────────────────────────────────
exports.onIngredientUpdated = functions.firestore
  .document('ingredients/{ingredientId}')
  .onUpdate(async (change, context) => {
    const after = change.after.data();
    const before = change.before.data();
    if (
      after.quantity <= (after.lowStockThreshold || 1) &&
      before.quantity > (after.lowStockThreshold || 1)
    ) {
      await sendToUser(
        after.bakerId,
        'Low stock alert',
        `${after.name || 'An ingredient'} is running low.`,
        { type: 'low_stock', ingredientId: context.params.ingredientId }
      );
    }

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
