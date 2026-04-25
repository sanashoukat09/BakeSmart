import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'auth_provider.dart';
import 'notification_service.dart';
import '../models/user_model.dart';
import '../models/order_model.dart';
import '../models/community_post_model.dart';
import '../models/notification_model.dart';

final adminServiceProvider = Provider<AdminService>((ref) {
  return AdminService(ref.read(firestoreProvider), ref);
});

// --- Stream Providers for DataTables ---

final verificationQueueProvider = StreamProvider<List<UserModel>>((ref) {
  return ref.watch(firestoreProvider)
      .collection('users')
      .where('verificationStatus', isEqualTo: 'pending')
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) => UserModel.fromMap(doc.data())).toList());
});

final allUsersProvider = StreamProvider<List<UserModel>>((ref) {
  return ref.watch(firestoreProvider)
      .collection('users')
      .orderBy('createdAt', descending: true)
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) => UserModel.fromMap(doc.data())).toList());
});

final flaggedPostsProvider = StreamProvider<List<CommunityPostModel>>((ref) {
  return ref.watch(firestoreProvider)
      .collection('communityPosts')
      .where('isFlagged', isEqualTo: true)
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) => CommunityPostModel.fromMap(doc.data() as Map<String, dynamic>, doc.id)).toList());
});

final allPostsProvider = StreamProvider<List<CommunityPostModel>>((ref) {
  return ref.watch(firestoreProvider)
      .collection('communityPosts')
      .orderBy('createdAt', descending: true)
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) => CommunityPostModel.fromMap(doc.data() as Map<String, dynamic>, doc.id)).toList());
});

final recentOrdersProvider = StreamProvider<List<OrderModel>>((ref) {
  return ref.watch(firestoreProvider)
      .collection('orders')
      .orderBy('placedAt', descending: true)
      .limit(10)
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) => OrderModel.fromMap(doc.data(), doc.id)).toList());
});

// --- Analytics ---

class BakerPerformance {
  final String name;
  final int orderCount;
  BakerPerformance(this.name, this.orderCount);
}

class AdminAnalytics {
  final int totalBakers;
  final int totalCustomers;
  final int ordersToday;
  final double totalRevenue;
  final int totalOrders;
  final String mostOrderedProduct;
  final int newUsersLast7Days;
  final List<int> ordersLast7Days;
  final List<BakerPerformance> topBakers;

  AdminAnalytics({
    required this.totalBakers,
    required this.totalCustomers,
    required this.ordersToday,
    required this.totalRevenue,
    required this.totalOrders,
    required this.mostOrderedProduct,
    required this.newUsersLast7Days,
    required this.ordersLast7Days,
    required this.topBakers,
  });
}

final adminAnalyticsProvider = FutureProvider<AdminAnalytics>((ref) async {
  final firestore = ref.watch(firestoreProvider);
  final now = DateTime.now();
  final sevenDaysAgo = DateTime(now.year, now.month, now.day).subtract(const Duration(days: 7));

  // Addition 4: Read totals from summary document
  final summaryDoc = await firestore.collection('analytics').doc('summary').get();
  final summaryData = summaryDoc.data() ?? {};
  
  final totalRevenue = (summaryData['totalRevenue'] ?? 0).toDouble();
  final totalOrders = (summaryData['totalOrders'] ?? 0).toInt();

  // User counts
  final bakersQuery = await firestore.collection('users').where('role', isEqualTo: 'baker').get();
  final customersQuery = await firestore.collection('users').where('role', isEqualTo: 'customer').get();
  
  // Weekly data for chart and performance
  final weeklyOrdersQuery = await firestore.collection('orders')
      .where('placedAt', isGreaterThan: Timestamp.fromDate(sevenDaysAgo))
      .get();

  final List<int> dailyOrders = List.filled(7, 0);
  final Map<String, int> productFrequency = {};
  final Map<String, int> bakerOrderCount = {};

  for (var doc in weeklyOrdersQuery.docs) {
    final data = doc.data();
    final placedAt = (data['placedAt'] as Timestamp).toDate();
    final bakerName = data['bakerName'] ?? 'Unknown';
    
    // Fill chart bars
    for (int i = 0; i < 7; i++) {
      final dayToMatch = DateTime(now.year, now.month, now.day).subtract(Duration(days: 6 - i));
      if (placedAt.year == dayToMatch.year && placedAt.month == dayToMatch.month && placedAt.day == dayToMatch.day) {
        dailyOrders[i]++;
      }
    }

    // Top products
    final items = data['items'] as List? ?? [];
    for (var item in items) {
      final name = item['productName'] as String? ?? 'Unknown';
      productFrequency[name] = (productFrequency[name] ?? 0) + 1;
    }

    // Baker performance
    bakerOrderCount[bakerName] = (bakerOrderCount[bakerName] ?? 0) + 1;
  }

  String topProduct = 'None';
  if (productFrequency.isNotEmpty) {
    topProduct = productFrequency.entries.reduce((a, b) => a.value > b.value ? a : b).key;
  }

  // Sort bakers and take top 5
  final topBakersList = bakerOrderCount.entries
      .map((e) => BakerPerformance(e.key, e.value))
      .toList()
    ..sort((a, b) => b.orderCount.compareTo(a.orderCount));

  final top5Bakers = topBakersList.length > 5 ? topBakersList.sublist(0, 5) : topBakersList;

  return AdminAnalytics(
    totalBakers: bakersQuery.docs.length,
    totalCustomers: customersQuery.docs.length,
    ordersToday: dailyOrders.last,
    totalRevenue: totalRevenue,
    totalOrders: totalOrders,
    mostOrderedProduct: topProduct,
    newUsersLast7Days: summaryData['newUsersLast7Days'] ?? 0,
    ordersLast7Days: dailyOrders,
    topBakers: top5Bakers,
  );
});

class AdminService {
  final FirebaseFirestore _firestore;
  final Ref _ref;

  AdminService(this._firestore, this._ref);

  Future<void> approveVerification(String userId) async {
    final batch = _firestore.batch();
    
    batch.update(_firestore.collection('users').doc(userId), {
      'verificationStatus': 'verified',
      'verificationBadge': true,
    });

    final products = await _firestore.collection('products')
        .where('bakerId', isEqualTo: userId)
        .get();
    
    for (var doc in products.docs) {
      batch.update(doc.reference, {'bakerIsVerified': true});
    }

    _ref.read(notificationServiceProvider).sendNotificationWithBatch(
      batch,
      recipientId: userId,
      title: 'Verification Approved! 🎉',
      body: 'Congratulations! Your bakery is now verified. You can now list products.',
      type: NotificationType.verificationUpdate,
      referenceId: userId,
    );

    await batch.commit();
  }

  Future<void> rejectVerification(String userId, String reason) async {
    final batch = _firestore.batch();
    
    // Addition 5: Write rejectionReason to users doc
    batch.update(_firestore.collection('users').doc(userId), {
      'verificationStatus': 'rejected',
      'rejectionReason': reason,
    });

    _ref.read(notificationServiceProvider).sendNotificationWithBatch(
      batch,
      recipientId: userId,
      title: 'Verification Update',
      body: 'Your verification was not approved. Reason: $reason',
      type: NotificationType.verificationUpdate,
      referenceId: userId,
    );

    await batch.commit();
  }

  Future<void> toggleUserSuspension(String userId, bool suspend) async {
    await _firestore.collection('users').doc(userId).update({'isSuspended': suspend});
  }

  Future<void> deleteUser(String userId) async {
    await _firestore.collection('users').doc(userId).delete();
  }

  Future<void> removePost(String adminId, String postId) async {
    final batch = _firestore.batch();
    final logRef = _firestore.collection('moderationLogs').doc();
    batch.set(logRef, {
      'adminId': adminId,
      'action': 'remove_post',
      'targetId': postId,
      'targetType': 'post',
      'timestamp': FieldValue.serverTimestamp(),
    });
    batch.delete(_firestore.collection('communityPosts').doc(postId));
    await batch.commit();
  }

  Future<void> restorePost(String adminId, String postId) async {
    final batch = _firestore.batch();
    batch.set(_firestore.collection('moderationLogs').doc(), {
      'adminId': adminId,
      'action': 'restore_post',
      'targetId': postId,
      'targetType': 'post',
      'timestamp': FieldValue.serverTimestamp(),
    });
    batch.update(_firestore.collection('communityPosts').doc(postId), {'isFlagged': false});
    await batch.commit();
  }
}
