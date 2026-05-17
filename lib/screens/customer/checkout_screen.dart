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

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const surface   = Color(0xFFFFFFFF);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  static const statusPink = Color(0xFFFF6B81);
  static const statusRed   = Color(0xFFE74C3C);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

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
  bool _didPrefill = false;

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
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: _T.brown,
              onPrimary: Colors.white,
              onSurface: _T.ink,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() => _deliveryDate = picked);
    }
  }

  Future<void> _selectTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _deliveryTime,
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: _T.brown,
              onPrimary: Colors.white,
              onSurface: _T.ink,
            ),
          ),
          child: child!,
        );
      },
    );
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
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _T.ink),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'Checkout',
          style: TextStyle(
            color: _T.ink,
            fontSize: 19,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Section: Address
              const Text(
                'Delivery Address',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: _T.ink),
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _addressController,
                maxLines: 2,
                cursorColor: _T.brown,
                style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600, fontSize: 14.5),
                decoration: InputDecoration(
                  hintText: 'Full address (House #, Street, Area)',
                  hintStyle: const TextStyle(color: _T.inkFaint, fontWeight: FontWeight.w500, fontSize: 13.5),
                  fillColor: _T.surface,
                  filled: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.brown, width: 1.5),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                ),
                validator: (v) => v!.isEmpty ? 'Address is required' : null,
              ),
              const SizedBox(height: 24),
              
              // Section: Phone
              const Text(
                'Contact Phone',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: _T.ink),
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9+]'))],
                cursorColor: _T.brown,
                style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600, fontSize: 14.5),
                decoration: InputDecoration(
                  hintText: '03xx xxxxxxx',
                  hintStyle: const TextStyle(color: _T.inkFaint, fontWeight: FontWeight.w500, fontSize: 13.5),
                  fillColor: _T.surface,
                  filled: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.brown, width: 1.5),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                ),
                validator: ValidationUtil.validatePhoneNumber,
              ),
              const SizedBox(height: 24),

              // Section: Schedule
              const Text(
                'Delivery Schedule',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: _T.ink),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: InkWell(
                      onTap: _selectDate,
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                        decoration: BoxDecoration(
                          color: _T.surface,
                          border: Border.all(color: _T.rimLight, width: 1.5),
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: _T.shadowSm,
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              DateFormat('MMM dd, yyyy').format(_deliveryDate),
                              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w700, fontSize: 13.5),
                            ),
                            const Icon(Icons.calendar_month_rounded, color: _T.brown, size: 20),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: InkWell(
                      onTap: _selectTime,
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                        decoration: BoxDecoration(
                          color: _T.surface,
                          border: Border.all(color: _T.rimLight, width: 1.5),
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: _T.shadowSm,
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              _deliveryTime.format(context),
                              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w700, fontSize: 13.5),
                            ),
                            const Icon(Icons.access_time_rounded, color: _T.brown, size: 20),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Section: Payment
              const Text(
                'Payment Method',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: _T.ink),
              ),
              const SizedBox(height: 10),
              _PaymentOption(
                label: 'Cash on Delivery',
                value: 'COD',
                groupValue: _paymentMethod,
                onChanged: (v) => setState(() => _paymentMethod = v!),
              ),
              const SizedBox(height: 28),

              // Summary card
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xFFFAF0E6), // Elegant warm cream/ivory
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Total Amount', 
                          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: _T.ink),
                        ),
                        Text(
                          'Rs. ${cartTotal.toStringAsFixed(0)}', 
                          style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 20, color: _T.statusPink),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: _placeOrder,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _T.brown, 
                        foregroundColor: Colors.white,
                        minimumSize: const Size(double.infinity, 54),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        elevation: 0,
                      ),
                      child: const Text(
                        'Place Order',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
                      ),
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
    final bool isSelected = value == groupValue;
    return Container(
      decoration: BoxDecoration(
        color: isSelected ? const Color(0xFFFFECE0) : _T.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isSelected ? _T.brown : _T.rimLight,
          width: 1.5,
        ),
      ),
      child: RadioListTile<String>(
        title: Text(
          label,
          style: const TextStyle(
            color: _T.ink,
            fontWeight: FontWeight.w800,
            fontSize: 14.5,
          ),
        ),
        value: value,
        groupValue: groupValue,
        onChanged: onChanged,
        activeColor: _T.brown,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12),
      ),
    );
  }
}
