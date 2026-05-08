import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/surplus_item_model.dart';
import 'auth_provider.dart';

final bakerSurplusProvider = StreamProvider<List<SurplusItemModel>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null || !user.isBaker) return Stream.value([]);
  return ref.watch(firestoreServiceProvider).streamBakerSurplus(user.uid);
});

final allSurplusProvider = StreamProvider<List<SurplusItemModel>>((ref) {
  return ref.watch(firestoreServiceProvider).streamAllSurplus();
});

final discountedSurplusProvider = Provider<List<SurplusItemModel>>((ref) {
  final allSurplus = ref.watch(allSurplusProvider).valueOrNull ?? [];
  return allSurplus.toList(); // Could add more complex sorting/filtering here
});

final activeSurplusByProductProvider =
    Provider<Map<String, SurplusItemModel>>((ref) {
  final surplusItems = ref.watch(allSurplusProvider).valueOrNull ?? [];
  final surplusByProduct = <String, SurplusItemModel>{};

  for (final item in surplusItems.where((item) => item.quantity > 0)) {
    final current = surplusByProduct[item.productId];
    if (current == null || item.discountPrice < current.discountPrice) {
      surplusByProduct[item.productId] = item;
    }
  }

  return surplusByProduct;
});
