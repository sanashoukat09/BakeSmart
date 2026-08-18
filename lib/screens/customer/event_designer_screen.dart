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
  final _knownReference = TextEditingController();

  String _areaType = 'room';
  String _venueType = 'living_room';
  String _environment = 'indoor';
  String _eventType = 'birthday';
  String _themeId = 'floral-romantic';
  String _cakeShape = 'round';
  XFile? _cakeImage;
  Uint8List? _cakeImageBytes;
  Uint8List? _wideVenueImageBytes;
  VenuePhotoAnalysis? _wideVenueAnalysis;
  Uint8List? _secondVenueImageBytes;
  VenuePhotoAnalysis? _secondVenueAnalysis;
  bool _analysingWidePhoto = false;
  bool _analysingSecondPhoto = false;
  bool _obstacleMapConfirmed = false;
  final List<_ObstacleDraft> _obstacles = [];

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
      _knownReference,
    ]) {
      controller.dispose();
    }
    for (final obstacle in _obstacles) {
      obstacle.dispose();
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

  Future<void> _pickVenueImage(String angle) async {
    final image = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      imageQuality: 88,
      maxWidth: 2200,
    );
    if (image == null) return;
    final bytes = await image.readAsBytes();
    if (!mounted) return;
    setState(() {
      if (angle == 'wide') {
        _wideVenueImageBytes = bytes;
        _wideVenueAnalysis = null;
        _analysingWidePhoto = true;
      } else {
        _secondVenueImageBytes = bytes;
        _secondVenueAnalysis = null;
        _analysingSecondPhoto = true;
      }
    });
    try {
      final analysis = await ref.read(eventDesignServiceProvider).analyzeVenuePhoto(
            bytes: bytes,
            fileName: image.name,
            angle: angle,
          );
      if (!mounted) return;
      setState(() {
        if (angle == 'wide') {
          _wideVenueAnalysis = analysis;
        } else {
          _secondVenueAnalysis = analysis;
        }
      });
    } catch (error) {
      if (!mounted) return;
      _showMessage('Could not analyse the venue photo: $error');
    } finally {
      if (mounted) {
        setState(() {
          if (angle == 'wide') {
            _analysingWidePhoto = false;
          } else {
            _analysingSecondPhoto = false;
          }
        });
      }
    }
  }

  void _addObstacle() {
    if (_obstacles.length >= 10) {
      _showMessage('You can add up to 10 major obstacles in this form.');
      return;
    }
    setState(() {
      _obstacles.add(_ObstacleDraft());
      _obstacleMapConfirmed = false;
    });
  }

  void _removeObstacle(int index) {
    setState(() {
      _obstacles.removeAt(index).dispose();
      _obstacleMapConfirmed = false;
    });
  }

  Future<void> _generate() async {
    if (!_formKey.currentState!.validate()) return;
    if (_cakeImage == null) {
      _showMessage('Select a cake picture before generating the design.');
      return;
    }
    if (_wideVenueAnalysis == null) {
      _showMessage('Select and analyse a wide venue photo first.');
      return;
    }
    if (!_obstacleMapConfirmed) {
      _showMessage(
        'Confirm that all visible obstacles are listed, including doors and walkways.',
      );
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
      venuePhotos: [
        _wideVenueAnalysis!,
        if (_secondVenueAnalysis != null) _secondVenueAnalysis!,
      ],
      obstacles: _obstacles.map((draft) => draft.toModel()).toList(),
      obstacleMapConfirmed: _obstacleMapConfirmed,
      knownReferenceM: _optionalDouble(_knownReference.text),
      minimumClearanceM: 0.9,
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

  static double? _optionalDouble(String input) {
    final normalized = input.trim();
    return normalized.isEmpty ? null : double.parse(normalized);
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
              title: 'Venue photos and safety map',
              subtitle: 'Photos are analysed locally and are not retained.',
              children: [
                _venuePhotoPicker(
                  title: 'Wide venue photo (required)',
                  subtitle: 'Show the main wall, floor, doors and nearby furniture.',
                  bytes: _wideVenueImageBytes,
                  analysis: _wideVenueAnalysis,
                  analysing: _analysingWidePhoto,
                  onTap: () => _pickVenueImage('wide'),
                ),
                _venuePhotoPicker(
                  title: 'Second angle (recommended)',
                  subtitle: 'Reduces blind spots outside the first photo.',
                  bytes: _secondVenueImageBytes,
                  analysis: _secondVenueAnalysis,
                  analysing: _analysingSecondPhoto,
                  onTap: () => _pickVenueImage('second_angle'),
                ),
                _optionalDecimalField(
                  'Known reference length (m)',
                  _knownReference,
                  0.01,
                  20,
                  hint: 'Example: measured table width 1.5',
                ),
                const Text(
                  'Obstacle coordinates use the left side of the setup as x = 0 '
                  'and the focal wall as y = 0.',
                  style: TextStyle(color: Color(0xFF8C6D5F), fontSize: 12),
                ),
                ...List.generate(
                  _obstacles.length,
                  (index) => _obstacleEditor(index, _obstacles[index]),
                ),
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton.icon(
                    onPressed: _addObstacle,
                    icon: const Icon(Icons.add),
                    label: const Text('Add door, furniture or obstacle'),
                  ),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _obstacleMapConfirmed,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: const Text(
                    'I listed all visible obstacles and required walkways',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: const Text(
                    'Tick this even when the measured setup area has no obstacles.',
                  ),
                  onChanged: (value) => setState(
                    () => _obstacleMapConfirmed = value ?? false,
                  ),
                ),
                const Text(
                  'BakeSmart will preserve at least 0.90 m of front circulation. '
                  'The photo alone is never used to claim exact scale.',
                  style: TextStyle(color: Color(0xFF8C6D5F), height: 1.4),
                ),
              ],
            ),
            _section(
              icon: Icons.cake_outlined,
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

  Widget _venuePhotoPicker({
    required String title,
    required String subtitle,
    required Uint8List? bytes,
    required VenuePhotoAnalysis? analysis,
    required bool analysing,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: analysing ? null : onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFF7FBF7),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFCFE5D5)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 88,
              height: 78,
              clipBehavior: Clip.antiAlias,
              decoration: BoxDecoration(
                color: const Color(0xFFE7F2EA),
                borderRadius: BorderRadius.circular(10),
              ),
              child: bytes == null
                  ? const Icon(Icons.add_a_photo_outlined, color: _brown)
                  : Image.memory(bytes, fit: BoxFit.cover),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: _ink,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    analysing
                        ? 'Analysing pixels locally…'
                        : analysis == null
                            ? subtitle
                            : '${analysis.pixelWidth} × ${analysis.pixelHeight} • '
                                '${analysis.quality} quality',
                    style: const TextStyle(
                      color: Color(0xFF8C6D5F),
                      fontSize: 12,
                      height: 1.35,
                    ),
                  ),
                  if (analysing) ...[
                    const SizedBox(height: 8),
                    const LinearProgressIndicator(minHeight: 3),
                  ] else if (analysis != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      analysis.observations.take(2).join(' '),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Color(0xFF287A50),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              analysis == null ? Icons.chevron_right : Icons.check_circle,
              color: analysis == null ? _brown : const Color(0xFF287A50),
            ),
          ],
        ),
      ),
    );
  }

  Widget _obstacleEditor(int index, _ObstacleDraft draft) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF9F2),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFF2E0CC)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Obstacle ${index + 1}',
                  style: const TextStyle(
                    color: _ink,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Remove obstacle',
                onPressed: () => _removeObstacle(index),
                icon: const Icon(Icons.delete_outline),
              ),
            ],
          ),
          _dropdown(
            'Type',
            draft.type,
            EventDesignOptions.obstacleTypes,
            (value) => setState(() {
              draft.type = value;
              _obstacleMapConfirmed = false;
            }),
          ),
          _textField(
            'Label',
            draft.label,
            hint: 'Example: main door',
            onChanged: (_) => setState(() => _obstacleMapConfirmed = false),
          ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _decimalField(
                  'X',
                  draft.x,
                  0,
                  100,
                  onChanged: (_) =>
                      setState(() => _obstacleMapConfirmed = false),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _decimalField(
                  'Y',
                  draft.y,
                  0,
                  100,
                  onChanged: (_) =>
                      setState(() => _obstacleMapConfirmed = false),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _decimalField(
                  'Z',
                  draft.z,
                  0,
                  30,
                  onChanged: (_) =>
                      setState(() => _obstacleMapConfirmed = false),
                ),
              ),
            ],
          ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _decimalField(
                  'Width',
                  draft.width,
                  0.01,
                  100,
                  onChanged: (_) =>
                      setState(() => _obstacleMapConfirmed = false),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _decimalField(
                  'Depth',
                  draft.depth,
                  0.01,
                  100,
                  onChanged: (_) =>
                      setState(() => _obstacleMapConfirmed = false),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _decimalField(
                  'Height',
                  draft.height,
                  0.01,
                  30,
                  onChanged: (_) =>
                      setState(() => _obstacleMapConfirmed = false),
                ),
              ),
            ],
          ),
        ],
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
    ValueChanged<String>? onChanged,
  }) {
    return TextFormField(
      controller: controller,
      decoration: _decoration(label, hint: hint),
      onChanged: onChanged,
    );
  }

  Widget _decimalField(
    String label,
    TextEditingController controller,
    double minimum,
    double maximum, {
    ValueChanged<String>? onChanged,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: _decoration('$label (m)'),
      onChanged: onChanged,
      validator: (value) {
        final number = double.tryParse(value?.trim() ?? '');
        if (number == null || number < minimum || number > maximum) {
          return '$minimum–$maximum';
        }
        return null;
      },
    );
  }

  Widget _optionalDecimalField(
    String label,
    TextEditingController controller,
    double minimum,
    double maximum, {
    String? hint,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: _decoration(label, hint: hint),
      validator: (value) {
        final text = value?.trim() ?? '';
        if (text.isEmpty) return null;
        final number = double.tryParse(text);
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

class _ObstacleDraft {
  String type = 'door';
  final label = TextEditingController();
  final x = TextEditingController(text: '0.0');
  final y = TextEditingController(text: '0.0');
  final z = TextEditingController(text: '0.0');
  final width = TextEditingController(text: '0.9');
  final depth = TextEditingController(text: '0.2');
  final height = TextEditingController(text: '2.1');

  VenueObstacle toModel() {
    return VenueObstacle(
      type: type,
      label: label.text.trim(),
      xM: double.parse(x.text.trim()),
      yM: double.parse(y.text.trim()),
      zM: double.parse(z.text.trim()),
      widthM: double.parse(width.text.trim()),
      depthM: double.parse(depth.text.trim()),
      heightM: double.parse(height.text.trim()),
    );
  }

  void dispose() {
    label.dispose();
    x.dispose();
    y.dispose();
    z.dispose();
    width.dispose();
    depth.dispose();
    height.dispose();
  }
}
