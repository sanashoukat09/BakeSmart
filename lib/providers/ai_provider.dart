import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/ai_service.dart';
import 'auth_provider.dart';

final aiServiceProvider = Provider<AiService>((ref) => AiService());

final aiHistoryProvider = StreamProvider<List<Map<String, dynamic>>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null) return Stream.value([]);
  
  return ref.watch(aiServiceProvider).streamUserHistory(user.uid);
});

class AiNotifier extends StateNotifier<AsyncValue<Map<String, dynamic>?>> {
  final AiService _aiService;

  AiNotifier(this._aiService) : super(const AsyncValue.data(null));

  Future<void> analyzeImage({
    required String imageUrl,
    required String bakerId,
  }) async {
    state = const AsyncValue.loading();
    try {
      final result = await _aiService.analyzeCakeDesign(
        imageUrl: imageUrl,
        bakerId: bakerId,
      );
      state = AsyncValue.data(result);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
  
  void reset() {
    state = const AsyncValue.data(null);
  }
}

final aiNotifierProvider =
    StateNotifierProvider<AiNotifier, AsyncValue<Map<String, dynamic>?>>((ref) {
  return AiNotifier(ref.watch(aiServiceProvider));
});
