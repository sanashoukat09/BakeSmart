import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/router/app_router.dart';
import '../../models/event_design_model.dart';
import '../../providers/auth_provider.dart';
import '../../providers/event_design_provider.dart';

class EventDesignerScreen extends ConsumerStatefulWidget {
  const EventDesignerScreen({super.key});

  @override
  ConsumerState<EventDesignerScreen> createState() =>
      _EventDesignerScreenState();
}

class _EventDesignerScreenState extends ConsumerState<EventDesignerScreen> {
  static const _brown = Color(0xFFB05E27);
  static const _ink = Color(0xFF4A2B20);
  static const _canvas = Color(0xFFFFFDF8);

  final _formKey = GlobalKey<FormState>();
  final _width = TextEditingController(text: '3.0');
  final _depth = TextEditingController(text: '2.4');
  final _height = TextEditingController(text: '2.7');
  final _guestCount = TextEditingController(text: '35');
  final _budget = TextEditingController(text: '50000');
  final _tiers = TextEditingController(text: '2');
  final _servings = TextEditingController(text: '41');
  final _cakeWidth = TextEditingController(text: '0.30');
  final _cakeDepth = TextEditingController(text: '0.30');
  final _cakeHeight = TextEditingController(text: '0.35');
  final _colors = TextEditingController(text: 'blush pink, cream, muted gold');

  String _areaType = 'room';
  String _venueType = 'living_room';
  String _environment = 'indoor';
  String _eventType = 'birthday';
  String _themeId = 'floral-romantic';
  String _cakeShape = 'round';
  XFile? _cakeImage;
  Uint8List? _cakeImageBytes;

  bool get _requiresDepth => _areaType != 'wall';

  @override
  void dispose() {
    for (final controller in [
      _width,
      _depth,
      _height,
      _guestCount,
      _budget,
      _tiers,
      _servings,
      _cakeWidth,
      _cakeDepth,
      _cakeHeight,
      _colors,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _pickCakeImage() async {
    final image = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      imageQuality: 85,
      maxWidth: 1800,
    );
    if (image == null) return;
    final bytes = await image.readAsBytes();
    if (!mounted) return;
    setState(() {
      _cakeImage = image;
      _cakeImageBytes = bytes;
    });
  }

  Future<void> _generate() async {
    if (!_formKey.currentState!.validate()) return;
    if (_cakeImage == null) {
      _showMessage('Select a cake picture before generating the design.');
      return;
    }
    final user = ref.read(currentUserProvider).valueOrNull;
    if (user == null) {
      _showMessage('Your customer account is not ready. Please sign in again.');
      return;
    }

    final request = EventDesignRequest(
      customerId: user.uid,
      areaType: _areaType,
      venueType: _venueType,
      environment: _environment,
      widthM: double.parse(_width.text.trim()),
      depthM: _requiresDepth ? double.parse(_depth.text.trim()) : null,
      heightM: double.parse(_height.text.trim()),
      eventType: _eventType,
      guestCount: int.parse(_guestCount.text.trim()),
      themeId: _themeId,
      preferredColors: _parseColors(_colors.text),
      cakeImageReference: _safeImageReference(_cakeImage!.name),
      cakeShape: _cakeShape,
      cakeTiers: int.parse(_tiers.text.trim()),
      servingsRequired: int.parse(_servings.text.trim()),
      cakeWidthM: double.parse(_cakeWidth.text.trim()),
      cakeDepthM: double.parse(_cakeDepth.text.trim()),
      cakeHeightM: double.parse(_cakeHeight.text.trim()),
      decorationBudgetPkr: int.parse(_budget.text.trim()),
    );
    final recommendation = await ref
        .read(eventDesignNotifierProvider.notifier)
        .generate(request);
    if (!mounted) return;
    if (recommendation == null) {
      final failure = ref.read(eventDesignNotifierProvider);
      _showMessage(failure.error?.toString() ?? 'Could not create the design.');
      return;
    }
    context.push(
      AppRoutes.customerEventDesignResult,
      extra: EventDesignResultArgs(
        request: request,
        recommendation: recommendation,
      ),
    );
  }

  static List<String> _parseColors(String input) {
    return input
        .split(',')
        .map((value) => value
            .trim()
            .toLowerCase()
            .replaceAll(RegExp(r'[^a-z0-9]+'), '-'))
        .where((value) => value.isNotEmpty)
        .take(8)
        .toList(growable: false);
  }

  static String _safeImageReference(String fileName) {
    final cleaned = fileName
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9._-]+'), '-');
    return 'customer-cake-${DateTime.now().millisecondsSinceEpoch}-$cleaned';
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final generation = ref.watch(eventDesignNotifierProvider);
    return Scaffold(
      backgroundColor: _canvas,
      appBar: AppBar(
        title: const Text('3D Event Designer'),
        backgroundColor: _canvas,
        foregroundColor: _ink,
        elevation: 0,
        actions: [
          TextButton.icon(
            onPressed: () => context.push(AppRoutes.customerSavedEventDesigns),
            icon: const Icon(Icons.bookmark_outline),
            label: const Text('Saved'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
          children: [
            _introCard(),
            const SizedBox(height: 18),
            _section(
              icon: Icons.photo_camera_back_outlined,
              title: 'Cake picture',
              subtitle: 'Used as a design reference for the procedural cake.',
              children: [_imagePicker()],
            ),
            _section(
              icon: Icons.meeting_room_outlined,
              title: 'Space and location',
              subtitle: 'Enter measured dimensions in metres.',
              children: [
                _dropdown('Area to decorate', _areaType,
                    EventDesignOptions.areaTypes, (value) {
                  setState(() => _areaType = value);
                }),
                _dropdown('Venue', _venueType, EventDesignOptions.venueTypes,
                    (value) => setState(() => _venueType = value)),
                _dropdown(
                  'Environment',
                  _environment,
                  EventDesignOptions.environments,
                  (value) => setState(() => _environment = value),
                ),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: _decimalField('Width', _width, 0.1, 100)),
                    if (_requiresDepth) ...[
                      const SizedBox(width: 12),
                      Expanded(
                        child: _decimalField('Depth', _depth, 0.1, 100),
                      ),
                    ],
                    const SizedBox(width: 12),
                    Expanded(child: _decimalField('Height', _height, 0.1, 30)),
                  ],
                ),
              ],
            ),
            _section(
              icon: Icons.celebration_outlined,
              title: 'Event and theme',
              subtitle: 'Choose the style and decoration budget.',
              children: [
                _dropdown('Event type', _eventType, EventDesignOptions.eventTypes,
                    (value) => setState(() => _eventType = value)),
                _dropdown('Theme', _themeId, EventDesignOptions.themes,
                    (value) => setState(() => _themeId = value)),
                Row(
                  children: [
                    Expanded(
                      child: _integerField('Guests', _guestCount, 1, 10000),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _integerField(
                        'Decor budget (PKR)',
                        _budget,
                        1,
                        100000000,
                      ),
                    ),
                  ],
                ),
                _textField(
                  'Preferred colors',
                  _colors,
                  hint: 'blush pink, cream, muted gold',
                ),
              ],
            ),
            _section(
              icon: Icons.cake_outlined,
              title: 'Cake details',
              subtitle: 'These dimensions create the placeholder cake geometry.',
              children: [
                _dropdown('Cake shape', _cakeShape,
                    EventDesignOptions.cakeShapes, (value) {
                  setState(() => _cakeShape = value);
                }),
                Row(
                  children: [
                    Expanded(child: _integerField('Tiers', _tiers, 1, 10)),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _integerField('Servings', _servings, 1, 2000),
                    ),
                  ],
                ),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _decimalField(
                        _cakeShape == 'round' ? 'Diameter' : 'Width',
                        _cakeWidth,
                        0.02,
                        3,
                      ),
                    ),
                    if (_cakeShape != 'round') ...[
                      const SizedBox(width: 12),
                      Expanded(
                        child: _decimalField('Depth', _cakeDepth, 0.02, 3),
                      ),
                    ],
                    const SizedBox(width: 12),
                    Expanded(
                      child: _decimalField('Height', _cakeHeight, 0.02, 3),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 6),
            SizedBox(
              height: 54,
              child: FilledButton.icon(
                onPressed: generation.isLoading ? null : _generate,
                style: FilledButton.styleFrom(
                  backgroundColor: _brown,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                icon: generation.isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.threed_rotation),
                label: Text(
                  generation.isLoading
                      ? 'Building combined scene…'
                      : 'Generate 3D design',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _introCard() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF4A2B20), Color(0xFFB05E27)],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'See the cake and decorations together',
            style: TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          SizedBox(height: 8),
          Text(
            'BakeSmart uses its local trained model and procedural 3D renderer. '
            'No AR service is required.',
            style: TextStyle(color: Color(0xFFFFE8D5), height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _section({
    required IconData icon,
    required String title,
    required String subtitle,
    required List<Widget> children,
  }) {
    return Padding(
      padding: const EdgeInsets.only(top: 22),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFFF2EAE0)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: _brown),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: _ink,
                          fontSize: 17,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        subtitle,
                        style: const TextStyle(
                          color: Color(0xFF8C6D5F),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...children.map(
              (child) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: child,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _imagePicker() {
    return InkWell(
      onTap: _pickCakeImage,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        height: 160,
        width: double.infinity,
        decoration: BoxDecoration(
          color: const Color(0xFFFFF4F5),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFFFC5CF)),
        ),
        clipBehavior: Clip.antiAlias,
        child: _cakeImageBytes == null
            ? const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.add_photo_alternate_outlined,
                      size: 38, color: _brown),
                  SizedBox(height: 8),
                  Text(
                    'Select cake picture',
                    style: TextStyle(color: _ink, fontWeight: FontWeight.w800),
                  ),
                  Text(
                    'JPG or PNG from your device',
                    style: TextStyle(color: Color(0xFF8C6D5F), fontSize: 12),
                  ),
                ],
              )
            : Stack(
                fit: StackFit.expand,
                children: [
                  Image.memory(_cakeImageBytes!, fit: BoxFit.cover),
                  Positioned(
                    right: 10,
                    bottom: 10,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.65),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Text(
                        'Change picture',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _dropdown(
    String label,
    String value,
    List<EventDesignOption> options,
    ValueChanged<String> onChanged,
  ) {
    return DropdownButtonFormField<String>(
      value: value,
      isExpanded: true,
      decoration: _decoration(label),
      items: options
          .map(
            (option) => DropdownMenuItem(
              value: option.value,
              child: Text(option.label, overflow: TextOverflow.ellipsis),
            ),
          )
          .toList(growable: false),
      onChanged: (next) {
        if (next != null) onChanged(next);
      },
    );
  }

  Widget _textField(
    String label,
    TextEditingController controller, {
    String? hint,
  }) {
    return TextFormField(
      controller: controller,
      decoration: _decoration(label, hint: hint),
    );
  }

  Widget _decimalField(
    String label,
    TextEditingController controller,
    double minimum,
    double maximum,
  ) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: _decoration('$label (m)'),
      validator: (value) {
        final number = double.tryParse(value?.trim() ?? '');
        if (number == null || number < minimum || number > maximum) {
          return '$minimum–$maximum';
        }
        return null;
      },
    );
  }

  Widget _integerField(
    String label,
    TextEditingController controller,
    int minimum,
    int maximum,
  ) {
    return TextFormField(
      controller: controller,
      keyboardType: TextInputType.number,
      decoration: _decoration(label),
      validator: (value) {
        final number = int.tryParse(value?.trim() ?? '');
        if (number == null || number < minimum || number > maximum) {
          return '$minimum–$maximum';
        }
        return null;
      },
    );
  }

  InputDecoration _decoration(String label, {String? hint}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      filled: true,
      fillColor: const Color(0xFFFFFDF8),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFF2EAE0)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFF2EAE0)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _brown, width: 1.5),
      ),
    );
  }
}
