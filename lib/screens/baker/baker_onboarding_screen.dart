import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_constants.dart';
import '../../core/router/app_router.dart';
import '../../providers/auth_provider.dart';
import '../../core/theme/baker_theme.dart';


class BakerOnboardingScreen extends ConsumerStatefulWidget {
  const BakerOnboardingScreen({super.key});

  @override
  ConsumerState<BakerOnboardingScreen> createState() =>
      _BakerOnboardingScreenState();
}

class _BakerOnboardingScreenState
    extends ConsumerState<BakerOnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;
  bool _isLoading = false;

  // Page 1 — Bakery Info
  final _bakeryNameController = TextEditingController();
  final _locationController = TextEditingController();
  final _phoneController = TextEditingController();
  final _contactEmailController = TextEditingController();

  // Page 2 — Specialties
  final List<String> _selectedSpecialties = [];

  // Page 3 — Bio
  final _bioController = TextEditingController();
  int _dailyCapacity = 10;

  @override
  void dispose() {
    _pageController.dispose();
    _bakeryNameController.dispose();
    _locationController.dispose();
    _phoneController.dispose();
    _contactEmailController.dispose();
    _bioController.dispose();
    super.dispose();
  }

  void _nextPage() {
    if (_currentPage < 2) {
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

  bool _canProceed() {
    if (_currentPage == 0) {
      return _bakeryNameController.text.isNotEmpty &&
          _locationController.text.isNotEmpty;
    }
    if (_currentPage == 1) {
      return _selectedSpecialties.isNotEmpty;
    }
    return true;
  }

  Future<void> _completeOnboarding() async {
    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('User profile not found. Please try again.')),
      );
      return;
    }

    setState(() => _isLoading = true);

    try {
      await ref.read(firestoreServiceProvider).completeOnboarding(user.uid, {
        'bakeryName': _bakeryNameController.text.trim(),
        'location': _locationController.text.trim(),
        'contactPhone': _phoneController.text.trim(),
        'contactEmail': _contactEmailController.text.trim().isNotEmpty
            ? _contactEmailController.text.trim()
            : user.email,
        'specialties': _selectedSpecialties,
        'bio': _bioController.text.trim(),
        'dailyOrderCapacity': _dailyCapacity,
      });

      if (mounted) {
        context.go(AppRoutes.bakerDashboard);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving profile: ${e.toString()}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BakerTheme.background,

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
                          color: BakerTheme.primary,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.bakery_dining_rounded,
                            color: Colors.white, size: 22),

                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'BakeSmart',
                        style: TextStyle(
                          color: BakerTheme.textPrimary,
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),

                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  // Step indicators
                  Row(
                    children: List.generate(3, (i) {
                      return Expanded(
                        child: Container(
                          height: 3,
                          margin: EdgeInsets.only(right: i < 2 ? 6 : 0),
                          decoration: BoxDecoration(
                            color: i <= _currentPage
                                ? BakerTheme.secondary
                                : BakerTheme.divider,

                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Step ${_currentPage + 1} of 3',
                    style: const TextStyle(
                        color: BakerTheme.textSecondary, fontSize: 12),

                  ),
                ],
              ),
            ),

            // Pages
            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _Page1(
                    bakeryNameController: _bakeryNameController,
                    locationController: _locationController,
                    phoneController: _phoneController,
                    emailController: _contactEmailController,
                    onChanged: () => setState(() {}),
                  ),
                  _Page2(
                    selectedSpecialties: _selectedSpecialties,
                    onToggle: (s) {
                      setState(() {
                        if (_selectedSpecialties.contains(s)) {
                          _selectedSpecialties.remove(s);
                        } else {
                          _selectedSpecialties.add(s);
                        }
                      });
                    },
                  ),
                  _Page3(
                    bioController: _bioController,
                    dailyCapacity: _dailyCapacity,
                    onCapacityChanged: (v) =>
                        setState(() => _dailyCapacity = v),
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
                            side: const BorderSide(color: BakerTheme.divider),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            foregroundColor: BakerTheme.textPrimary,

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
                        onPressed:
                            (_canProceed() && !_isLoading) ? _nextPage : null,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: BakerTheme.primary,
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: BakerTheme.divider,
                          disabledForegroundColor: BakerTheme.textMuted,

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
                                _currentPage == 2
                                    ? 'Launch Dashboard 🚀'
                                    : 'Continue',
                                style: const TextStyle(
                                    fontSize: 15, fontWeight: FontWeight.w700),
                              ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Page 1: Bakery Info ──────────────────────────────────────
class _Page1 extends StatelessWidget {
  final TextEditingController bakeryNameController;
  final TextEditingController locationController;
  final TextEditingController phoneController;
  final TextEditingController emailController;
  final VoidCallback onChanged;

  const _Page1({
    required this.bakeryNameController,
    required this.locationController,
    required this.phoneController,
    required this.emailController,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            "Set up your\nbakery 🏪",
            style: TextStyle(
              color: BakerTheme.textPrimary,
              fontSize: 30,
              fontWeight: FontWeight.w700,
              height: 1.2,
            ),

          ),
          const SizedBox(height: 8),
          const Text(
            'This is how your clients will find your bakery.',
            style: TextStyle(color: BakerTheme.textSecondary, fontSize: 15),

          ),
          const SizedBox(height: 32),
          _OnboardingField(
            controller: bakeryNameController,
            label: 'Bakery name *',
            hint: "e.g. Zara's Sweet Kitchen",
            icon: Icons.store_rounded,
            onChanged: (_) => onChanged(),
          ),
          const SizedBox(height: 16),
          _OnboardingField(
            controller: locationController,
            label: 'Location / City *',
            hint: 'e.g. Lahore, DHA Phase 5',
            icon: Icons.location_on_outlined,
            onChanged: (_) => onChanged(),
          ),
          const SizedBox(height: 16),
          _OnboardingField(
            controller: phoneController,
            label: 'Phone number',
            hint: '+92 300 0000000',
            icon: Icons.phone_outlined,
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 16),
          _OnboardingField(
            controller: emailController,
            label: 'Contact email (optional)',
            hint: 'orders@yourbakery.com',
            icon: Icons.email_outlined,
            keyboardType: TextInputType.emailAddress,
          ),
        ],
      ),
    );
  }
}

// ─── Page 2: Specialties ──────────────────────────────────────
class _Page2 extends StatelessWidget {
  final List<String> selectedSpecialties;
  final void Function(String) onToggle;

  const _Page2({
    required this.selectedSpecialties,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            "What do you\nspecialize in? ✨",
            style: TextStyle(
              color: BakerTheme.textPrimary,
              fontSize: 30,
              fontWeight: FontWeight.w700,
              height: 1.2,
            ),

          ),
          const SizedBox(height: 8),
          const Text(
            'Pick all that apply. This shows on your storefront.',
            style: TextStyle(color: BakerTheme.textSecondary, fontSize: 15),

          ),
          const SizedBox(height: 32),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: AppConstants.bakerSpecialties.map((s) {
              final isSelected = selectedSpecialties.contains(s);
              return GestureDetector(
                onTap: () => onToggle(s),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 10),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? BakerTheme.secondary.withOpacity(0.15)
                        : Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isSelected
                          ? BakerTheme.secondary
                          : BakerTheme.divider,
                      width: 1.5,
                    ),

                  ),
                  child: Text(
                    s,
                    style: TextStyle(
                      color: isSelected
                          ? BakerTheme.secondary
                          : BakerTheme.textSecondary,
                      fontSize: 14,
                      fontWeight: isSelected
                          ? FontWeight.w600
                          : FontWeight.w400,

                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

// ─── Page 3: Bio & Capacity ───────────────────────────────────
class _Page3 extends StatelessWidget {
  final TextEditingController bioController;
  final int dailyCapacity;
  final void Function(int) onCapacityChanged;

  const _Page3({
    required this.bioController,
    required this.dailyCapacity,
    required this.onCapacityChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            "Almost done! 🎉",
            style: TextStyle(
              color: BakerTheme.textPrimary,
              fontSize: 30,
              fontWeight: FontWeight.w700,
            ),

          ),
          const SizedBox(height: 8),
          const Text(
            'Tell your clients about your story.',
            style: TextStyle(color: BakerTheme.textSecondary, fontSize: 15),

          ),
          const SizedBox(height: 32),
          TextFormField(
            controller: bioController,
            maxLines: 4,
              style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 15),
              decoration: InputDecoration(
                labelText: 'Bakery bio (optional)',
                hintText:
                    'Tell your clients what makes your bakes special, your story, signature items...',
                alignLabelWithHint: true,
                filled: true,
                fillColor: Colors.white,
                labelStyle: const TextStyle(color: BakerTheme.textSecondary),
                hintStyle: const TextStyle(
                    color: BakerTheme.textMuted, fontSize: 13),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: BakerTheme.divider),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: BakerTheme.divider),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(
                      color: BakerTheme.primary, width: 1.5),
                ),
              ),

          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: BakerTheme.divider),
            ),

            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.calendar_today_outlined,
                        color: Color(0xFFF59E0B), size: 18),
                    SizedBox(width: 8),
                    Text(
                      'Daily order capacity',
                      style: TextStyle(
                        color: BakerTheme.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),

                    ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text(
                  'Max orders you can handle per day',
                  style:
                      const TextStyle(color: BakerTheme.textSecondary, fontSize: 13),

                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    IconButton(
                      onPressed: dailyCapacity > 1
                          ? () => onCapacityChanged(dailyCapacity - 1)
                          : null,
                      icon: const Icon(Icons.remove_circle_outline),
                      color: BakerTheme.secondary,

                      iconSize: 28,
                    ),
                    Expanded(
                      child: Center(
                        child: Text(
                          '$dailyCapacity',
                          style: const TextStyle(
                            color: BakerTheme.textPrimary,
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                          ),

                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () => onCapacityChanged(dailyCapacity + 1),
                      icon: const Icon(Icons.add_circle_outline),
                      color: BakerTheme.secondary,

                      iconSize: 28,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Shared Field Widget ──────────────────────────────────────
class _OnboardingField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final IconData icon;
  final TextInputType? keyboardType;
  final void Function(String)? onChanged;

  const _OnboardingField({
    required this.controller,
    required this.label,
    required this.hint,
    required this.icon,
    this.keyboardType,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      onChanged: onChanged,
      style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 15),

      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, size: 20),
        filled: true,
        fillColor: Colors.white,
        labelStyle: const TextStyle(color: BakerTheme.textSecondary),
        hintStyle: const TextStyle(color: BakerTheme.textMuted),
        prefixIconColor: const Color(0xFF8B949E),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: BakerTheme.divider),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: BakerTheme.divider),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: BakerTheme.primary, width: 1.5),
        ),

      ),
    );
  }
}
