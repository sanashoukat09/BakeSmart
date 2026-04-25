import 'dart:io';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../core/services/cloudinary_service.dart';
import '../../auth/services/auth_provider.dart';
import '../models/product_model.dart';

final productServiceProvider = Provider<ProductService>((ref) {
  return ProductService(FirebaseFirestore.instance, ref.read(cloudinaryServiceProvider));
});

final bakerProductsStreamProvider = StreamProvider<List<ProductModel>>((ref) {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return const Stream.empty();

  return FirebaseFirestore.instance
      .collection('products')
      .where('bakerId', isEqualTo: user.uid)
      .snapshots()
      .map((snapshot) => snapshot.docs
          .map((doc) => ProductModel.fromMap(doc.data(), doc.id))
          .toList());
});

class ProductService {
  final FirebaseFirestore _firestore;
  final CloudinaryService _cloudinary;

  ProductService(this._firestore, this._cloudinary);

  Future<List<String>> uploadImages(List<XFile> images, String productId) async {
    List<String> paths = images.map((e) => e.path).toList();
    return await _cloudinary.uploadMultipleImages(paths);
  }

  Future<void> addProduct(ProductModel product, List<XFile> localImages) async {
    final docRef = _firestore.collection('products').doc();
    
    // 1. Create the document first to ensure the collection exists
    final initialProduct = product.copyWith(
      productId: docRef.id,
      images: [],
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
    final batch = _firestore.batch();
    batch.set(docRef, initialProduct.toMap());

    // Deduct ingredients from inventory since the product is physically made
    for (var ingredient in product.recipeIngredients) {
      if (ingredient.ingredientId.isNotEmpty) {
        final invDocRef = _firestore.collection('inventory').doc(ingredient.ingredientId);
        final invDoc = await invDocRef.get();
        if (invDoc.exists) {
          final currentQty = (invDoc.data()?['quantity'] as num?)?.toDouble() ?? 0.0;
          final lowStock = (invDoc.data()?['lowStockThreshold'] as num?)?.toDouble() ?? 0.0;
          
          var newQty = currentQty - ingredient.quantityUsed;
          if (newQty < 0) newQty = 0;
          
          String newStatus = 'in_stock';
          if (newQty <= 0) {
            newStatus = 'out_of_stock';
          } else if (newQty < lowStock) {
            newStatus = 'low';
          }
          
          batch.update(invDocRef, {
            'quantity': newQty,
            'status': newStatus,
          });
        }
      }
    }

    await batch.commit();
    // 2. Upload images if any
    if (localImages.isNotEmpty) {
      try {
        final imageUrls = await uploadImages(localImages, docRef.id);
        // 3. Update with images
        await docRef.update({'images': imageUrls});
      } catch (e) {
        // If upload fails, the product still exists but with no images
        rethrow;
      }
    }
  }

  Future<void> updateProduct(ProductModel product, List<XFile> newLocalImages) async {
    final docRef = _firestore.collection('products').doc(product.productId);
    
    // 1. Update basic info first
    await docRef.update(product.toMap());

    // 2. Upload new images if any
    if (newLocalImages.isNotEmpty) {
      final newUrls = await uploadImages(newLocalImages, product.productId);
      
      // 3. Append to existing images
      await docRef.update({
        'images': FieldValue.arrayUnion(newUrls),
        'updatedAt': Timestamp.now(),
      });
    }
  }

  Future<void> deleteProduct(String productId) async {
    // Note: To be fully clean, we should delete storage images too, 
    // but leaving it simple for this module
    await _firestore.collection('products').doc(productId).delete();
  }

  Future<void> toggleAvailability(ProductModel product) async {
    await _firestore
        .collection('products')
        .doc(product.productId)
        .update({'isAvailable': !product.isAvailable, 'updatedAt': Timestamp.now()});
  }
}
