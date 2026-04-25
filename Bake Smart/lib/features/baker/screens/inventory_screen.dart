import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/inventory_service.dart';
import 'add_edit_ingredient_screen.dart';

class InventoryScreen extends ConsumerStatefulWidget {
  const InventoryScreen({super.key});

  @override
  ConsumerState<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends ConsumerState<InventoryScreen> {
  bool _filterLowAndExpired = false;

  Color _getStatusColor(String status) {
    switch (status) {
      case 'in_stock':
        return Colors.green;
      case 'low':
        return Colors.orange;
      case 'expired':
      case 'out_of_stock':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  String _formatStatusLabel(String status) {
    return status.replaceAll('_', ' ').toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final inventoryAsync = ref.watch(inventoryStreamProvider);

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: const Text('Inventory'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const AddEditIngredientScreen()),
        ),
        backgroundColor: Colors.brown,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      body: inventoryAsync.when(
        data: (ingredients) {
          if (ingredients.isEmpty) {
            return const Center(child: Text('No ingredients found. Add some!'));
          }

          int lowCount = 0;
          int expiredCount = 0;
          for (var item in ingredients) {
            if (item.status == 'low') lowCount++;
            if (item.status == 'expired' || item.status == 'out_of_stock') {
              expiredCount++;
            }
          }

          final hasAlert = lowCount > 0 || expiredCount > 0;

          // Apply filter
          final displayedItems = _filterLowAndExpired
              ? ingredients.where((i) => i.status != 'in_stock').toList()
              : ingredients;

          return Column(
            children: [
              if (hasAlert)
                GestureDetector(
                  onTap: () {
                    setState(() => _filterLowAndExpired = !_filterLowAndExpired);
                  },
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.red[100],
                      border: Border.all(color: Colors.red[300]!),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.warning_amber_rounded, color: Colors.red),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '⚠️ $lowCount ingredient(s) are low · $expiredCount ingredient(s) expired/out',
                            style: const TextStyle(
                                color: Colors.red, fontWeight: FontWeight.bold),
                          ),
                        ),
                        if (_filterLowAndExpired)
                          const Icon(Icons.close, color: Colors.red)
                        else
                          const Icon(Icons.filter_list, color: Colors.red)
                      ],
                    ),
                  ),
                ),
              if (_filterLowAndExpired && !hasAlert)
                 Padding(
                   padding: const EdgeInsets.all(16.0),
                   child: IconButton(
                     icon: const Icon(Icons.close),
                     onPressed: () => setState(() => _filterLowAndExpired = false),
                   ),
                 ),
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.only(bottom: 80, left: 16, right: 16),
                  itemCount: displayedItems.length,
                  itemBuilder: (context, index) {
                    final item = displayedItems[index];

                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: ListTile(
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => AddEditIngredientScreen(ingredient: item),
                            ),
                          );
                        },
                        title: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                                child: Text(item.name,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.bold, fontSize: 18))),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: _getStatusColor(item.status).withOpacity(0.2),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                _formatStatusLabel(item.status),
                                style: TextStyle(
                                  color: _getStatusColor(item.status),
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            )
                          ],
                        ),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 8.0),
                          child: Text('${item.quantity} ${item.unit}'),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.remove_circle_outline, color: Colors.brown),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(),
                              onPressed: () {
                                ref.read(inventoryServiceProvider).updateQuantity(item, -1.0);
                              },
                            ),
                            const SizedBox(width: 12),
                            IconButton(
                              icon: const Icon(Icons.add_circle_outline, color: Colors.brown),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(),
                              onPressed: () {
                                ref.read(inventoryServiceProvider).updateQuantity(item, 1.0);
                              },
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, stack) => Center(child: Text('Error: $e')),
      ),
    );
  }
}
