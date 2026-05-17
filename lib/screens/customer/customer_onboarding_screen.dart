import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/router/app_router.dart';
import '../../providers/auth_provider.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const surface   = Color(0xFFFFFFFF);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  static const statusPink = Color(0xFFFF6B81);
  static const statusRed   = Color(0xFFE74C3C);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

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
    return Scaffold(
      backgroundColor: _T.canvas,
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
                          color: _T.brown,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(Icons.bakery_dining_rounded,
                            color: Colors.white, size: 22),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'BakeSmart',
                        style: TextStyle(
                          color: _T.ink,
                          fontSize: 20,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  Row(
                    children: List.generate(2, (i) {
                      return Expanded(
                        child: Container(
                          height: 5,
                          margin: EdgeInsets.only(right: i < 1 ? 8 : 0),
                          decoration: BoxDecoration(
                            color: i <= _currentPage
                                ? _T.brown
                                : _T.rimLight,
                            borderRadius: BorderRadius.circular(3),
                          ),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Step ${_currentPage + 1} of 2',
                    style: const TextStyle(
                        color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
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
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          "Your food\npreferences 🌿",
                          style: TextStyle(
                            color: _T.ink,
                            fontSize: 28,
                            fontWeight: FontWeight.w800,
                            height: 1.25,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "We'll filter products to match your needs.",
                          style: TextStyle(color: _T.inkMid, fontSize: 14.5, fontWeight: FontWeight.w600),
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
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? const Color(0xFFFFECE0)
                                    : _T.surface,
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: isSelected
                                      ? _T.brown
                                      : _T.rimLight,
                                  width: 1.5,
                                ),
                                boxShadow: isSelected ? _T.shadowSm : null,
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
                                            color: _T.ink,
                                            fontSize: 15,
                                            fontWeight: FontWeight.w800,
                                          ),
                                        ),
                                        const SizedBox(height: 2),
                                        Text(
                                          opt['desc'],
                                          style: const TextStyle(
                                            color: _T.inkMid,
                                            fontSize: 12,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  if (isSelected)
                                    Container(
                                      width: 24,
                                      height: 24,
                                      decoration: const BoxDecoration(
                                        color: _T.brown,
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
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          "Any allergies\nwe should know? ⚠️",
                          style: TextStyle(
                            color: _T.ink,
                            fontSize: 28,
                            fontWeight: FontWeight.w800,
                            height: 1.25,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "We'll show warnings if a product contains these.",
                          style:
                              TextStyle(color: _T.inkMid, fontSize: 14.5, fontWeight: FontWeight.w600),
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
                                      ? _T.statusPink.withOpacity(0.08)
                                      : _T.surface,
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(
                                    color: isSelected
                                        ? _T.statusPink
                                        : _T.rimLight,
                                    width: 1.5,
                                  ),
                                  boxShadow: isSelected ? _T.shadowSm : null,
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
                                            ? _T.statusPink
                                            : _T.ink,
                                        fontSize: 14.5,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 28),
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFFECE0), // Soft cream
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: _T.rimLight, width: 1.5),
                          ),
                          child: const Row(
                            children: [
                              Icon(Icons.info_outline_rounded,
                                  color: _T.brown, size: 20),
                              SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  'You can update these anytime in your profile settings.',
                                  style: TextStyle(
                                      color: _T.ink,
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600),
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
                        height: 54,
                        child: OutlinedButton(
                          onPressed: _prevPage,
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(
                                color: _T.rimLight, width: 1.5),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            foregroundColor: _T.ink,
                          ),
                          child: const Text('Back', style: TextStyle(fontWeight: FontWeight.w800)),
                        ),
                      ),
                    ),
                  if (_currentPage > 0) const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: SizedBox(
                      height: 54,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _nextPage,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _T.brown,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          elevation: 0,
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
                padding: const EdgeInsets.only(bottom: 24),
                child: Text(
                  'Skip for now',
                  style: TextStyle(
                    color: _T.inkMid.withOpacity(0.7),
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    decoration: TextDecoration.underline,
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
