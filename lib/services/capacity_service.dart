import 'package:flutter/foundation.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user_model.dart';
import '../core/constants/app_constants.dart';

class CapacityService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  /// Check if baker has capacity on given date
  Future<Map<String, dynamic>> checkCapacity({
    required String bakerId,
    required DateTime deliveryDate,
  }) async {
    try {
      debugPrint('[CapacityCheck] Starting check for bakerId: $bakerId, date: $deliveryDate');
      // Get baker's capacity limit
      final bakerDoc = await _db.collection(AppConstants.usersCollection).doc(bakerId).get();
      if (!bakerDoc.exists) {
        debugPrint('[CapacityCheck] Baker doc does not exist for ID: $bakerId');
        return {'available': true, 'ordersCount': 0, 'capacity': 10, 'percentFull': 0};
      }

      final baker = UserModel.fromFirestore(bakerDoc);
      final capacity = baker.dailyOrderCapacity;
      debugPrint('[CapacityCheck] Baker capacity limit: $capacity');

      // Get orders for this date
      final startOfDay = DateTime(deliveryDate.year, deliveryDate.month, deliveryDate.day);
      final endOfDay = startOfDay.add(const Duration(days: 1));
      debugPrint('[CapacityCheck] Date range: $startOfDay to $endOfDay');

      final ordersSnapshot = await _db
          .collection(AppConstants.ordersCollection)
          .where('bakerId', isEqualTo: bakerId)
          .where('deliveryDate', isGreaterThanOrEqualTo: Timestamp.fromDate(startOfDay))
          .where('deliveryDate', isLessThan: Timestamp.fromDate(endOfDay))
          .get();

      debugPrint('[CapacityCheck] Found ${ordersSnapshot.docs.length} total orders in date range');

      final activeStatuses = [
        AppConstants.orderPlaced,
        AppConstants.orderAccepted,
        AppConstants.orderPreparing,
        AppConstants.orderReady,
      ];

      final filteredDocs = ordersSnapshot.docs.where((doc) {
        final data = doc.data();
        final status = data['status'] as String?;
        final delDate = data['deliveryDate'];
        debugPrint('[CapacityCheck] Order ${doc.id} - Status: $status, DeliveryDate: $delDate');
        return activeStatuses.contains(status);
      }).toList();

      final ordersCount = filteredDocs.length;
      final percentFull = (ordersCount / capacity * 100).toInt();
      final available = ordersCount < capacity;

      debugPrint('[CapacityCheck] Active orders count: $ordersCount, Percent Full: $percentFull%, Available: $available');

      return {
        'available': available,
        'ordersCount': ordersCount,
        'capacity': capacity,
        'percentFull': percentFull,
      };
    } catch (e, stack) {
      debugPrint('[CapacityCheck] Exception caught: $e');
      debugPrint('[CapacityCheck] Stack trace: $stack');
      return {
        'available': true,
        'ordersCount': 0,
        'capacity': 10,
        'percentFull': 0,
        'error': e.toString(),
      };
    }
  }

  /// Get alternate available dates (next 14 days with capacity)
  Future<List<DateTime>> getAlternateDates({
    required String bakerId,
    required DateTime requestedDate,
    int daysToCheck = 14,
  }) async {
    final List<DateTime> availableDates = [];
    DateTime checkDate = requestedDate.add(const Duration(days: 1));

    for (int i = 0; i < daysToCheck && availableDates.length < 5; i++) {
      final capacityInfo = await checkCapacity(
        bakerId: bakerId,
        deliveryDate: checkDate,
      );

      if (capacityInfo['available'] == true) {
        availableDates.add(checkDate);
      }

      checkDate = checkDate.add(const Duration(days: 1));
    }

    return availableDates;
  }
}
