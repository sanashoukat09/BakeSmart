import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../providers/inventory_provider.dart';
import '../../core/router/app_router.dart';
import '../../models/ingredient_model.dart';

class InventoryScreen extends ConsumerWidget {
  const InventoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ingredientsAsync = ref.watch(bakerIngredientsProvider);
    final lowStockCount = ref.watch(lowStockIngredientsProvider).length;
    final expiryCount = ref.watch(nearExpiryIngredientsProvider).length;

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFDFCF9),
        title: const Text('Inventory', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF451A03))),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: Color(0xFF78350F)),
            onPressed: () => context.push(AppRoutes.bakerAddIngredient),
          ),
        ],
      ),
      body: Column(
        children: [
          // Alerts Header
          if (lowStockCount > 0 || expiryCount > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              color: const Color(0xFFFEF3C7).withOpacity(0.3),
              child: Row(
                children: [
                  if (lowStockCount > 0)
                    _AlertBadge(
                      label: '$lowStockCount Low Stock',
                      color: Colors.orange,
                      icon: Icons.warning_amber_rounded,
                    ),
                  if (lowStockCount > 0 && expiryCount > 0) const SizedBox(width: 8),
                  if (expiryCount > 0)
                    _AlertBadge(
                      label: '$expiryCount Near Expiry',
                      color: Colors.red,
                      icon: Icons.timer_outlined,
                    ),
                ],
              ),
            ),

          Expanded(
            child: ingredientsAsync.when(
              data: (ingredients) {
                if (ingredients.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.kitchen_outlined, color: Color(0xFF484F58), size: 64),
                        const SizedBox(height: 16),
                        const Text('No ingredients added', style: TextStyle(color: Color(0xFFF0F6FC))),
                        const SizedBox(height: 8),
                        ElevatedButton(
                          onPressed: () => context.push(AppRoutes.bakerAddIngredient),
                          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFF59E0B), foregroundColor: const Color(0xFF0D1117)),
                          child: const Text('Add Ingredient'),
                        ),
                      ],
                    ),
                  );
                }

                return ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: ingredients.length,
                  itemBuilder: (context, index) {
                    final ingredient = ingredients[index];
                    return _IngredientCard(ingredient: ingredient);
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFFF59E0B))),
              error: (e, _) => Center(child: Text('Error: $e')),
            ),
          ),
        ],
      ),
    );
  }
}

class _AlertBadge extends StatelessWidget {
  final String label;
  final Color color;
  final IconData icon;

  const _AlertBadge({required this.label, required this.color, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}

class _IngredientCard extends ConsumerWidget {
  final IngredientModel ingredient;
  const _IngredientCard({required this.ingredient});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bool isLow = ingredient.isLowStock;
    final bool isExpiring = ingredient.isNearExpiry;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isExpiring ? Colors.red.withOpacity(0.5) : (isLow ? Colors.orange.withOpacity(0.5) : const Color(0xFFFEF3C7)),
          width: 1.5,
        ),
      ),
      child: ListTile(
        onTap: () => context.push('${AppRoutes.bakerEditIngredient}/${ingredient.id}'),
        title: Text(ingredient.name, style: const TextStyle(color: Color(0xFF451A03), fontWeight: FontWeight.bold)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text('Stock: ${ingredient.quantity} ${ingredient.unit}', 
              style: TextStyle(color: isLow ? Colors.orange : const Color(0xFF92400E))),
            if (ingredient.expiryDate != null)
              Text('Expires: ${DateFormat('MMM dd, yyyy').format(ingredient.expiryDate!)}',
                style: TextStyle(color: isExpiring ? Colors.red : const Color(0xFFA8A29E), fontSize: 12)),
          ],
        ),
        trailing: IconButton(
          icon: const Icon(Icons.add_circle_outline, color: Color(0xFF78350F)),
          onPressed: () {
            _showUpdateQuantityDialog(context, ref);
          },
        ),
      ),
    );
  }

  void _showUpdateQuantityDialog(BuildContext context, WidgetRef ref) {
    final controller = TextEditingController(text: ingredient.quantity.toString());
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.white,
        title: Text('Update ${ingredient.name}', style: const TextStyle(color: Color(0xFF451A03))),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: controller,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: Color(0xFF451A03)),
              decoration: InputDecoration(
                labelText: 'Quantity (${ingredient.unit})',
                labelStyle: const TextStyle(color: Color(0xFF92400E)),
                enabledBorder: const UnderlineInputBorder(borderSide: BorderSide(color: Color(0xFFFEF3C7))),
                focusedBorder: const UnderlineInputBorder(borderSide: BorderSide(color: Color(0xFF78350F))),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel', style: TextStyle(color: Color(0xFF92400E)))),
          ElevatedButton(
            onPressed: () {
              final newQty = double.tryParse(controller.text);
              if (newQty == null || newQty < 0) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Please enter a valid non-negative quantity.')),
                );
                return;
              }
              ref.read(inventoryNotifierProvider.notifier).updateQuantity(ingredient.id, newQty);
              Navigator.pop(context);
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF78350F), foregroundColor: Colors.white),
            child: const Text('Update'),
          ),
        ],
      ),
    );
  }
}
