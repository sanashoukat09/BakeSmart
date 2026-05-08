import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import '../../providers/cart_provider.dart';
import '../../providers/auth_provider.dart';
import '../../models/order_model.dart';
import '../../core/router/app_router.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter/services.dart';
import '../../core/utils/validation_util.dart';

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  final _formKey = GlobalKey<FormState>();
  final _addressController = TextEditingController();
  final _phoneController = TextEditingController();
  final _noteController = TextEditingController();

  DateTime _deliveryDate = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _deliveryTime = const TimeOfDay(hour: 12, minute: 0);
  String _paymentMethod = 'COD';
  bool _isAtCapacity = false;
  int _bakerCapacity = 10;
  int _currentOrderCount = 0;
  bool _didPrefill = false;

  @override
  void initState() {
    super.initState();
    _checkCapacity();
  }

  void _prefillDeliveryDetails() {
    if (_didPrefill) return;
    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null || user.savedAddresses.isEmpty) return;

    final address = user.savedAddresses.firstWhere(
      (addr) => addr['isDefault'] == true,
      orElse: () => user.savedAddresses.first,
    );
    
    // Use post-frame callback to avoid state issues during build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !_didPrefill) {
        _addressController.text = (address['details'] ?? '').toString();
        _phoneController.text = (address['phone'] ?? '').toString();
        setState(() => _didPrefill = true);
      }
    });
  }

  @override
  void dispose() {
    _addressController.dispose();
    _phoneController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _deliveryDate,
      firstDate: DateTime.now().add(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 30)),
    );
    if (picked != null) {
      setState(() => _deliveryDate = picked);
      _checkCapacity();
    }
  }

  Future<void> _checkCapacity() async {
    final cart = ref.read(cartProvider);
    if (cart.isEmpty) return;

    final bakerId = cart.first.bakerId;
    final count = await ref
        .read(firestoreServiceProvider)
        .getOrdersCountForDate(bakerId, _deliveryDate);
    final baker = await ref.read(firestoreServiceProvider).getBakerProfile(bakerId);

    if (mounted) {
      setState(() {
        _currentOrderCount = count;
        _bakerCapacity = baker?.dailyOrderCapacity ?? 10;
        _isAtCapacity = _currentOrderCount >= _bakerCapacity;
      });
    }
  }

  Future<void> _selectTime() async {
    final picked = await showTimePicker(context: context, initialTime: _deliveryTime);
    if (picked != null) setState(() => _deliveryTime = picked);
  }

  Future<void> _placeOrder() async {
    if (!_formKey.currentState!.validate()) return;

    final user = ref.read(currentUserProvider).valueOrNull;
    final cart = ref.read(cartProvider);
    if (user == null || cart.isEmpty) {
      if (mounted) context.go(AppRoutes.customerCart);
      return;
    }
    final total = ref.read(cartProvider.notifier).totalAmount;

    final deliveryDateTime = DateTime(
      _deliveryDate.year,
      _deliveryDate.month,
      _deliveryDate.day,
      _deliveryTime.hour,
      _deliveryTime.minute,
    );

    final order = OrderModel(
      id: const Uuid().v4(),
      customerId: user.uid,
      bakerId: cart.first.bakerId,
      items: cart
          .map((item) => OrderItem(
                productId: item.productId,
                productName: item.productName,
                quantity: item.quantity,
                price: item.price,
                imageUrl: item.imageUrl,
                selectedAddOns: item.selectedAddOns,
                surplusId: item.surplusId,
              ))
          .toList(),
      totalAmount: total,
      status: 'placed',
      createdAt: DateTime.now(),
      deliveryDate: deliveryDateTime,
      deliveryAddress: _addressController.text.trim(),
      customerName: user.displayName ?? 'Customer',
      customerPhone: _phoneController.text.trim(),
      customerNote: _noteController.text.trim(),
      referencePhotos: cart.expand((item) => item.referencePhotos).toList(),
      capacityWarning: _isAtCapacity,
      capacityWarningMessage: _isAtCapacity
          ? 'Baker has $_currentOrderCount orders for this date and a daily capacity of $_bakerCapacity.'
          : null,
      paymentMethod: _paymentMethod,
    );

    try {
      await ref.read(firestoreServiceProvider).saveOrder(order);
      await _saveDeliveryDetails(user.uid);

      ref.read(cartProvider.notifier).clearCart();
      if (mounted) context.go(AppRoutes.customerOrderSuccess);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    }
  }

  Future<void> _saveDeliveryDetails(String uid) async {
    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) return;

    final address = _addressController.text.trim();
    final phone = _phoneController.text.trim();
    final addresses = List<Map<String, dynamic>>.from(user.savedAddresses);
    final existingIndex = addresses.indexWhere((item) => item['details'] == address);

    final savedAddress = {
      'id': existingIndex == -1
          ? DateTime.now().millisecondsSinceEpoch.toString()
          : addresses[existingIndex]['id'],
      'name': existingIndex == -1 ? 'Last delivery' : addresses[existingIndex]['name'],
      'details': address,
      'phone': phone,
      'isDefault': true,
    };

    for (final item in addresses) {
      item['isDefault'] = false;
    }
    if (existingIndex == -1) {
      addresses.insert(0, savedAddress);
    } else {
      addresses[existingIndex] = savedAddress;
    }

    await ref.read(firestoreServiceProvider).updateUser(uid, {
      'savedAddresses': addresses,
    });
  }

  @override
  Widget build(BuildContext context) {
    final cartTotal = ref.watch(cartProvider.notifier).totalAmount;
    _prefillDeliveryDetails();

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: const Text('Checkout'),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Delivery Address', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 12),
              TextFormField(
                controller: _addressController,
                maxLines: 2,
                decoration: InputDecoration(
                  hintText: 'Full address (House #, Street, Area)',
                  fillColor: Colors.white,
                ),
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 20),
              
              const Text('Contact Phone', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9+]'))],
                decoration: InputDecoration(
                  hintText: '03xx xxxxxxx',
                  fillColor: Colors.white,
                ),
                validator: ValidationUtil.validatePhoneNumber,
              ),
              const SizedBox(height: 20),

              const Text('Delivery Schedule', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: _selectDate,
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(color: Colors.white, border: Border.all(color: Colors.grey[300]!), borderRadius: BorderRadius.circular(12)),
                        child: Text(DateFormat('MMM dd, yyyy').format(_deliveryDate)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: InkWell(
                      onTap: _selectTime,
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(color: Colors.white, border: Border.all(color: Colors.grey[300]!), borderRadius: BorderRadius.circular(12)),
                        child: Text(_deliveryTime.format(context)),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (_isAtCapacity)
                Container(
                  margin: const EdgeInsets.only(bottom: 20),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEF2F2),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFFECACA)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded,
                          color: Color(0xFFDC2626), size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Busy Day! 🥐',
                              style: TextStyle(
                                  color: Color(0xFF991B1B),
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13),
                            ),
                            const Text(
                              'This baker is at capacity for this date. We suggest picking the next available day.',
                              style: TextStyle(color: Color(0xFFB91C1C), fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 20),

              const Text('Payment Method', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 12),
              _PaymentOption(
                label: 'Cash on Delivery',
                value: 'COD',
                groupValue: _paymentMethod,
                onChanged: (v) => setState(() => _paymentMethod = v!),
              ),
              _PaymentOption(
                label: 'JazzCash / Easypaisa',
                value: 'DIGITAL',
                groupValue: _paymentMethod,
                onChanged: (v) => setState(() => _paymentMethod = v!),
              ),
              const SizedBox(height: 24),

              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(color: const Color(0xFFFEF3C7), borderRadius: BorderRadius.circular(16)),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Total Amount', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text('Rs. ${cartTotal.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 20, color: Color(0xFFD97706))),
                      ],
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: _placeOrder,
                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFD97706), foregroundColor: Colors.white),
                      child: const Text('Place Order'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}

class _PaymentOption extends StatelessWidget {
  final String label;
  final String value;
  final String groupValue;
  final ValueChanged<String?> onChanged;

  const _PaymentOption({required this.label, required this.value, required this.groupValue, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return RadioListTile<String>(
      title: Text(label),
      value: value,
      groupValue: groupValue,
      onChanged: onChanged,
      activeColor: const Color(0xFFD97706),
      contentPadding: EdgeInsets.zero,
    );
  }
}
