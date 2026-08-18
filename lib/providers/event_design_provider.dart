import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/event_design_model.dart';
import '../services/event_design_service.dart';
import 'auth_provider.dart';

final eventDesignServiceProvider = Provider<EventDesignService>((ref) {
  return EventDesignService();
});

class EventDesignNotifier
    extends StateNotifier<AsyncValue<EventDesignRecommendation?>> {
  final EventDesignService _service;

  EventDesignNotifier(this._service) : super(const AsyncValue.data(null));

  Future<EventDesignRecommendation?> generate(
    EventDesignRequest request,
  ) async {
    state = const AsyncValue.loading();
    try {
      final recommendation = await _service.generate(request);
      state = AsyncValue.data(recommendation);
      return recommendation;
    } catch (error, stackTrace) {
      state = AsyncValue.error(error, stackTrace);
      return null;
    }
  }

  void clear() => state = const AsyncValue.data(null);
}

final eventDesignNotifierProvider = StateNotifierProvider<EventDesignNotifier,
    AsyncValue<EventDesignRecommendation?>>((ref) {
  return EventDesignNotifier(ref.watch(eventDesignServiceProvider));
});

final savedEventDesignsProvider =
    StreamProvider.autoDispose<List<SavedEventDesign>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null) return Stream.value(const []);
  return ref.watch(eventDesignServiceProvider).streamSavedDesigns(user.uid);
});
