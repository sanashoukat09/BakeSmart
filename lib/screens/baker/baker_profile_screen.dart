import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/constants/app_constants.dart';
import '../../providers/auth_provider.dart';
import '../../services/cloudinary_service.dart';
import '../../core/theme/baker_theme.dart';
import '../../widgets/baker/baker_bottom_nav.dart';
import '../../core/utils/validation_util.dart';


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
  bool _notificationsEnabled = true;
  bool _newOrderNotif = true;
  bool _lowStockNotif = true;
  bool _surplusNotif = true;

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
        backgroundColor: BakerTheme.background,
        body: Center(
            child: CircularProgressIndicator(color: BakerTheme.secondary)),
      );
    }

    _populateControllers(user);

    return Scaffold(
          backgroundColor: BakerTheme.background,
          bottomNavigationBar: const BakerBottomNav(currentIndex: 4),
          appBar: AppBar(
            backgroundColor: BakerTheme.background,
            elevation: 0,
            centerTitle: false,
            title: const Text('Profile',
                style: TextStyle(color: BakerTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.w700)),

            actions: [
              if (!_isEditing)
                TextButton(
                  onPressed: () => setState(() => _isEditing = true),
                  child: const Text('Edit',
                      style: TextStyle(color: BakerTheme.secondary, fontWeight: FontWeight.w600)),

                )
              else
                TextButton(
                  onPressed: _isSaving ? null : () => _saveProfile(user.uid),
                  child: _isSaving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Color(0xFFF59E0B)))
                      : const Text('Save',
                          style: TextStyle(
                              color: BakerTheme.secondary, fontWeight: FontWeight.w700)),

                ),
            ],
          ),
          body: Form(
            key: _formKey,
            autovalidateMode: AutovalidateMode.onUserInteraction,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                // Avatar section
                Center(
                  child: Column(
                    children: [
                      Container(
                        width: 90,
                        height: 90,
                        decoration: BoxDecoration(
                          color: BakerTheme.secondary.withOpacity(0.15),
                          shape: BoxShape.circle,
                          border: Border.all(
                              color: BakerTheme.secondary.withOpacity(0.4),
                              width: 2),
                        ),

                        child: user.photoUrl != null
                            ? ClipOval(
                                child:
                                    Image.network(user.photoUrl!, fit: BoxFit.cover))
                            : Center(
                                child: Text(
                                  (user.displayName ?? 'B')[0].toUpperCase(),
                                  style: const TextStyle(
                                    color: BakerTheme.secondary,
                                    fontWeight: FontWeight.w700,
                                    fontSize: 36,
                                  ),

                                ),
                              ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        user.displayName ?? '',
                        style: const TextStyle(
                          color: BakerTheme.textPrimary,
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),

                      ),
                      Text(
                        user.email,
                        style: const TextStyle(
                            color: BakerTheme.textSecondary, fontSize: 13),

                      ),
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: BakerTheme.secondary.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(20),
                        ),

                        child: const Text(
                          '🎂 Baker',
                          style: TextStyle(
                            color: BakerTheme.secondary,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
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
                    margin: const EdgeInsets.only(bottom: 20),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: BakerTheme.divider),
                    ),

                    child: Row(
                      children: [
                        const Icon(Icons.star_rounded,
                            color: BakerTheme.secondary, size: 28),

                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              user.rating.toStringAsFixed(1),
                              style: const TextStyle(
                                color: BakerTheme.textPrimary,
                                fontSize: 24,
                                fontWeight: FontWeight.w700,
                              ),
                            ),

                            Text(
                              '${user.totalReviews} reviews',
                              style: const TextStyle(
                                  color: BakerTheme.textSecondary, fontSize: 13),

                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                // Bakery Info section
                _SectionHeader(title: 'Bakery Information'),
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

                const SizedBox(height: 24),

                // Specialties
                _SectionHeader(title: 'Specialties'),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: user.specialties.map<Widget>((s) {
                    return Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: BakerTheme.secondary.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                            color: BakerTheme.secondary.withOpacity(0.3)),
                      ),

                      child: Text(
                        s,
                        style: const TextStyle(
                          color: BakerTheme.secondary,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),

                      ),
                    );
                  }).toList(),
                ),

                const SizedBox(height: 24),

                // Portfolio
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _SectionHeader(title: 'Portfolio'),
                    GestureDetector(
                      onTap: _isUploadingImage
                          ? null
                          : () => _pickAndUploadPortfolioImage(user.uid),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: BakerTheme.secondary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                              color: BakerTheme.secondary.withOpacity(0.3)),
                        ),

                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.add_photo_alternate_outlined,
                                color: BakerTheme.secondary, size: 16),

                            const SizedBox(width: 4),
                            const Text('Add Photo',
                                style: TextStyle(
                                    color: BakerTheme.secondary,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600)),

                          ],
                        ),
                      ),
                    ),
                  ],
                ),
                if (_isUploadingImage) ...[
                  const SizedBox(height: 8),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Uploading... ${(_uploadProgress * 100).toInt()}%',
                        style: const TextStyle(
                            color: Color(0xFF8B949E), fontSize: 12),
                      ),
                      const SizedBox(height: 4),
                      LinearProgressIndicator(
                        value: _uploadProgress,
                        color: BakerTheme.secondary,
                        backgroundColor: BakerTheme.divider,
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 12),
                if (user.portfolioImages.isEmpty)
                  Container(
                    height: 100,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                          color: BakerTheme.divider,
                          style: BorderStyle.solid),
                    ),

                    child: const Center(
                      child: Text('No portfolio images yet',
                          style: TextStyle(
                              color: Color(0xFF484F58), fontSize: 13)),
                    ),
                  )
                else
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 3,
                      crossAxisSpacing: 8,
                      mainAxisSpacing: 8,
                    ),
                    itemCount: user.portfolioImages.length,
                    itemBuilder: (context, i) {
                      return Stack(
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(10),
                            child: Image.network(
                              user.portfolioImages[i],
                              fit: BoxFit.cover,
                              width: double.infinity,
                              height: double.infinity,
                            ),
                          ),
                          Positioned(
                            top: 4,
                            right: 4,
                            child: GestureDetector(
                              onTap: () => ref
                                  .read(firestoreServiceProvider)
                                  .removePortfolioImage(
                                      user.uid, user.portfolioImages[i]),
                              child: Container(
                                width: 24,
                                height: 24,
                                decoration: const BoxDecoration(
                                  color: Color(0xFFEF4444),
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(Icons.close,
                                    color: Colors.white, size: 14),
                              ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),

                const SizedBox(height: 24),

                // Notification preferences
                _SectionHeader(title: 'Notification Preferences'),
                const SizedBox(height: 12),
                Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: BakerTheme.divider),
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

                const SizedBox(height: 24),

                // Sign out
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      await ref.read(authNotifierProvider.notifier).signOut();
                    },
                    icon: const Icon(Icons.logout, size: 18),
                    label: const Text('Sign Out'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFFEF4444),
                      side: const BorderSide(
                          color: Color(0xFFEF4444), width: 0.5),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
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
        color: BakerTheme.textPrimary,
        fontSize: 15,
        fontWeight: FontWeight.w700,
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
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: BakerTheme.divider),
        ),

        child: Row(
          children: [
            Icon(icon, color: BakerTheme.textSecondary, size: 18),
            const SizedBox(width: 10),

            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: const TextStyle(
                          color: BakerTheme.textSecondary, fontSize: 11)),

                  const SizedBox(height: 2),
                  Text(
                    controller.text.isEmpty ? '—' : controller.text,
                    style: TextStyle(
                      color: controller.text.isEmpty
                          ? BakerTheme.textMuted
                          : BakerTheme.textPrimary,
                      fontSize: 14,
                    ),

                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return TextFormField(
      controller: controller,
      maxLines: maxLines,
      keyboardType: keyboardType,
      validator: validator,
      inputFormatters: keyboardType == TextInputType.phone
          ? [FilteringTextInputFormatter.allow(RegExp(r'[0-9+]'))]
          : null,
      style: const TextStyle(color: BakerTheme.textPrimary, fontSize: 14),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 18),
        filled: true,
        fillColor: Colors.white,
        labelStyle: const TextStyle(color: BakerTheme.textSecondary),
        prefixIconColor: BakerTheme.textSecondary,
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
          borderSide: const BorderSide(color: BakerTheme.secondary, width: 1.5),
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
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        border: isLast
            ? null
            : const Border(
                bottom: BorderSide(color: BakerTheme.divider, width: 1)),

      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                      color: onChanged != null
                          ? BakerTheme.textPrimary
                          : BakerTheme.textMuted,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    )),

                Text(subtitle,
                    style: const TextStyle(
                        color: BakerTheme.textSecondary, fontSize: 12)),

              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: BakerTheme.secondary,
            activeTrackColor: BakerTheme.secondary.withOpacity(0.3),
            inactiveThumbColor: Colors.grey,
            inactiveTrackColor: BakerTheme.divider,
          ),

        ],
      ),
    );
  }
}
