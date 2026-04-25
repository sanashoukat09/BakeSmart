import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/product_model.dart';

class CostCalculatorService {
  
  double calculateTotalCost(List<RecipeIngredient> ingredients) {
    double total = 0;
    for (var i in ingredients) {
      total += i.measuredCostPrice * i.quantityUsed;
    }
    return total;
  }

  double calculateSuggestedPrice(double costPrice) {
    if (costPrice <= 0) return 0;
    // 40% margin suggested
    return costPrice * 1.4;
  }

  double calculateProfitMargin(double basePrice, double costPrice) {
    if (basePrice <= 0) return 0;
    return ((basePrice - costPrice) / basePrice) * 100;
  }
}

final costCalculatorProvider = Provider<CostCalculatorService>((ref) {
  return CostCalculatorService();
});
