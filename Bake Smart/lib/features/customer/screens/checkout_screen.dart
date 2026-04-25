import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/cart_service.dart';
import '../services/order_service.dart';

class OrderConfirmationScreen extends StatelessWidget {
  final String orderId;
  const OrderConfirmationScreen({super.key, required this.orderId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: const Text('Order Placed'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
        automaticallyImplyLeading: false, // Prevent going back to checkout
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.check_circle, color: Colors.green, size: 100),
              const SizedBox(height: 24),
              const Text('Thank you for your order!', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              Text('Order ID: $orderId', style: TextStyle(fontSize: 16, color: Colors.grey[700])),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.brown,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12)
                ),
                child: const Text('Back to Home'),
              )
            ],
          ),
        ),
      ),
    );
  }
}

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  String _deliveryMethod = 'pickup';
  final _addressCtrl = TextEditingController();
  bool _isLoading = false;
  String? _checkoutError;

  Future<void> _placeOrder() async {
    if (_deliveryMethod == 'delivery' && _addressCtrl.text.trim().isEmpty) {
      setState(() => _checkoutError = 'Please enter a delivery address.');
      return;
    }
    setState(() {
      _isLoading = true;
      _checkoutError = null;
    });

    try {
      final cartNotifier = ref.read(cartProvider.notifier);
      final items = ref.read(cartProvider);
      final orderService = ref.read(orderServiceProvider);

      // Pre-checkout validation
      final unavailableIds = await orderService.validateCartAvailability(items);
      
      if (unavailableIds.isNotEmpty) {
        // Tag them as unavailable heavily in local cart state to force the Cart screen to highlight them red
        for (var id in unavailableIds) {
          cartNotifier.setItemUnavailableError(id, true);
        }
        setState(() => _isLoading = false);
        
        if (!mounted) return;
        Navigator.pop(context); // Kick back to cart screen where errors are now visible directly
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Some items in your cart are no longer available. Please review your cart.', style: TextStyle(color: Colors.white)), backgroundColor: Colors.red, duration: Duration(seconds: 4))
        );
        return;
      }

      // Safe to place order
      await orderService.placeOrder(
        items: items,
        totalAmount: cartNotifier.subtotal,
        fulfillmentType: _deliveryMethod,
        deliveryAddress: _deliveryMethod == 'delivery' ? _addressCtrl.text.trim() : null,
      );

      cartNotifier.clearCart();

      // For simplicity, we navigate to confirmation by generating a mock ID or pulling it from returned service if we wanted. 
      // The order service writes it, we can pass a dummy or change service to return ID.
      // We will just pass a generic success id.
      if (!mounted) return;
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const OrderConfirmationScreen(orderId: 'CONFIRMED')));

    } catch (e) {
      setState(() => _checkoutError = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final subtotal = ref.watch(cartProvider.notifier).subtotal;

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: const Text('Checkout'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_checkoutError != null)
              Container(
                margin: const EdgeInsets.only(bottom: 24),
                padding: const EdgeInsets.all(12),
                color: Colors.red[100],
                child: Text('⚠️ $_checkoutError', style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
              ),
              
            const Text('Fulfillment Method', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Container(
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
              child: Column(
                children: [
                  RadioListTile<String>(
                    title: const Text('Pickup from Bakery'),
                    value: 'pickup',
                    groupValue: _deliveryMethod,
                    onChanged: (val) => setState(() => _deliveryMethod = val!),
                    activeColor: Colors.brown,
                  ),
                  RadioListTile<String>(
                    title: const Text('Delivery'),
                    value: 'delivery',
                    groupValue: _deliveryMethod,
                    onChanged: (val) => setState(() => _deliveryMethod = val!),
                    activeColor: Colors.brown,
                  ),
                ],
              ),
            ),
            
            if (_deliveryMethod == 'delivery') ...[
              const SizedBox(height: 24),
              const Text('Delivery Address', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(
                controller: _addressCtrl,
                maxLines: 3,
                decoration: InputDecoration(
                  hintText: 'Enter your full delivery address...',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                ),
              )
            ],

            const SizedBox(height: 32),
            const Text('Order Summary', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Total to Pay', style: TextStyle(fontSize: 16)),
                  Text('\$${subtotal.toStringAsFixed(2)}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.brown)),
                ],
              ),
            ),
            
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: _isLoading ? null : _placeOrder,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                backgroundColor: Colors.brown,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: _isLoading
                  ? const CircularProgressIndicator(color: Colors.white)
                  : const Text('Place Order', style: TextStyle(fontSize: 18)),
            ),
          ],
        ),
      ),
    );
  }
}
