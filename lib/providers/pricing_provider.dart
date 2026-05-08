import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/product_model.dart';
import '../models/ingredient_model.dart';
import 'product_provider.dart';
import 'inventory_provider.dart';

// Helper to calculate product cost
class ProductCostResult {
  final double baseCost;
  final double suggestedPrice;
  final double currentProfit;
  final double currentMargin;
  final Map<String, double> missingIngredients; // id: quantity

  ProductCostResult({
    required this.baseCost,
    required this.suggestedPrice,
    required this.currentProfit,
    required this.currentMargin,
    required this.missingIngredients,
  });
}

final productCostProvider = Provider.family<ProductCostResult, ProductModel>((ref, product) {
  final ingredients = ref.watch(bakerIngredientsProvider).valueOrNull ?? [];
  
  double totalCost = 0;
  Map<String, double> missing = {};

  product.ingredients.forEach((ingId, qtyNeeded) {
    final ingredient = ingredients.firstWhere(
      (i) => i.id == ingId,
      orElse: () => IngredientModel(
        id: 'missing',
        bakerId: '',
        name: 'Unknown',
        quantity: 0,
        unit: '',
        unitPrice: 0,
        updatedAt: DateTime.now(),
      ),
    );

    if (ingredient.id == 'missing') {
      missing[ingId] = qtyNeeded;
    } else {
      totalCost += ingredient.unitPrice * qtyNeeded;
    }
  });

  final suggestedPrice = totalCost * (1 + (product.profitMargin / 100));
  final currentProfit = product.price - totalCost;
  final currentMargin = product.price > 0 ? (currentProfit / product.price) * 100 : 0.0;

  return ProductCostResult(
    baseCost: totalCost,
    suggestedPrice: suggestedPrice,
    currentProfit: currentProfit,
    currentMargin: currentMargin,
    missingIngredients: missing,
  );
});

// Summary of overall profitability
final businessProfitabilityProvider = Provider((ref) {
  final products = ref.watch(bakerProductsProvider).valueOrNull ?? [];
  
  double totalPotentialRevenue = 0;
  double totalPotentialCost = 0;

  for (var product in products) {
    final result = ref.watch(productCostProvider(product));
    totalPotentialRevenue += product.price;
    totalPotentialCost += result.baseCost;
  }

  final totalProfit = totalPotentialRevenue - totalPotentialCost;
  final avgMargin = totalPotentialRevenue > 0 ? (totalProfit / totalPotentialRevenue) * 100 : 0.0;

  return {
    'totalRevenue': totalPotentialRevenue,
    'totalCost': totalPotentialCost,
    'totalProfit': totalProfit,
    'avgMargin': avgMargin,
  };
});
