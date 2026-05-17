import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/ai_provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/product_provider.dart';
import '../../core/constants/app_constants.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';

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

class AiAssistantScreen extends ConsumerStatefulWidget {
  const AiAssistantScreen({super.key});

  @override
  ConsumerState<AiAssistantScreen> createState() => _AiAssistantScreenState();
}

class _AiAssistantScreenState extends ConsumerState<AiAssistantScreen> {
  File? _selectedImage;
  bool _isUploading = false;

  Future<void> _pickImage(ImageSource source) async {
    final picker = ImagePicker();
    final pickedFile = await picker.pickImage(
      source: source,
      imageQuality: 85,
    );

    if (pickedFile != null) {
      final file = File(pickedFile.path);
      
      // 1. Validation: Format
      final ext = pickedFile.path.split('.').last.toLowerCase();
      if (!['jpg', 'jpeg', 'png', 'webp'].contains(ext)) {
        _showError('Only JPG, PNG, and WEBP images are allowed.');
        return;
      }

      // 2. Validation: Size (Max 5MB)
      final size = await file.length();
      if (size > 5 * 1024 * 1024) {
        _showError('Image size must be less than 5MB.');
        return;
      }

      // 3. Validation: Dimensions (Min 200x200)
      final image = await decodeImageFromList(await file.readAsBytes());
      if (image.width < 200 || image.height < 200) {
        _showError('Image dimensions must be at least 200x200px.');
        return;
      }

      setState(() {
        _selectedImage = file;
      });
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
        backgroundColor: _T.statusPink,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Future<void> _analyze() async {
    if (_selectedImage == null) {
      _showError('Please select an image first.');
      return;
    }

    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) return;

    setState(() => _isUploading = true);

    try {
      // 1. Upload to Cloudinary
      final cloudinary = ref.read(cloudinaryServiceProvider);
      final imageUrl = await cloudinary.uploadImage(
        imageFile: _selectedImage!,
        folder: 'bakesmart/photo_analysis',
      );

      // 2. Call AI Analysis directly
      await ref.read(aiNotifierProvider.notifier).analyzeImage(
            imageUrl: imageUrl,
            bakerId: user.uid,
          );
      
      setState(() => _selectedImage = null);

    } catch (e) {
      _showError('Error: ${e.toString()}');
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final aiState = ref.watch(aiNotifierProvider);
    final historyAsync = ref.watch(aiHistoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'AI Photo Assistant', 
          style: TextStyle(color: _T.brown, fontWeight: FontWeight.w800, fontSize: 18),
        ),
        backgroundColor: _T.canvas,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.history, color: _T.brown),
            onPressed: () => _showHistoryBottomSheet(context, historyAsync),
          ),
        ],
      ),
      backgroundColor: _T.canvas,
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(),
            const SizedBox(height: 28),
            _buildImagePicker(),
            const SizedBox(height: 28),
            _buildAnalyzeButton(aiState.isLoading || _isUploading),
            const SizedBox(height: 28),
            _buildResult(aiState),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _T.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: _T.rimLight, width: 1.5),
                boxShadow: _T.shadowSm,
              ),
              child: const Icon(Icons.auto_awesome_rounded, color: _T.brown, size: 28),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Cake Design Analyzer',
                    style: TextStyle(
                      color: _T.ink,
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.5,
                    ),
                  ),
                  Text(
                    'Powered by Gemini AI',
                    style: TextStyle(
                      color: _T.statusCopper,
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        const Text(
          'Upload a photo to automatically extract decoration steps, ingredients, and professional baking tips.',
          style: TextStyle(
            color: _T.inkMid,
            fontSize: 14,
            height: 1.5,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }

  Widget _buildImagePicker() {
    return GestureDetector(
      onTap: () => _showImageSourceOptions(),
      child: Container(
        height: 250,
        width: double.infinity,
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: BorderRadius.circular(24),
          boxShadow: _T.shadowSm,
          border: Border.all(
            color: _T.rimLight,
            width: 1.5,
          ),
        ),
        child: _selectedImage != null
            ? Stack(
                fit: StackFit.expand,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(22),
                    child: Image.file(_selectedImage!, fit: BoxFit.cover),
                  ),
                  Positioned(
                    top: 12,
                    right: 12,
                    child: CircleAvatar(
                      backgroundColor: Colors.white,
                      child: IconButton(
                        icon: const Icon(Icons.close, color: _T.ink),
                        onPressed: () => setState(() => _selectedImage = null),
                      ),
                    ),
                  ),
                ],
              )
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: const BoxDecoration(
                      color: _T.pinkL,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.add_a_photo_rounded,
                        size: 40, color: _T.statusPink),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Select Cake Photo',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: _T.ink),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'JPG, PNG, WEBP (Max 5MB)',
                    style: TextStyle(color: _T.inkFaint, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
      ),
    );
  }

  void _showImageSourceOptions() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library, color: _T.brown),
              title: const Text('Gallery', style: TextStyle(fontWeight: FontWeight.w700, color: _T.ink)),
              onTap: () {
                Navigator.pop(context);
                _pickImage(ImageSource.gallery);
              },
            ),
            ListTile(
              leading: const Icon(Icons.camera_alt, color: _T.brown),
              title: const Text('Camera', style: TextStyle(fontWeight: FontWeight.w700, color: _T.ink)),
              onTap: () {
                Navigator.pop(context);
                _pickImage(ImageSource.camera);
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnalyzeButton(bool isLoading) {
    return Container(
      width: double.infinity,
      height: 54,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        boxShadow: _T.shadowSm,
      ),
      child: ElevatedButton(
        onPressed: isLoading ? null : _analyze,
        style: ElevatedButton.styleFrom(
          backgroundColor: _T.brown,
          foregroundColor: Colors.white,
          disabledBackgroundColor: _T.rimLight,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: isLoading
            ? const SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.auto_awesome, size: 20),
                  SizedBox(width: 12),
                  Text('Analyze Cake Design', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
                ],
              ),
      ),
    );
  }

  Widget _buildResult(AsyncValue<Map<String, dynamic>?> state) {
    return state.when(
      data: (analysis) {
        if (analysis == null) return const SizedBox.shrink();
        
        if (analysis['error'] != null) {
          return _buildErrorState(analysis['error']);
        }

        return _AnalysisResultView(analysis: analysis);
      },
      loading: () => const Center(
        child: Padding(
          padding: EdgeInsets.all(40),
          child: Column(
            children: [
              CircularProgressIndicator(color: _T.statusCopper),
              const SizedBox(height: 20),
              Text(
                'Gemini AI is analyzing your design...', 
                style: TextStyle(fontWeight: FontWeight.w800, color: _T.ink),
              ),
            ],
          ),
        ),
      ),
      error: (e, _) => _buildErrorState(e.toString()),
    );
  }

  Widget _buildErrorState(String errorType) {
    String message;
    IconData icon;

    switch (errorType) {
      case 'not_a_cake':
        message = "Oops! This doesn't look like a cake. Please upload a cake design photo.";
        icon = Icons.block;
        break;
      case 'image_too_unclear':
        message = "The image is too blurry or unclear. Please try with a better photo.";
        icon = Icons.camera_enhance;
        break;
      case 'rate_limit_exceeded':
        message = "Daily limit reached (10 analyses). Please try again tomorrow.";
        icon = Icons.timer_outlined;
        break;
      default:
        message = "Something went wrong. Please try again.";
        icon = Icons.error_outline;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _T.pinkL,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.pink.withOpacity(0.3), width: 1.5),
      ),
      child: Column(
        children: [
          Icon(icon, color: _T.statusPink, size: 40),
          const SizedBox(height: 12),
          Text(
            message.contains('Exception:') ? message.replaceFirst('Exception: ', '') : message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: _T.statusPink, fontWeight: FontWeight.w800),
          ),
          if (icon == Icons.error_outline) ...[
             const SizedBox(height: 8),
             Text(errorType, style: const TextStyle(fontSize: 11, color: _T.inkMid, fontWeight: FontWeight.w600)),
          ]
        ],
      ),
    );
  }

  void _showHistoryBottomSheet(BuildContext context, AsyncValue<List<Map<String, dynamic>>> history) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.8,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => Container(
          decoration: const BoxDecoration(
            color: _T.canvas,
            borderRadius: BorderRadius.vertical(top: Radius.circular(30)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 12),
              Container(width: 40, height: 4, decoration: BoxDecoration(color: _T.rimLight, borderRadius: BorderRadius.circular(2))),
              const Padding(
                padding: EdgeInsets.fromLTRB(24, 24, 24, 12),
                child: Row(
                  children: [
                    Text('Analysis History', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: _T.ink)),
                  ],
                ),
              ),
              Expanded(
                child: history.when(
                  data: (list) {
                    if (list.isEmpty) {
                      return const Center(
                        child: Text(
                          'No previous analyses found.',
                          style: TextStyle(color: _T.inkMid, fontWeight: FontWeight.w600),
                        ),
                      );
                    }
                    return ListView.separated(
                      controller: scrollController,
                      padding: const EdgeInsets.fromLTRB(20, 10, 20, 30),
                      itemCount: list.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final item = list[index];
                        return Card(
                          elevation: 0,
                          color: _T.surface,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                            side: const BorderSide(color: _T.rimLight, width: 1.5),
                          ),
                          child: ListTile(
                            contentPadding: const EdgeInsets.all(12),
                            leading: ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: Image.network(item['imageUrl'], width: 60, height: 60, fit: BoxFit.cover),
                            ),
                            title: Text('Cake Design #${list.length - index}', style: const TextStyle(fontWeight: FontWeight.w800, color: _T.ink)),
                            subtitle: Text(
                              DateFormat('MMM dd, yyyy • hh:mm a').format((item['analyzedAt'] as Timestamp).toDate()),
                              style: const TextStyle(color: _T.inkMid, fontSize: 12, fontWeight: FontWeight.w600),
                            ),
                            trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: _T.brown),
                            onTap: () {
                              Navigator.pop(context);
                              _showAnalysisDetail(context, item);
                            },
                          ),
                        );
                      },
                    );
                  },
                  loading: () => const Center(child: CircularProgressIndicator(color: _T.brown)),
                  error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: _T.statusPink))),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showAnalysisDetail(BuildContext context, Map<String, dynamic> item) {
    showDialog(
      context: context,
      builder: (context) => Dialog.fullscreen(
        backgroundColor: _T.canvas,
        child: Scaffold(
          backgroundColor: _T.canvas,
          appBar: AppBar(
            backgroundColor: _T.canvas,
            title: const Text('Analysis Detail', style: TextStyle(fontWeight: FontWeight.w800, color: _T.brown, fontSize: 18)),
            leading: IconButton(icon: const Icon(Icons.close, color: _T.brown), onPressed: () => Navigator.pop(context)),
            elevation: 0,
          ),
          body: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            child: Column(
              children: [
                Hero(
                  tag: item['imageUrl'],
                  child: Image.network(item['imageUrl'], width: double.infinity, height: 350, fit: BoxFit.cover),
                ),
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: _AnalysisResultView(analysis: item),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AnalysisResultView extends StatelessWidget {
  final Map<String, dynamic> analysis;
  const _AnalysisResultView({required this.analysis});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            decoration: BoxDecoration(
              color: _T.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: _T.rimLight, width: 1.5),
              boxShadow: _T.shadowSm,
            ),
            child: TabBar(
              labelColor: _T.brown,
              unselectedLabelColor: _T.inkMid,
              indicatorColor: _T.brown,
              labelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
              unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
              indicatorSize: TabBarIndicatorSize.label,
              dividerColor: Colors.transparent,
              tabs: const [
                Tab(text: 'Steps'),
                Tab(text: 'Materials'),
                Tab(text: 'Details'),
              ],
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 400,
            child: TabBarView(
              children: [
                _buildListTab(analysis['steps'] ?? []),
                _buildListTab(analysis['tools_materials'] ?? []),
                _buildDetailsTab(context),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildListTab(List<dynamic> items) {
    return ListView.builder(
      physics: const BouncingScrollPhysics(),
      itemCount: items.length,
      itemBuilder: (context, index) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _T.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _T.rimLight, width: 1.5),
          boxShadow: _T.shadowSm,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: const BoxDecoration(
                color: _T.pinkL,
                shape: BoxShape.circle,
              ),
              child: Text(
                '${index + 1}', 
                style: const TextStyle(fontSize: 12, color: _T.statusPink, fontWeight: FontWeight.w800),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                items[index].toString(), 
                style: const TextStyle(height: 1.4, color: _T.ink, fontWeight: FontWeight.w600, fontSize: 13.5),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailsTab(BuildContext context) {
    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildDetailItem('Estimated Time', '${analysis['estimated_time_minutes']} mins', Icons.timer_outlined),
          _buildDetailItem('Visible Layers', '${analysis['layers']}', Icons.layers_outlined),
          _buildChipDetail('Colors Used', analysis['colors'] ?? []),
          _buildChipDetail('Piping Tips', analysis['piping_tips'] ?? []),
        ],
      ),
    );
  }

  Widget _buildDetailItem(String label, String value, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: _T.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _T.rimLight, width: 1.5),
        boxShadow: _T.shadowSm,
      ),
      child: ListTile(
        leading: Icon(icon, color: _T.brown),
        title: Text(label, style: const TextStyle(fontSize: 11, color: _T.inkMid, fontWeight: FontWeight.w600)),
        subtitle: Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: _T.ink)),
      ),
    );
  }

  Widget _buildChipDetail(String label, List<dynamic> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 14),
        Text(label, style: const TextStyle(fontSize: 12, color: _T.ink, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: items.map((item) => Chip(
            label: Text(item.toString()),
            backgroundColor: _T.pinkL,
            labelStyle: const TextStyle(color: _T.statusPink, fontSize: 12, fontWeight: FontWeight.w800),
            side: const BorderSide(color: _T.pink, width: 1),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          )).toList(),
        ),
      ],
    );
  }
}
