import 'package:bakesmart/models/cart_item_model.dart';
import 'package:bakesmart/providers/cart_provider.dart';
import 'package:bakesmart/providers/store_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('StoreFilter can clear a selected category', () {
    final filter = StoreFilter(category: 'Cakes');

    expect(filter.copyWith(category: null).category, isNull);
  });

  test('Cart keeps customized variants as separate lines', () async {
    SharedPreferences.setMockInitialValues({});
    final cart = CartNotifier();
    await Future<void>.delayed(Duration.zero);

    final base = CartItemModel(
      productId: 'cake-1',
      bakerId: 'baker-1',
      productName: 'Chocolate Cake',
      price: 1200,
    );
    final customized = CartItemModel(
      productId: 'cake-1',
      bakerId: 'baker-1',
      productName: 'Chocolate Cake',
      price: 1400,
      selectedAddOns: const ['Message topper'],
    );

    cart.addItemFromModel(base);
    cart.addItemFromModel(customized);
    cart.updateLineQuantity(customized.lineKey, 1);

    expect(cart.state, hasLength(2));
    expect(cart.state.first.quantity, 1);
    expect(cart.state.last.quantity, 2);
    expect(cart.totalAmount, 4000);
  });

  test('Cart replaces items when a different baker is selected', () async {
    SharedPreferences.setMockInitialValues({});
    final cart = CartNotifier();
    await Future<void>.delayed(Duration.zero);

    cart.addItemFromModel(
      CartItemModel(
        productId: 'cake-1',
        bakerId: 'baker-1',
        productName: 'Chocolate Cake',
        price: 1200,
      ),
    );
    cart.addItemFromModel(
      CartItemModel(
        productId: 'pie-1',
        bakerId: 'baker-2',
        productName: 'Apple Pie',
        price: 900,
      ),
    );

    expect(cart.state, hasLength(1));
    expect(cart.state.single.bakerId, 'baker-2');
  });
}
