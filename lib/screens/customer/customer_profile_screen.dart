import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/validation_util.dart';
import '../../widgets/customer/customer_bottom_nav.dart';

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
  static const statusAmber = Color(0xFFF39C12);
  static const statusRed   = Color(0xFFE74C3C);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

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
        SnackBar(
          content: const Text('Profile saved ✓'),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          backgroundColor: _T.brown,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final userAsync = ref.watch(currentUserProvider);
    final user = userAsync.valueOrNull;

    if (user == null) {
      return const Scaffold(
        backgroundColor: _T.canvas,
        body: Center(child: CircularProgressIndicator(color: _T.brown)),
      );
    }

    _populate(user);

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          'My Profile',
          style: TextStyle(
            color: _T.ink,
            fontSize: 19,
            fontWeight: FontWeight.w800,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _T.ink),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          if (!_isEditing)
            TextButton(
              onPressed: () => setState(() => _isEditing = true),
              child: const Text(
                'Edit',
                style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 15),
              ),
            )
          else
            TextButton(
              onPressed: _isSaving ? null : () => _saveProfile(user.uid),
              child: _isSaving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: _T.brown),
                    )
                  : const Text(
                      'Save',
                      style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 15),
                    ),
            ),
        ],
      ),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Avatar Section
            Center(
              child: Column(
                children: [
                  Stack(
                    children: [
                      Container(
                        width: 96,
                        height: 96,
                        decoration: BoxDecoration(
                          color: _T.brown.withOpacity(0.06),
                          shape: BoxShape.circle,
                          border: Border.all(color: _T.rimLight, width: 2.5),
                          boxShadow: _T.shadowSm,
                        ),
                        child: user.photoUrl != null
                            ? ClipOval(
                                child: Image.network(user.photoUrl!, fit: BoxFit.cover),
                              )
                            : Center(
                                child: Text(
                                  (user.displayName ?? 'C')[0].toUpperCase(),
                                  style: const TextStyle(
                                    color: _T.brown,
                                    fontWeight: FontWeight.w800,
                                    fontSize: 36,
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
                      color: _T.ink,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    user.email,
                    style: const TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                    decoration: BoxDecoration(
                      color: _T.statusAmber.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Text(
                      '🛍️ Customer',
                      style: TextStyle(
                        color: _T.statusAmber,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Name field
            _sectionTitle('Personal Info'),
            const SizedBox(height: 12),
            if (_isEditing)
              TextFormField(
                controller: _nameController,
                style: const TextStyle(color: _T.ink, fontSize: 15, fontWeight: FontWeight.w700),
                decoration: InputDecoration(
                  labelText: 'Display name',
                  prefixIcon: const Icon(Icons.person_outline, size: 20, color: _T.inkMid),
                  filled: true,
                  fillColor: Colors.white,
                  labelStyle: const TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _T.brown, width: 2),
                  ),
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

            // Dietary Preferences Expandable Tile
            GestureDetector(
              onTap: () => setState(() => _prefsSectionExpanded = !_prefsSectionExpanded),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Row(
                  children: [
                    const Icon(Icons.restaurant_menu_outlined, color: _T.brown, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Dietary Preferences & Allergens',
                            style: TextStyle(
                              color: _T.ink,
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          if (user.dietaryPreferences.isNotEmpty || user.allergens.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 2),
                              child: Text(
                                '${user.dietaryPreferences.length} preferences · ${user.allergens.length} allergens',
                                style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
                              ),
                            ),
                        ],
                      ),
                    ),
                    Icon(
                      _prefsSectionExpanded ? Icons.expand_less : Icons.expand_more,
                      color: _T.inkMid,
                    ),
                  ],
                ),
              ),
            ),
            if (_prefsSectionExpanded) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Dietary Preferences',
                      style: TextStyle(color: _T.ink, fontSize: 13, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: _dietaryOptions.map((opt) {
                        final sel = _selectedDietary.contains(opt['label']);
                        return GestureDetector(
                          onTap: _isEditing
                              ? () {
                                  setState(() {
                                    if (sel) {
                                      _selectedDietary.remove(opt['label']);
                                    } else {
                                      _selectedDietary.add(opt['label']);
                                    }
                                  });
                                }
                              : null,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: sel ? _T.brown.withOpacity(0.08) : Colors.white,
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: sel ? _T.brown : _T.rimLight,
                                width: sel ? 1.8 : 1.2,
                              ),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(opt['icon'], style: const TextStyle(fontSize: 14)),
                                const SizedBox(width: 4),
                                Text(
                                  opt['label'],
                                  style: TextStyle(
                                    color: sel ? _T.brown : _T.inkMid,
                                    fontSize: 12,
                                    fontWeight: sel ? FontWeight.w800 : FontWeight.w600,
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
                      style: TextStyle(color: _T.ink, fontSize: 13, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: _allergenOptions.map((opt) {
                        final sel = _selectedAllergens.contains(opt['label']);
                        return GestureDetector(
                          onTap: _isEditing
                              ? () {
                                  setState(() {
                                    if (sel) {
                                      _selectedAllergens.remove(opt['label']);
                                    } else {
                                      _selectedAllergens.add(opt['label']);
                                    }
                                  });
                                }
                              : null,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: sel ? _T.statusRed.withOpacity(0.08) : Colors.white,
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: sel ? _T.statusRed : _T.rimLight,
                                width: sel ? 1.8 : 1.2,
                              ),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(opt['icon'], style: const TextStyle(fontSize: 14)),
                                const SizedBox(width: 4),
                                Text(
                                  opt['label'],
                                  style: TextStyle(
                                    color: sel ? _T.statusRed : _T.inkMid,
                                    fontSize: 12,
                                    fontWeight: sel ? FontWeight.w800 : FontWeight.w600,
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
                        height: 48,
                        child: ElevatedButton(
                          onPressed: () => _saveProfile(user.uid),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _T.brown,
                            foregroundColor: Colors.white,
                            elevation: 0,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                          ),
                          child: const Text('Save Preferences', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],

            const SizedBox(height: 12),

            // Saved Delivery Addresses Section
            GestureDetector(
              onTap: () => setState(() => _addressesSectionExpanded = !_addressesSectionExpanded),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Row(
                  children: [
                    const Icon(Icons.location_on_outlined, color: _T.brown, size: 20),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        'Saved Delivery Addresses',
                        style: TextStyle(color: _T.ink, fontSize: 14, fontWeight: FontWeight.w800),
                      ),
                    ),
                    Icon(
                      _addressesSectionExpanded ? Icons.expand_less : Icons.expand_more,
                      color: _T.inkMid,
                    ),
                  ],
                ),
              ),
            ),
            if (_addressesSectionExpanded) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (user.savedAddresses.isEmpty)
                      const Center(
                        child: Padding(
                          padding: EdgeInsets.symmetric(vertical: 20),
                          child: Text('No addresses saved yet.', style: TextStyle(color: _T.inkMid, fontSize: 13, fontWeight: FontWeight.w600)),
                        ),
                      )
                    else
                      ...user.savedAddresses.map((addr) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          children: [
                            const Icon(Icons.home_outlined, color: _T.inkMid, size: 20),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(addr['name'], style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: _T.ink)),
                                  Text(addr['details'], style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600)),
                                ],
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete_outline, color: _T.statusRed, size: 20),
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
                        label: const Text('Add New Address', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13)),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: _T.brown,
                          side: const BorderSide(color: _T.brown, width: 1.5),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 12),

            // Notification Settings Section
            GestureDetector(
              onTap: () => setState(() => _notificationsSectionExpanded = !_notificationsSectionExpanded),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Row(
                  children: [
                    const Icon(Icons.notifications_none_outlined, color: _T.brown, size: 20),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        'Notification Settings',
                        style: TextStyle(color: _T.ink, fontSize: 14, fontWeight: FontWeight.w800),
                      ),
                    ),
                    Icon(
                      _notificationsSectionExpanded ? Icons.expand_less : Icons.expand_more,
                      color: _T.inkMid,
                    ),
                  ],
                ),
              ),
            ),
            if (_notificationsSectionExpanded) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _T.rimLight, width: 1.5),
                  boxShadow: _T.shadowSm,
                ),
                child: Column(
                  children: [
                    _notifSwitch(
                      'Push Notifications',
                      'Master toggle for all alerts',
                      user.notificationsEnabled,
                      (v) => _updateNotifPref(user.uid, 'notificationsEnabled', v),
                    ),
                    const Divider(color: _T.rimLight),
                    _notifSwitch(
                      'Special Offers',
                      'Get alerts for surplus deals and discounts',
                      user.surplusNotif,
                      (v) => _updateNotifPref(user.uid, 'surplusNotif', v),
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
                  await ref.read(authNotifierProvider.notifier).signOut();
                },
                icon: const Icon(Icons.logout, size: 18),
                label: const Text('Sign Out', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: _T.statusRed,
                  side: const BorderSide(color: _T.statusRed, width: 1.5),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
      bottomNavigationBar: const CustomerBottomNav(currentIndex: 2),
    );
  }

  Widget _sectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        color: _T.ink,
        fontSize: 15,
        fontWeight: FontWeight.w800,
      ),
    );
  }

  Widget _menuTile({required IconData icon, required String label, required VoidCallback onTap}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: Row(
          children: [
            Icon(icon, color: _T.brown, size: 22),
            const SizedBox(width: 16),
            Text(label, style: const TextStyle(color: _T.ink, fontSize: 15, fontWeight: FontWeight.w700)),
            const Spacer(),
            const Icon(Icons.chevron_right, color: _T.inkMid),
          ],
        ),
      ),
    );
  }

  Widget _infoTile({required IconData icon, required String label, required String value}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: Row(
        children: [
          Icon(icon, color: _T.inkMid, size: 18),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: _T.inkFaint, fontSize: 11, fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(color: _T.ink, fontSize: 14, fontWeight: FontWeight.w700)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _notifSwitch(String title, String subtitle, bool value, ValueChanged<bool> onChanged) {
    return SwitchListTile(
      title: Text(title, style: const TextStyle(color: _T.ink, fontSize: 14, fontWeight: FontWeight.w700)),
      subtitle: Text(subtitle, style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w500)),
      value: value,
      onChanged: onChanged,
      activeColor: _T.brown,
      contentPadding: EdgeInsets.zero,
    );
  }

  void _showAddAddressDialog(String uid, List<Map<String, dynamic>> currentAddresses) {
    final formKey = GlobalKey<FormState>();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _T.canvas,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: const Text('Add New Address', style: TextStyle(color: _T.ink, fontWeight: FontWeight.w800, fontSize: 18)),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _addressNameController,
                style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
                decoration: const InputDecoration(labelText: 'Label (e.g. Home, Work)', labelStyle: TextStyle(color: _T.inkMid)),
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              TextFormField(
                controller: _addressDetailController,
                style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
                decoration: const InputDecoration(labelText: 'Full Address', labelStyle: TextStyle(color: _T.inkMid)),
                maxLines: 2,
                validator: (v) => v!.isEmpty ? 'Required' : null,
              ),
              TextFormField(
                controller: _phoneController,
                style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600),
                decoration: const InputDecoration(labelText: 'Contact Phone', labelStyle: TextStyle(color: _T.inkMid)),
                keyboardType: TextInputType.phone,
                validator: ValidationUtil.validatePhoneNumber,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel', style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w700)),
          ),
          ElevatedButton(
            onPressed: () {
              if (formKey.currentState!.validate()) {
                _addAddress(uid, currentAddresses);
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: _T.brown,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            child: const Text('Add Address', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
