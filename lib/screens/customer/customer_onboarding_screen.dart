import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/router/app_router.dart';
import '../../providers/auth_provider.dart';

class CustomerOnboardingScreen extends ConsumerStatefulWidget {
  const CustomerOnboardingScreen({super.key});

  @override
  ConsumerState<CustomerOnboardingScreen> createState() =>
      _CustomerOnboardingScreenState();
}

class _CustomerOnboardingScreenState
    extends ConsumerState<CustomerOnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;
  bool _isLoading = false;

  final List<String> _selectedDietary = [];
  final List<String> _selectedAllergens = [];

  static const List<Map<String, dynamic>> _dietaryOptions = [
    {'label': 'Eggless', 'icon': '🥚', 'desc': 'No eggs in any ingredients'},
    {'label': 'Sugar-Free', 'icon': '🍬', 'desc': 'Diabetic-friendly options'},
    {'label': 'Gluten-Free', 'icon': '🌾', 'desc': 'No wheat or gluten'},
    {'label': 'Nut-Free', 'icon': '🥜', 'desc': 'Safe for nut allergies'},
    {'label': 'Vegan', 'icon': '🌱', 'desc': 'No animal products'},
    {'label': 'Halal', 'icon': '✅', 'desc': 'Halal certified'},
  ];

  static const List<Map<String, dynamic>> _allergenOptions = [
    {'label': 'Nuts', 'icon': '🥜'},
    {'label': 'Dairy', 'icon': '🥛'},
    {'label': 'Eggs', 'icon': '🥚'},
    {'label': 'Gluten', 'icon': '🌾'},
    {'label': 'Soy', 'icon': '🫘'},
    {'label': 'Seeds', 'icon': '🌻'},
  ];

  void _nextPage() {
    if (_currentPage < 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
      setState(() => _currentPage++);
    } else {
      _completeOnboarding();
    }
  }

  void _prevPage() {
    if (_currentPage > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
      setState(() => _currentPage--);
    }
  }

  Future<void> _completeOnboarding() async {
    setState(() => _isLoading = true);
    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) return;

    await ref.read(firestoreServiceProvider).completeOnboarding(user.uid, {
      'dietaryPreferences': _selectedDietary,
      'allergens': _selectedAllergens,
    });

    if (mounted) {
      setState(() => _isLoading = false);
      context.go(AppRoutes.customerHome);
    }
  }

  @override
  Widget build(BuildContext context) {
    const primary = Color(0xFFC2410C);
    const bg = Color(0xFFFFFBF5);
    const textPrimary = Color(0xFF1C1917);
    const textSecondary = Color(0xFF57534E);

    return Scaffold(
      backgroundColor: bg,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: primary,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.bakery_dining_rounded,
                            color: Colors.white, size: 22),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'BakeSmart',
                        style: TextStyle(
                          color: textPrimary,
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Row(
                    children: List.generate(2, (i) {
                      return Expanded(
                        child: Container(
                          height: 4,
                          margin: EdgeInsets.only(right: i < 1 ? 8 : 0),
                          decoration: BoxDecoration(
                            color: i <= _currentPage
                                ? primary
                                : const Color(0xFFE7E5E4),
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Step ${_currentPage + 1} of 2',
                    style: const TextStyle(
                        color: textSecondary, fontSize: 12),
                  ),
                ],
              ),
            ),

            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  // Page 1: Dietary
                  SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          "Your food\npreferences 🌿",
                          style: TextStyle(
                            color: textPrimary,
                            fontSize: 30,
                            fontWeight: FontWeight.w800,
                            height: 1.2,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "We'll filter products to match your needs.",
                          style: TextStyle(color: textSecondary, fontSize: 15),
                        ),
                        const SizedBox(height: 28),
                        ..._dietaryOptions.map((opt) {
                          final isSelected =
                              _selectedDietary.contains(opt['label']);
                          return GestureDetector(
                            onTap: () {
                              setState(() {
                                if (isSelected) {
                                  _selectedDietary.remove(opt['label']);
                                } else {
                                  _selectedDietary.add(opt['label']);
                                }
                              });
                            },
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 150),
                              margin: const EdgeInsets.only(bottom: 10),
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? primary.withOpacity(0.06)
                                    : const Color(0xFFFFFFFF),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: isSelected
                                      ? primary
                                      : const Color(0xFFE7E5E4),
                                  width: isSelected ? 1.5 : 1,
                                ),
                              ),
                              child: Row(
                                children: [
                                  Text(opt['icon'],
                                      style: const TextStyle(fontSize: 24)),
                                  const SizedBox(width: 14),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          opt['label'],
                                          style: TextStyle(
                                            color: isSelected
                                                ? primary
                                                : textPrimary,
                                            fontSize: 15,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                        Text(
                                          opt['desc'],
                                          style: const TextStyle(
                                            color: textSecondary,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  if (isSelected)
                                    Container(
                                      width: 24,
                                      height: 24,
                                      decoration: BoxDecoration(
                                        color: primary,
                                        shape: BoxShape.circle,
                                      ),
                                      child: const Icon(Icons.check,
                                          color: Colors.white, size: 14),
                                    ),
                                ],
                              ),
                            ),
                          );
                        }),
                      ],
                    ),
                  ),

                  // Page 2: Allergens
                  SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          "Any allergies\nwe should know? ⚠️",
                          style: TextStyle(
                            color: textPrimary,
                            fontSize: 30,
                            fontWeight: FontWeight.w800,
                            height: 1.2,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "We'll show warnings if a product contains these.",
                          style:
                              TextStyle(color: textSecondary, fontSize: 15),
                        ),
                        const SizedBox(height: 28),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: _allergenOptions.map((opt) {
                            final isSelected =
                                _selectedAllergens.contains(opt['label']);
                            return GestureDetector(
                              onTap: () {
                                setState(() {
                                  if (isSelected) {
                                    _selectedAllergens.remove(opt['label']);
                                  } else {
                                    _selectedAllergens.add(opt['label']);
                                  }
                                });
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 150),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 12),
                                decoration: BoxDecoration(
                                  color: isSelected
                                      ? const Color(0xFFDC2626).withOpacity(0.08)
                                      : const Color(0xFFFFFFFF),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: isSelected
                                        ? const Color(0xFFDC2626)
                                        : const Color(0xFFE7E5E4),
                                    width: isSelected ? 1.5 : 1,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(opt['icon'],
                                        style:
                                            const TextStyle(fontSize: 20)),
                                    const SizedBox(width: 8),
                                    Text(
                                      opt['label'],
                                      style: TextStyle(
                                        color: isSelected
                                            ? const Color(0xFFDC2626)
                                            : textPrimary,
                                        fontSize: 14,
                                        fontWeight: isSelected
                                            ? FontWeight.w700
                                            : FontWeight.w500,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 20),
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF9C3),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                                color: const Color(0xFFFDE047)),
                          ),
                          child: const Row(
                            children: [
                              Icon(Icons.info_outline,
                                  color: Color(0xFFCA8A04), size: 18),
                              SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'You can update these anytime in your profile settings.',
                                  style: TextStyle(
                                      color: Color(0xFF78350F),
                                      fontSize: 13),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            // Buttons
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
              child: Row(
                children: [
                  if (_currentPage > 0)
                    Expanded(
                      flex: 1,
                      child: SizedBox(
                        height: 52,
                        child: OutlinedButton(
                          onPressed: _prevPage,
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(
                                color: Color(0xFFE7E5E4)),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            foregroundColor: textPrimary,
                          ),
                          child: const Text('Back'),
                        ),
                      ),
                    ),
                  if (_currentPage > 0) const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: SizedBox(
                      height: 52,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _nextPage,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: primary,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: _isLoading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.5,
                                  valueColor: AlwaysStoppedAnimation<Color>(
                                      Colors.white),
                                ),
                              )
                            : Text(
                                _currentPage == 1
                                    ? 'Start Shopping! 🛍️'
                                    : 'Continue',
                                style: const TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w800),
                              ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // Skip button
            GestureDetector(
              onTap: _isLoading ? null : _completeOnboarding,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(
                  'Skip for now',
                  style: TextStyle(
                    color: textSecondary.withOpacity(0.6),
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
