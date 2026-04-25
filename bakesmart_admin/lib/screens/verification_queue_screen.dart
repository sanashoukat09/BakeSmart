import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/admin_service.dart';
import '../models/user_model.dart';

class VerificationQueueScreen extends ConsumerStatefulWidget {
  const VerificationQueueScreen({super.key});

  @override
  ConsumerState<VerificationQueueScreen> createState() => _VerificationQueueScreenState();
}

class _VerificationQueueScreenState extends ConsumerState<VerificationQueueScreen> {
  UserModel? _selectedBaker;
  final Map<String, List<bool>> _checklists = {};

  @override
  Widget build(BuildContext context) {
    final queueAsync = ref.watch(verificationQueueProvider);

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: queueAsync.when(
        data: (bakers) => bakers.isEmpty
            ? Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.verified_user_outlined, size: 64, color: Colors.green[200]),
                    const SizedBox(height: 16),
                    const Text('No pending verifications', style: TextStyle(color: Colors.grey)),
                  ],
                ),
              )
            : Row(
                children: [
                  // List Side
                  Expanded(
                    flex: 2,
                    child: _buildList(bakers),
                  ),
                  // Details Side
                  Expanded(
                    flex: 3,
                    child: _selectedBaker == null
                        ? _buildPlaceholder()
                        : _buildDetails(_selectedBaker!),
                  ),
                ],
              ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }

  Widget _buildList(List<UserModel> bakers) {
    return Container(
      margin: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.02), blurRadius: 10)],
      ),
      child: ListView.separated(
        itemCount: bakers.length,
        separatorBuilder: (_, __) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final baker = bakers[index];
          final isSelected = _selectedBaker?.uid == baker.uid;
          return ListTile(
            selected: isSelected,
            selectedTileColor: Colors.brown[50],
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            leading: CircleAvatar(
              backgroundImage: baker.profileImageUrl != null ? NetworkImage(baker.profileImageUrl!) : null,
              child: baker.profileImageUrl == null ? const Icon(Icons.person) : null,
            ),
            title: Text(baker.bakeryName ?? baker.name, style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('${baker.city} • ${DateFormat('MMM dd').format(baker.verificationSubmittedAt ?? baker.createdAt)}'),
            onTap: () => setState(() => _selectedBaker = baker),
          );
        },
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.arrow_back, size: 48, color: Colors.grey[300]),
          const SizedBox(height: 16),
          const Text('Select a baker from the list to review', style: TextStyle(color: Colors.grey)),
        ],
      ),
    );
  }

  Widget _buildDetails(UserModel baker) {
    if (!_checklists.containsKey(baker.uid)) {
      _checklists[baker.uid] = List.filled(6, false);
    }
    final checklist = _checklists[baker.uid]!;
    final canApprove = checklist.every((item) => item == true);

    return Container(
      margin: const EdgeInsets.fromLTRB(0, 24, 24, 24),
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.02), blurRadius: 10)],
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildBakerHeader(baker),
            const Divider(height: 48),
            _buildSectionTitle('Bakery Information'),
            const SizedBox(height: 16),
            _buildInfoGrid(baker),
            const SizedBox(height: 32),
            _buildSectionTitle('Photos Gallery'),
            const SizedBox(height: 16),
            _buildPhotoGallery(baker),
            const SizedBox(height: 40),
            _buildAdminChecklist(baker, checklist),
            const SizedBox(height: 40),
            _buildActionButtons(baker, canApprove),
          ],
        ),
      ),
    );
  }

  Widget _buildBakerHeader(UserModel baker) {
    return Row(
      children: [
        CircleAvatar(
          radius: 40,
          backgroundImage: baker.profileImageUrl != null ? NetworkImage(baker.profileImageUrl!) : null,
          child: baker.profileImageUrl == null ? const Icon(Icons.person, size: 40) : null,
        ),
        const SizedBox(width: 24),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(baker.bakeryName ?? 'Unnamed Bakery', style: GoogleFonts.outfit(fontSize: 28, fontWeight: FontWeight.bold)),
              Text('Baker: ${baker.name}', style: const TextStyle(fontSize: 16, color: Colors.grey)),
            ],
          ),
        ),
        _buildWhatsAppButton(baker.whatsappNumber),
      ],
    );
  }

  Widget _buildWhatsAppButton(String? phone) {
    if (phone == null || phone.isEmpty) return const SizedBox.shrink();
    // Convert 03XX-XXXXXXX to 923XXXXXXXX
    String waNumber = phone.replaceAll('-', '').replaceFirst('0', '92');
    String url = 'https://wa.me/$waNumber';

    return ElevatedButton.icon(
      onPressed: () async {
        final uri = Uri.parse(url);
        if (await canLaunchUrl(uri)) await launchUrl(uri);
      },
      icon: const Icon(Icons.chat_bubble_outline, size: 18),
      label: const Text('Contact on WhatsApp'),
      style: ElevatedButton.styleFrom(
        backgroundColor: const Color(0xFF25D366),
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.brown));
  }

  Widget _buildInfoGrid(UserModel baker) {
    return Wrap(
      spacing: 40,
      runSpacing: 24,
      children: [
        _buildInfoItem('Delivery Area', baker.deliveryArea ?? 'Not provided'),
        _buildInfoItem('City', baker.city ?? 'Not provided'),
        _buildInfoItem('Payment Method', baker.paymentMethod ?? 'Not provided'),
        _buildInfoItem('Payment Number', baker.paymentNumber ?? 'Not provided'),
        _buildInfoItem('Phone', baker.phone ?? 'Not provided'),
        _buildInfoItem('Submitted At', baker.verificationSubmittedAt != null ? DateFormat('MMM dd, yyyy HH:mm').format(baker.verificationSubmittedAt!) : 'Unknown'),
      ],
    );
  }

  Widget _buildInfoItem(String label, String value) {
    return SizedBox(
      width: 200,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildPhotoGallery(UserModel baker) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Kitchen Photo', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.grey)),
        const SizedBox(height: 8),
        _buildImagePreview(baker.kitchenPhotoUrl, height: 200),
        const SizedBox(height: 24),
        const Text('Product Photo Showcase', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.grey)),
        const SizedBox(height: 8),
        SizedBox(
          height: 120,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: (baker.productPhotoUrls ?? []).map((url) => _buildImagePreview(url, width: 120, margin: 12)).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildImagePreview(String? url, {double? width, double? height, double margin = 0}) {
    if (url == null || url.isEmpty) {
      return Container(
        width: width ?? double.infinity,
        height: height ?? 120,
        margin: EdgeInsets.only(right: margin),
        decoration: BoxDecoration(color: Colors.grey[100], borderRadius: BorderRadius.circular(12)),
        child: const Icon(Icons.image_not_supported_outlined, color: Colors.grey),
      );
    }
    return GestureDetector(
      onTap: () => _openImageUrl(url),
      child: Container(
        width: width ?? double.infinity,
        height: height ?? 120,
        margin: EdgeInsets.only(right: margin),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          image: DecorationImage(image: NetworkImage(url), fit: BoxFit.cover),
        ),
      ),
    );
  }

  void _openImageUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) await launchUrl(uri);
  }

  Widget _buildAdminChecklist(UserModel baker, List<bool> checklist) {
    final labels = [
      'Profile photo shows a real person',
      'Kitchen photo looks like a genuine home baking setup',
      'Product photos show real baked goods (not stock images)',
      'WhatsApp number is in valid Pakistani format',
      'Payment number (JazzCash/EasyPaisa) is provided',
      'All information looks consistent and genuine',
    ];

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(color: Colors.green[50], borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.green[100]!)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Admin Review Checklist', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green)),
          const SizedBox(height: 16),
          ...List.generate(6, (index) => CheckboxListTile(
            value: checklist[index],
            onChanged: (v) => setState(() => checklist[index] = v!),
            title: Text(labels[index], style: const TextStyle(fontSize: 14)),
            dense: true,
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
          )),
        ],
      ),
    );
  }

  Widget _buildActionButtons(UserModel baker, bool canApprove) {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton(
            onPressed: canApprove ? () async {
              await ref.read(adminServiceProvider).approveVerification(baker.uid);
              setState(() => _selectedBaker = null);
            } : null,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 20),
              disabledBackgroundColor: Colors.grey[300],
            ),
            child: const Text('Approve Application', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
        const SizedBox(width: 16),
        OutlinedButton(
          onPressed: () => _showRejectDialog(context, baker.uid),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.red,
            side: const BorderSide(color: Colors.red),
            padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 32),
          ),
          child: const Text('Reject'),
        ),
      ],
    );
  }

  void _showRejectDialog(BuildContext context, String uid) {
    final reasonCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reject Verification'),
        content: TextField(
          controller: reasonCtrl,
          decoration: const InputDecoration(labelText: 'Reason for rejection (Required)', hintText: 'Missing kitchen photo, invalid WA format...'),
          maxLines: 4,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              if (reasonCtrl.text.trim().isEmpty) return;
              ref.read(adminServiceProvider).rejectVerification(uid, reasonCtrl.text.trim());
              Navigator.pop(ctx);
              setState(() => _selectedBaker = null);
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red, foregroundColor: Colors.white),
            child: const Text('Confirm Rejection'),
          ),
        ],
      ),
    );
  }
}
