import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/router/app_router.dart';
import '../../core/utils/share_util.dart';
import '../../models/event_design_model.dart';
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
    final viewerPath = _recommendation.viewerPath;
    if (!_recommendation.interactive3dReady || viewerPath == null) {
      _message(_recommendation.fallbackLabel ??
          'Concept preview—not to scale. A shareable 3D link is unavailable.');
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
        viewerUrl: service.absoluteResourceUri(viewerPath).toString(),
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
    return Scaffold(
      backgroundColor: _canvas,
      appBar: AppBar(
        backgroundColor: _canvas,
        foregroundColor: _ink,
        elevation: 0,
        title: const Text('Your 3D Design'),
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
          _actionButtons(),
          const SizedBox(height: 22),
          _detailsCard(
            title: 'Recommended decorations',
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
                const Text(
                  'This is a procedural concept preview—not to scale. The cake '
                  'picture is a reference and is not reconstructed into 3D.',
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
            'Cake, dessert table and decorations combined in one scene',
            style: TextStyle(color: Color(0xFFFFE8D5), height: 1.4),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: const [
              _Badge(label: 'Procedural GLB'),
              _Badge(label: 'Interactive 3D'),
              _Badge(label: 'No AR required'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _actionButtons() {
    final interactive =
        _recommendation.interactive3dReady && _recommendation.viewerPath != null;
    return Column(
      children: [
        if (interactive)
          SizedBox(
            width: double.infinity,
            height: 52,
            child: FilledButton.icon(
              onPressed: _openViewer,
              style: FilledButton.styleFrom(backgroundColor: _brown),
              icon: const Icon(Icons.threed_rotation),
              label: const Text(
                'Open Interactive 3D View',
                style: TextStyle(fontWeight: FontWeight.w800),
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
              _recommendation.fallbackLabel ?? 'Concept preview—not to scale',
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
