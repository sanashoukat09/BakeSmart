import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../core/services/cloudinary_service.dart';
import '../../auth/services/auth_provider.dart';
import '../../notifications/models/notification_model.dart';
import '../../notifications/services/notification_service.dart';
import 'trust_and_safety_screen.dart';

class SellerVerificationScreen extends ConsumerStatefulWidget {
  const SellerVerificationScreen({super.key});

  @override
  ConsumerState<SellerVerificationScreen> createState() => _SellerVerificationScreenState();
}

class _SellerVerificationScreenState extends ConsumerState<SellerVerificationScreen> {
  final _formKey = GlobalKey<FormState>();
  
  // Section 1 Controllers
  final _bakeryNameCtrl = TextEditingController();
  final _deliveryAreaCtrl = TextEditingController();
  final _whatsappCtrl = TextEditingController();
  final _paymentNumberCtrl = TextEditingController();
  String _paymentMethod = 'JazzCash';

  // Section 2 Photos
  XFile? _profileFile;
  XFile? _kitchenFile;
  final List<XFile> _productFiles = [];
  
  // Existing Photo URLs (for resubmission)
  String? _existingProfileUrl;
  String? _existingKitchenUrl;
  List<String> _existingProductUrls = [];

  // Section 3 Agreements
  bool _hygieneAgreed = false;
  bool _termsAgreed = false;

  bool _isLoading = false;
  String _loadingMessage = '';

  @override
  void initState() {
    super.initState();
    _prepopulate();
  }

  void _prepopulate() {
    final user = ref.read(userDataProvider).value;
    if (user != null) {
      _bakeryNameCtrl.text = user.bakeryName ?? '';
      _deliveryAreaCtrl.text = user.deliveryArea ?? '';
      _whatsappCtrl.text = user.whatsappNumber ?? '';
      _paymentNumberCtrl.text = user.paymentNumber ?? '';
      if (user.paymentMethod != null) _paymentMethod = user.paymentMethod!;
      
      _existingProfileUrl = user.profileImageUrl;
      _existingKitchenUrl = user.kitchenPhotoUrl;
      _existingProductUrls = List.from(user.productPhotoUrls ?? []);
      
      _hygieneAgreed = user.hygieneAgreement;
      _termsAgreed = user.termsAgreement;
    }
  }

  Future<void> _pickImage(String type) async {
    final picker = ImagePicker();
    if (type == 'products') {
      if (_productFiles.length + _existingProductUrls.length >= 5) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Maximum 5 product photos allowed')));
        return;
      }
      final files = await picker.pickMultiImage(imageQuality: 70);
      if (files.isNotEmpty) {
        setState(() {
          _productFiles.addAll(files);
          if (_productFiles.length + _existingProductUrls.length > 5) {
            _productFiles.removeRange(5 - _existingProductUrls.length, _productFiles.length);
          }
        });
      }
    } else {
      final file = await picker.pickImage(source: ImageSource.gallery, imageQuality: 70);
      if (file != null) {
        setState(() {
          if (type == 'profile') _profileFile = file;
          if (type == 'kitchen') _kitchenFile = file;
        });
      }
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if ((_profileFile == null && _existingProfileUrl == null) || 
        (_kitchenFile == null && _existingKitchenUrl == null) || 
        (_productFiles.length + _existingProductUrls.length < 2)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please provide all required photos (Profile, Kitchen, and min 2 Products)')));
      return;
    }

    setState(() {
      _isLoading = true;
      _loadingMessage = 'Preparing photos...';
    });

    try {
      final user = ref.read(authStateProvider).value;
      if (user == null || user.uid.isEmpty) throw Exception('User ID not found. Please log in again.');

      final cloudinary = ref.read(cloudinaryServiceProvider);

      String? profileUrl = _existingProfileUrl;
      String? kitchenUrl = _existingKitchenUrl;
      List<String> productUrls = List.from(_existingProductUrls);

      int totalToUpload = (_profileFile != null ? 1 : 0) + 
                          (_kitchenFile != null ? 1 : 0) + 
                          _productFiles.length;
      int currentUpload = 0;

      // 1. Upload Profile
      if (_profileFile != null) {
        currentUpload++;
        setState(() => _loadingMessage = 'Uploading photos... ($currentUpload of $totalToUpload)');
        profileUrl = await cloudinary.uploadImage(_profileFile!.path);
      }

      // 2. Upload Kitchen
      if (_kitchenFile != null) {
        currentUpload++;
        setState(() => _loadingMessage = 'Uploading photos... ($currentUpload of $totalToUpload)');
        kitchenUrl = await cloudinary.uploadImage(_kitchenFile!.path);
      }

      // 3. Upload Products
      for (int i = 0; i < _productFiles.length; i++) {
        currentUpload++;
        setState(() => _loadingMessage = 'Uploading photos... ($currentUpload of $totalToUpload)');
        final url = await cloudinary.uploadImage(_productFiles[i].path);
        productUrls.add(url);
      }

      setState(() => _loadingMessage = 'Saving information...');

      // 4. Update Firestore
      final firestore = ref.read(firestoreProvider);
      final batch = firestore.batch();

      batch.update(firestore.collection('users').doc(user.uid), {
        'bakeryName': _bakeryNameCtrl.text.trim(),
        'deliveryArea': _deliveryAreaCtrl.text.trim(),
        'whatsappNumber': _whatsappCtrl.text.trim(),
        'paymentMethod': _paymentMethod,
        'paymentNumber': _paymentNumberCtrl.text.trim(),
        'profileImageUrl': profileUrl,
        'kitchenPhotoUrl': kitchenUrl,
        'productPhotoUrls': productUrls,
        'hygieneAgreement': _hygieneAgreed,
        'termsAgreement': _termsAgreed,
        'verificationStatus': 'pending',
        'verificationSubmittedAt': FieldValue.serverTimestamp(),
        'rejectionReason': null,
      });

      // 5. Notify Admins
      final admins = await firestore.collection('users').where('role', isEqualTo: 'admin').get();
      for (var adminDoc in admins.docs) {
        ref.read(notificationServiceProvider).sendNotificationWithBatch(
          batch,
          recipientId: adminDoc.id,
          title: 'New Verification Request',
          body: '${_bakeryNameCtrl.text.trim()} has submitted their bakery for verification.',
          type: NotificationType.verificationUpdate,
          referenceId: user.uid,
        );
      }

      await batch.commit();

      if (mounted) {
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            title: const Text('Application Submitted'),
            content: const Text('Your application has been submitted. We will review it within 24 to 48 hours.'),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(ctx); // Close dialog
                  Navigator.pop(context); // Go back to dashboard
                },
                child: const Text('OK'),
              ),
            ],
          ),
        );
      }
    } on FirebaseException catch (e) {
      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Firestore Error'),
            content: Text('Code: ${e.code}\nMessage: ${e.message}'),
            actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Submission Error'),
            content: Text(e.toString()),
            actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.brown[50],
      appBar: AppBar(
        title: const Text('Seller Verification'),
        backgroundColor: Colors.brown,
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildHeader(),
                  const SizedBox(height: 32),
                  _buildBakeryInfo(),
                  const SizedBox(height: 32),
                  _buildPhotoSection(),
                  const SizedBox(height: 32),
                  _buildAgreements(),
                  const SizedBox(height: 48),
                  ElevatedButton(
                    onPressed: (_isLoading || !_hygieneAgreed || !_termsAgreed) ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.brown,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 18),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      elevation: 0,
                    ),
                    child: Text(
                      'Submit Application',
                      style: GoogleFonts.outfit(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
          if (_isLoading)
            Container(
              color: Colors.black54,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.all(32),
                  margin: const EdgeInsets.symmetric(horizontal: 40),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(color: Colors.brown),
                      const SizedBox(height: 24),
                      Text(
                        _loadingMessage,
                        style: const TextStyle(fontWeight: FontWeight.bold),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Stage 2: Seller Application',
          style: GoogleFonts.outfit(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.brown),
        ),
        const SizedBox(height: 8),
        const Text(
          'Become a verified seller and start listing your products on the BakeSmart marketplace.',
          style: TextStyle(color: Colors.grey, fontSize: 15),
        ),
      ],
    );
  }

  Widget _buildBakeryInfo() {
    return _SectionCard(
      title: 'Bakery Information',
      icon: Icons.store_outlined,
      children: [
        TextFormField(
          controller: _bakeryNameCtrl,
          decoration: const InputDecoration(labelText: 'Bakery Name', hintText: 'e.g. Grandma\'s Kitchen'),
          validator: (v) => v!.isEmpty ? 'Required' : null,
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: _deliveryAreaCtrl,
          decoration: const InputDecoration(labelText: 'Delivery Area & Neighbourhood', hintText: 'e.g. DHA Phase 5, Model Town'),
          validator: (v) => v!.isEmpty ? 'Required' : null,
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: _whatsappCtrl,
          decoration: const InputDecoration(labelText: 'WhatsApp Number', hintText: '03XX-XXXXXXX'),
          keyboardType: TextInputType.phone,
          validator: (v) {
            if (v!.isEmpty) return 'Required';
            if (!RegExp(r'^03[0-9]{2}-[0-9]{7}$').hasMatch(v)) return 'Invalid format (03XX-XXXXXXX)';
            return null;
          },
        ),
        const SizedBox(height: 24),
        const Text('Payment Method for Withdrawals', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        Row(
          children: [
            Expanded(
              child: RadioListTile<String>(
                title: const Text('JazzCash', style: TextStyle(fontSize: 13)),
                value: 'JazzCash',
                groupValue: _paymentMethod,
                contentPadding: EdgeInsets.zero,
                onChanged: (v) => setState(() => _paymentMethod = v!),
              ),
            ),
            Expanded(
              child: RadioListTile<String>(
                title: const Text('EasyPaisa', style: TextStyle(fontSize: 13)),
                value: 'EasyPaisa',
                groupValue: _paymentMethod,
                contentPadding: EdgeInsets.zero,
                onChanged: (v) => setState(() => _paymentMethod = v!),
              ),
            ),
          ],
        ),
        TextFormField(
          controller: _paymentNumberCtrl,
          decoration: InputDecoration(labelText: '$_paymentMethod Number'),
          keyboardType: TextInputType.phone,
          validator: (v) => v!.isEmpty ? 'Required' : null,
        ),
      ],
    );
  }

  Widget _buildPhotoSection() {
    return _SectionCard(
      title: 'Identity & Setup Photos',
      icon: Icons.camera_alt_outlined,
      children: [
        const Text(
          'Photos of you, your kitchen and your work help build trust with customers.',
          style: TextStyle(color: Colors.grey, fontSize: 12),
        ),
        const SizedBox(height: 20),
        
        // Profile Photo
        _PhotoPickerTile(
          label: 'Profile Photo (Required)',
          sublabel: 'Clear face photo of the baker',
          file: _profileFile,
          existingUrl: _existingProfileUrl,
          onTap: () => _pickImage('profile'),
          onRemove: () => setState(() { _profileFile = null; _existingProfileUrl = null; }),
        ),
        const Divider(height: 32),
        
        // Kitchen Photo
        _PhotoPickerTile(
          label: 'Kitchen Setup (Required)',
          sublabel: 'Photo of the area where you bake',
          file: _kitchenFile,
          existingUrl: _existingKitchenUrl,
          onTap: () => _pickImage('kitchen'),
          onRemove: () => setState(() { _kitchenFile = null; _existingKitchenUrl = null; }),
        ),
        const Divider(height: 32),
        
        // Product Photos
        const Text('Product Showcase (2-5 Photos required)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        SizedBox(
          height: 100,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              ..._existingProductUrls.map((url) => _SquareThumb(
                url: url,
                onRemove: () => setState(() => _existingProductUrls.remove(url)),
              )),
              ..._productFiles.map((file) => _SquareThumb(
                file: file,
                onRemove: () => setState(() => _productFiles.remove(file)),
              )),
              if (_productFiles.length + _existingProductUrls.length < 5)
                GestureDetector(
                  onTap: () => _pickImage('products'),
                  child: Container(
                    width: 100,
                    margin: const EdgeInsets.only(right: 8),
                    decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(12)),
                    child: const Icon(Icons.add_photo_alternate_outlined, color: Colors.grey),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAgreements() {
    return Column(
      children: [
        CheckboxListTile(
          value: _hygieneAgreed,
          onChanged: (v) => setState(() => _hygieneAgreed = v!),
          title: const Text(
            'I confirm I prepare food in a clean kitchen following basic hygiene and food safety practices',
            style: TextStyle(fontSize: 13),
          ),
          controlAffinity: ListTileControlAffinity.leading,
          contentPadding: EdgeInsets.zero,
        ),
        CheckboxListTile(
          value: _termsAgreed,
          onChanged: (v) => setState(() => _termsAgreed = v!),
          title: const Text(
            'I agree to BakeSmart Terms and Conditions and confirm all submitted information is accurate and truthful',
            style: TextStyle(fontSize: 13),
          ),
          controlAffinity: ListTileControlAffinity.leading,
          contentPadding: EdgeInsets.zero,
        ),
        const SizedBox(height: 16),
        TextButton(
          onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TrustAndSafetyScreen())),
          child: const Text('Why do we need this information? See Trust & Safety'),
        ),
      ],
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final List<Widget> children;

  const _SectionCard({required this.title, required this.icon, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 10, offset: const Offset(0, 4))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: Colors.brown, size: 20),
              const SizedBox(width: 8),
              Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Colors.brown)),
            ],
          ),
          const SizedBox(height: 24),
          ...children,
        ],
      ),
    );
  }
}

class _PhotoPickerTile extends StatelessWidget {
  final String label;
  final String sublabel;
  final XFile? file;
  final String? existingUrl;
  final VoidCallback onTap;
  final VoidCallback onRemove;

  const _PhotoPickerTile({
    required this.label,
    required this.sublabel,
    required this.onTap,
    required this.onRemove,
    this.file,
    this.existingUrl,
  });

  @override
  Widget build(BuildContext context) {
    bool hasPhoto = file != null || existingUrl != null;

    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              Text(sublabel, style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
        ),
        const SizedBox(width: 16),
        GestureDetector(
          onTap: hasPhoto ? null : onTap,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.grey[100],
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey[300]!),
                ),
                child: file != null
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: kIsWeb 
                          ? Image.network(file!.path, fit: BoxFit.cover) 
                          : Image.file(File(file!.path), fit: BoxFit.cover))
                    : existingUrl != null
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: Image.network(
                          existingUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (ctx, e, s) => const Icon(Icons.broken_image_outlined, color: Colors.grey),
                        ),
                      )
                        : const Icon(Icons.add_a_photo_outlined, color: Colors.grey),
              ),
              if (hasPhoto)
                Positioned(
                  top: -10,
                  right: -10,
                  child: IconButton(
                    onPressed: onRemove,
                    icon: const CircleAvatar(
                      radius: 12,
                      backgroundColor: Colors.red,
                      child: Icon(Icons.close, color: Colors.white, size: 14),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SquareThumb extends StatelessWidget {
  final XFile? file;
  final String? url;
  final VoidCallback onRemove;

  const _SquareThumb({this.file, this.url, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          width: 100,
          margin: const EdgeInsets.only(right: 12),
          decoration: BoxDecoration(
            color: Colors.grey[100],
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.grey[300]!),
          ),
          child: file != null
              ? ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: kIsWeb 
                    ? Image.network(file!.path, fit: BoxFit.cover)
                    : Image.file(File(file!.path), fit: BoxFit.cover))
              : ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    url!,
                    fit: BoxFit.cover,
                    errorBuilder: (ctx, e, s) => const Icon(Icons.broken_image_outlined, color: Colors.grey),
                  ),
                ),
        ),
        Positioned(
          top: -10,
          right: 2,
          child: IconButton(
            onPressed: onRemove,
            icon: const CircleAvatar(
              radius: 10,
              backgroundColor: Colors.red,
              child: Icon(Icons.close, color: Colors.white, size: 12),
            ),
          ),
        ),
      ],
    );
  }
}
