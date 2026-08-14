import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../../models/user_model.dart';
import '../../core/constants/app_constants.dart';
import '../../core/utils/share_util.dart';
import '../../widgets/customer/customer_bottom_nav.dart';
import 'baker_storefront_screen.dart';

class BakerSearchScreen extends ConsumerStatefulWidget {
  const BakerSearchScreen({super.key});

  @override
  ConsumerState<BakerSearchScreen> createState() => _BakerSearchScreenState();
}

class _BakerSearchScreenState extends ConsumerState<BakerSearchScreen> {
  final _searchController = TextEditingController();
  final _focusNode = FocusNode();
  final _db = FirebaseFirestore.instance;
  
  String _searchQuery = '';
  String? _selectedCity;
  String? _selectedSpecialty;
  double _minRating = 0;
  String _sortBy = 'rating'; // rating, reviews, name
  
  List<UserModel> _allBakers = [];
  List<UserModel> _filteredBakers = [];
  bool _isLoading = true;
  
  // Available cities (you can populate from Firestore or hardcode)
  final List<String> _cities = [
    'Karachi',
    'Lahore',
    'Islamabad',
    'Rawalpindi',
    'Faisalabad',
    'Multan',
    'Peshawar',
    'Quetta',
  ];

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(() {
      setState(() {});
    });
    _loadBakers();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _loadBakers() async {
    setState(() => _isLoading = true);
    
    try {
      final snapshot = await _db
          .collection(AppConstants.usersCollection)
          .where('role', isEqualTo: AppConstants.roleBaker)
          .get();

      final bakers = snapshot.docs
          .map((doc) => UserModel.fromFirestore(doc))
          .toList();

      setState(() {
        _allBakers = bakers;
        _filteredBakers = bakers;
        _isLoading = false;
      });
      
      _applyFilters();
    } catch (e) {
      print('Error loading bakers: $e');
      setState(() => _isLoading = false);
    }
  }

  void _applyFilters() {
    setState(() {
      _filteredBakers = _allBakers.where((baker) {
        // Search query filter (name or bakery name)
        if (_searchQuery.isNotEmpty) {
          final query = _searchQuery.toLowerCase();
          final matchesName = (baker.displayName ?? '').toLowerCase().contains(query);
          final matchesBakery = baker.bakeryName?.toLowerCase().contains(query) ?? false;
          if (!matchesName && !matchesBakery) return false;
        }

        // City filter
        if (_selectedCity != null && baker.location != _selectedCity) {
          return false;
        }

        // Specialty filter
        if (_selectedSpecialty != null) {
          if (!baker.specialties.contains(_selectedSpecialty)) {
            return false;
          }
        }

        // Rating filter
        if (baker.rating < _minRating) {
          return false;
        }

        return true;
      }).toList();

      // Apply sorting
      switch (_sortBy) {
        case 'rating':
          _filteredBakers.sort((a, b) => b.rating.compareTo(a.rating));
          break;
        case 'reviews':
          _filteredBakers.sort((a, b) => b.totalReviews.compareTo(a.totalReviews));
          break;
        case 'name':
          _filteredBakers.sort((a, b) => (a.displayName ?? '').compareTo(b.displayName ?? ''));
          break;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFFDF8),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFFFDF8),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFFB05E27)),
        title: const Text(
          'Discover Bakers',
          style: TextStyle(
            color: Color(0xFF451A03),
            fontWeight: FontWeight.w800,
            fontSize: 18,
          ),
        ),
      ),
      body: Column(
        children: [
          // Search Bar
          _buildSearchBar(),

          // Filters Row
          _buildFiltersRow(),

          // Results Count
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Row(
              children: [
                Text(
                  '${_filteredBakers.length} bakers found',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF92400E),
                  ),
                ),
                const Spacer(),
                _buildSortDropdown(),
              ],
            ),
          ),

          // Baker List
          Expanded(
            child: _isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      color: Color(0xFFB05E27),
                    ),
                  )
                : _filteredBakers.isEmpty
                    ? _buildEmptyState()
                    : RefreshIndicator(
                        onRefresh: _loadBakers,
                        color: const Color(0xFFB05E27),
                        child: ListView.builder(
                          padding: const EdgeInsets.all(16),
                          itemCount: _filteredBakers.length,
                          itemBuilder: (context, index) {
                            return _buildBakerCard(_filteredBakers[index]);
                          },
                        ),
                      ),
          ),
        ],
      ),
      bottomNavigationBar: const CustomerBottomNav(currentIndex: 1),
    );
  }

  Widget _buildSearchBar() {
    final isFocused = _focusNode.hasFocus;
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isFocused ? const Color(0xFF451A03) : const Color(0xFFD4A574),
          width: isFocused ? 2.0 : 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: isFocused 
                ? const Color(0xFF451A03).withOpacity(0.1) 
                : Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: TextField(
        controller: _searchController,
        focusNode: _focusNode,
        decoration: const InputDecoration(
          hintText: 'Search by name or bakery...',
          hintStyle: TextStyle(color: Color(0xFFD4A574), fontSize: 14),
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          errorBorder: InputBorder.none,
          disabledBorder: InputBorder.none,
          icon: Icon(Icons.search, color: Color(0xFFB05E27)),
        ),
        style: const TextStyle(color: Color(0xFF451A03)),
        onChanged: (value) {
          setState(() => _searchQuery = value);
          _applyFilters();
        },
      ),
    );
  }

  Widget _buildFiltersRow() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _buildFilterChip(
            label: _selectedCity ?? 'City',
            icon: Icons.location_city,
            onTap: () => _showCityPicker(),
            isActive: _selectedCity != null,
          ),
          const SizedBox(width: 8),
          _buildFilterChip(
            label: _selectedSpecialty ?? 'Specialty',
            icon: Icons.cake,
            onTap: () => _showSpecialtyPicker(),
            isActive: _selectedSpecialty != null,
          ),
          const SizedBox(width: 8),
          _buildFilterChip(
            label: _minRating > 0 ? '${_minRating.toStringAsFixed(0)}★ & up' : 'Rating',
            icon: Icons.star,
            onTap: () => _showRatingPicker(),
            isActive: _minRating > 0,
          ),
          const SizedBox(width: 8),
          if (_selectedCity != null || _selectedSpecialty != null || _minRating > 0)
            GestureDetector(
              onTap: _clearFilters,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFFDC2626),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.clear, color: Colors.white, size: 16),
                    SizedBox(width: 4),
                    Text(
                      'Clear',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFilterChip({
    required String label,
    required IconData icon,
    required VoidCallback onTap,
    required bool isActive,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFFB05E27) : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isActive ? const Color(0xFFB05E27) : const Color(0xFFD4A574),
            width: 1.5,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              color: isActive ? Colors.white : const Color(0xFFB05E27),
              size: 16,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: isActive ? Colors.white : const Color(0xFF451A03),
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSortDropdown() {
    return PopupMenuButton<String>(
      initialValue: _sortBy,
      onSelected: (value) {
        setState(() => _sortBy = value);
        _applyFilters();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFD4A574)),
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.sort, size: 16, color: Color(0xFFB05E27)),
            SizedBox(width: 4),
            Text(
              'Sort',
              style: TextStyle(fontSize: 12, color: Color(0xFF451A03)),
            ),
          ],
        ),
      ),
      itemBuilder: (context) => [
        const PopupMenuItem(value: 'rating', child: Text('Highest Rated')),
        const PopupMenuItem(value: 'reviews', child: Text('Most Reviewed')),
        const PopupMenuItem(value: 'name', child: Text('Name (A-Z)')),
      ],
    );
  }

  Widget _buildBakerCard(UserModel baker) {
    return GestureDetector(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => BakerStorefrontScreen(bakerId: baker.uid),
        ),
      ),
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFD4A574), width: 1.5),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Cover/Profile Image
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
              child: baker.portfolioImages.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: baker.portfolioImages.first,
                      height: 120,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      placeholder: (context, url) => Container(
                        color: const Color(0xFFFEF3C7),
                      ),
                      errorWidget: (context, url, error) => Container(
                        color: const Color(0xFFFEF3C7),
                        child: const Icon(
                          Icons.bakery_dining,
                          size: 48,
                          color: Color(0xFFB05E27),
                        ),
                      ),
                    )
                  : Container(
                      height: 120,
                      color: const Color(0xFFFEF3C7),
                      child: const Center(
                        child: Icon(
                          Icons.bakery_dining,
                          size: 48,
                          color: Color(0xFFB05E27),
                        ),
                      ),
                    ),
            ),

            // Baker Info
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Bakery Name
                  Text(
                    baker.bakeryName ?? baker.displayName ?? '',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF451A03),
                    ),
                  ),
                  const SizedBox(height: 4),

                  // Rating
                  if (baker.rating > 0)
                    Row(
                      children: [
                        Icon(
                          Icons.star,
                          size: 16,
                          color: Colors.orange[700],
                        ),
                        const SizedBox(width: 4),
                        Text(
                          baker.rating.toStringAsFixed(1),
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF92400E),
                          ),
                        ),
                        if (baker.totalReviews > 0)
                          Text(
                            ' (${baker.totalReviews} reviews)',
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFFD4A574),
                            ),
                          ),
                      ],
                    ),
                  const SizedBox(height: 8),

                  // Location
                  if (baker.location != null)
                    Row(
                      children: [
                        const Icon(
                          Icons.location_on,
                          size: 14,
                          color: Color(0xFFB05E27),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          baker.location!,
                          style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFF92400E),
                          ),
                        ),
                      ],
                    ),
                  const SizedBox(height: 8),

                  // Specialties
                  if (baker.specialties.isNotEmpty)
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: baker.specialties.take(3).map((specialty) {
                        return Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF3C7),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            specialty,
                            style: const TextStyle(
                              fontSize: 10,
                              color: Color(0xFFB05E27),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  const SizedBox(height: 12),

                  // Action Buttons
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (context) =>
                                  BakerStorefrontScreen(bakerId: baker.uid),
                            ),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFB05E27),
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                          icon: const Icon(Icons.storefront, size: 16),
                          label: const Text(
                            'View Store',
                            style: TextStyle(fontSize: 13, color: Colors.white),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        onPressed: () => _shareStorefront(baker),
                        icon: const Icon(Icons.share),
                        color: const Color(0xFFB05E27),
                        style: IconButton.styleFrom(
                          backgroundColor: const Color(0xFFFEF3C7),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.search_off,
            size: 80,
            color: const Color(0xFFD4A574).withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          const Text(
            'No bakers found',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: Color(0xFF92400E),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Try adjusting your filters',
            style: TextStyle(
              fontSize: 13,
              color: Color(0xFFD4A574),
            ),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: _clearFilters,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFB05E27),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
            child: const Text('Clear Filters', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showCityPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFFFFFDF8),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFD4A574),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const Padding(
            padding: EdgeInsets.all(20),
            child: Text(
              'Select City',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Color(0xFF451A03),
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: _cities.length,
              itemBuilder: (context, index) {
                final city = _cities[index];
                return ListTile(
                  leading: const Icon(Icons.location_city, color: Color(0xFFB05E27)),
                  title: Text(city),
                  trailing: _selectedCity == city
                      ? const Icon(Icons.check, color: Color(0xFF10B981))
                      : null,
                  onTap: () {
                    setState(() => _selectedCity = city);
                    _applyFilters();
                    Navigator.pop(context);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _showSpecialtyPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFFFFFDF8),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFD4A574),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const Padding(
            padding: EdgeInsets.all(20),
            child: Text(
              'Select Specialty',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Color(0xFF451A03),
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: AppConstants.bakerSpecialties.length,
              itemBuilder: (context, index) {
                final specialty = AppConstants.bakerSpecialties[index];
                return ListTile(
                  leading: const Icon(Icons.cake, color: Color(0xFFB05E27)),
                  title: Text(specialty),
                  trailing: _selectedSpecialty == specialty
                      ? const Icon(Icons.check, color: Color(0xFF10B981))
                      : null,
                  onTap: () {
                    setState(() => _selectedSpecialty = specialty);
                    _applyFilters();
                    Navigator.pop(context);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _showRatingPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFFFFFDF8),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              margin: const EdgeInsets.only(bottom: 20),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFD4A574),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Text(
              'Minimum Rating',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Color(0xFF451A03),
              ),
            ),
            const SizedBox(height: 20),
            ...List.generate(5, (index) {
              final rating = 5 - index.toDouble();
              return ListTile(
                leading: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: List.generate(
                    5,
                    (i) => Icon(
                      i < rating ? Icons.star : Icons.star_border,
                      color: Colors.orange[700],
                      size: 20,
                    ),
                  ),
                ),
                title: Text('${rating.toStringAsFixed(0)}★ & up'),
                trailing: _minRating == rating
                    ? const Icon(Icons.check, color: Color(0xFF10B981))
                    : null,
                onTap: () {
                  setState(() => _minRating = rating);
                  _applyFilters();
                  Navigator.pop(context);
                },
              );
            }),
          ],
        ),
      ),
    );
  }

  void _clearFilters() {
    setState(() {
      _selectedCity = null;
      _selectedSpecialty = null;
      _minRating = 0;
      _searchQuery = '';
      _searchController.clear();
    });
    _applyFilters();
  }

  void _shareStorefront(UserModel baker) {
    ShareUtil.shareStore(
      bakerName: baker.bakeryName ?? baker.displayName ?? '',
      bakerId: baker.uid,
    );
  }
}
