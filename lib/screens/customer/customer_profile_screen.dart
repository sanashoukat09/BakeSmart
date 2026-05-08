import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/validation_util.dart';

class CustomerProfileScreen extends ConsumerStatefulWidget {
  const CustomerProfileScreen({super.key});

  @override
  ConsumerState<CustomerProfileScreen> createState() =>
      _CustomerProfileScreenState();
}

class _CustomerProfileScreenState
    extends ConsumerState<CustomerProfileScreen> {
  final _nameController = TextEditingController();
  bool _isEditing = false;
  bool _isSaving = false;

  static const List<Map<String, dynamic>> _dietaryOptions = [
    {'label': 'Eggless', 'icon': '🥚'},
    {'label': 'Sugar-Free', 'icon': '🍬'},
    {'label': 'Gluten-Free', 'icon': '🌾'},
    {'label': 'Nut-Free', 'icon': '🥜'},
    {'label': 'Vegan', 'icon': '🌱'},
    {'label': 'Halal', 'icon': '✅'},
  ];

  static const List<Map<String, dynamic>> _allergenOptions = [
    {'label': 'Nuts', 'icon': '🥜'},
    {'label': 'Dairy', 'icon': '🥛'},
    {'label': 'Eggs', 'icon': '🥚'},
    {'label': 'Gluten', 'icon': '🌾'},
    {'label': 'Soy', 'icon': '🫘'},
    {'label': 'Seeds', 'icon': '🌻'},
  ];

  List<String> _selectedDietary = [];
  List<String> _selectedAllergens = [];
  bool _prefsSectionExpanded = false;
  bool _addressesSectionExpanded = false;
  bool _notificationsSectionExpanded = false;

  final _addressNameController = TextEditingController();
  final _addressDetailController = TextEditingController();
  final _phoneController = TextEditingController();

  @override
  void dispose() {
    _nameController.dispose();
    _addressNameController.dispose();
    _addressDetailController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _populate(dynamic user) {
    if (!_isEditing) {
      _nameController.text = user.displayName ?? '';
      _selectedDietary = List<String>.from(user.dietaryPreferences);
      _selectedAllergens = List<String>.from(user.allergens);
    }
  }

  Future<void> _addAddress(String uid, List<Map<String, dynamic>> currentAddresses) async {
    if (_addressNameController.text.isEmpty || _addressDetailController.text.isEmpty) return;

    final newAddress = {
      'id': DateTime.now().millisecondsSinceEpoch.toString(),
      'name': _addressNameController.text.trim(),
      'details': _addressDetailController.text.trim(),
      'phone': _phoneController.text.trim(),
      'isDefault': currentAddresses.isEmpty,
    };

    final updatedAddresses = [...currentAddresses, newAddress];
    
    await ref.read(firestoreServiceProvider).updateUser(uid, {
      'savedAddresses': updatedAddresses,
    });

    _addressNameController.clear();
    _addressDetailController.clear();
    _phoneController.clear();
    
    if (mounted) Navigator.pop(context);
  }

  Future<void> _deleteAddress(String uid, List<Map<String, dynamic>> currentAddresses, String addressId) async {
    final updatedAddresses = currentAddresses.where((a) => a['id'] != addressId).toList();
    await ref.read(firestoreServiceProvider).updateUser(uid, {
      'savedAddresses': updatedAddresses,
    });
  }

  Future<void> _updateNotifPref(String uid, String field, bool value) async {
    await ref.read(firestoreServiceProvider).updateUser(uid, {
      field: value,
    });
  }

  Future<void> _saveProfile(String uid) async {
    setState(() => _isSaving = true);
    await ref.read(firestoreServiceProvider).updateUser(uid, {
      'displayName': _nameController.text.trim(),
      'dietaryPreferences': _selectedDietary,
      'allergens': _selectedAllergens,
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

  @override
  Widget build(BuildContext context) {
    const primary = Color(0xFFC2410C);
    const bg = Color(0xFFFFFBF5);
    const textPrimary = Color(0xFF1C1917);
    const textSecondary = Color(0xFF57534E);
    const borderColor = Color(0xFFE7E5E4);

    final userAsync = ref.watch(currentUserProvider);
    final user = userAsync.valueOrNull;

    if (user == null) {
      return const Scaffold(
        backgroundColor: bg,
        body: Center(child: CircularProgressIndicator(color: primary)),
      );
    }

    _populate(user);

    return Scaffold(
          backgroundColor: bg,
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: const Text(
              'My Profile',
              style: TextStyle(
                  color: textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800),
            ),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back, color: textPrimary),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              if (!_isEditing)
                TextButton(
                  onPressed: () => setState(() => _isEditing = true),
                  child: const Text('Edit',
                      style: TextStyle(
                          color: primary, fontWeight: FontWeight.w700)),
                )
              else
                TextButton(
                  onPressed: _isSaving ? null : () => _saveProfile(user.uid),
                  child: _isSaving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: primary))
                      : const Text('Save',
                          style: TextStyle(
                              color: primary, fontWeight: FontWeight.w700)),
                ),
            ],
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Avatar
                Center(
                  child: Column(
                    children: [
                      Stack(
                        children: [
                          Container(
                            width: 88,
                            height: 88,
                            decoration: BoxDecoration(
                              color: primary.withOpacity(0.1),
                              shape: BoxShape.circle,
                              border: Border.all(
                                  color: primary.withOpacity(0.3), width: 2),
                            ),
                            child: user.photoUrl != null
                                ? ClipOval(
                                    child: Image.network(user.photoUrl!,
                                        fit: BoxFit.cover))
                                : Center(
                                    child: Text(
                                      (user.displayName ?? 'C')[0]
                                          .toUpperCase(),
                                      style: const TextStyle(
                                        color: primary,
                                        fontWeight: FontWeight.w800,
                                        fontSize: 34,
                                      ),
                                    ),
                                  ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        user.displayName ?? '',
                        style: const TextStyle(
                          color: textPrimary,
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(user.email,
                          style: const TextStyle(
                              color: textSecondary, fontSize: 13)),
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFD97706).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: const Text(
                          '🛍️ Customer',
                          style: TextStyle(
                            color: Color(0xFFD97706),
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),

                // Name field
                _sectionTitle('Personal Info'),
                const SizedBox(height: 12),
                if (_isEditing)
                  TextFormField(
                    controller: _nameController,
                    style: const TextStyle(color: textPrimary, fontSize: 15),
                    decoration: InputDecoration(
                      labelText: 'Display name',
                      prefixIcon:
                          const Icon(Icons.person_outline, size: 20),
                      filled: true,
                      fillColor: Colors.white,
                      labelStyle: const TextStyle(color: textSecondary),
                      prefixIconColor: textSecondary,
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide:
                              const BorderSide(color: borderColor)),
                      enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide:
                              const BorderSide(color: borderColor)),
                      focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(
                              color: primary, width: 1.5)),
                    ),
                  )
                else
                  _infoTile(
                    icon: Icons.person_outline,
                    label: 'Name',
                    value: user.displayName ?? '—',
                  ),

                const SizedBox(height: 12),
                _infoTile(
                  icon: Icons.email_outlined,
                  label: 'Email',
                  value: user.email,
                ),

                const SizedBox(height: 24),

                // Dietary Preferences
                GestureDetector(
                  onTap: () => setState(
                      () => _prefsSectionExpanded = !_prefsSectionExpanded),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: borderColor),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.restaurant_menu_outlined,
                            color: primary, size: 20),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Dietary Preferences & Allergens',
                                style: TextStyle(
                                  color: textPrimary,
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              if (user.dietaryPreferences.isNotEmpty ||
                                  user.allergens.isNotEmpty)
                                Text(
                                  '${user.dietaryPreferences.length} preferences · ${user.allergens.length} allergens',
                                  style: const TextStyle(
                                      color: textSecondary, fontSize: 12),
                                ),
                            ],
                          ),
                        ),
                        Icon(
                          _prefsSectionExpanded
                              ? Icons.expand_less
                              : Icons.expand_more,
                          color: textSecondary,
                        ),
                      ],
                    ),
                  ),
                ),
                if (_prefsSectionExpanded) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: borderColor),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Dietary Preferences',
                          style: TextStyle(
                              color: textPrimary,
                              fontSize: 13,
                              fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _dietaryOptions.map((opt) {
                            final sel = _selectedDietary
                                .contains(opt['label']);
                            return GestureDetector(
                              onTap: _isEditing
                                  ? () {
                                      setState(() {
                                        if (sel) {
                                          _selectedDietary
                                              .remove(opt['label']);
                                        } else {
                                          _selectedDietary
                                              .add(opt['label']);
                                        }
                                      });
                                    }
                                  : null,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: sel
                                      ? primary.withOpacity(0.08)
                                      : const Color(0xFFFAFAF9),
                                  borderRadius:
                                      BorderRadius.circular(20),
                                  border: Border.all(
                                    color:
                                        sel ? primary : borderColor,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(opt['icon'],
                                        style: const TextStyle(
                                            fontSize: 14)),
                                    const SizedBox(width: 4),
                                    Text(
                                      opt['label'],
                                      style: TextStyle(
                                        color: sel
                                            ? primary
                                            : textSecondary,
                                        fontSize: 12,
                                        fontWeight: sel
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
                        const SizedBox(height: 16),
                        const Text(
                          'Allergens',
                          style: TextStyle(
                              color: textPrimary,
                              fontSize: 13,
                              fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _allergenOptions.map((opt) {
                            final sel = _selectedAllergens
                                .contains(opt['label']);
                            return GestureDetector(
                              onTap: _isEditing
                                  ? () {
                                      setState(() {
                                        if (sel) {
                                          _selectedAllergens
                                              .remove(opt['label']);
                                        } else {
                                          _selectedAllergens
                                              .add(opt['label']);
                                        }
                                      });
                                    }
                                  : null,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: sel
                                      ? const Color(0xFFDC2626)
                                          .withOpacity(0.07)
                                      : const Color(0xFFFAFAF9),
                                  borderRadius:
                                      BorderRadius.circular(20),
                                  border: Border.all(
                                    color: sel
                                        ? const Color(0xFFDC2626)
                                        : borderColor,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(opt['icon'],
                                        style: const TextStyle(
                                            fontSize: 14)),
                                    const SizedBox(width: 4),
                                    Text(
                                      opt['label'],
                                      style: TextStyle(
                                        color: sel
                                            ? const Color(0xFFDC2626)
                                            : textSecondary,
                                        fontSize: 12,
                                        fontWeight: sel
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
                        if (_isEditing) ...[
                          const SizedBox(height: 16),
                          SizedBox(
                            width: double.infinity,
                            height: 44,
                            child: ElevatedButton(
                              onPressed: () => _saveProfile(user.uid),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: primary,
                                foregroundColor: Colors.white,
                                shape: RoundedRectangleBorder(
                                    borderRadius:
                                        BorderRadius.circular(10)),
                              ),
                              child: const Text('Save Preferences',
                                  style: TextStyle(
                                      fontWeight: FontWeight.w700)),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 12),

                // Saved Addresses Section
                GestureDetector(
                  onTap: () => setState(() => _addressesSectionExpanded = !_addressesSectionExpanded),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: borderColor),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.location_on_outlined, color: primary, size: 20),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Text(
                            'Saved Delivery Addresses',
                            style: TextStyle(color: textPrimary, fontSize: 14, fontWeight: FontWeight.w700),
                          ),
                        ),
                        Icon(
                          _addressesSectionExpanded ? Icons.expand_less : Icons.expand_more,
                          color: textSecondary,
                        ),
                      ],
                    ),
                  ),
                ),
                if (_addressesSectionExpanded) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: borderColor),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (user.savedAddresses.isEmpty)
                          const Center(
                            child: Padding(
                              padding: EdgeInsets.symmetric(vertical: 20),
                              child: Text('No addresses saved yet.', style: TextStyle(color: textSecondary, fontSize: 13)),
                            ),
                          )
                        else
                          ...user.savedAddresses.map((addr) => Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: Row(
                              children: [
                                const Icon(Icons.home_outlined, color: textSecondary, size: 20),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(addr['name'], style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                                      Text(addr['details'], style: const TextStyle(color: textSecondary, fontSize: 12)),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline, color: Color(0xFFDC2626), size: 20),
                                  onPressed: () => _deleteAddress(user.uid, user.savedAddresses, addr['id']),
                                ),
                              ],
                            ),
                          )),
                        const SizedBox(height: 8),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: () => _showAddAddressDialog(user.uid, user.savedAddresses),
                            icon: const Icon(Icons.add, size: 18),
                            label: const Text('Add New Address'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: primary,
                              side: const BorderSide(color: primary),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 12),

                // Notifications Section
                GestureDetector(
                  onTap: () => setState(() => _notificationsSectionExpanded = !_notificationsSectionExpanded),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: borderColor),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.notifications_none_outlined, color: primary, size: 20),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Text(
                            'Notification Settings',
                            style: TextStyle(color: textPrimary, fontSize: 14, fontWeight: FontWeight.w700),
                          ),
                        ),
                        Icon(
                          _notificationsSectionExpanded ? Icons.expand_less : Icons.expand_more,
                          color: textSecondary,
                        ),
                      ],
                    ),
                  ),
                ),
                if (_notificationsSectionExpanded) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: borderColor),
                    ),
                    child: Column(
                      children: [
                        _notifSwitch(
                          'Push Notifications',
                          'Master toggle for all alerts',
                          user.notificationsEnabled,
                          (v) => _updateNotifPref(user.uid, 'notificationsEnabled', v),
                        ),
                        const Divider(),
                        _notifSwitch(
                          'Special Offers',
                          'Get alerts for surplus deals and discounts',
                          user.surplusNotif,
                          (v) => _updateNotifPref(user.uid, 'surplusNotif', v),
                        ),
                        _notifSwitch(
                          'Order Updates',
                          'Real-time status of your orders',
                          user.newOrderNotif, // Reusing field for simplicity
                          (v) => _updateNotifPref(user.uid, 'newOrderNotif', v),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 24),
                
                // My Orders Tile
                _menuTile(
                  icon: Icons.history,
                  label: 'My Orders',
                  onTap: () => context.push(AppRoutes.customerOrders),
                ),
                const SizedBox(height: 24),

                // Sign out
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      await ref
                          .read(authNotifierProvider.notifier)
                          .signOut();
                    },
                    icon: const Icon(Icons.logout, size: 18),
                    label: const Text('Sign Out'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFFDC2626),
                      side: const BorderSide(
                          color: Color(0xFFDC2626), width: 0.5),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        );
  }

  Widget _sectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        color: Color(0xFF1C1917),
        fontSize: 15,
        fontWeight: FontWeight.w800,
      ),
    );
  }

  Widget _menuTile({required IconData icon, required String label, required VoidCallback onTap}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE7E5E4)),
        ),
        child: Row(
          children: [
            Icon(icon, color: const Color(0xFFC2410C), size: 22),
            const SizedBox(width: 16),
            Text(label, style: const TextStyle(color: Color(0xFF1C1917), fontSize: 15, fontWeight: FontWeight.w600)),
            const Spacer(),
            const Icon(Icons.chevron_right, color: Color(0xFFA8A29E)),
          ],
        ),
      ),
    );
  }

  Widget _infoTile(
      {required IconData icon,
      required String label,
      required String value}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE7E5E4)),
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF57534E), size: 18),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: const TextStyle(
                      color: Color(0xFFA8A29E), fontSize: 11)),
              const SizedBox(height: 2),
              Text(value,
                  style: const TextStyle(
                      color: Color(0xFF1C1917), fontSize: 14)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _notifSwitch(String title, String subtitle, bool value, ValueChanged<bool> onChanged) {
    return SwitchListTile(
      title: Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 12)),
      value: value,
      onChanged: onChanged,
      activeColor: const Color(0xFFC2410C),
      contentPadding: EdgeInsets.zero,
    );
  }

  void _showAddAddressDialog(String uid, List<Map<String, dynamic>> currentAddresses) {
    final formKey = GlobalKey<FormState>();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add New Address'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _addressNameController,
                decoration: const InputDecoration(labelText: 'Label (e.g. Home, Work)'),
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              TextFormField(
                controller: _addressDetailController,
                decoration: const InputDecoration(labelText: 'Full Address'),
                maxLines: 2,
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              TextFormField(
                controller: _phoneController,
                decoration: const InputDecoration(labelText: 'Contact Phone'),
                keyboardType: TextInputType.phone,
                validator: ValidationUtil.validatePhoneNumber,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              if (formKey.currentState!.validate()) {
                _addAddress(uid, currentAddresses);
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFC2410C), foregroundColor: Colors.white),
            child: const Text('Add Address'),
          ),
        ],
      ),
    );
  }
}
