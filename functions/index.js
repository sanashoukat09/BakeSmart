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

// ─────────────────────────────────────────────────────────────
// Module 10 — Denormalized Baker Analytics (orders + reviews)
// Time basis: received=createdAt, revenue/completed=relevant deliveryDate
// Range basis: rolling last 7 days (week) + rolling last 30 days (month)
// Aggregates written to: bakerAnalytics/{bakerId}/ranges/{rangeKey}
// ─────────────────────────────────────────────────────────────

// Helpers
function toDateKey(date) {
  // date is a Firestore Timestamp or JS Date
  const d = date.toDate ? date.toDate() : date;
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function isDelivered(status) {
  return status === 'delivered';
}
function isRejected(status) {
  return status === 'rejected';
}

function getRangeKeys(now = new Date()) {
  const nowD = now;
  const weekStart = new Date(nowD);
  weekStart.setUTCDate(weekStart.getUTCDate() - 6); // last 7 days inclusive
  const monthStart = new Date(nowD);
  monthStart.setUTCDate(monthStart.getUTCDate() - 29); // last 30 days inclusive

  return { weekStart, monthStart, now: nowD };
}

async function bumpRangeDoc(tx, bakerId, dateKey, status, totals, kind) {
  // totals: { receivedByDay: {}, completedByDay: {}, rejectedByDay:{}, revenueByDay:{}, profitByDay:{} ...}
  const analyticsRef = db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling');
  const doc = await tx.get(analyticsRef);

  const base = doc.exists ? doc.data() : {};
  const data = { ...base };

  // Ensure nested objects exist
  data.receivedByDay = data.receivedByDay || {};
  data.completedByDay = data.completedByDay || {};
  data.rejectedByDay = data.rejectedByDay || {};
  data.revenueByDay = data.revenueByDay || {};
  data.profitByDay = data.profitByDay || {};

  const dayTotals = dateKey;

  if (kind === 'received') {
    data.receivedByDay[dayTotals] = (data.receivedByDay[dayTotals] || 0) + 1;
    tx.set(analyticsRef, data, { merge: true });
    return;
  }

  if (kind === 'completed' && isDelivered(status)) {
    data.completedByDay[dayTotals] = (data.completedByDay[dayTotals] || 0) + 1;
    tx.set(analyticsRef, data, { merge: true });
    return;
  }

  if (kind === 'rejected' && isRejected(status)) {
    data.rejectedByDay[dayTotals] = (data.rejectedByDay[dayTotals] || 0) + 1;
    tx.set(analyticsRef, data, { merge: true });
    return;
  }

  tx.set(analyticsRef, data, { merge: true });
}

async function bumpRevenueProfitForDelivered(tx, bakerId, deliveryDate, order, rangeStartKey, rangeEndKey) {
  // NOTE: profit estimation in client uses product.profitMargin.
  // For denormalization without joining products here, we store revenue only.
  // Profit can be derived later in FE using product margins; or you can add product lookup here later.
  const analyticsRef = db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling');
  const doc = await tx.get(analyticsRef);
  const data = doc.exists ? doc.data() : {};
  data.revenueByDay = data.revenueByDay || {};
  data.profitByDay = data.profitByDay || {}; // kept for compatibility (0 until computed)

  const dayKey = toDateKey(deliveryDate);

  data.revenueByDay[dayKey] = (data.revenueByDay[dayKey] || 0) + (order.totalAmount || 0);
  data.profitByDay[dayKey] = (data.profitByDay[dayKey] || 0) + 0;

  tx.set(analyticsRef, data, { merge: true });
}

exports.onOrderCreatedUpdateBakerAnalytics = functions.firestore
  .document('orders/{orderId}')
  .onCreate(async (snap, context) => {
    const order = snap.data();
    if (!order || !order.bakerId || !order.createdAt) return;

    const bakerId = order.bakerId;
    const createdAtKey = toDateKey(order.createdAt);

    const now = new Date();
    const { weekStart, monthStart } = getRangeKeys(now);

    const createdDate = order.createdAt.toDate ? order.createdAt.toDate() : order.createdAt;
    if (createdDate < weekStart || createdDate > now) {
      // Still write to rolling doc because UI reads last N days by day keys.
      // But to keep doc small, skip days far outside 30-day window:
      if (createdDate < monthStart) return;
    }

    await db.runTransaction(async (tx) => {
      await bumpRangeDoc(tx, bakerId, createdAtKey, order.status, null, 'received');
    });
  });

exports.onOrderStatusChangedUpdateBakerAnalytics = functions.firestore
  .document('orders/{orderId}')
  .onUpdate(async (change, context) => {
    const before = change.before.data();
    const after = change.after.data();
    if (!before || !after) return;
    if (before.status === after.status) return;
    if (!after.bakerId) return;

    const bakerId = after.bakerId;

    await db.runTransaction(async (tx) => {
      const txOrderRef = change.after.ref;

      // received/completed/rejected counts are bucketted by createdAt for received,
      // and deliveryDate for completed/rejected (if present).
      if (!before.createdAt) return;
      const createdAtKey = toDateKey(after.createdAt);

      // For FE-1 received counts: count when order is created (handled by onCreate).
      // For transitions:
      if (after.status === 'delivered' && after.deliveryDate) {
        const deliveredKey = toDateKey(after.deliveryDate);
        // completedByDay
        const data = (await tx.get(db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling'))).data() || {};
        data.completedByDay = data.completedByDay || {};
        data.completedByDay[deliveredKey] = (data.completedByDay[deliveredKey] || 0) + 1;

        // revenueByDay
        data.revenueByDay = data.revenueByDay || {};
        data.revenueByDay[deliveredKey] = (data.revenueByDay[deliveredKey] || 0) + (after.totalAmount || 0);

        data.profitByDay = data.profitByDay || {};
        data.profitByDay[deliveredKey] = (data.profitByDay[deliveredKey] || 0) + 0;

        tx.set(db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling'), data, { merge: true });
      }

      if (after.status === 'rejected' && after.deliveryDate) {
        const rejectedKey = toDateKey(after.deliveryDate);
        const data = (await tx.get(db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling'))).data() || {};
        data.rejectedByDay = data.rejectedByDay || {};
        data.rejectedByDay[rejectedKey] = (data.rejectedByDay[rejectedKey] || 0) + 1;

        tx.set(db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling'), data, { merge: true });
      }
    });
  });

// Reviews aggregation for FE-4 (count + avg rating per product)
// If your review schema includes productIds, we can distribute rating across products.
// If not, we can only aggregate by bakerId.
exports.onReviewCreatedUpdateBakerAnalytics = functions.firestore
  .document('reviews/{reviewId}')
  .onCreate(async (snap, context) => {
    const review = snap.data();
    if (!review || !review.bakerId || !review.rating) return;

    const bakerId = review.bakerId;
    const productIds = Array.isArray(review.productIds) ? review.productIds : [];

    // If productIds missing, just skip; you can extend later.
    if (!productIds.length) return;

    await db.runTransaction(async (tx) => {
      const analyticsRef = db.collection('bakerAnalytics').doc(bakerId).collection('ranges').doc('rolling');
      const doc = await tx.get(analyticsRef);
      const data = doc.exists ? doc.data() : {};

      data.reviewCountByProduct = data.reviewCountByProduct || {};
      data.reviewAvgByProduct = data.reviewAvgByProduct || {};
      data.reviewSumByProduct = data.reviewSumByProduct || {};

      for (const pid of productIds) {
        const key = String(pid);
        const prevCount = data.reviewCountByProduct[key] || 0;
        const prevSum = data.reviewSumByProduct[key] || 0;

        const newCount = prevCount + 1;
        const newSum = prevSum + review.rating;
        data.reviewCountByProduct[key] = newCount;
        data.reviewSumByProduct[key] = newSum;
        data.reviewAvgByProduct[key] = newSum / newCount;
      }

      tx.set(analyticsRef, data, { merge: true });
    });
  });

// ─────────────────────────────────────────────────────────────
// Module 7 — Step 1: Photo-to-Instruction Assistant (Gemini 2.0 Flash)
// ─────────────────────────────────────────────────────────────
const GEMINI_API_KEY = 'AIzaSyACyy06R4AjDT8v8s11EQKHJoFcYh3bzlo';
const GEMINI_MODEL = 'gemini-2.0-flash';

exports.analyzeCakeDesign = functions.https.onRequest(async (req, res) => {
  // 1. Enable CORS
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'POST');
  res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.status(204).send('');
    return;
  }

  if (req.method !== 'POST') {
    res.status(405).send('Method Not Allowed');
    return;
  }

  try {
    // 2. Verify Firebase Auth Token
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      res.status(401).send('Unauthorized');
      return;
    }
    const idToken = authHeader.split('Bearer ')[1];
    const decodedToken = await admin.auth().verifyIdToken(idToken);
    const userId = decodedToken.uid;

    const { imageUrl, bakerId } = req.body;

    if (!imageUrl || !bakerId) {
      res.status(400).send('Missing imageUrl or bakerId');
      return;
    }

    // Security check: Ensure user is only requesting for themselves
    if (userId !== bakerId) {
       res.status(403).send('Forbidden');
       return;
    }

    // 3. Check Rate Limit (Usage Counter)
    const usageRef = db.collection('usage_counters').doc(bakerId);
    const usageSnap = await usageRef.get();
    const usageData = usageSnap.data() || { photo_analysis_today: 0 };

    if (usageData.photo_analysis_today >= 10) {
      res.status(429).json({ error: 'rate_limit_exceeded', message: 'Daily limit of 10 analyses reached.' });
      return;
    }

    // 4. Fetch Image and Call Gemini
    const imageResponse = await fetch(imageUrl);
    if (!imageResponse.ok) throw new Error('Failed to fetch image from URL');
    const arrayBuffer = await imageResponse.arrayBuffer();
    const base64Image = Buffer.from(arrayBuffer).toString('base64');
    const mimeType = imageResponse.headers.get('content-type') || 'image/jpeg';

    const systemPrompt = `You are an expert cake decorator. Analyze this cake design image and produce:
1. Step-by-step decoration instructions (numbered, in order of execution)
2. Colors used (identify each color and where it appears)
3. Piping tip styles required (e.g., star tip #1M, round tip #2, etc.)
4. Number of cake layers visible or estimated
5. Complete tools and materials list
6. Estimated completion time for an intermediate baker

Return ONLY a valid JSON object with these exact keys: steps (array of strings), colors (array of strings), piping_tips (array of strings), layers (number), tools_materials (array of strings), estimated_time_minutes (number).
If image is not a cake, return: {"error": "not_a_cake"}
If image is too unclear, return: {"error": "image_too_unclear"}
Return nothing else. No markdown, no explanation, only the JSON object.`;

    const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;
    
    const geminiResponse = await fetch(geminiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [
            { text: systemPrompt },
            {
              inline_data: {
                mime_type: mimeType,
                data: base64Image
              }
            }
          ]
        }],
        generationConfig: {
          temperature: 0.1, // Low temperature for more rigid JSON
          maxOutputTokens: 2048,
        }
      })
    });

    if (!geminiResponse.ok) {
      const error = await geminiResponse.json();
      throw new Error(`Gemini Error: ${error.error?.message || 'Unknown'}`);
    }

    const geminiResult = await geminiResponse.json();
    let rawText = geminiResult.candidates?.[0]?.content?.parts?.[0]?.text || '';
    
    // Cleanup potential markdown backticks
    rawText = rawText.replace(/```json\n?|\n?```/g, '').trim();
    
    let analysis;
    try {
      analysis = JSON.parse(rawText);
    } catch (e) {
      console.error('Failed to parse Gemini response:', rawText);
      throw new Error('Invalid JSON format returned by AI');
    }

    // 5. Save to Firestore and Update Counter
    if (!analysis.error) {
      const analysisRecord = {
        bakerId,
        imageUrl,
        ...analysis,
        analyzedAt: admin.firestore.FieldValue.serverTimestamp(),
        status: 'completed'
      };

      await db.collection('photo_analyses').add(analysisRecord);
      await usageRef.set({ 
        photo_analysis_today: admin.firestore.FieldValue.increment(1),
        last_analysis_at: admin.firestore.FieldValue.serverTimestamp()
      }, { merge: true });
    }

    // 6. Return Result
    res.status(200).json(analysis);

  } catch (error) {
    console.error('Error in analyzeCakeDesign:', error);
    res.status(500).json({ error: 'internal_error', message: error.message });
  }
});
