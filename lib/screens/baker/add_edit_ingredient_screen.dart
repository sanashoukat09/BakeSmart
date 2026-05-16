import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import '../../models/ingredient_model.dart';
import '../../providers/inventory_provider.dart';
import '../../providers/auth_provider.dart';

class AddEditIngredientScreen extends ConsumerStatefulWidget {
  final String? ingredientId;
  const AddEditIngredientScreen({super.key, this.ingredientId});

  @override
  ConsumerState<AddEditIngredientScreen> createState() => _AddEditIngredientScreenState();
}

class _AddEditIngredientScreenState extends ConsumerState<AddEditIngredientScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _quantityController = TextEditingController();
  final _unitController = TextEditingController();
  final _thresholdController = TextEditingController(text: '1.0');
  final _unitPriceController = TextEditingController(text: '0.0');
  DateTime? _selectedExpiry;

  @override
  void dispose() {
    _nameController.dispose();
    _quantityController.dispose();
    _unitController.dispose();
    _thresholdController.dispose();
    _unitPriceController.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    if (widget.ingredientId != null) {
      _loadIngredient();
    }
  }

  void _loadIngredient() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final ingredients = ref.read(bakerIngredientsProvider).valueOrNull ?? [];
      final ingredient = ingredients.firstWhere((i) => i.id == widget.ingredientId);
      
      _nameController.text = ingredient.name;
      _quantityController.text = ingredient.quantity.toString();
      _unitController.text = ingredient.unit;
      _thresholdController.text = ingredient.lowStockThreshold.toString();
      _unitPriceController.text = ingredient.unitPrice.toString();
      _selectedExpiry = ingredient.expiryDate;
      setState(() {});
    });
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedExpiry ?? DateTime.now(),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365 * 2)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.dark(
              primary: Color(0xFFF59E0B),
              onPrimary: Color(0xFF0D1117),
              surface: Color(0xFF161B22),
              onSurface: Color(0xFFF0F6FC),
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) setState(() => _selectedExpiry = picked);
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    final user = ref.read(currentUserProvider).valueOrNull!;
    final ingredient = IngredientModel(
      id: widget.ingredientId ?? const Uuid().v4(),
      bakerId: user.uid,
      name: _nameController.text.trim(),
      quantity: double.parse(_quantityController.text.trim()),
      unit: _unitController.text.trim(),
      unitPrice: double.parse(_unitPriceController.text.trim()),
      lowStockThreshold: double.parse(_thresholdController.text.trim()),
      expiryDate: _selectedExpiry,
      updatedAt: DateTime.now(),
    );

    await ref.read(inventoryNotifierProvider.notifier).saveIngredient(ingredient);

    if (mounted) {
      final state = ref.read(inventoryNotifierProvider);
      if (state.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${state.error}')));
      } else {
        Navigator.pop(context);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSaving = ref.watch(inventoryNotifierProvider).isLoading;

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFDFCF9),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF451A03)),
        title: Text(widget.ingredientId == null ? 'Add Ingredient' : 'Edit Ingredient', 
          style: const TextStyle(color: Color(0xFF451A03))),
        actions: [
          if (isSaving)
            const Center(child: Padding(padding: EdgeInsets.only(right: 16), child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF78350F))))
          else
            IconButton(icon: const Icon(Icons.check, color: Color(0xFF78350F)), onPressed: _save),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              _Field(controller: _nameController, label: 'Ingredient Name *', hint: 'e.g. Flour, Sugar, Eggs', validator: (v) => v!.isEmpty ? 'Required' : null),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _Field(controller: _quantityController, label: 'Current Quantity *', hint: '0.0', keyboardType: TextInputType.number, validator: (v) {
                    if (v == null || v.isEmpty) return 'Required';
                    final val = double.tryParse(v);
                    if (val == null || val < 0) return 'Must be >= 0';
                    return null;
                  })),
                  const SizedBox(width: 16),
                  Expanded(child: _Field(controller: _unitController, label: 'Unit *', hint: 'e.g. kg, pieces', validator: (v) => v!.isEmpty ? 'Required' : null)),
                ],
              ),
              const SizedBox(height: 16),
              _Field(controller: _thresholdController, label: 'Low Stock Threshold *', hint: '1.0', keyboardType: TextInputType.number, validator: (v) {
                if (v == null || v.isEmpty) return 'Required';
                final val = double.tryParse(v);
                if (val == null || val < 0) return 'Must be >= 0';
                return null;
              }),
              const SizedBox(height: 16),
              _Field(controller: _unitPriceController, label: 'Unit Price (Rs.) *', hint: '0.0', keyboardType: TextInputType.number, validator: (v) {
                if (v == null || v.isEmpty) return 'Required';
                final val = double.tryParse(v);
                if (val == null || val < 0) return 'Must be >= 0';
                return null;
              }),
              const SizedBox(height: 16),
              
              // Expiry Date Picker
              InkWell(
                onTap: _selectDate,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFFFEF3C7), width: 1.5),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today_outlined, color: Color(0xFF92400E), size: 18),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Expiry Date (Optional)', style: TextStyle(color: Color(0xFF92400E), fontSize: 11)),
                            const SizedBox(height: 2),
                            Text(
                              _selectedExpiry == null ? 'Not set' : DateFormat('MMM dd, yyyy').format(_selectedExpiry!),
                              style: TextStyle(color: _selectedExpiry == null ? const Color(0xFFA8A29E) : const Color(0xFF451A03), fontSize: 14),
                            ),
                          ],
                        ),
                      ),
                      if (_selectedExpiry != null)
                        IconButton(
                          icon: const Icon(Icons.close, color: Color(0xFFEF4444), size: 18),
                          onPressed: () => setState(() => _selectedExpiry = null),
                        ),
                    ],
                  ),
                ),
              ),
              
              if (widget.ingredientId != null) ...[
                const SizedBox(height: 32),
                SizedBox(
                  width: double.infinity,
                  child: TextButton.icon(
                    onPressed: () async {
                      await ref.read(inventoryNotifierProvider.notifier).deleteIngredient(widget.ingredientId!);
                      if (mounted) Navigator.pop(context);
                    },
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    label: const Text('Delete Ingredient', style: TextStyle(color: Colors.red)),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _Field extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final TextInputType? keyboardType;
  final String? Function(String?)? validator;

  const _Field({required this.controller, required this.label, required this.hint, this.keyboardType, this.validator});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Color(0xFF92400E), fontSize: 12)),
        const SizedBox(height: 4),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          validator: validator,
          style: const TextStyle(color: Color(0xFF451A03)),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: Color(0xFFA8A29E), fontSize: 14),
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFFEF3C7), width: 1.5)),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFFEF3C7), width: 1.5)),
            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFF78350F), width: 1.5)),
          ),
        ),
      ],
    );
  }
}
