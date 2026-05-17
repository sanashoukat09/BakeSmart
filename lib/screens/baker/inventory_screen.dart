import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../providers/inventory_provider.dart';
import '../../core/router/app_router.dart';
import '../../models/ingredient_model.dart';

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

class InventoryScreen extends ConsumerWidget {
  const InventoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ingredientsAsync = ref.watch(bakerIngredientsProvider);
    final lowStockCount = ref.watch(lowStockIngredientsProvider).length;
    final expiryCount = ref.watch(nearExpiryIngredientsProvider).length;

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        centerTitle: false,
        title: const Text(
          'Inventory', 
          style: TextStyle(fontWeight: FontWeight.w800, color: _T.brown, fontSize: 18),
        ),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: _T.brown, size: 26),
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
              color: _T.pinkL.withOpacity(0.4),
              child: Row(
                children: [
                  if (lowStockCount > 0)
                    _AlertBadge(
                      label: '$lowStockCount Low Stock',
                      color: _T.statusCopper,
                      icon: Icons.warning_amber_rounded,
                    ),
                  if (lowStockCount > 0 && expiryCount > 0) const SizedBox(width: 8),
                  if (expiryCount > 0)
                    _AlertBadge(
                      label: '$expiryCount Near Expiry',
                      color: _T.statusPink,
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
                        Container(
                          width: 72,
                          height: 72,
                          decoration: BoxDecoration(
                            color: _T.pinkL,
                            borderRadius: BorderRadius.circular(22),
                            border: Border.all(color: _T.pink.withOpacity(0.2), width: 1.5),
                          ),
                          child: const Icon(Icons.kitchen_outlined, color: _T.copper, size: 32),
                        ),
                        const SizedBox(height: 16),
                        const Text(
                          'No ingredients added', 
                          style: TextStyle(color: _T.ink, fontSize: 16, fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 12),
                        ElevatedButton(
                          onPressed: () => context.push(AppRoutes.bakerAddIngredient),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _T.brown, 
                            foregroundColor: Colors.white,
                            elevation: 0,
                            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                          ),
                          child: const Text('Add Ingredient', style: TextStyle(fontWeight: FontWeight.w800)),
                        ),
                      ],
                    ),
                  );
                }

                return ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  itemCount: ingredients.length,
                  itemBuilder: (context, index) {
                    final ingredient = ingredients[index];
                    return _IngredientCard(ingredient: ingredient);
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator(color: _T.copper)),
              error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 6),
          Text(
            label, 
            style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: -0.1),
          ),
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
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isExpiring ? _T.statusPink.withOpacity(0.5) : (isLow ? _T.statusCopper.withOpacity(0.5) : _T.rimLight),
          width: 1.5,
        ),
        boxShadow: _T.shadowSm,
      ),
      child: ListTile(
        onTap: () => context.push('${AppRoutes.bakerEditIngredient}/${ingredient.id}'),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        title: Text(
          ingredient.name, 
          style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 16, letterSpacing: -0.2),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 6),
            Text(
              'Stock: ${ingredient.quantity} ${ingredient.unit}', 
              style: TextStyle(color: isLow ? _T.statusCopper : _T.taupe, fontWeight: FontWeight.w700, fontSize: 13),
            ),
            if (ingredient.expiryDate != null) ...[
              const SizedBox(height: 2),
              Text(
                'Expires: ${DateFormat('MMM dd, yyyy').format(ingredient.expiryDate!)}',
                style: TextStyle(color: isExpiring ? _T.statusPink : _T.inkMid, fontSize: 11, fontWeight: FontWeight.w600),
              ),
            ],
          ],
        ),
        trailing: Container(
          decoration: BoxDecoration(
            color: _T.surfaceWarm,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: _T.rimLight),
          ),
          child: IconButton(
            icon: const Icon(Icons.add, color: _T.copper, size: 20),
            onPressed: () {
              _showUpdateQuantityDialog(context, ref);
            },
          ),
        ),
      ),
    );
  }

  void _showUpdateQuantityDialog(BuildContext context, WidgetRef ref) {
    final controller = TextEditingController(text: ingredient.quantity.toString());
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _T.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: Text(
          'Update ${ingredient.name}', 
          style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: controller,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
              decoration: InputDecoration(
                labelText: 'Quantity (${ingredient.unit})',
                labelStyle: const TextStyle(color: _T.copper, fontWeight: FontWeight.w600),
                enabledBorder: const UnderlineInputBorder(borderSide: BorderSide(color: _T.rimLight, width: 1.5)),
                focusedBorder: const UnderlineInputBorder(borderSide: BorderSide(color: _T.copper, width: 2)),
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
            style: ElevatedButton.styleFrom(
              backgroundColor: _T.brown, 
              foregroundColor: Colors.white,
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('Update', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
