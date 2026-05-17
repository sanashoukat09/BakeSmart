import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import '../../models/ingredient_model.dart';
import '../../providers/inventory_provider.dart';
import '../../providers/auth_provider.dart';

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
            colorScheme: const ColorScheme.light(
              primary: _T.brown,
              onPrimary: Colors.white,
              surface: _T.surface,
              onSurface: _T.ink,
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
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${state.error}', style: const TextStyle(color: _T.statusPink))));
      } else {
        Navigator.pop(context);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSaving = ref.watch(inventoryNotifierProvider).isLoading;

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        iconTheme: const IconThemeData(color: _T.brown),
        title: Text(
          widget.ingredientId == null ? 'Add Ingredient' : 'Edit Ingredient', 
          style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        actions: [
          if (isSaving)
            const Center(child: Padding(padding: EdgeInsets.only(right: 16), child: CircularProgressIndicator(strokeWidth: 2.5, color: _T.copper)))
          else
            IconButton(
              icon: const Icon(Icons.check, color: _T.brown, size: 26), 
              onPressed: _save,
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              _Field(
                controller: _nameController, 
                label: 'Ingredient Name *', 
                hint: 'e.g. Flour, Sugar, Eggs', 
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: _Field(
                      controller: _quantityController, 
                      label: 'Current Quantity *', 
                      hint: '0.0', 
                      keyboardType: TextInputType.number, 
                      validator: (v) {
                        if (v == null || v.isEmpty) return 'Required';
                        final val = double.tryParse(v);
                        if (val == null || val < 0) return 'Must be >= 0';
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _Field(
                      controller: _unitController, 
                      label: 'Unit *', 
                      hint: 'e.g. kg, pieces', 
                      validator: (v) => v!.isEmpty ? 'Required' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              _Field(
                controller: _thresholdController, 
                label: 'Low Stock Threshold *', 
                hint: '1.0', 
                keyboardType: TextInputType.number, 
                validator: (v) {
                  if (v == null || v.isEmpty) return 'Required';
                  final val = double.tryParse(v);
                  if (val == null || val < 0) return 'Must be >= 0';
                  return null;
                },
              ),
              const SizedBox(height: 16),
              _Field(
                controller: _unitPriceController, 
                label: 'Unit Price (Rs.) *', 
                hint: '0.0', 
                keyboardType: TextInputType.number, 
                validator: (v) {
                  if (v == null || v.isEmpty) return 'Required';
                  final val = double.tryParse(v);
                  if (val == null || val < 0) return 'Must be >= 0';
                  return null;
                },
              ),
              const SizedBox(height: 16),
              
              // Expiry Date Picker
              InkWell(
                onTap: _selectDate,
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _T.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: _T.rimLight, width: 1.5),
                    boxShadow: _T.shadowSm,
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today_outlined, color: _T.copper, size: 18),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Expiry Date (Optional)', 
                              style: TextStyle(color: _T.copper, fontSize: 11, fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _selectedExpiry == null ? 'Not set' : DateFormat('MMM dd, yyyy').format(_selectedExpiry!),
                              style: TextStyle(
                                color: _selectedExpiry == null ? _T.inkFaint : _T.ink, 
                                fontSize: 14, 
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (_selectedExpiry != null)
                        IconButton(
                          icon: const Icon(Icons.close, color: _T.statusPink, size: 18),
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
                  height: 48,
                  child: TextButton.icon(
                    onPressed: () async {
                      await ref.read(inventoryNotifierProvider.notifier).deleteIngredient(widget.ingredientId!);
                      if (mounted) Navigator.pop(context);
                    },
                    style: TextButton.styleFrom(
                      foregroundColor: _T.statusPink,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    ),
                    icon: const Icon(Icons.delete_outline, color: _T.statusPink),
                    label: const Text('Delete Ingredient', style: TextStyle(color: _T.statusPink, fontWeight: FontWeight.w800)),
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
        Text(
          label, 
          style: const TextStyle(color: _T.copper, fontSize: 12, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 6),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          validator: validator,
          style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: _T.inkFaint, fontSize: 14),
            filled: true,
            fillColor: _T.surface,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.rimLight, width: 1.5)),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.rimLight, width: 1.5)),
            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.brown, width: 1.5)),
          ),
        ),
      ],
    );
  }
}
