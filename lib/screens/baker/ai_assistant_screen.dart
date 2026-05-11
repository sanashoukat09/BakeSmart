import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/ai_provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/product_provider.dart';
import '../../core/theme/baker_theme.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';

class AiColors {
  static const Color primary = Color(0xFF3D1A0E); // Matching Dashboard Espresso
  static const Color accent = Color(0xFFC49A7A); // Matching Dashboard Tan
  static const Color surface = Color(0xFFFDFCF9); // Native Baker Cream
  static const Color card = Colors.white;
  static const Color text = Color(0xFF3D1A0E); 
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
        content: Text(message, style: const TextStyle(color: Colors.white)),
        backgroundColor: AiColors.primary,
        behavior: SnackBarBehavior.floating,
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
      // 1. Upload to Cloudinary using existing Service
      final cloudinary = ref.read(cloudinaryServiceProvider);
      final imageUrl = await cloudinary.uploadImage(
        imageFile: _selectedImage!,
        folder: 'bakesmart/photo_analysis',
      );

      // 2. Call AI Analysis directly from Flutter
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
        title: const Text('AI Photo Assistant', style: TextStyle(color: AiColors.primary, fontWeight: FontWeight.bold)),
        backgroundColor: BakerTheme.background,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.history, color: AiColors.primary),
            onPressed: () => _showHistoryBottomSheet(context, historyAsync),
          ),
        ],
      ),
      backgroundColor: BakerTheme.background,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(),
            const SizedBox(height: 24),
            _buildImagePicker(),
            const SizedBox(height: 30),
            _buildAnalyzeButton(aiState.isLoading || _isUploading),
            const SizedBox(height: 30),
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
                color: AiColors.primary.withOpacity(0.08),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(Icons.auto_awesome_rounded, color: AiColors.primary, size: 28),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Cake Design Analyzer',
                    style: TextStyle(
                      color: AiColors.primary,
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.5,
                    ),
                  ),
                  Text(
                    'Powered by Gemini AI',
                    style: TextStyle(
                      color: AiColors.accent,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Text(
          'Upload a photo to automatically extract decoration steps, ingredients, and professional baking tips.',
          style: TextStyle(
            color: BakerTheme.textSecondary.withOpacity(0.8),
            fontSize: 14,
            height: 1.5,
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
          color: BakerTheme.cardColor,
          borderRadius: BorderRadius.circular(24),
          boxShadow: [
            BoxShadow(
              color: BakerTheme.primary.withOpacity(0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
          border: Border.all(
            color: BakerTheme.divider,
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
                        icon: const Icon(Icons.close, color: AiColors.primary),
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
                    decoration: BoxDecoration(
                      color: AiColors.primary.withOpacity(0.08),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.add_a_photo_rounded,
                        size: 40, color: AiColors.primary),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Select Cake Photo',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AiColors.primary),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'JPG, PNG, WEBP (Max 5MB)',
                    style: TextStyle(color: BakerTheme.textMuted, fontSize: 12),
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
              leading: const Icon(Icons.photo_library),
              title: const Text('Gallery'),
              onTap: () {
                Navigator.pop(context);
                _pickImage(ImageSource.gallery);
              },
            ),
            ListTile(
              leading: const Icon(Icons.camera_alt),
              title: const Text('Camera'),
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
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          if (!isLoading)
            BoxShadow(
              color: AiColors.primary.withOpacity(0.3),
              blurRadius: 15,
              offset: const Offset(0, 5),
            ),
        ],
      ),
      child: ElevatedButton(
        onPressed: isLoading ? null : _analyze,
        style: ElevatedButton.styleFrom(
          backgroundColor: AiColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 18),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
        child: isLoading
            ? const SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.auto_awesome, size: 20),
                  SizedBox(width: 12),
                  Text('Analyze Cake Design', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
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
              CircularProgressIndicator(color: AiColors.primary),
              SizedBox(height: 20),
              Text('Gemini AI is analyzing your design...', 
                style: TextStyle(fontWeight: FontWeight.w600, color: BakerTheme.textPrimary)),
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
        color: BakerTheme.error.withOpacity(0.05),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: BakerTheme.error.withOpacity(0.2)),
      ),
      child: Column(
        children: [
          Icon(icon, color: BakerTheme.error, size: 40),
          const SizedBox(height: 12),
          Text(
            message.contains('Exception:') ? message.replaceFirst('Exception: ', '') : message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: BakerTheme.error, fontWeight: FontWeight.bold),
          ),
          if (icon == Icons.error_outline) ...[
             const SizedBox(height: 8),
             Text(errorType, style: TextStyle(fontSize: 10, color: BakerTheme.error.withOpacity(0.5))),
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
            color: BakerTheme.background,
            borderRadius: BorderRadius.vertical(top: Radius.circular(30)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 12),
              Container(width: 40, height: 4, decoration: BoxDecoration(color: AiColors.primary.withOpacity(0.2), borderRadius: BorderRadius.circular(2))),
              Padding(
                padding: const EdgeInsets.all(24),
                child: Row(
                  children: [
                    const Text('Analysis History', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: BakerTheme.textPrimary)),
                  ],
                ),
              ),
              Expanded(
                child: history.when(
                  data: (list) {
                    if (list.isEmpty) return const Center(child: Text('No previous analyses found.'));
                    return ListView.separated(
                      controller: scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      itemCount: list.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final item = list[index];
                        return Card(
                          elevation: 0,
                          color: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                            side: BorderSide(color: AiColors.primary.withOpacity(0.05)),
                          ),
                          child: ListTile(
                            contentPadding: const EdgeInsets.all(12),
                            leading: ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: Image.network(item['imageUrl'], width: 60, height: 60, fit: BoxFit.cover),
                            ),
                            title: Text('Cake Design #${list.length - index}', style: const TextStyle(fontWeight: FontWeight.bold, color: BakerTheme.textPrimary)),
                            subtitle: Text(
                              DateFormat('MMM dd, yyyy • hh:mm a').format((item['analyzedAt'] as Timestamp).toDate()),
                              style: const TextStyle(color: BakerTheme.textSecondary, fontSize: 12),
                            ),
                            trailing: const Icon(Icons.arrow_forward_ios, size: 14, color: AiColors.primary),
                            onTap: () {
                              Navigator.pop(context);
                              _showAnalysisDetail(context, item);
                            },
                          ),
                        );
                      },
                    );
                  },
                  loading: () => const Center(child: CircularProgressIndicator(color: AiColors.primary)),
                  error: (e, _) => Center(child: Text('Error: $e')),
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
        backgroundColor: BakerTheme.background,
        child: Scaffold(
          backgroundColor: BakerTheme.background,
          appBar: AppBar(
            backgroundColor: BakerTheme.background,
            title: const Text('Analysis Detail'),
            leading: IconButton(icon: const Icon(Icons.close, color: AiColors.primary), onPressed: () => Navigator.pop(context)),
          ),
          body: SingleChildScrollView(
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
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: BakerTheme.divider),
            ),
            child: TabBar(
              labelColor: AiColors.primary,
              unselectedLabelColor: Colors.grey,
              indicatorColor: AiColors.primary,
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
      itemCount: items.length,
      itemBuilder: (context, index) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AiColors.primary.withOpacity(0.05)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AiColors.primary.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Text('${index + 1}', style: const TextStyle(fontSize: 12, color: AiColors.primary, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(items[index].toString(), style: const TextStyle(height: 1.4, color: BakerTheme.textPrimary))),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailsTab(BuildContext context) {
    return SingleChildScrollView(
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
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AiColors.primary.withOpacity(0.05)),
      ),
      child: ListTile(
        leading: Icon(icon, color: AiColors.primary),
        title: Text(label, style: const TextStyle(fontSize: 12, color: BakerTheme.textSecondary)),
        subtitle: Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: BakerTheme.textPrimary)),
      ),
    );
  }

  Widget _buildChipDetail(String label, List<dynamic> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 12),
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: items.map((item) => Chip(
            label: Text(item.toString()),
            backgroundColor: AiColors.primary.withOpacity(0.05),
            labelStyle: const TextStyle(color: AiColors.primary, fontSize: 12, fontWeight: FontWeight.bold),
            side: BorderSide(color: AiColors.primary.withOpacity(0.1)),
          )).toList(),
        ),
      ],
    );
  }
}
