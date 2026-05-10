import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../../models/product_model.dart';
import '../../models/surplus_item_model.dart';
import '../../providers/product_provider.dart';
import '../../providers/surplus_provider.dart';
import '../../providers/auth_provider.dart';
import '../../core/theme/baker_theme.dart';


class SurplusManagementScreen extends ConsumerWidget {
  const SurplusManagementScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final productsAsync = ref.watch(bakerProductsProvider);
    final surplusAsync = ref.watch(bakerSurplusProvider);

    return Scaffold(
      backgroundColor: BakerTheme.background,

      appBar: AppBar(
        backgroundColor: BakerTheme.background,
        title: const Text('Surplus Management', style: TextStyle(fontWeight: FontWeight.bold, color: BakerTheme.textPrimary)),
        elevation: 0,

      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Active Surplus Listings',
              style: TextStyle(color: BakerTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.bold),

            ),
            const SizedBox(height: 12),
            surplusAsync.when(
              data: (items) {
                if (items.isEmpty) {
                  return Container(
                    padding: const EdgeInsets.all(24),
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: BakerTheme.divider),

                    ),
                    child: const Center(
                      child: Text('No active surplus items', style: TextStyle(color: BakerTheme.textSecondary)),

                    ),
                  );
                }
                return Column(
                  children: items.map((item) => _ActiveSurplusCard(item: item)).toList(),
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('Error: $e'),
            ),
            const SizedBox(height: 32),
            const Text(
              'Create New Surplus Deal',
              style: TextStyle(color: BakerTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.bold),

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
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: BakerTheme.divider),

      ),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: item.imageUrl != null
                ? Image.network(item.imageUrl!, width: 50, height: 50, fit: BoxFit.cover)
                : Container(width: 50, height: 50, color: BakerTheme.background),

          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.name, style: const TextStyle(color: BakerTheme.textPrimary, fontWeight: FontWeight.bold)),

                Text('Rs. ${item.discountPrice.toStringAsFixed(0)} (was Rs. ${item.originalPrice.toStringAsFixed(0)})',
                    style: const TextStyle(color: BakerTheme.secondary, fontSize: 12)),

              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.red),
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
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: BakerTheme.divider),

      ),
      child: ListTile(
        title: Text(product.name, style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 14)),
        subtitle: Text('Price: Rs. ${product.price}', style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12)),

        trailing: const Icon(Icons.add_circle_outline, color: Colors.green),

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
        backgroundColor: Colors.white,
        title: Text('Create Surplus Deal: ${product.name}', style: const TextStyle(color: BakerTheme.textPrimary)),

        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: priceController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: BakerTheme.textPrimary),
              decoration: const InputDecoration(
                labelText: 'Discounted Price (Rs.)',
                labelStyle: TextStyle(color: BakerTheme.textSecondary),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: BakerTheme.divider)),
              ),

            ),
            const SizedBox(height: 12),
            TextField(
              controller: qtyController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: BakerTheme.textPrimary),
              decoration: const InputDecoration(
                labelText: 'Quantity Available',
                labelStyle: TextStyle(color: BakerTheme.textSecondary),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: BakerTheme.divider)),
              ),

            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel', style: TextStyle(color: BakerTheme.textSecondary))),

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
                  const SnackBar(content: Text('Discounted price must be lower than the original price.')),
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
            style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),

            child: const Text('List Surplus'),
          ),
        ],
      ),
    );
  }
}
