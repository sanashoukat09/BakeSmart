import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/router/app_router.dart';
import '../../models/event_design_model.dart';
import '../../providers/event_design_provider.dart';

class SavedEventDesignsScreen extends ConsumerWidget {
  const SavedEventDesignsScreen({super.key});

  static const _brown = Color(0xFFB05E27);
  static const _ink = Color(0xFF4A2B20);
  static const _muted = Color(0xFF8C6D5F);
  static const _canvas = Color(0xFFFFFDF8);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final designs = ref.watch(savedEventDesignsProvider);
    return Scaffold(
      backgroundColor: _canvas,
      appBar: AppBar(
        title: const Text('Saved 3D Designs'),
        backgroundColor: _canvas,
        foregroundColor: _ink,
        elevation: 0,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push(AppRoutes.customerEventDesigner),
        backgroundColor: _brown,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('New design'),
      ),
      body: designs.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _messageState(
          icon: Icons.cloud_off_outlined,
          title: 'Saved designs could not be loaded',
          message: error.toString(),
        ),
        data: (items) {
          if (items.isEmpty) {
            return _messageState(
              icon: Icons.bookmark_border,
              title: 'No saved designs yet',
              message: 'Generate a 3D event concept and tap Save to keep it here.',
              action: FilledButton(
                onPressed: () => context.push(AppRoutes.customerEventDesigner),
                style: FilledButton.styleFrom(backgroundColor: _brown),
                child: const Text('Create first design'),
              ),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 100),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) => _designCard(
              context,
              ref,
              items[index],
            ),
          );
        },
      ),
    );
  }

  Widget _designCard(
    BuildContext context,
    WidgetRef ref,
    SavedEventDesign design,
  ) {
    final date = DateFormat('d MMM yyyy, h:mm a').format(design.updatedAt);
    final budget = NumberFormat.decimalPattern()
        .format(design.recommendation.decorationCostPkr);
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => context.push(
          AppRoutes.customerEventDesignResult,
          extra: EventDesignResultArgs(
            request: design.request,
            recommendation: design.recommendation,
            fromSavedDesign: true,
          ),
        ),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFFF2EAE0)),
          ),
          child: Row(
            children: [
              Container(
                width: 58,
                height: 58,
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF0E4),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.threed_rotation, color: _brown),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      design.recommendation.themeLabel,
                      style: const TextStyle(
                        color: _ink,
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      '${EventDesignOptions.labelFor(EventDesignOptions.eventTypes, design.request.eventType)} • PKR $budget decor',
                      style: const TextStyle(color: _muted, fontSize: 12),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Updated $date${design.isShared ? ' • Shared ${design.shareCount}×' : ''}',
                      style: const TextStyle(color: _muted, fontSize: 11),
                    ),
                  ],
                ),
              ),
              PopupMenuButton<String>(
                onSelected: (action) {
                  if (action == 'delete') {
                    _confirmDelete(context, ref, design);
                  }
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        Icon(Icons.delete_outline, color: Colors.red),
                        SizedBox(width: 8),
                        Text('Delete'),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    SavedEventDesign design,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete saved design?'),
        content: const Text(
          'This removes the saved request and result from your account. '
          'It cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    try {
      await ref.read(eventDesignServiceProvider).deleteDesign(design);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved design deleted.')),
        );
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not delete the design: $error')),
        );
      }
    }
  }

  Widget _messageState({
    required IconData icon,
    required String title,
    required String message,
    Widget? action,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 52, color: _brown),
            const SizedBox(height: 14),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: _ink,
                fontSize: 19,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: _muted, height: 1.4),
            ),
            if (action != null) ...[
              const SizedBox(height: 18),
              action,
            ],
          ],
        ),
      ),
    );
  }
}
