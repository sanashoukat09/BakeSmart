import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/constants/app_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/cloudinary_service.dart';
import '../../widgets/baker/baker_bottom_nav.dart';
import '../../core/utils/validation_util.dart';

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

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class BakerProfileScreen extends ConsumerStatefulWidget {
  const BakerProfileScreen({super.key});

  @override
  ConsumerState<BakerProfileScreen> createState() => _BakerProfileScreenState();
}

class _BakerProfileScreenState extends ConsumerState<BakerProfileScreen> {
  final _bakeryNameController = TextEditingController();
  final _locationController = TextEditingController();
  final _bioController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _isEditing = false;
  bool _isSaving = false;
  final _formKey = GlobalKey<FormState>();
  
  bool _isUploadingImage = false;
  double _uploadProgress = 0;
  bool _isUploadingProfilePhoto = false;

  bool _notificationsEnabled = true;
  bool _newOrderNotif = true;
  bool _lowStockNotif = true;
  bool _surplusNotif = true;

  final List<String> _selectedSpecialties = [];

  @override
  void dispose() {
    _bakeryNameController.dispose();
    _locationController.dispose();
    _bioController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _populateControllers(dynamic user) {
    if (!_isEditing) {
      _bakeryNameController.text = user.bakeryName ?? '';
      _locationController.text = user.location ?? '';
      _bioController.text = user.bio ?? '';
      _phoneController.text = user.contactPhone ?? '';
      _notificationsEnabled = user.notificationsEnabled;
      _newOrderNotif = user.newOrderNotif;
      _lowStockNotif = user.lowStockNotif;
      _surplusNotif = user.surplusNotif;

      _selectedSpecialties.clear();
      _selectedSpecialties.addAll(List<String>.from(user.specialties));
    }
  }

  Future<void> _saveProfile(String uid) async {
    if (!_formKey.currentState!.validate()) return;
    
    setState(() => _isSaving = true);
    await ref.read(firestoreServiceProvider).updateUser(uid, {
      'bakeryName': _bakeryNameController.text.trim(),
      'location': _locationController.text.trim(),
      'bio': _bioController.text.trim(),
      'contactPhone': _phoneController.text.trim(),
      'specialties': _selectedSpecialties,
    });
    if (mounted) {
      setState(() {
        _isSaving = false;
        _isEditing = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile saved ✓')),
      );
    }
  }

  Future<void> _pickAndUploadProfilePhoto(String uid) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
        source: ImageSource.gallery, imageQuality: 70);
    if (picked == null) return;

    setState(() {
      _isUploadingProfilePhoto = true;
    });

    try {
      final url = await CloudinaryService().uploadImage(
        imageFile: File(picked.path),
        folder: 'bakesmart/profile/$uid',
      );
      await ref.read(firestoreServiceProvider).updateUser(uid, {
        'photoUrl': url,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile picture updated!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUploadingProfilePhoto = false;
        });
      }
    }
  }

  Future<void> _pickAndUploadPortfolioImage(String uid) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
        source: ImageSource.gallery, imageQuality: 80);
    if (picked == null) return;

    setState(() {
      _isUploadingImage = true;
      _uploadProgress = 0;
    });

    try {
      final url = await CloudinaryService().uploadImage(
        imageFile: File(picked.path),
        folder: 'bakesmart/portfolio/$uid',
        onProgress: (p) => setState(() => _uploadProgress = p),
      );
      await ref.read(firestoreServiceProvider).addPortfolioImage(uid, url);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Portfolio image added!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUploadingImage = false;
          _uploadProgress = 0;
        });
      }
    }
  }

  Future<void> _saveNotifPrefs(String uid) async {
    await ref.read(firestoreServiceProvider).updateNotificationPrefs(uid,
        enabled: _notificationsEnabled,
        newOrder: _newOrderNotif,
        lowStock: _lowStockNotif,
        surplus: _surplusNotif);
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Preferences saved')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final userAsync = ref.watch(currentUserProvider);
    final user = userAsync.valueOrNull;

    if (user == null) {
      return const Scaffold(
        backgroundColor: _T.canvas,
        body: Center(
          child: CircularProgressIndicator(color: _T.copper),
        ),
      );
    }

    _populateControllers(user);

    return Scaffold(
      backgroundColor: _T.canvas,
      bottomNavigationBar: const BakerBottomNav(currentIndex: 4),
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: false,
        title: const Text(
          'Profile',
          style: TextStyle(color: _T.brown, fontSize: 18, fontWeight: FontWeight.w800),
        ),
        actions: [
          if (!_isEditing)
            TextButton(
              onPressed: () => setState(() => _isEditing = true),
              child: const Text(
                'Edit',
                style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 14),
              ),
            )
          else ...[
            TextButton(
              onPressed: () => setState(() {
                _isEditing = false;
                _populateControllers(user);
              }),
              child: const Text(
                'Cancel',
                style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600, fontSize: 14),
              ),
            ),
            TextButton(
              onPressed: _isSaving ? null : () => _saveProfile(user.uid),
              child: _isSaving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: _T.copper,
                      ),
                    )
                  : const Text(
                      'Save',
                      style: TextStyle(color: _T.statusCopper, fontWeight: FontWeight.w800, fontSize: 14),
                    ),
            ),
          ],
        ],
      ),
      body: Form(
        key: _formKey,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 40),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Avatar section
              Center(
                child: Column(
                  children: [
                    GestureDetector(
                      onTap: _isEditing && !_isUploadingProfilePhoto
                          ? () => _pickAndUploadProfilePhoto(user.uid)
                          : null,
                      child: Stack(
                        children: [
                          Container(
                            width: 90,
                            height: 90,
                            decoration: BoxDecoration(
                              color: _T.surfaceWarm,
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: _T.rimLight,
                                width: 2,
                              ),
                              boxShadow: _T.shadowSm,
                            ),
                            child: _isUploadingProfilePhoto
                                ? const Center(child: CircularProgressIndicator(color: _T.copper))
                                : user.photoUrl != null
                                    ? ClipOval(
                                        child: Image.network(user.photoUrl!, fit: BoxFit.cover),
                                      )
                                    : Center(
                                        child: Text(
                                          (user.displayName ?? 'B')[0].toUpperCase(),
                                          style: const TextStyle(
                                            color: _T.brown,
                                            fontWeight: FontWeight.w800,
                                            fontSize: 32,
                                          ),
                                        ),
                                      ),
                          ),
                          if (_isEditing)
                            Positioned(
                              bottom: 0,
                              right: 0,
                              child: Container(
                                padding: const EdgeInsets.all(6),
                                decoration: const BoxDecoration(
                                  color: _T.brown,
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(
                                  Icons.camera_alt,
                                  color: Colors.white,
                                  size: 16,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      user.displayName ?? '',
                      style: const TextStyle(
                        color: _T.ink,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      user.email,
                      style: const TextStyle(
                        color: _T.inkMid, 
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: _T.pinkL,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: _T.pink.withOpacity(0.3), width: 1),
                      ),
                      child: const Text(
                        '🎂 Baker Partner',
                        style: TextStyle(
                          color: _T.statusPink,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),

              // Rating card
              if (user.totalReviews > 0)
                Container(
                  margin: const EdgeInsets.only(bottom: 24),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _T.surface,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: _T.rimLight, width: 1.5),
                    boxShadow: _T.shadowSm,
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.star_rounded, color: _T.statusCopper, size: 32),
                      const SizedBox(width: 14),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            user.rating.toStringAsFixed(1),
                            style: const TextStyle(
                              color: _T.ink,
                              fontSize: 22,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          Text(
                            'Based on ${user.totalReviews} reviews',
                            style: const TextStyle(
                              color: _T.inkMid, 
                              fontSize: 12.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

              // Bakery Info section
              const _SectionHeader(title: 'Bakery Information'),
              const SizedBox(height: 12),
              _ProfileField(
                label: 'Bakery Name',
                controller: _bakeryNameController,
                isEditing: _isEditing,
                icon: Icons.store_rounded,
              ),
              const SizedBox(height: 12),
              _ProfileField(
                label: 'Location',
                controller: _locationController,
                isEditing: _isEditing,
                icon: Icons.location_on_outlined,
              ),
              const SizedBox(height: 12),
              _ProfileField(
                label: 'Phone',
                controller: _phoneController,
                isEditing: _isEditing,
                icon: Icons.phone_outlined,
                keyboardType: TextInputType.phone,
                validator: ValidationUtil.validatePhoneNumber,
              ),
              const SizedBox(height: 12),
              _ProfileField(
                label: 'Bio',
                controller: _bioController,
                isEditing: _isEditing,
                icon: Icons.info_outline,
                maxLines: 3,
              ),

              const SizedBox(height: 28),

              // Specialties
              const _SectionHeader(title: 'Specialties'),
              const SizedBox(height: 12),
              if (!_isEditing)
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: user.specialties.map<Widget>((s) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: _T.pinkL,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: _T.pink.withOpacity(0.3), width: 1),
                      ),
                      child: Text(
                        s,
                        style: const TextStyle(
                          color: _T.statusPink,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    );
                  }).toList(),
                )
              else
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: AppConstants.bakerSpecialties.map((s) {
                    final isSelected = _selectedSpecialties.contains(s);
                    return GestureDetector(
                      onTap: () {
                        setState(() {
                          if (isSelected) {
                            _selectedSpecialties.remove(s);
                          } else {
                            _selectedSpecialties.add(s);
                          }
                        });
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: isSelected ? _T.pinkL : _T.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isSelected ? _T.pink : _T.rimLight,
                            width: 1.5,
                          ),
                          boxShadow: isSelected ? [] : _T.shadowSm,
                        ),
                        child: Text(
                          s,
                          style: TextStyle(
                            color: isSelected ? _T.statusPink : _T.inkMid,
                            fontSize: 12,
                            fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),

              const SizedBox(height: 28),

              // Portfolio
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const _SectionHeader(title: 'Portfolio'),
                  GestureDetector(
                    onTap: _isUploadingImage
                        ? null
                        : () => _pickAndUploadPortfolioImage(user.uid),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: _T.surface,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: _T.rimLight, width: 1.5),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.add_photo_alternate_outlined, color: _T.brown, size: 16),
                          SizedBox(width: 6),
                          Text(
                            'Add Photo',
                            style: TextStyle(
                              color: _T.brown,
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              if (_isUploadingImage) ...[
                const SizedBox(height: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Uploading... ${(_uploadProgress * 100).toInt()}%',
                      style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 6),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: _uploadProgress,
                        color: _T.brown,
                        backgroundColor: _T.rimLight,
                        minHeight: 6,
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 12),
              if (user.portfolioImages.isEmpty)
                Container(
                  height: 100,
                  decoration: BoxDecoration(
                    color: _T.surfaceWarm,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: _T.rimLight, width: 1.5),
                  ),
                  child: const Center(
                    child: Text(
                      'No portfolio images yet',
                      style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ),
                )
              else
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                  ),
                  itemCount: user.portfolioImages.length,
                  itemBuilder: (context, i) {
                    return Stack(
                      children: [
                        Positioned.fill(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: Image.network(
                              user.portfolioImages[i],
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                        Positioned(
                          top: 4,
                          right: 4,
                          child: GestureDetector(
                            onTap: () => ref
                                .read(firestoreServiceProvider)
                                .removePortfolioImage(user.uid, user.portfolioImages[i]),
                            child: Container(
                              width: 24,
                              height: 24,
                              decoration: const BoxDecoration(
                                color: _T.statusPink,
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.close, color: Colors.white, size: 14),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),

              const SizedBox(height: 28),

              // Notification preferences
              const _SectionHeader(title: 'Notification Preferences'),
              const SizedBox(height: 12),
              Container(
                decoration: BoxDecoration(
                  color: _T.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Column(
                  children: [
                    _NotifToggle(
                      title: 'All Notifications',
                      subtitle: 'Master toggle',
                      value: _notificationsEnabled,
                      onChanged: (v) {
                        setState(() => _notificationsEnabled = v);
                        _saveNotifPrefs(user.uid);
                      },
                      isFirst: true,
                      isLast: false,
                    ),
                    _NotifToggle(
                      title: 'New Orders',
                      subtitle: 'When a customer places an order',
                      value: _newOrderNotif && _notificationsEnabled,
                      onChanged: _notificationsEnabled
                          ? (v) {
                              setState(() => _newOrderNotif = v);
                              _saveNotifPrefs(user.uid);
                            }
                          : null,
                      isFirst: false,
                      isLast: false,
                    ),
                    _NotifToggle(
                      title: 'Low Stock Alerts',
                      subtitle: 'When ingredients run low',
                      value: _lowStockNotif && _notificationsEnabled,
                      onChanged: _notificationsEnabled
                          ? (v) {
                              setState(() => _lowStockNotif = v);
                              _saveNotifPrefs(user.uid);
                            }
                          : null,
                      isFirst: false,
                      isLast: false,
                    ),
                    _NotifToggle(
                      title: 'Surplus Deals',
                      subtitle: 'When surplus items are posted',
                      value: _surplusNotif && _notificationsEnabled,
                      onChanged: _notificationsEnabled
                          ? (v) {
                              setState(() => _surplusNotif = v);
                              _saveNotifPrefs(user.uid);
                            }
                          : null,
                      isFirst: false,
                      isLast: true,
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              // Sign out
              SizedBox(
                width: double.infinity,
                height: 52,
                child: OutlinedButton.icon(
                  onPressed: () async {
                    await ref.read(authNotifierProvider.notifier).signOut();
                  },
                  icon: const Icon(Icons.logout, size: 18),
                  label: const Text('Sign Out', style: TextStyle(fontWeight: FontWeight.w800)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _T.statusPink,
                    side: const BorderSide(color: _T.statusPink, width: 1.5),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
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

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: _T.ink,
        fontSize: 15,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

class _ProfileField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final bool isEditing;
  final IconData icon;
  final int maxLines;
  final TextInputType? keyboardType;
  final String? Function(String?)? validator;

  const _ProfileField({
    required this.label,
    required this.controller,
    required this.isEditing,
    required this.icon,
    this.maxLines = 1,
    this.keyboardType,
    this.validator,
  });

  @override
  Widget build(BuildContext context) {
    if (!isEditing) {
      return Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _T.rimLight, width: 1.5),
        ),
        child: Row(
          children: [
            Icon(icon, color: _T.brown, size: 18),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(color: _T.inkMid, fontSize: 11, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    controller.text.isEmpty ? '—' : controller.text,
                    style: TextStyle(
                      color: controller.text.isEmpty ? _T.inkFaint : _T.ink,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        maxLines: maxLines,
        keyboardType: keyboardType,
        validator: validator,
        inputFormatters: keyboardType == TextInputType.phone
            ? [FilteringTextInputFormatter.allow(RegExp(r'[0-9+]'))]
            : null,
        style: const TextStyle(color: _T.ink, fontSize: 14, fontWeight: FontWeight.w700),
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon, size: 18),
          filled: true,
          fillColor: _T.surface,
          labelStyle: const TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600),
          prefixIconColor: _T.inkMid,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: _T.rimLight),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: _T.rimLight),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: _T.brown, width: 1.5),
          ),
        ),
      ),
    );
  }
}

class _NotifToggle extends StatelessWidget {
  final String title;
  final String subtitle;
  final bool value;
  final void Function(bool)? onChanged;
  final bool isFirst;
  final bool isLast;

  const _NotifToggle({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
    required this.isFirst,
    required this.isLast,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        border: isLast
            ? null
            : const Border(bottom: BorderSide(color: _T.rimLight, width: 1.5)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: onChanged != null ? _T.ink : _T.inkFaint,
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: _T.statusCopper,
            activeTrackColor: _T.statusCopper.withOpacity(0.3),
            inactiveThumbColor: Colors.grey,
            inactiveTrackColor: _T.rimLight,
          ),
        ],
      ),
    );
  }
}
