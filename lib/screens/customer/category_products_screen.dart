import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/store_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/wishlist_provider.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';
import '../../models/product_model.dart';
import '../../widgets/customer/product_card.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════
abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const surface   = Colors.white;
  static const brown     = Color(0xFFB05E27);
  static const rimLight  = Color(0xFFF2EAE0);
  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class CategoryProductsScreen extends ConsumerStatefulWidget {
  final String category;

  const CategoryProductsScreen({super.key, required this.category});

  @override
  ConsumerState<CategoryProductsScreen> createState() => _CategoryProductsScreenState();
}

class _CategoryProductsScreenState extends ConsumerState<CategoryProductsScreen> {
  @override
  void initState() {
    super.initState();
    // Set the category filter in the global state on load
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final currentFilter = ref.read(storeFilterProvider);
      ref.read(storeFilterProvider.notifier).state = currentFilter.copyWith(category: widget.category);
    });
  }

  @override
  Widget build(BuildContext context) {
    final products = ref.watch(filteredProductsProvider);
    final filter = ref.watch(storeFilterProvider);

    return PopScope(
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) {
          // Reset category filter when leaving this screen
          ref.read(storeFilterProvider.notifier).state = ref.read(storeFilterProvider).copyWith(category: null);
        }
      },
      child: Scaffold(
        backgroundColor: _T.canvas,
        appBar: AppBar(
          backgroundColor: _T.canvas,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded, color: _T.ink, size: 20),
            onPressed: () => context.pop(),
          ),
          title: Text(
            widget.category,
            style: const TextStyle(
              color: _T.ink,
              fontWeight: FontWeight.w800,
              fontSize: 20,
              letterSpacing: -0.4,
            ),
          ),
          centerTitle: true,
        ),
        body: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Search Bar for this category
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                child: Container(
                  decoration: BoxDecoration(
                    color: _T.surface,
                    borderRadius: BorderRadius.circular(30),
                    border: Border.all(color: _T.rimLight, width: 1.2),
                    boxShadow: _T.shadowSm,
                  ),
                  child: TextField(
                    onChanged: (v) => ref.read(storeFilterProvider.notifier).state = filter.copyWith(query: v),
                    style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w700),
                    decoration: InputDecoration(
                      hintText: 'Search in ${widget.category}...',
                      hintStyle: const TextStyle(color: _T.inkFaint, fontWeight: FontWeight.w600, fontSize: 14),
                      prefixIcon: const Icon(Icons.search, color: _T.inkFaint, size: 22),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                    ),
                  ),
                ),
              ),

              // 2. Dietary Filter chips
              SizedBox(
                height: 42,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(),
                  padding: const EdgeInsets.only(left: 20),
                  itemCount: AppConstants.dietaryLabels.length,
                  itemBuilder: (context, i) {
                    final label = AppConstants.dietaryLabels[i];
                    final isSelected = filter.dietaryLabels.contains(label);

                    String icon = '';
                    if (label == 'Eggless') icon = '🥚';
                    if (label == 'Sugar-Free') icon = '🚫🍭';
                    if (label == 'Gluten-Free') icon = '🌾';
                    if (label == 'Nut-Free') icon = '🥜';

                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: Text('$icon $label', style: TextStyle(
                          color: isSelected ? Colors.white : _T.inkMid,
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                        )),
                        selected: isSelected,
                        onSelected: (val) {
                          final newList = List<String>.from(filter.dietaryLabels);
                          if (val) {
                            newList.add(label);
                          } else {
                            newList.remove(label);
                          }
                          ref.read(storeFilterProvider.notifier).state = filter.copyWith(dietaryLabels: newList);
                        },
                        selectedColor: _T.brown,
                        checkmarkColor: Colors.white,
                        backgroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                          side: BorderSide(color: isSelected ? Colors.transparent : _T.rimLight, width: 1.2),
                        ),
                      ),
                    );
                  },
                ),
              ),

              const SizedBox(height: 16),

              // 3. Products List / Grid
              Expanded(
                child: products.isNotEmpty
                    ? GridView.builder(
                        physics: const BouncingScrollPhysics(),
                        padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          childAspectRatio: 0.72,
                          mainAxisSpacing: 16,
                          crossAxisSpacing: 16,
                        ),
                        itemCount: products.length,
                        itemBuilder: (context, i) => ProductCard(
                          product: products[i],
                          onTap: () => context.push('${AppRoutes.customerProduct}/${products[i].id}'),
                        ),
                      )
                    : Center(
                        child: SingleChildScrollView(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.cookie_outlined, size: 70, color: _T.inkFaint),
                              const SizedBox(height: 16),
                              Text(
                                'No ${widget.category} found',
                                style: const TextStyle(
                                  color: _T.ink,
                                  fontWeight: FontWeight.w800,
                                  fontSize: 18,
                                ),
                              ),
                              const SizedBox(height: 6),
                              const Padding(
                                padding: EdgeInsets.symmetric(horizontal: 40),
                                child: Text(
                                  'We couldn\'t find any creations matching your dietary preferences.',
                                  style: TextStyle(
                                    color: _T.inkMid,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500,
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ),
                              if (filter.dietaryLabels.isNotEmpty || filter.query.isNotEmpty) ...[
                                const SizedBox(height: 20),
                                ElevatedButton(
                                  onPressed: () {
                                    ref.read(storeFilterProvider.notifier).state = filter.copyWith(
                                      query: '',
                                      dietaryLabels: [],
                                    );
                                  },
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: _T.brown,
                                    foregroundColor: Colors.white,
                                    elevation: 0,
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                                  ),
                                  child: const Text('Reset Filters', style: TextStyle(fontWeight: FontWeight.w700)),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
