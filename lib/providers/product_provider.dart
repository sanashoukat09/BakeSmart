import 'dart:io';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/product_model.dart';
import 'auth_provider.dart';
import '../services/cloudinary_service.dart';

final cloudinaryServiceProvider =
    Provider<CloudinaryService>((ref) => CloudinaryService());

// Stream of products for the current baker
final bakerProductsProvider = StreamProvider<List<ProductModel>>((ref) {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null || !user.isBaker) return Stream.value([]);

  return ref.watch(firestoreServiceProvider).streamBakerProducts(user.uid);
});

// Product Notifier for CRUD actions
class ProductNotifier extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;

  ProductNotifier(this._ref) : super(const AsyncValue.data(null));

  Future<void> saveProduct({
    required ProductModel product,
    List<File>? newImages,
  }) async {
    state = const AsyncValue.loading();
    try {
      List<String> imageUrls = List.from(product.images);

      // Upload new images to Cloudinary if any
      if (newImages != null && newImages.isNotEmpty) {
        final cloudinary = _ref.read(cloudinaryServiceProvider);
        final uploadedUrls = await cloudinary.uploadMultipleImages(
          imageFiles: newImages,
          folder: 'products/${product.bakerId}',
        );
        imageUrls.addAll(uploadedUrls);
      }

      final updatedProduct = product.copyWith(images: imageUrls);
      await _ref.read(firestoreServiceProvider).saveProduct(updatedProduct);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> deleteProduct(String productId) async {
    state = const AsyncValue.loading();
    try {
      await _ref.read(firestoreServiceProvider).deleteProduct(productId);
      state = const AsyncValue.data(null);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> toggleAvailability(String productId, bool isAvailable) async {
    try {
      await _ref
          .read(firestoreServiceProvider)
          .toggleProductAvailability(productId, isAvailable);
    } catch (e) {
      // Handle error quietly or show snackbar
    }
  }
}

final productNotifierProvider =
    StateNotifierProvider<ProductNotifier, AsyncValue<void>>((ref) {
  return ProductNotifier(ref);
});
