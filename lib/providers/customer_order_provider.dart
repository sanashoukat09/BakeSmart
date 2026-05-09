import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/order_model.dart';
import '../models/review_model.dart';
import 'auth_provider.dart';
import 'dart:async';

// Stream of orders for the current customer
final customerOrdersProvider = StreamProvider<List<OrderModel>>((ref) {
  final uid = ref.watch(firebaseAuthStateProvider.select((user) => user.value?.uid));
  if (uid == null) return Stream.value([]);

  return ref.watch(firestoreServiceProvider).streamCustomerOrders(uid);
});

// Review State Notifier
class ReviewNotifier extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;
  ReviewNotifier(this._ref) : super(const AsyncValue.data(null));

  Future<void> submitReview(ReviewModel review) async {
    state = const AsyncValue.loading();
    try {
      await _ref.read(firestoreServiceProvider).saveReview(review);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final reviewNotifierProvider =
    StateNotifierProvider<ReviewNotifier, AsyncValue<void>>((ref) {
  return ReviewNotifier(ref);
});
