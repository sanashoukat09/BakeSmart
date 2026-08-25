import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../models/device_capability_model.dart';
import '../../models/event_design_model.dart';
import '../../providers/device_capability_provider.dart';
import '../../providers/event_design_provider.dart';

class EventDesignResultScreen extends ConsumerStatefulWidget {
  final EventDesignResultArgs args;

  const EventDesignResultScreen({super.key, required this.args});

  @override
  ConsumerState<EventDesignResultScreen> createState() =>
      _EventDesignResultScreenState();
}

class _EventDesignResultScreenState
    extends ConsumerState<EventDesignResultScreen> {
  static const _brown = Color(0xFFB05E27);
  static const _ink = Color(0xFF4A2B20);
  static const _muted = Color(0xFF8C6D5F);
  static const _canvas = Color(0xFFFFFDF8);

  late EventDesignRecommendation _recommendation;
  bool _saving = false;
  bool _regenerating = false;

  @override
  void initState() {
    super.initState();
    _recommendation = widget.args.recommendation;
  }

  Future<void> _openViewer() async {
    try {
      await ref
          .read(eventDesignServiceProvider)
          .openViewer(_recommendation);
    } catch (error) {
      if (mounted) _message(error.toString());
    }
  }

  Future<void> _openPhotoPreview(EventDesignPackage package) async {
    final path = package.photoPreviewPath;
    if (path == null) {
      _message(
        'This temporary photo preview is unavailable. Reanalyse the photos and generate again.',
      );
      return;
    }
    try {
      final opened =
          await ref.read(eventDesignServiceProvider).openResource(path);
      if (!opened && mounted) {
        _message('The photo-based concept preview could not be opened.');
      }
    } catch (error) {
      if (mounted) _message(error.toString());
    }
  }

  Future<void> _openPreview(EventPreviewDecision decision) async {
    final path = decision.resourcePath;
    if (path == null) {
      _message(decision.label);
      return;
    }
    try {
      final opened =
          await ref.read(eventDesignServiceProvider).openResource(path);
      if (!opened && mounted) {
        _message('${decision.label} could not be opened on this device.');
      }
    } catch (error) {
      if (mounted) _message(error.toString());
    }
  }

  Future<SavedEventDesign?> _save({bool showConfirmation = true}) async {
    setState(() => _saving = true);
    try {
      final saved = await ref.read(eventDesignServiceProvider).saveDesign(
            request: widget.args.request,
            recommendation: _recommendation,
          );
      if (mounted && showConfirmation) {
        _message('Design saved to your BakeSmart account.');
      }
      return saved;
    } catch (error) {
      if (mounted) _message('Could not save this design: $error');
      return null;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _share() async {
    EventDesignPackage? recommendedPackage;
    for (final package in _recommendation.packages) {
      if (package.recommended) {
        recommendedPackage = package;
        break;
      }
    }
    final photoPath = recommendedPackage?.photoPreviewPath;
    final viewerPath = _recommendation.viewerPath;
    final resourcePath = photoPath ?? viewerPath;
    if (resourcePath == null) {
      _message(_recommendation.fallbackLabel ??
          'Concept preview—not to scale. A shareable preview is unavailable.');
      return;
    }
    final saved = await _save(showConfirmation: false);
    if (saved == null || !mounted) return;
    try {
      final service = ref.read(eventDesignServiceProvider);
      final renderObject = context.findRenderObject();
      final renderBox = renderObject is RenderBox ? renderObject : null;
      final shared = await ShareUtil.shareEventDesign(
        themeName: _recommendation.themeLabel,
        designId: _recommendation.designId,
        previewUrl: service.absoluteResourceUri(resourcePath).toString(),
        previewLabel: photoPath == null
            ? 'Open Basic 3D Layout Preview'
            : 'Open Photo-Based Preview',
        sharePositionOrigin: renderBox == null
            ? null
            : renderBox.localToGlobal(Offset.zero) & renderBox.size,
      );
      if (shared) await service.markShared(saved);
    } catch (error) {
      if (mounted) _message('Could not share this design: $error');
    }
  }

  Future<void> _regenerate() async {
    setState(() => _regenerating = true);
    final refreshed = await ref
        .read(eventDesignNotifierProvider.notifier)
        .generate(widget.args.request);
    if (!mounted) return;
    setState(() => _regenerating = false);
    if (refreshed == null) {
      final failure = ref.read(eventDesignNotifierProvider);
      _message(failure.error?.toString() ?? 'Could not regenerate the design.');
      return;
    }
    setState(() => _recommendation = refreshed);
    await _save(showConfirmation: false);
    if (mounted) {
      _message('The interactive scene was regenerated and saved.');
    }
  }

  void _message(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final money = NumberFormat.decimalPattern();
    final capabilities = ref.watch(deviceCapabilitiesProvider);
    return Scaffold(
      backgroundColor: _canvas,
      appBar: AppBar(
        backgroundColor: _canvas,
        foregroundColor: _ink,
        elevation: 0,
        title: const Text('Your Design Options'),
        actions: [
          IconButton(
            tooltip: 'Saved designs',
            onPressed: () => context.push(AppRoutes.customerSavedEventDesigns),
            icon: const Icon(Icons.bookmarks_outlined),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
        children: [
          _hero(),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: _stat(
                  'Decorations',
                  'PKR ${money.format(_recommendation.decorationCostPkr)}',
                  Icons.auto_awesome_outlined,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _stat(
                  'Budget left',
                  'PKR ${money.format(_recommendation.remainingBudgetPkr)}',
                  Icons.account_balance_wallet_outlined,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _stat(
            'Cake planning estimate',
            'PKR ${money.format(_recommendation.cakeCostPkr)}',
            Icons.cake_outlined,
          ),
          const SizedBox(height: 18),
          if (_recommendation.packages.isNotEmpty) ...[
            _packageOptions(money),
            const SizedBox(height: 18),
          ],
          _deviceCompatibilityCard(capabilities),
          const SizedBox(height: 12),
          if (_recommendation.venueAssessment != null) ...[
            _venueAssessmentCard(_recommendation.venueAssessment!),
            const SizedBox(height: 12),
          ],
          _actionButtons(capabilities),
          const SizedBox(height: 22),
          _detailsCard(
            title: 'Top recommended package details',
            icon: Icons.celebration_outlined,
            child: _recommendation.decorations.isEmpty
                ? const Text('No decoration package was selected.')
                : Column(
                    children: _recommendation.decorations
                        .map(
                          (decoration) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const CircleAvatar(
                              backgroundColor: Color(0xFFFFF0E4),
                              foregroundColor: _brown,
                              child: Icon(Icons.local_florist_outlined),
                            ),
                            title: Text(
                              decoration.name,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w800),
                            ),
                            subtitle: Text(
                              '${decoration.category} • Quantity ${decoration.quantity}',
                            ),
                            trailing: Text(
                              'PKR ${money.format(decoration.unitCostPkr * decoration.quantity)}',
                              style: const TextStyle(
                                color: _brown,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                        )
                        .toList(growable: false),
                  ),
          ),
          const SizedBox(height: 16),
          _detailsCard(
            title: 'Important preview notes',
            icon: Icons.info_outline,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _recommendation.venueAssessment?.clearanceVerified == true &&
                          _recommendation.venueAssessment?.scaleSource ==
                              'user_confirmed_measurements'
                      ? 'The photo previews use your real venue and cake pictures. They '
                          'are visual concepts, not scale-accurate installation plans. '
                          'The Basic 3D preview remains a measured placeholder layout.'
                      : 'The photo previews use your real venue and cake pictures, but '
                          'remain Concept previews—not to scale. Recheck all physical '
                          'clearances before installation.',
                  style: const TextStyle(color: _muted, height: 1.45),
                ),
                const SizedBox(height: 10),
                const Text(
                  'Stage 1 does not include photorealistic 3D catalogue assets. '
                  'The Basic 3D Layout Preview uses placeholders; real GLB decor '
                  'assets and material textures belong to Stage 2.',
                  style: TextStyle(color: _muted, height: 1.45),
                ),
                if (_recommendation.warnings.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  ..._recommendation.warnings.map(
                    (warning) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Padding(
                            padding: EdgeInsets.only(top: 3),
                            child: Icon(Icons.circle, size: 7, color: _brown),
                          ),
                          const SizedBox(width: 9),
                          Expanded(
                            child: Text(
                              warning,
                              style: const TextStyle(color: _muted, height: 1.35),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _hero() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF4A2B20), Color(0xFFB05E27)],
        ),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              _recommendation.modelVersion,
              style: const TextStyle(color: Colors.white, fontSize: 12),
            ),
          ),
          const SizedBox(height: 14),
          Text(
            _recommendation.themeLabel,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 25,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Three varied decoration packages using your venue and cake photos',
            style: TextStyle(color: Color(0xFFFFE8D5), height: 1.4),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: const [
              _Badge(label: 'Real-photo preview'),
              _Badge(label: '3 varied packages'),
              _Badge(label: 'Local processing'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _packageOptions(NumberFormat money) {
    final packages = [..._recommendation.packages]
      ..sort((left, right) {
        if (left.recommended == right.recommended) return 0;
        return left.recommended ? -1 : 1;
      });
    return _detailsCard(
      title: 'Choose a decoration direction',
      icon: Icons.photo_library_outlined,
      child: Column(
        children: packages.map((package) {
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: package.recommended
                  ? const Color(0xFFFFF3E8)
                  : Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: package.recommended
                    ? _brown
                    : const Color(0xFFE8DDD6),
              ),
            ),
            child: ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              initiallyExpanded: package.recommended,
              title: Row(
                children: [
                  Expanded(
                    child: Text(
                      package.name,
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                  ),
                  if (package.recommended)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: _brown,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: const Text(
                        'Top pick',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                ],
              ),
              subtitle: Text(
                '${package.decorations.length} decor types • PKR ${money.format(package.totalCostPkr)} total',
                style: const TextStyle(color: _muted),
              ),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    package.rationale,
                    style: const TextStyle(color: _muted, height: 1.4),
                  ),
                ),
                const SizedBox(height: 12),
                ...package.decorations.map(
                  (decoration) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check_circle_outline, size: 19, color: _brown),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '${decoration.name} × ${decoration.quantity}\n'
                            '${_decorationDescription(decoration)}',
                            style: const TextStyle(height: 1.35),
                          ),
                        ),
                        Text(
                          'PKR ${money.format(decoration.unitCostPkr * decoration.quantity)}',
                          style: const TextStyle(
                            color: _brown,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: package.photoPreviewPath == null
                        ? null
                        : () => _openPhotoPreview(package),
                    style: FilledButton.styleFrom(backgroundColor: _brown),
                    icon: const Icon(Icons.photo_outlined),
                    label: const Text('Open Photo-Based Preview'),
                  ),
                ),
              ],
            ),
          );
        }).toList(growable: false),
      ),
    );
  }

  static String _decorationDescription(EventDecoration decoration) {
    final reason = decoration.reason ?? decoration.category;
    final safety = decoration.safetyNote;
    return safety == null ? reason : '$reason\nSafety: $safety';
  }

  Widget _actionButtons(
    AsyncValue<DeviceCapabilities> capabilities,
  ) {
    final detected = capabilities.valueOrNull ??
        DeviceCapabilities.unavailable(
          platform: 'unknown',
          diagnostic: 'Capability detection is still loading.',
        );
    final decision = EventPreviewPolicy.decide(
      recommendation: _recommendation,
      capabilities: detected,
    );
    return Column(
      children: [
        if (decision.mode != EventPreviewMode.conceptFallback)
          SizedBox(
            width: double.infinity,
            height: 52,
            child: FilledButton.icon(
              onPressed: decision.mode == EventPreviewMode.interactive3d
                  ? _openViewer
                  : () => _openPreview(decision),
              style: FilledButton.styleFrom(backgroundColor: _brown),
              icon: Icon(
                decision.mode == EventPreviewMode.augmentedReality
                    ? Icons.view_in_ar_outlined
                    : Icons.threed_rotation,
              ),
              label: Text(
                decision.label,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
          )
        else
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF4F5),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Text(
              decision.label,
              textAlign: TextAlign.center,
              style: const TextStyle(color: _ink, fontWeight: FontWeight.w800),
            ),
          ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _saving ? null : () => _save(),
                icon: _saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.bookmark_add_outlined),
                label: const Text('Save'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _saving ? null : _share,
                icon: const Icon(Icons.share_outlined),
                label: const Text('Share'),
              ),
            ),
          ],
        ),
        if (widget.args.fromSavedDesign) ...[
          const SizedBox(height: 10),
          TextButton.icon(
            onPressed: _regenerating ? null : _regenerate,
            icon: _regenerating
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            label: const Text('Regenerate 3D scene'),
          ),
        ],
      ],
    );
  }

  Widget _deviceCompatibilityCard(
    AsyncValue<DeviceCapabilities> capabilities,
  ) {
    if (capabilities.isLoading) {
      return _compatibilitySurface(
        icon: Icons.phonelink_setup_outlined,
        title: 'Checking device preview support',
        message: 'Interactive 3D remains available during this local check.',
        color: const Color(0xFF5B6472),
        trailing: const SizedBox(
          width: 18,
          height: 18,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    final detected = capabilities.valueOrNull;
    if (detected == null) {
      return _compatibilitySurface(
        icon: Icons.threed_rotation,
        title: 'Interactive 3D fallback active',
        message: 'AR support could not be verified. No AR installation is '
            'required to rotate and zoom this design.',
        color: const Color(0xFF8A5A16),
      );
    }

    switch (detected.arState) {
      case ArCapabilityState.supported:
        final sceneHasAr = _recommendation.backendArSupported == true &&
            _recommendation.arPath != null;
        return _compatibilitySurface(
          icon: sceneHasAr ? Icons.view_in_ar_outlined : Icons.threed_rotation,
          title: sceneHasAr ? 'AR preview available' : 'Interactive 3D shown',
          message: sceneHasAr
              ? 'Compatible AR camera hardware and a real BakeSmart AR scene '
                  'were both detected.'
              : 'This device reports AR camera hardware, but this result has no '
                  'real AR scene. BakeSmart will not show a fake AR button.',
          color: sceneHasAr
              ? const Color(0xFF287A50)
              : const Color(0xFF8A5A16),
          detail: detected.apiLevel == null
              ? null
              : 'Android API ${detected.apiLevel}',
        );
      case ArCapabilityState.unsupported:
        return _compatibilitySurface(
          icon: Icons.threed_rotation,
          title: 'Interactive 3D fallback active',
          message: 'Live-camera AR is not supported by this device. Rotate and '
              'zoom the design without installing Google Play Services for AR.',
          color: const Color(0xFF8A5A16),
          detail: detected.apiLevel == null
              ? null
              : 'Android API ${detected.apiLevel}',
        );
      case ArCapabilityState.unavailable:
        return _compatibilitySurface(
          icon: Icons.threed_rotation,
          title: 'Interactive 3D fallback active',
          message: 'AR hardware support could not be verified. No AR service is '
              'required for the 3D viewer.',
          color: const Color(0xFF5B6472),
        );
    }
  }

  Widget _venueAssessmentCard(VenueAssessment assessment) {
    final verified = assessment.clearanceVerified;
    final color = verified
        ? const Color(0xFF287A50)
        : const Color(0xFF9A5A14);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.24)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                verified ? Icons.verified_outlined : Icons.rule_outlined,
                color: color,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  verified
                      ? 'Venue clearance verified from supplied measurements'
                      : 'Manual venue review required',
                  style: TextStyle(color: color, fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 9),
          Text(
            '${assessment.photoCount} photo angle(s) • '
            '${assessment.evidenceConfidence} evidence confidence • '
            '${assessment.availableFrontClearanceM.toStringAsFixed(2)} m front '
            'clearance (minimum ${assessment.minimumClearanceM.toStringAsFixed(2)} m)',
            style: const TextStyle(color: _muted, height: 1.4),
          ),
          const SizedBox(height: 5),
          Text(
            'Suggested focal centre: '
            '${assessment.selectedFocalCenterXM.toStringAsFixed(2)} m from the left edge.',
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (assessment.blockingObstacles.isNotEmpty) ...[
            const SizedBox(height: 7),
            Text(
              'Blocking items: ${assessment.blockingObstacles.join(', ')}',
              style: const TextStyle(color: _muted, fontSize: 12),
            ),
          ],
          const SizedBox(height: 10),
          const Text(
            'Confirmed evidence',
            style: TextStyle(color: _ink, fontWeight: FontWeight.w900),
          ),
          ...assessment.observedFacts.map(
            (fact) => _venueEvidenceLine(fact, Icons.check, color),
          ),
          if (assessment.assumptions.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text(
              'Still assumed or unknown',
              style: TextStyle(color: _ink, fontWeight: FontWeight.w900),
            ),
            ...assessment.assumptions.map(
              (item) => _venueEvidenceLine(
                item,
                Icons.help_outline,
                const Color(0xFF9A5A14),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _venueEvidenceLine(String text, IconData icon, Color color) {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(icon, size: 15, color: color),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: _muted, fontSize: 12, height: 1.35),
            ),
          ),
        ],
      ),
    );
  }

  Widget _compatibilitySurface({
    required IconData icon,
    required String title,
    required String message,
    required Color color,
    String? detail,
    Widget? trailing,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.24)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(color: color, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 4),
                Text(
                  message,
                  style: const TextStyle(color: _muted, height: 1.35),
                ),
                if (detail != null) ...[
                  const SizedBox(height: 5),
                  Text(
                    detail,
                    style: TextStyle(
                      color: color,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: 10),
            trailing,
          ],
        ],
      ),
    );
  }

  Widget _stat(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFF2EAE0)),
      ),
      child: Row(
        children: [
          Icon(icon, color: _brown),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(color: _muted, fontSize: 12)),
                const SizedBox(height: 3),
                Text(
                  value,
                  style: const TextStyle(
                    color: _ink,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _detailsCard({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
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
              Text(
                title,
                style: const TextStyle(
                  color: _ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;

  const _Badge({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.13),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withOpacity(0.2)),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
