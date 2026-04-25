import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../../products/models/product_model.dart';
import '../../community/screens/community_hub_screen.dart';
import '../services/cart_service.dart';
import 'product_detail_screen.dart';
import 'cart_screen.dart';
import 'order_history_screen.dart';
import '../../auth/services/auth_provider.dart';
import '../../notifications/screens/notifications_screen.dart';
import '../../notifications/services/notification_service.dart';
import 'package:cached_network_image/cached_network_image.dart';

class CatalogueState {
  final List<ProductModel> products;
  final bool isLoading;
  final bool hasMore;
  final DocumentSnapshot? lastDoc;
  final String? errorMessage;

  CatalogueState({
    this.products = const [],
    this.isLoading = false,
    this.hasMore = true,
    this.lastDoc,
    this.errorMessage,
  });

  // Sentinel so callers can explicitly pass null to clear lastDoc/errorMessage.
  // Using a named copyWith for lastDoc avoids the "null means keep" antipattern.
  static const Object _absent = Object();

  CatalogueState copyWith({
    List<ProductModel>? products,
    bool? isLoading,
    bool? hasMore,
    Object? lastDoc = _absent,
    Object? errorMessage = _absent,
  }) {
    return CatalogueState(
      products: products ?? this.products,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
      lastDoc: identical(lastDoc, _absent) ? this.lastDoc : lastDoc as DocumentSnapshot?,
      errorMessage: identical(errorMessage, _absent) ? this.errorMessage : errorMessage as String?,
    );
  }
}

class CatalogueNotifier extends Notifier<CatalogueState> {
  final int _pageSize = 20;
  String _currentFilter = 'All';
  String _currentQuery = '';

  @override
  CatalogueState build() {
    // Start with isLoading: true so the UI shows a spinner immediately instead
    // of flashing "No products found" before the first fetch completes.
    Future.microtask(() => fetchFirstPage());
    return CatalogueState(isLoading: true);
  }

  void updateFilter(String newFilter) {
    _currentFilter = newFilter;
    fetchFirstPage();
  }

  void updateSearch(String newQuery) {
    _currentQuery = newQuery;
    fetchFirstPage();
  }

  Future<void> fetchFirstPage() async {
    // Passing null for lastDoc and errorMessage explicitly clears them (sentinel pattern).
    state = state.copyWith(isLoading: true, products: [], lastDoc: null, hasMore: true, errorMessage: null);
    await _fetchData(isNextPage: false);
  }

  Future<void> fetchNextPage() async {
    if (state.isLoading || !state.hasMore) return;
    state = state.copyWith(isLoading: true);
    await _fetchData(isNextPage: true);
  }

  Future<void> _fetchData({required bool isNextPage}) async {
    // Build the query. WHERE clauses must come before orderBy for Firestore
    // to correctly use composite indexes.
    Query query = FirebaseFirestore.instance.collection('products');

    if (_currentFilter == 'Surplus Deals') {
      // Requires composite index: isSurplus ASC + createdAt DESC
      query = query.where('isSurplus', isEqualTo: true);
    } else if (_currentFilter != 'All') {
      // Requires composite index: tags ARRAY_CONTAINS + createdAt DESC
      query = query.where('tags', arrayContains: _currentFilter.toLowerCase());
    }

    query = query.orderBy('createdAt', descending: true);

    if (isNextPage && state.lastDoc != null) {
      query = query.startAfterDocument(state.lastDoc!);
    }

    query = query.limit(_pageSize);

    try {
      final snapshot = await query.get();

      List<ProductModel> fetchedProducts = snapshot.docs
          .map((doc) => ProductModel.fromMap(doc.data() as Map<String, dynamic>, doc.id))
          .where((p) => p.isAvailable && p.bakerIsVerified) // filter unavailable or unverified products client-side
          .toList();

      // Firestore doesn't support full-text substring search; filter locally.
      if (_currentQuery.isNotEmpty) {
        fetchedProducts = fetchedProducts.where((p) =>
            p.name.toLowerCase().contains(_currentQuery) ||
            p.bakerName.toLowerCase().contains(_currentQuery)).toList();
      }

      final newProducts = isNextPage ? [...state.products, ...fetchedProducts] : fetchedProducts;
      final bool hasMore = snapshot.docs.length == _pageSize;

      // Pass null explicitly for lastDoc when empty — the sentinel-based copyWith
      // correctly distinguishes "omitted" from "set to null", so this resets
      // the pagination cursor when there are no results.
      state = state.copyWith(
        products: newProducts,
        lastDoc: snapshot.docs.isNotEmpty ? snapshot.docs.last : null,
        hasMore: hasMore,
        isLoading: false,
        errorMessage: null,
      );
    } catch (e) {
      debugPrint('Catalogue fetch error: $e');
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Could not load products. Pull down to retry.',
      );
    }
  }
}

final catalogueProvider = NotifierProvider<CatalogueNotifier, CatalogueState>(() {
  return CatalogueNotifier();
});

class ProductCatalogueScreen extends ConsumerStatefulWidget {
  const ProductCatalogueScreen({super.key});

  @override
  ConsumerState<ProductCatalogueScreen> createState() => _ProductCatalogueScreenState();
}

class _ProductCatalogueScreenState extends ConsumerState<ProductCatalogueScreen> {
  final _scrollController = ScrollController();
  final List<String> _filters = ['All', 'Eggless', 'Sugar-Free', 'Gluten-Free', 'Vegan', 'Surplus Deals'];
  String _selectedFilter = 'All';

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(() {
      if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
        ref.read(catalogueProvider.notifier).fetchNextPage();
      }
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final catState = ref.watch(catalogueProvider);
    final catNotifier = ref.read(catalogueProvider.notifier);
    final cartCount = ref.watch(cartProvider.notifier).totalItemCount;
    final unreadCountAsync = ref.watch(unreadNotificationsCountProvider);

    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: const Text('BakeSmart Catalogue'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
        actions: [
          Stack(
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_none_rounded),
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
              ),
              unreadCountAsync.when(
                data: (val) => val > 0 
                  ? Positioned(
                      right: 8,
                      top: 8,
                      child: Container(
                        padding: const EdgeInsets.all(2),
                        decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(10)),
                        constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                        child: Text('$val', style: const TextStyle(color: Colors.white, fontSize: 10), textAlign: TextAlign.center),
                      ),
                    )
                  : const SizedBox.shrink(),
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
              ),
            ],
          ),
          Stack(
            alignment: Alignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.shopping_cart),
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CartScreen())),
              ),
              if (cartCount > 0)
                Positioned(
                  right: 8,
                  top: 8,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                    child: Text('$cartCount', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                  ),
                )
            ],
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.red),
            onPressed: () => ref.read(authControllerProvider).signOut(),
          ),
        ],
      ),
      drawer: Drawer(
        child: ListView(
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: Colors.brown),
              child: Text('BakeSmart Customer', style: TextStyle(color: Colors.white, fontSize: 24)),
            ),
            ListTile(
              leading: const Icon(Icons.receipt_long),
              title: const Text('My Orders'),
              onTap: () {
                Navigator.pop(context); // close drawer
                Navigator.push(context, MaterialPageRoute(builder: (_) => const OrderHistoryScreen()));
              },
            ),
            ListTile(
              leading: const Icon(Icons.people_alt_rounded, color: Color(0xFF00897B)),
              title: const Text('Community Hub'),
              onTap: () {
                Navigator.pop(context); // close drawer
                Navigator.push(context, MaterialPageRoute(builder: (_) => const CommunityHubScreen()));
              },
            ),
            ListTile(
              leading: const Icon(Icons.logout, color: Colors.red),
              title: const Text('Sign Out', style: TextStyle(color: Colors.red)),
              onTap: () {
                Navigator.pop(context);
                ref.read(authControllerProvider).signOut();
              },
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          // Search Bar
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Search products or bakers...',
                prefixIcon: const Icon(Icons.search),
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
              ),
              onChanged: (val) => catNotifier.updateSearch(val.toLowerCase()),
            ),
          ),
          
          // Filter Chips
          SizedBox(
            height: 50,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _filters.length,
              itemBuilder: (ctx, i) {
                final filter = _filters[i];
                final isSelected = _selectedFilter == filter;
                return Padding(
                  padding: const EdgeInsets.only(right: 8.0),
                  child: FilterChip(
                    label: Text(filter, style: TextStyle(color: isSelected ? Colors.white : Colors.brown)),
                    selected: isSelected,
                    selectedColor: Colors.brown,
                    backgroundColor: Colors.brown[100],
                    onSelected: (selected) {
                      setState(() => _selectedFilter = filter);
                      catNotifier.updateFilter(filter);
                    },
                  ),
                );
              },
            ),
          ),

          // Grid with Infinite Scroll
          Expanded(
            child: RefreshIndicator(
              onRefresh: () async => catNotifier.fetchFirstPage(),
              color: Colors.brown,
              child: catState.errorMessage != null
                  ? SingleChildScrollView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.all(32),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.cloud_off, size: 48, color: Colors.grey),
                              const SizedBox(height: 16),
                              Text(catState.errorMessage!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
                            ],
                          ),
                        ),
                      ),
                    )
                  : catState.products.isEmpty && !catState.isLoading
                      ? const SingleChildScrollView(physics: AlwaysScrollableScrollPhysics(), child: Center(child: Padding(padding: EdgeInsets.all(32), child: Text('No products found matching those criteria.'))))
                      : GridView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(16),
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        childAspectRatio: 0.7,
                        crossAxisSpacing: 16,
                        mainAxisSpacing: 16,
                      ),
                      itemCount: catState.products.length + (catState.hasMore ? 1 : 0),
                      itemBuilder: (context, index) {
                        if (index == catState.products.length) {
                          return const Center(child: CircularProgressIndicator(color: Colors.brown));
                        }

                        final product = catState.products[index];
                        final priceToDisplay = product.isSurplus && product.surplusPrice != null ? product.surplusPrice! : product.basePrice;

                        return GestureDetector(
                          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ProductDetailScreen(product: product))),
                          child: Container(
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                              boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 4, offset: const Offset(0, 2))],
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                // Cover Image Area
                                Expanded(
                                  flex: 3,
                                  child: Stack(
                                    children: [
                                      ClipRRect(
                                        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                                        child: product.images.isNotEmpty
                                            ? CachedNetworkImage(
                                                imageUrl: product.images.first,
                                                fit: BoxFit.cover,
                                                width: double.infinity,
                                                height: double.infinity,
                                                placeholder: (context, url) => Container(color: Colors.grey[200]),
                                                errorWidget: (context, url, error) => const Icon(Icons.error),
                                              )
                                            : Container(color: Colors.grey[300], child: const Center(child: Icon(Icons.image, color: Colors.grey))),
                                      ),
                                      if (product.isSurplus)
                                        Positioned(
                                          top: 8, right: 8,
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(color: Colors.blue, borderRadius: BorderRadius.circular(4)),
                                            child: const Text('DEAL', style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                                // Details Area
                                Expanded(
                                  flex: 2,
                                  child: Padding(
                                    padding: const EdgeInsets.all(8.0),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(product.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                                        const SizedBox(height: 4),
                                        Text('by ${product.bakerName}', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: Colors.grey[600], fontSize: 12)),
                                        const Spacer(),
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text('\$${priceToDisplay.toStringAsFixed(2)}', style: const TextStyle(color: Colors.brown, fontWeight: FontWeight.bold)),
                                            if (product.isSurplus && product.surplusPrice != null)
                                              Text('\$${product.basePrice.toStringAsFixed(2)}', style: const TextStyle(fontSize: 10, decoration: TextDecoration.lineThrough, color: Colors.grey)),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
