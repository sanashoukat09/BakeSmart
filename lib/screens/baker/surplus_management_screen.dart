import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../../models/product_model.dart';
import '../../models/surplus_item_model.dart';
import '../../providers/product_provider.dart';
import '../../providers/surplus_provider.dart';
import '../../providers/auth_provider.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const taupe     = Color(0xFF6F3C2C);
  static const pink      = Color(0xFFFF8B9F);
  static const pinkL     = Color(0xFFFFF4F5);
  static const copper    = Color(0xFFE67E22);
  static const cream     = Color(0xFFFAF0E6);
  
  static const surface   = Color(0xFFFFFFFF);
  static const surfaceWarm = Color(0xFFFFF9F2);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  // Vibrant accents for status and icons
  static const statusPink = Color(0xFFFF6B81);
  static const statusBrown = Color(0xFFB37E56);
  static const statusCopper = Color(0xFFF39C12);
  static const statusGreen = Color(0xFF52B788);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class SurplusManagementScreen extends ConsumerWidget {
  const SurplusManagementScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final productsAsync = ref.watch(bakerProductsProvider);
    final surplusAsync = ref.watch(bakerSurplusProvider);

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        iconTheme: const IconThemeData(color: _T.brown),
        title: const Text(
          'Surplus Management', 
          style: TextStyle(fontWeight: FontWeight.w800, color: _T.brown, fontSize: 18),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Active Surplus Listings',
              style: TextStyle(color: _T.brown, fontSize: 14.5, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 12),
            surplusAsync.when(
              data: (items) {
                if (items.isEmpty) {
                  return Container(
                    padding: const EdgeInsets.all(24),
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: _T.surface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: _T.rimLight, width: 1.5),
                      boxShadow: _T.shadowSm,
                    ),
                    child: const Center(
                      child: Text(
                        'No active surplus items', 
                        style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                    ),
                  );
                }
                return Column(
                  children: items.map((item) => _ActiveSurplusCard(item: item)).toList(),
                );
              },
              loading: () => const LinearProgressIndicator(color: _T.copper),
              error: (e, _) => Text('Error: $e', style: const TextStyle(color: _T.statusPink)),
            ),
            const SizedBox(height: 32),
            const Text(
              'Create New Surplus Deal',
              style: TextStyle(color: _T.brown, fontSize: 14.5, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 12),
            productsAsync.when(
              data: (products) {
                return ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: products.length,
                  itemBuilder: (context, index) {
                    final product = products[index];
                    return _ProductSurplusSelector(product: product);
                  },
                );
              },
              loading: () => const SizedBox.shrink(),
              error: (e, _) => const SizedBox.shrink(),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActiveSurplusCard extends ConsumerWidget {
  final SurplusItemModel item;
  const _ActiveSurplusCard({required this.item});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: item.imageUrl != null
                ? Image.network(item.imageUrl!, width: 52, height: 52, fit: BoxFit.cover)
                : Container(
                    width: 52, 
                    height: 52, 
                    color: _T.surfaceWarm,
                    child: const Icon(Icons.kitchen_outlined, color: _T.inkFaint, size: 24),
                  ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.name, 
                  style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 15, letterSpacing: -0.2),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: _T.pinkL,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: _T.pink.withOpacity(0.4), width: 1),
                      ),
                      child: Text(
                        'Rs. ${item.discountPrice.toStringAsFixed(0)}',
                        style: const TextStyle(color: _T.statusPink, fontSize: 12, fontWeight: FontWeight.w900),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Rs. ${item.originalPrice.toStringAsFixed(0)}',
                      style: const TextStyle(
                        color: _T.inkMid, 
                        fontSize: 11.5, 
                        fontWeight: FontWeight.w600, 
                        decoration: TextDecoration.lineThrough,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline, color: _T.statusPink),
            onPressed: () => ref.read(firestoreServiceProvider).deactivateSurplus(item.id),
          ),
        ],
      ),
    );
  }
}

class _ProductSurplusSelector extends ConsumerWidget {
  final ProductModel product;
  const _ProductSurplusSelector({required this.product});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        title: Text(
          product.name, 
          style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 14, letterSpacing: -0.2),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(
              'Price: Rs. ${product.price}', 
              style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ],
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFFF39C12), Color(0xFFE67E22)],
              begin: Alignment.topLeft, end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(10),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFFE67E22).withOpacity(0.3), 
                blurRadius: 8, 
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.add_rounded, color: Colors.white, size: 14),
              SizedBox(width: 4),
              Text(
                'LIST',
                style: TextStyle(
                  color: Colors.white, 
                  fontWeight: FontWeight.w900, 
                  fontSize: 10, 
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
        onTap: () => _showCreateSurplusDialog(context, ref),
      ),
    );
  }

  void _showCreateSurplusDialog(BuildContext context, WidgetRef ref) {
    final priceController = TextEditingController(text: (product.price * 0.7).toStringAsFixed(0));
    final qtyController = TextEditingController(text: '1');

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _T.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: Text(
          'Create Surplus Deal: ${product.name}', 
          style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: priceController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
              decoration: const InputDecoration(
                labelText: 'Discounted Price (Rs.)',
                labelStyle: TextStyle(color: _T.copper, fontWeight: FontWeight.w600),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: _T.rimLight, width: 1.5)),
                focusedBorder: UnderlineInputBorder(borderSide: BorderSide(color: _T.copper, width: 2)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: qtyController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
              decoration: const InputDecoration(
                labelText: 'Quantity Available',
                labelStyle: TextStyle(color: _T.copper, fontWeight: FontWeight.w600),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: _T.rimLight, width: 1.5)),
                focusedBorder: UnderlineInputBorder(borderSide: BorderSide(color: _T.copper, width: 2)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context), 
            child: const Text('Cancel', style: TextStyle(color: _T.taupe, fontWeight: FontWeight.w800)),
          ),
          ElevatedButton(
            onPressed: () async {
              final discountPrice = double.tryParse(priceController.text);
              final quantity = int.tryParse(qtyController.text);
              if (discountPrice == null || discountPrice <= 0) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Enter a valid discounted price.')),
                );
                return;
              }
              if (discountPrice >= product.price) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Discounted price must be lower than original price.')),
                );
                return;
              }
              if (quantity == null || quantity <= 0) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Enter a valid quantity.')),
                );
                return;
              }

              final surplus = SurplusItemModel(
                id: const Uuid().v4(),
                productId: product.id,
                bakerId: product.bakerId,
                name: product.name,
                imageUrl: product.images.isNotEmpty ? product.images.first : null,
                originalPrice: product.price,
                discountPrice: discountPrice,
                quantity: quantity,
                createdAt: DateTime.now(),
              );
              await ref.read(firestoreServiceProvider).saveSurplusItem(surplus);
              Navigator.pop(context);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: _T.brown, 
              foregroundColor: Colors.white,
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('List Surplus', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
