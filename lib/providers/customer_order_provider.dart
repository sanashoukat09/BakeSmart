import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/order_model.dart';
import '../models/review_model.dart';
import 'auth_provider.dart';

// Stream of orders for the current customer
final customerOrdersProvider = StreamProvider<List<OrderModel>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null || user.isBaker) return Stream.value([]);

  return ref.watch(firestoreServiceProvider).streamCustomerOrders(user.uid);
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
