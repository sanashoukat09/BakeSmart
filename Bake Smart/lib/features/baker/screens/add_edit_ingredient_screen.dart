import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../auth/services/auth_provider.dart';
import '../models/ingredient_model.dart';
import '../services/inventory_service.dart';

class AddEditIngredientScreen extends ConsumerStatefulWidget {
  final IngredientModel? ingredient;

  const AddEditIngredientScreen({super.key, this.ingredient});

  @override
  ConsumerState<AddEditIngredientScreen> createState() => _AddEditIngredientScreenState();
}

class _AddEditIngredientScreenState extends ConsumerState<AddEditIngredientScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameCtrl;
  late TextEditingController _quantityCtrl;
  late TextEditingController _thresholdCtrl;
  String _selectedUnit = 'grams';
  DateTime? _selectedExpiry;
  bool _isLoading = false;

  final List<String> _units = ['grams', 'kg', 'litres', 'pieces'];

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.ingredient?.name ?? '');
    _quantityCtrl = TextEditingController(text: widget.ingredient?.quantity.toString() ?? '');
    _thresholdCtrl = TextEditingController(text: widget.ingredient?.lowStockThreshold.toString() ?? '0');
    if (widget.ingredient != null) {
      _selectedUnit = widget.ingredient!.unit;
      _selectedExpiry = widget.ingredient!.expiryDate;
    }
  }

  Future<void> _pickDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _selectedExpiry ?? DateTime.now(),
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (date != null) {
      setState(() => _selectedExpiry = date);
    }
  }

  void _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final user = ref.read(authStateProvider).value;
      if (user == null) throw Exception('Not authenticated');

      final quantity = double.parse(_quantityCtrl.text);
      final threshold = double.parse(_thresholdCtrl.text);

      final status = IngredientModel.calculateStatus(quantity, threshold, _selectedExpiry);

      final model = IngredientModel(
        ingredientId: widget.ingredient?.ingredientId ?? '',
        bakerId: user.uid,
        name: _nameCtrl.text.trim(),
        quantity: quantity,
        unit: _selectedUnit,
        lowStockThreshold: threshold,
        expiryDate: _selectedExpiry,
        status: status,
      );

      final service = ref.read(inventoryServiceProvider);
      if (widget.ingredient == null) {
        await service.addIngredient(model);
      } else {
        await service.updateIngredient(model);
      }

      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.ingredient == null ? 'Add Ingredient' : 'Edit Ingredient';

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: Text(title),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: Colors.brown,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _nameCtrl,
                decoration: InputDecoration(
                  labelText: 'Ingredient Name',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                ),
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextFormField(
                      controller: _quantityCtrl,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                        labelText: 'Quantity',
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      validator: (v) {
                        if (v!.isEmpty) return 'Required';
                        if (double.tryParse(v) == null || double.parse(v) < 0) return 'Invalid';
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 1,
                    child: DropdownButtonFormField<String>(
                      initialValue: _selectedUnit,
                      decoration: InputDecoration(
                        labelText: 'Unit',
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      items: _units.map((u) => DropdownMenuItem(value: u, child: Text(u))).toList(),
                      onChanged: (val) => setState(() => _selectedUnit = val!),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _thresholdCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: 'Low Stock Threshold',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                ),
                validator: (v) {
                  if (v!.isEmpty) return 'Required';
                  if (double.tryParse(v) == null || double.parse(v) < 0) return 'Invalid';
                  return null;
                },
              ),
              const SizedBox(height: 16),
              GestureDetector(
                onTap: _pickDate,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey[400]!),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedExpiry == null
                            ? 'No Expiry Date'
                            : 'Expiry: ${DateFormat.yMMMd().format(_selectedExpiry!)}',
                        style: TextStyle(
                          fontSize: 16,
                          color: _selectedExpiry == null ? Colors.grey[600] : Colors.black87,
                        ),
                      ),
                      const Icon(Icons.calendar_today, color: Colors.brown),
                    ],
                  ),
                ),
              ),
              if (_selectedExpiry != null)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => setState(() => _selectedExpiry = null),
                    child: const Text('Clear Date', style: TextStyle(color: Colors.red)),
                  ),
                ),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: _isLoading ? null : _save,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: Colors.brown,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Save Ingredient', style: TextStyle(fontSize: 18)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
