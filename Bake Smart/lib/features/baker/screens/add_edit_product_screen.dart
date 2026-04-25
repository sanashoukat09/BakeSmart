import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:cached_network_image/cached_network_image.dart';

import '../../auth/services/auth_provider.dart';
import '../../products/models/product_model.dart';
import '../../products/services/product_service.dart';
import '../../products/services/cost_calculator_service.dart';
import '../models/ingredient_model.dart';
import '../services/inventory_service.dart';
import 'seller_verification_screen.dart';

class AddEditProductScreen extends ConsumerStatefulWidget {
  final ProductModel? product;
  const AddEditProductScreen({super.key, this.product});

  @override
  ConsumerState<AddEditProductScreen> createState() => _AddEditProductScreenState();
}

class _AddEditProductScreenState extends ConsumerState<AddEditProductScreen> {
  final _formKey = GlobalKey<FormState>();
  
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _basePriceCtrl = TextEditingController();
  final _surplusPriceCtrl = TextEditingController();
  
  String _category = 'Cakes';
  final List<String> _categories = ['Cakes', 'Pastries', 'Breads', 'Cookies', 'Other'];
  
  final List<String> _availableTags = ['eggless', 'sugar-free', 'gluten-free', 'vegan', 'nut-free'];
  final List<String> _selectedTags = [];
  
  bool _isSurplus = false;
  bool _isAvailable = true;
  bool _isLoading = false;

  List<RecipeIngredient> _recipeIngredients = [];
  final List<XFile> _localImages = [];
  List<String> _existingImages = [];

  double _formCostPrice = 0.0;
  double _formBasePrice = 0.0;

  @override
  void initState() {
    super.initState();
    if (widget.product != null) {
      _nameCtrl.text = widget.product!.name;
      _descCtrl.text = widget.product!.description;
      _basePriceCtrl.text = widget.product!.basePrice.toString();
      _surplusPriceCtrl.text = widget.product!.surplusPrice?.toString() ?? '';
      _category = widget.product!.category;
      _selectedTags.addAll(widget.product!.tags);
      _isSurplus = widget.product!.isSurplus;
      _isAvailable = widget.product!.isAvailable;
      _existingImages = List.from(widget.product!.images);
      _recipeIngredients = List.from(widget.product!.recipeIngredients);
      _formBasePrice = widget.product!.basePrice;
    }
    
    _basePriceCtrl.addListener(() {
      setState(() {
        _formBasePrice = double.tryParse(_basePriceCtrl.text) ?? 0.0;
      });
    });
    
    _recalculateCost();
  }

  void _recalculateCost() {
    final costCalc = ref.read(costCalculatorProvider);
    _formCostPrice = costCalc.calculateTotalCost(_recipeIngredients);
  }

  Future<void> _pickImages() async {
    final ImagePicker picker = ImagePicker();
    final List<XFile> images = await picker.pickMultiImage();
    if (images.isNotEmpty) {
      setState(() {
        _localImages.addAll(images);
      });
    }
  }

  void _addRecipeIngredient(List<IngredientModel> inventory) {
    if (inventory.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Your inventory is empty!')));
      return;
    }
    
    IngredientModel? selectedIng = inventory.first;
    final qtyCtrl = TextEditingController();
    final costCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Add Component'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<IngredientModel>(
                    initialValue: selectedIng,
                    items: inventory.map((i) => DropdownMenuItem(value: i, child: Text('${i.name} (Stock: ${i.quantity} ${i.unit})'))).toList(),
                    onChanged: (val) => setDialogState(() => selectedIng = val),
                    decoration: const InputDecoration(labelText: 'From Inventory'),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: qtyCtrl,
                          keyboardType: TextInputType.number,
                          decoration: InputDecoration(labelText: 'Qty Used (${selectedIng?.unit})'),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: TextField(
                          controller: costCtrl,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(labelText: 'Estimated Cost (\$)'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                ElevatedButton(
                  onPressed: () {
                    final qty = double.tryParse(qtyCtrl.text) ?? 0;
                    final cost = double.tryParse(costCtrl.text) ?? 0;
                    if (selectedIng != null) {
                      setState(() {
                        _recipeIngredients.add(RecipeIngredient(
                          ingredientId: selectedIng!.ingredientId,
                          name: selectedIng!.name,
                          quantityUsed: qty,
                          measuredCostPrice: cost,
                        ));
                        _recalculateCost();
                      });
                      Navigator.pop(ctx);
                    }
                  },
                  child: const Text('Add'),
                )
              ],
            );
          }
        );
      }
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    
    if (_isSurplus) {
      final base = double.tryParse(_basePriceCtrl.text) ?? 0;
      final surplus = double.tryParse(_surplusPriceCtrl.text) ?? 0;
      if (surplus > base) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Surplus price cannot be greater than Base Price!')));
        return;
      }
    }

    setState(() => _isLoading = true);
    
    try {
      final user = ref.read(authStateProvider).value;
      if (user == null) throw Exception('Not authenticated!');
      
      final userData = await ref.read(userDataProvider.future);
      if (userData == null) throw Exception('User data not loaded!');

      if (userData.verificationStatus != 'verified') {
        if (mounted) {
          showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('Verification Required'),
              content: const Text('You need to complete seller verification before listing products.'),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                ElevatedButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    Navigator.push(context, MaterialPageRoute(builder: (_) => SellerVerificationScreen()));
                  }, 
                  child: const Text('Apply Now'),
                ),
              ],
            ),
          );
        }
        setState(() => _isLoading = false);
        return;
      }

      final product = ProductModel(
        productId: widget.product?.productId ?? '',
        bakerId: user.uid,
        bakerName: userData.bakeryName ?? userData.name,
        bakerIsVerified: userData.verificationStatus == 'verified',
        name: _nameCtrl.text.trim(),
        description: _descCtrl.text.trim(),
        category: _category,
        tags: _selectedTags,
        basePrice: _formBasePrice,
        costPrice: _formCostPrice,
        isSurplus: _isSurplus,
        surplusPrice: _isSurplus ? double.tryParse(_surplusPriceCtrl.text) : null,
        images: _existingImages,
        isAvailable: _isAvailable,
        recipeIngredients: _recipeIngredients,
        createdAt: widget.product?.createdAt ?? DateTime.now(),
        updatedAt: DateTime.now(),
      );

      final service = ref.read(productServiceProvider);
      if (widget.product == null) {
        await service.addProduct(product, _localImages);
      } else {
        await service.updateProduct(product, _localImages);
      }
      
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final costCalc = ref.read(costCalculatorProvider);
    final margin = costCalc.calculateProfitMargin(_formBasePrice, _formCostPrice);

    Color marginColor = Colors.green;
    String marginMsg = 'Healthy Margin';
    if (margin < 0) {
      marginColor = Colors.red;
      marginMsg = 'Selling price is below cost';
    } else if (margin < 10) {
      marginColor = Colors.orange;
      marginMsg = 'Low Profit Margin';
    }

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(title: Text(widget.product == null ? 'Create Product' : 'Edit Product'), backgroundColor: Colors.brown, foregroundColor: Colors.white),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Photos section
              Row(
                children: [
                  GestureDetector(
                    onTap: _pickImages,
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.brown)),
                      child: const Icon(Icons.add_a_photo, color: Colors.brown),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: SizedBox(
                      height: 80,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          ..._existingImages.map((url) => Padding(
                            padding: const EdgeInsets.only(right: 8.0),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: CachedNetworkImage(
                                imageUrl: url,
                                width: 80,
                                height: 80,
                                fit: BoxFit.cover,
                                placeholder: (context, url) => Container(color: Colors.grey[200]),
                                errorWidget: (context, url, error) => const Icon(Icons.error),
                              ),
                            ),
                          )),
                          ..._localImages.map((file) => Padding(
                            padding: const EdgeInsets.only(right: 8.0),
                            child: ClipRRect(borderRadius: BorderRadius.circular(8), child: kIsWeb ? Image.network(file.path, width: 80, height: 80, fit: BoxFit.cover) : Image.file(File(file.path), width: 80, height: 80, fit: BoxFit.cover)),
                          )),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              TextFormField(
                controller: _nameCtrl,
                decoration: InputDecoration(labelText: 'Product Name', filled: true, fillColor: Colors.white, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              
              TextFormField(
                controller: _descCtrl,
                maxLines: 3,
                decoration: InputDecoration(labelText: 'Description', filled: true, fillColor: Colors.white, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
              ),
              const SizedBox(height: 16),
              
              DropdownButtonFormField<String>(
                initialValue: _category,
                decoration: InputDecoration(labelText: 'Category', filled: true, fillColor: Colors.white, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                items: _categories.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                onChanged: (val) => setState(() => _category = val!),
              ),
              const SizedBox(height: 16),

              const Text('Dietary Tags', style: TextStyle(fontWeight: FontWeight.bold)),
              Wrap(
                spacing: 8,
                children: _availableTags.map((tag) => FilterChip(
                  label: Text(tag),
                  selected: _selectedTags.contains(tag),
                  selectedColor: Colors.brown[200],
                  onSelected: (selected) {
                    setState(() {
                      selected ? _selectedTags.add(tag) : _selectedTags.remove(tag);
                    });
                  },
                )).toList(),
              ),
              const SizedBox(height: 24),

              // Cost Calculator Section
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.brown[200]!)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Cost Recipe', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.brown)),
                        Consumer(builder: (ctx, constRef, _) {
                          final invAsync = constRef.watch(inventoryStreamProvider);
                          return invAsync.when(
                            data: (inv) => TextButton.icon(
                              onPressed: () => _addRecipeIngredient(inv), 
                              icon: const Icon(Icons.add), 
                              label: const Text('Add Component')
                            ),
                            loading: () => const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
                            error: (e,s) => const Icon(Icons.error, color: Colors.red),
                          );
                        }),
                      ],
                    ),
                    if (_recipeIngredients.isEmpty)
                      const Text('No components added. Cost is \$0.00', style: TextStyle(fontStyle: FontStyle.italic)),
                    ..._recipeIngredients.map((i) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(i.name),
                      subtitle: Text('Qty: ${i.quantityUsed}'),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text('\$${i.measuredCostPrice.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold)),
                          IconButton(
                            icon: const Icon(Icons.delete, color: Colors.red),
                            onPressed: () => setState(() {
                              _recipeIngredients.remove(i);
                              _recalculateCost();
                            }),
                          )
                        ],
                      ),
                    )),
                    const Divider(),
                    Text('Total Calculated Cost: \$${_formCostPrice.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              TextFormField(
                controller: _basePriceCtrl,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(labelText: 'Selling Price (\$)', filled: true, fillColor: Colors.white, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              const SizedBox(height: 8),

              // Realtime Margin alert
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: marginColor.withOpacity(0.1), borderRadius: BorderRadius.circular(8), border: Border.all(color: marginColor)),
                child: Row(
                  children: [
                    Icon(margin < 0 ? Icons.error : margin < 10 ? Icons.warning : Icons.check_circle, color: marginColor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Profit Margin: ${margin.toStringAsFixed(1)}%\n$marginMsg',
                        style: TextStyle(color: marginColor, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              SwitchListTile(
                title: const Text('Is Surplus Item?'),
                subtitle: const Text('Apply a discount for end-of-day sales'),
                value: _isSurplus,
                onChanged: (val) => setState(() => _isSurplus = val),
              ),
              if (_isSurplus)
                TextFormField(
                  controller: _surplusPriceCtrl,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(labelText: 'Surplus Price (\$)', filled: true, fillColor: Colors.white, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
                  validator: (v) {
                    if (v!.isEmpty) return 'Required when surplus is active';
                    final s = double.tryParse(v);
                    final b = double.tryParse(_basePriceCtrl.text);
                    if (s == null || b == null) return 'Invalid numbers';
                    if (s > b) return 'Surplus cannot be higher than Base Price';
                    return null;
                  },
                ),

              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: _isLoading ? null : _save,
                style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16), backgroundColor: Colors.brown, foregroundColor: Colors.white, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                child: _isLoading ? const CircularProgressIndicator(color: Colors.white) : const Text('Save Product', style: TextStyle(fontSize: 18)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
