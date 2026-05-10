import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:uuid/uuid.dart';
import '../../models/product_model.dart';
import '../../models/ingredient_model.dart';
import '../../providers/product_provider.dart';
import '../../providers/inventory_provider.dart';
import '../../providers/auth_provider.dart';
import '../../core/constants/app_constants.dart';

class AddEditProductScreen extends ConsumerStatefulWidget {
  final String? productId;
  const AddEditProductScreen({super.key, this.productId});

  @override
  ConsumerState<AddEditProductScreen> createState() => _AddEditProductScreenState();
}

class _AddEditProductScreenState extends ConsumerState<AddEditProductScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _priceController = TextEditingController();
  String? _selectedCategory;
  final List<String> _selectedDietary = [];
  bool _includesAllDietaryLabels = false;
  bool _includesNoDietaryLabels = false;
  final List<String> _existingImages = [];
  final List<File> _newImages = [];
  final Map<String, double> _selectedIngredients = {}; // ingredientId: quantity
  Map<String, double> _selectedAddOns = {}; // label: price
  bool _isAvailable = true;
  double _profitMargin = 30.0;

  @override
  void initState() {
    super.initState();
    if (widget.productId != null) {
      _loadProduct();
    }
  }

  void _loadProduct() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final products = ref.read(bakerProductsProvider).valueOrNull ?? [];
      final product = products.firstWhere((p) => p.id == widget.productId);
      
      _nameController.text = product.name;
      _descriptionController.text = product.description;
      _priceController.text = product.price.toString();
      _selectedCategory = product.category;

      _includesAllDietaryLabels = product.includesAllDietaryLabels;
      _includesNoDietaryLabels = product.includesNoDietaryLabels;

      _selectedDietary.clear();
      _selectedDietary.addAll(product.dietaryLabels);
      _existingImages.addAll(product.images);
      _selectedIngredients.addAll(product.ingredients);
      _selectedAddOns.addAll(product.addOns);
      _isAvailable = product.isAvailable;
      _profitMargin = product.profitMargin;
      setState(() {});
      _checkConflicts();
    });
  }

  List<String> _getConflicts() {
    final conflicts = <String>[];
    final ingredientsAsync = ref.read(bakerIngredientsProvider);
    final allIngredients = ingredientsAsync.valueOrNull ?? [];

    for (final entry in _selectedIngredients.entries) {
      if (entry.value <= 0) continue;
      final ingredient = allIngredients.firstWhere((i) => i.id == entry.key, 
        orElse: () => IngredientModel(id: '', bakerId: '', name: '', unit: '', quantity: 0, unitPrice: 0, updatedAt: DateTime.now()));
      
      final name = ingredient.name.toLowerCase();
      
      if (name.contains('egg') && _selectedDietary.contains('Eggless')) {
        conflicts.add('Eggless (contains ${ingredient.name})');
      }
      if (name.contains('sugar') && _selectedDietary.contains('Sugar-Free')) {
        conflicts.add('Sugar-Free (contains ${ingredient.name})');
      }
      if ((name.contains('flour') || name.contains('wheat')) && _selectedDietary.contains('Gluten-Free')) {
        conflicts.add('Gluten-Free (contains ${ingredient.name})');
      }
      if (name.contains('nut') && _selectedDietary.contains('Nut-Free')) {
        conflicts.add('Nut-Free (contains ${ingredient.name})');
      }
    }
    return conflicts;
  }

  void _checkConflicts() {
    final conflicts = _getConflicts();
    if (conflicts.isNotEmpty) {
      setState(() {
        // Option 1: Auto-remove (safer for data integrity)
        for (final conflict in conflicts) {
          final label = conflict.split(' ').first;
          _selectedDietary.remove(label);
        }
      });
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Removed conflicting dietary labels: ${conflicts.join(", ")}'),
          backgroundColor: const Color(0xFF991B1B),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  double _calculateTotalCost(AsyncValue<List<IngredientModel>> ingredientsAsync) {
    return ingredientsAsync.maybeWhen(
      data: (ingredients) {
        double cost = 0;
        _selectedIngredients.forEach((id, qty) {
          final ingredient = ingredients.firstWhere((i) => i.id == id);
          cost += ingredient.unitPrice * qty;
        });
        return cost;
      },
      orElse: () => 0.0,
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _priceController.dispose();
    super.dispose();
  }

  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.gallery, imageQuality: 80);
    if (picked != null) {
      setState(() {
        _newImages.add(File(picked.path));
      });
    }
  }

  void _removeImage(int index, bool isExisting) {
    setState(() {
      if (isExisting) {
        _existingImages.removeAt(index);
      } else {
        _newImages.removeAt(index);
      }
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    if (_selectedDietary.isEmpty && !_includesAllDietaryLabels && !_includesNoDietaryLabels) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least one Dietary Label (or All/None)')),
      );
      return;
    }

    if (_existingImages.isEmpty && _newImages.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please add at least one image')),
      );
      return;
    }

    final user = ref.read(currentUserProvider).valueOrNull!;
    final product = ProductModel(
      id: widget.productId ?? const Uuid().v4(),
      bakerId: user.uid,
      name: _nameController.text.trim(),
      description: _descriptionController.text.trim(),
      price: double.parse(_priceController.text.trim()),
      category: _selectedCategory!,
      images: _existingImages,
      dietaryLabels: _selectedDietary,
      ingredients: _selectedIngredients,
      addOns: _selectedAddOns,
      isAvailable: _isAvailable,
      profitMargin: _profitMargin,
      includesAllDietaryLabels: _includesAllDietaryLabels,
      includesNoDietaryLabels: _includesNoDietaryLabels,
      createdAt: DateTime.now(),
    );

    await ref.read(productNotifierProvider.notifier).saveProduct(
      product: product,
      newImages: _newImages,
    );

    if (mounted) {
      final state = ref.read(productNotifierProvider);
      if (state.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${state.error}')),
        );
      } else {
        Navigator.pop(context);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final ingredientsAsync = ref.watch(bakerIngredientsProvider);
    final isSaving = ref.watch(productNotifierProvider).isLoading;

    return Scaffold(
      backgroundColor: const Color(0xFFFDFCF9),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFDFCF9),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF451A03)),
        title: Text(widget.productId == null ? 'Add Product' : 'Edit Product', style: const TextStyle(color: Color(0xFF451A03))),
        actions: [
          if (isSaving)
            const Center(
              child: Padding(
                padding: EdgeInsets.only(right: 16),
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF78350F)),
                ),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.check, color: Color(0xFF78350F)),
              onPressed: _save,
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Images
              const Text('Images *', style: TextStyle(color: Color(0xFF78350F))),
              const SizedBox(height: 8),
              SizedBox(
                height: 100,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    GestureDetector(
                      onTap: _pickImage,
                      child: Container(
                        width: 100,
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF3C7),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Icon(Icons.add_a_photo_outlined, color: Color(0xFF92400E)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    ..._existingImages.asMap().entries.map((e) => _ImageThumbnail(
                          imageUrl: e.value,
                          onRemove: () => _removeImage(e.key, true),
                        )),
                    ..._newImages.asMap().entries.map((e) => _ImageThumbnail(
                          file: e.value,
                          onRemove: () => _removeImage(e.key, false),
                        )),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Basic Info
              _Field(
                controller: _nameController,
                label: 'Product Name *',
                hint: 'e.g. Chocolate Fudge Cake',
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              _Field(
                controller: _descriptionController,
                label: 'Description *',
                hint: 'Tell customers about your product...',
                maxLines: 3,
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              // Ingredients Linking
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Ingredients Used', style: TextStyle(color: Color(0xFF78350F), fontWeight: FontWeight.w600)),
                  Text('Total Cost: Rs. ${_calculateTotalCost(ingredientsAsync).toStringAsFixed(2)}', 
                    style: const TextStyle(color: Color(0xFF92400E), fontSize: 12, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 8),
              ingredientsAsync.when(
                data: (allIngredients) {
                  if (allIngredients.isEmpty) {
                    return Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFFFEF3C7))),
                      child: const Text('No ingredients in inventory. Add them first!', style: TextStyle(color: Color(0xFF92400E), fontSize: 13)),
                    );
                  }
                  
                  return Column(
                    children: [
                      // List of selected ingredients
                      ..._selectedIngredients.entries.map((entry) {
                        final ingredient = allIngredients.firstWhere((i) => i.id == entry.key);
                        final cost = ingredient.unitPrice * entry.value;
                        
                        return Container(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: const Color(0xFFFEF3C7)),
                          ),
                          child: Column(
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(ingredient.name, style: const TextStyle(color: Color(0xFF451A03), fontWeight: FontWeight.bold)),
                                  ),
                                  Text('Rs. ${cost.toStringAsFixed(2)}', style: const TextStyle(color: Color(0xFF16A34A), fontWeight: FontWeight.bold, fontSize: 13)),
                                  const SizedBox(width: 8),
                                  IconButton(
                                    icon: const Icon(Icons.remove_circle_outline, color: Color(0xFFEF4444), size: 20),
                                    onPressed: () => setState(() => _selectedIngredients.remove(entry.key)),
                                    constraints: const BoxConstraints(),
                                    padding: EdgeInsets.zero,
                                  ),
                                ],
                              ),
                              const Divider(height: 16, color: Color(0xFFFEF3C7)),
                              Row(
                                children: [
                                  const Text('Quantity:', style: TextStyle(color: Color(0xFF92400E), fontSize: 12)),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: SizedBox(
                                      height: 35,
                                      child: TextFormField(
                                        initialValue: entry.value.toString(),
                                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                        style: const TextStyle(fontSize: 14, color: Color(0xFF451A03)),
                                        decoration: InputDecoration(
                                          contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                                          filled: true,
                                          fillColor: const Color(0xFFFDFCF9),
                                          suffixText: ingredient.unit,
                                          suffixStyle: const TextStyle(color: Color(0xFF92400E), fontSize: 12),
                                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFFEF3C7))),
                                          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFFEF3C7))),
                                        ),
                                        onChanged: (v) {
                                          final qty = double.tryParse(v) ?? 0.0;
                                          setState(() => _selectedIngredients[entry.key] = qty);
                                        },
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Text('(@ Rs. ${ingredient.unitPrice}/${ingredient.unit})', style: const TextStyle(color: Color(0xFFA8A29E), fontSize: 10)),
                                ],
                              ),
                            ],
                          ),
                        );
                      }).toList(),

                      // Dropdown to add new ingredient
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        key: ValueKey(_selectedIngredients.length),
                        value: null,
                        hint: const Text('Add an ingredient...', style: TextStyle(fontSize: 14)),
                        dropdownColor: Colors.white,
                        decoration: _inputDecoration('Select to add'),
                        items: allIngredients
                            .where((i) => !_selectedIngredients.containsKey(i.id))
                            .map((i) => DropdownMenuItem(value: i.id, child: Text(i.name)))
                            .toList(),
                        onChanged: (val) {
                          if (val != null) {
                            setState(() => _selectedIngredients[val] = 1.0);
                            _checkConflicts();
                          }
                        },
                      ),
                    ],
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator(color: Color(0xFF78350F))),
                error: (_, __) => const Text('Error loading ingredients'),
              ),
              const SizedBox(height: 24),

              // Pricing Calculator
              _buildPricingCalculator(ingredientsAsync),
              const SizedBox(height: 24),

              Row(
                children: [
                  Expanded(
                    child: _Field(
                      controller: _priceController,
                      label: 'Price (Rs.) *',
                      hint: '0.00',
                      keyboardType: TextInputType.number,
                      validator: (v) => v!.isEmpty ? 'Required' : null,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Category *', style: TextStyle(color: Color(0xFF78350F), fontSize: 12)),
                        const SizedBox(height: 4),
                        DropdownButtonFormField<String>(
                          value: _selectedCategory,
                          dropdownColor: const Color(0xFFFEF3C7),
                          style: const TextStyle(color: Color(0xFF451A03)),
                          decoration: _inputDecoration('Select'),
                          items: AppConstants.productCategories
                              .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                              .toList(),
                          onChanged: (v) => setState(() => _selectedCategory = v),
                          validator: (v) => v == null ? 'Required' : null,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Dietary Labels
              const Text('Dietary Labels', style: TextStyle(color: Color(0xFF78350F))),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  // Individual Labels (First)
                  ...AppConstants.dietaryLabels.map((l) {
                    final isSelected = _selectedDietary.contains(l);
                    final disabled = _includesNoDietaryLabels;

                    // Icon mapping
                    Widget? icon;
                    if (l == 'Eggless') icon = const Text('🥚 ', style: TextStyle(fontSize: 14));
                    if (l == 'Sugar-Free') icon = const Text('🚫🍭 ', style: TextStyle(fontSize: 14));
                    if (l == 'Gluten-Free') icon = const Text('🌾 ', style: TextStyle(fontSize: 14));
                    if (l == 'Nut-Free') icon = const Text('🥜 ', style: TextStyle(fontSize: 14));

                    return FilterChip(
                      label: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (icon != null) icon,
                          Text(l),
                        ],
                      ),
                      selected: isSelected,
                      onSelected: disabled
                          ? null
                          : (val) {
                              setState(() {
                                if (val) {
                                  // Selecting individual labels cancels "None"
                                  _includesNoDietaryLabels = false;

                                  // Check for conflict before adding
                                  final ingredientsAsync = ref.read(bakerIngredientsProvider);
                                  final allIngredients = ingredientsAsync.valueOrNull ?? [];
                                  String? conflictSource;

                                  for (final entry in _selectedIngredients.entries) {
                                    final ing = allIngredients.firstWhere((i) => i.id == entry.key);
                                    final name = ing.name.toLowerCase();
                                    if ((l == 'Eggless' && name.contains('egg')) ||
                                        (l == 'Sugar-Free' && name.contains('sugar')) ||
                                        (l == 'Gluten-Free' && (name.contains('flour') || name.contains('wheat'))) ||
                                        (l == 'Nut-Free' && name.contains('nut'))) {
                                      conflictSource = ing.name;
                                      break;
                                    }
                                  }

                                  if (conflictSource != null) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(
                                        content: Text('Cannot select $l because the product contains $conflictSource'),
                                        backgroundColor: const Color(0xFF991B1B),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                  } else {
                                    _selectedDietary.add(l);
                                    // If all individual labels are selected, turn on "All" flag
                                    if (_selectedDietary.length == AppConstants.dietaryLabels.length) {
                                      _includesAllDietaryLabels = true;
                                    }
                                  }
                                } else {
                                  _selectedDietary.remove(l);
                                  _includesAllDietaryLabels = false;
                                }
                              });
                            },
                      selectedColor: const Color(0xFFFEF3C7),
                      labelStyle: TextStyle(
                        color: isSelected
                            ? const Color(0xFF78350F)
                            : const Color(0xFF451A03),
                      ),
                    );
                  }).toList(),

                  // "All" and "None" (At the End)
                  FilterChip(
                    label: const Text('All Labels'),
                    selected: _includesAllDietaryLabels,
                    onSelected: (val) {
                      setState(() {
                        _includesAllDietaryLabels = val;
                        if (val) {
                          _includesNoDietaryLabels = false;
                          _selectedDietary.clear();
                          _selectedDietary.addAll(AppConstants.dietaryLabels);
                        } else {
                          _selectedDietary.clear();
                        }
                      });
                    },
                    selectedColor: const Color(0xFFFEF3C7),
                    labelStyle: TextStyle(
                      color: _includesAllDietaryLabels
                          ? const Color(0xFF78350F)
                          : const Color(0xFF451A03),
                    ),
                  ),
                  FilterChip(
                    label: const Text('None'),
                    selected: _includesNoDietaryLabels,
                    onSelected: (val) {
                      setState(() {
                        _includesNoDietaryLabels = val;
                        if (val) {
                          _includesAllDietaryLabels = false;
                          _selectedDietary.clear();
                        }
                      });
                    },
                    selectedColor: const Color(0xFFFEF3C7),
                    labelStyle: TextStyle(
                      color: _includesNoDietaryLabels
                          ? const Color(0xFF78350F)
                          : const Color(0xFF451A03),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPricingCalculator(AsyncValue<List<IngredientModel>> ingredientsAsync) {
    if (_selectedIngredients.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(12),
        width: double.infinity,
        decoration: BoxDecoration(
          color: const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: const Row(
          children: [
            Icon(Icons.info_outline, color: Color(0xFF64748B), size: 18),
            SizedBox(width: 8),
            Text('Add ingredients above to calculate suggested price.', 
              style: TextStyle(color: Color(0xFF64748B), fontSize: 12)),
          ],
        ),
      );
    }

    return ingredientsAsync.when(
      data: (ingredients) {
        double cost = 0;
        _selectedIngredients.forEach((id, qty) {
          final ingredient = ingredients.firstWhere((i) => i.id == id, 
            orElse: () => IngredientModel(id: '', bakerId: '', name: '', unit: '', quantity: 0, unitPrice: 0, updatedAt: DateTime.now()));
          cost += ingredient.unitPrice * qty;
        });

        final suggestedPrice = cost / (1 - (_profitMargin / 100));
        
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFFFEF3C7).withOpacity(0.3),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFFEF3C7), width: 1.5),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Pricing & Profit Calculator',
                      style: TextStyle(color: Color(0xFF451A03), fontWeight: FontWeight.bold)),
                  Icon(Icons.calculate_outlined, color: const Color(0xFF78350F).withOpacity(0.5), size: 20),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Ingredient Cost', style: TextStyle(color: Color(0xFF92400E))),
                  Text('Rs. ${cost.toStringAsFixed(2)}', style: const TextStyle(color: Color(0xFF451A03), fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Expanded(child: Text('Profit Margin (%)', style: TextStyle(color: Color(0xFF92400E)))),
                  SizedBox(
                    width: 60,
                    child: TextFormField(
                      initialValue: _profitMargin.toStringAsFixed(0),
                      keyboardType: TextInputType.number,
                      style: const TextStyle(color: Color(0xFF78350F), fontWeight: FontWeight.bold),
                      decoration: const InputDecoration(isDense: true, border: UnderlineInputBorder()),
                      onChanged: (v) {
                        final val = double.tryParse(v) ?? 30.0;
                        setState(() => _profitMargin = val);
                      },
                    ),
                  ),
                ],
              ),
              const Divider(color: Color(0xFFFEF3C7), height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Suggested Price', style: TextStyle(color: Color(0xFF92400E))),
                  Row(
                    children: [
                      Text('Rs. ${suggestedPrice.toStringAsFixed(0)}', 
                        style: const TextStyle(color: Color(0xFF16A34A), fontWeight: FontWeight.bold, fontSize: 18)),
                      if (suggestedPrice > 0) ...[
                        const SizedBox(width: 8),
                        TextButton(
                          onPressed: () {
                            _priceController.text = suggestedPrice.toStringAsFixed(0);
                            setState(() {});
                          },
                          style: TextButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
                            minimumSize: Size.zero,
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          child: const Text('Apply', style: TextStyle(color: Color(0xFF78350F), fontWeight: FontWeight.bold, fontSize: 12)),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text('Suggested price covers ingredient costs and target profit.', 
                style: TextStyle(color: Color(0xFF92400E), fontSize: 10, fontStyle: FontStyle.italic)),
            ],
          ),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  InputDecoration _inputDecoration(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: Color(0xFFA8A29E), fontSize: 14),
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFFEF3C7), width: 1.5)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFFEF3C7), width: 1.5)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFF78350F), width: 1.5)),
    );
  }
}

class _Field extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final int maxLines;
  final TextInputType? keyboardType;
  final String? Function(String?)? validator;

  const _Field({
    required this.controller,
    required this.label,
    required this.hint,
    this.maxLines = 1,
    this.keyboardType,
    this.validator,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Color(0xFF92400E), fontSize: 12)),
        const SizedBox(height: 4),
        TextFormField(
          controller: controller,
          maxLines: maxLines,
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

class _ImageThumbnail extends StatelessWidget {
  final String? imageUrl;
  final File? file;
  final VoidCallback onRemove;

  const _ImageThumbnail({this.imageUrl, this.file, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 100,
      margin: const EdgeInsets.only(left: 8),
      child: Stack(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: file != null
                ? Image.file(file!, fit: BoxFit.cover, width: 100, height: 100)
                : Image.network(imageUrl!, fit: BoxFit.cover, width: 100, height: 100),
          ),
          Positioned(
            top: 4,
            right: 4,
            child: GestureDetector(
              onTap: onRemove,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                child: const Icon(Icons.close, size: 12, color: Colors.white),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
