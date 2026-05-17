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

  static const gPink = LinearGradient(
    colors: [Color(0xFFFFD1D8), Color(0xFFFF8B9F)],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );
  static const gCopper = LinearGradient(
    colors: [Color(0xFFF39C12), Color(0xFFE67E22)],
    begin: Alignment.topLeft, end: Alignment.bottomRight,
  );
  
  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
  static List<BoxShadow> shadowMd = [
    BoxShadow(color: brown.withOpacity(0.06), blurRadius: 20, offset: const Offset(0, 8)),
  ];
}

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
    // Explicit price check for high visibility snackbar
    final priceInput = double.tryParse(_priceController.text.trim());
    if (priceInput == null || priceInput < AppConstants.minProductPrice || priceInput > AppConstants.maxProductPrice) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Price must be between Rs. ${AppConstants.minProductPrice.toInt()} and Rs. ${AppConstants.maxProductPrice.toInt()}'),
          backgroundColor: const Color(0xFF991B1B),
          behavior: SnackBarBehavior.floating,
        ),
      );
      // Still call validate to show field-level error
      _formKey.currentState!.validate();
      return;
    }

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
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        iconTheme: const IconThemeData(color: _T.brown),
        title: Text(
          widget.productId == null ? 'Add Product' : 'Edit Product',
          style: const TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        actions: [
          if (isSaving)
            const Center(
              child: Padding(
                padding: EdgeInsets.only(right: 16),
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2, color: _T.brown),
                ),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.check, color: _T.brown),
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
              const Text(
                'Images *',
                style: TextStyle(color: _T.brown, fontWeight: FontWeight.w700, fontSize: 13),
              ),
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
                          color: _T.pinkL,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: _T.pink.withOpacity(0.3), width: 1.5),
                        ),
                        child: const Icon(Icons.add_a_photo_outlined, color: _T.copper),
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
              const SizedBox(height: 24),
              // Ingredients Linking
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Expanded(child: Text('Ingredients Used', style: TextStyle(color: _T.brown, fontWeight: FontWeight.w700, fontSize: 13))),
                  Text('Total Cost: Rs. ${_calculateTotalCost(ingredientsAsync).toStringAsFixed(2)}', 
                    style: const TextStyle(color: _T.copper, fontSize: 12.5, fontWeight: FontWeight.w800)),
                ],
              ),
              const SizedBox(height: 8),
              ingredientsAsync.when(
                data: (allIngredients) {
                  if (allIngredients.isEmpty) {
                    return Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _T.surface,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: _T.rimLight, width: 1.5),
                        boxShadow: _T.shadowSm,
                      ),
                      child: const Text('No ingredients in inventory. Add them first!', style: TextStyle(color: _T.copper, fontSize: 13, fontWeight: FontWeight.w600)),
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
                            color: _T.surface,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: _T.rimLight, width: 1.5),
                            boxShadow: _T.shadowSm,
                          ),
                          child: Column(
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(ingredient.name, style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w800)),
                                  ),
                                  Text('Rs. ${cost.toStringAsFixed(2)}', style: const TextStyle(color: _T.statusGreen, fontWeight: FontWeight.w800, fontSize: 13)),
                                  const SizedBox(width: 8),
                                  IconButton(
                                    icon: const Icon(Icons.remove_circle_outline, color: Color(0xFFEF4444), size: 20),
                                    onPressed: () => setState(() => _selectedIngredients.remove(entry.key)),
                                    constraints: const BoxConstraints(),
                                    padding: EdgeInsets.zero,
                                  ),
                                ],
                              ),
                              const Divider(height: 16, color: _T.rimLight),
                              Row(
                                children: [
                                  const Text('Quantity:', style: TextStyle(color: _T.taupe, fontSize: 12, fontWeight: FontWeight.w600)),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: SizedBox(
                                      height: 35,
                                      child: TextFormField(
                                        initialValue: entry.value.toString(),
                                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                        style: const TextStyle(fontSize: 14, color: _T.ink),
                                        decoration: InputDecoration(
                                          contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                                          filled: true,
                                          fillColor: _T.surfaceWarm,
                                          suffixText: ingredient.unit,
                                          suffixStyle: const TextStyle(color: _T.copper, fontSize: 12, fontWeight: FontWeight.w600),
                                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _T.rimLight)),
                                          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _T.rimLight)),
                                          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _T.brown)),
                                        ),
                                        onChanged: (v) {
                                          final qty = double.tryParse(v) ?? 0.0;
                                          if (qty < 0) {
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              const SnackBar(content: Text('Ingredient quantity cannot be negative.')),
                                            );
                                            return;
                                          }
                                          setState(() => _selectedIngredients[entry.key] = qty);
                                        },
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Text('(@ Rs. ${ingredient.unitPrice}/${ingredient.unit})', style: const TextStyle(color: _T.inkFaint, fontSize: 10)),
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
                        dropdownColor: _T.surface,
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
                loading: () => const Center(child: CircularProgressIndicator(color: _T.brown)),
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
                      validator: (v) {
                        if (v == null || v.isEmpty) return 'Required';
                        final price = double.tryParse(v);
                        if (price == null) return 'Enter a valid price';
                        if (price < AppConstants.minProductPrice) {
                          return 'Min Rs. 20';
                        }
                        if (price > AppConstants.maxProductPrice) {
                          return 'Max Rs. 250,000';
                        }
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Category *', style: TextStyle(color: _T.brown, fontSize: 12, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        DropdownButtonFormField<String>(
                          value: _selectedCategory,
                          dropdownColor: _T.surfaceWarm,
                          style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
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
              const Text('Dietary Labels', style: TextStyle(color: _T.brown, fontWeight: FontWeight.w700, fontSize: 13)),
              const SizedBox(height: 12),
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
                      selectedColor: _T.pinkL,
                      backgroundColor: _T.surface,
                      side: BorderSide(
                        color: isSelected ? _T.pink.withOpacity(0.5) : _T.rimLight,
                        width: 1.5,
                      ),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      showCheckmark: false,
                      labelStyle: TextStyle(
                        color: isSelected ? _T.brown : _T.taupe,
                        fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                        fontSize: 13,
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
                    selectedColor: _T.pinkL,
                    backgroundColor: _T.surface,
                    side: BorderSide(
                      color: _includesAllDietaryLabels ? _T.pink.withOpacity(0.5) : _T.rimLight,
                      width: 1.5,
                    ),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    showCheckmark: false,
                    labelStyle: TextStyle(
                      color: _includesAllDietaryLabels ? _T.brown : _T.taupe,
                      fontWeight: _includesAllDietaryLabels ? FontWeight.w800 : FontWeight.w600,
                      fontSize: 13,
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
                    selectedColor: _T.pinkL,
                    backgroundColor: _T.surface,
                    side: BorderSide(
                      color: _includesNoDietaryLabels ? _T.pink.withOpacity(0.5) : _T.rimLight,
                      width: 1.5,
                    ),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    showCheckmark: false,
                    labelStyle: TextStyle(
                      color: _includesNoDietaryLabels ? _T.brown : _T.taupe,
                      fontWeight: _includesNoDietaryLabels ? FontWeight.w800 : FontWeight.w600,
                      fontSize: 13,
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
          color: _T.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: const Row(
          children: [
            Icon(Icons.info_outline, color: _T.copper, size: 18),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'Add ingredients above to calculate suggested price.', 
                style: TextStyle(color: _T.taupe, fontSize: 12.5, fontWeight: FontWeight.w600),
              ),
            ),
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
            color: _T.pinkL.withOpacity(0.4),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _T.pink.withOpacity(0.2), width: 1.5),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Pricing & Profit Calculator',
                    style: TextStyle(color: _T.brown, fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  Icon(Icons.calculate_outlined, color: _T.copper.withOpacity(0.5), size: 20),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Expanded(child: Text('Ingredient Cost', style: TextStyle(color: _T.taupe, fontWeight: FontWeight.w600))),
                  Text('Rs. ${cost.toStringAsFixed(2)}', style: const TextStyle(color: _T.brown, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Expanded(child: Text('Profit Margin (%)', style: TextStyle(color: _T.taupe, fontWeight: FontWeight.w600))),
                  SizedBox(
                    width: 60,
                    child: TextFormField(
                      initialValue: _profitMargin.toStringAsFixed(0),
                      keyboardType: TextInputType.number,
                      style: const TextStyle(color: _T.brown, fontWeight: FontWeight.bold),
                      decoration: const InputDecoration(isDense: true, border: UnderlineInputBorder(borderSide: BorderSide(color: _T.rimLight))),
                      onChanged: (v) {
                        final val = double.tryParse(v) ?? 30.0;
                        setState(() => _profitMargin = val);
                      },
                    ),
                  ),
                ],
              ),
              const Divider(color: _T.rimLight, height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Expanded(child: Text('Suggested Price', style: TextStyle(color: _T.taupe, fontWeight: FontWeight.w700))),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('Rs. ${suggestedPrice.toStringAsFixed(0)}', 
                        style: const TextStyle(color: _T.statusGreen, fontWeight: FontWeight.bold, fontSize: 18)),
                      if (suggestedPrice > 0) ...[
                        const SizedBox(width: 4),
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
                          child: const Text('Apply', style: TextStyle(color: _T.copper, fontWeight: FontWeight.bold, fontSize: 12)),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Suggested price covers ingredient costs and target profit.', 
                style: TextStyle(color: _T.inkMid, fontSize: 10, fontStyle: FontStyle.italic),
              ),
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
      hintStyle: const TextStyle(color: _T.inkFaint, fontSize: 14),
      filled: true,
      fillColor: _T.surface,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.rimLight, width: 1.5)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.rimLight, width: 1.5)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.brown, width: 1.5)),
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
        Text(label, style: const TextStyle(color: _T.taupe, fontSize: 12, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        TextFormField(
          controller: controller,
          maxLines: maxLines,
          keyboardType: keyboardType,
          validator: validator,
          style: const TextStyle(color: _T.ink),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: _T.inkFaint, fontSize: 14),
            filled: true,
            fillColor: _T.surface,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.rimLight, width: 1.5)),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.rimLight, width: 1.5)),
            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: _T.brown, width: 1.5)),
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
