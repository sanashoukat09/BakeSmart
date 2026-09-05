import 'package:bakesmart/models/device_capability_model.dart';
import 'package:bakesmart/models/event_design_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses Android AR camera hardware facts', () {
    final capabilities = DeviceCapabilities.fromPlatformMap({
      'platform': 'android',
      'api_level': 35,
      'camera_available': true,
      'ar_hardware_supported': true,
    });

    expect(capabilities.platform, 'android');
    expect(capabilities.apiLevel, 35);
    expect(capabilities.cameraAvailable, isTrue);
    expect(capabilities.arState, ArCapabilityState.supported);
  });

  group('EventPreviewPolicy', () {
    test('shows AR only when hardware and a real AR scene are available', () {
      final decision = EventPreviewPolicy.decide(
        recommendation: _recommendation(
          arSupported: true,
          arPath: '/ar/design-1234567890abcdef1234',
        ),
        capabilities: _capabilities(arSupported: true),
      );

      expect(decision.mode, EventPreviewMode.augmentedReality);
      expect(decision.label, 'Open in AR');
      expect(decision.resourcePath, '/ar/design-1234567890abcdef1234');
    });

    test('uses interactive 3D when the Android device lacks AR hardware', () {
      final decision = EventPreviewPolicy.decide(
        recommendation: _recommendation(
          arSupported: true,
          arPath: '/ar/design-1234567890abcdef1234',
        ),
        capabilities: _capabilities(arSupported: false),
      );

      expect(decision.mode, EventPreviewMode.interactive3d);
      expect(decision.label, 'Open Basic 3D Layout Preview');
      expect(decision.explanation, contains('without Google Play Services'));
    });

    test('does not invent AR when the backend supplies no AR scene', () {
      final decision = EventPreviewPolicy.decide(
        recommendation: _recommendation(),
        capabilities: _capabilities(arSupported: true),
      );

      expect(decision.mode, EventPreviewMode.interactive3d);
      expect(decision.resourcePath, startsWith('/viewer/'));
      expect(
        decision.explanation,
        contains('does not include a real AR scene'),
      );
    });

    test('uses the exact concept fallback when no viewer is available', () {
      final decision = EventPreviewPolicy.decide(
        recommendation: _recommendation(interactive: false),
        capabilities: _capabilities(arSupported: false),
      );

      expect(decision.mode, EventPreviewMode.conceptFallback);
      expect(decision.label, 'Concept preview—not to scale');
      expect(decision.resourcePath, isNull);
    });
  });
}

DeviceCapabilities _capabilities({required bool arSupported}) {
  return DeviceCapabilities(
    platform: 'android',
    apiLevel: 35,
    cameraAvailable: true,
    arHardwareSupported: arSupported,
  );
}

EventDesignRecommendation _recommendation({
  bool interactive = true,
  bool? arSupported,
  String? arPath,
}) {
  return EventDesignRecommendation.fromJson({
    'design_id': 'design-1234567890abcdef1234',
    'created_at': '2026-08-18T08:00:00Z',
    'model_version': 'bootstrap-v1',
    'selected_theme_id': 'floral-romantic',
    'decorations': <Map<String, dynamic>>[],
    'costs': {
      'decoration_cost_pkr': 42000,
      'cake_cost_pkr': 18000,
      'total_cost_pkr': 60000,
      'budget_pkr': 50000,
      'remaining_budget_pkr': 8000,
    },
    'preview': {
      'interactive_3d_ready': interactive,
      'viewer_3d_url': interactive
          ? '/viewer/design-1234567890abcdef1234'
          : null,
      'scene_glb_url': interactive
          ? '/api/v1/designs/design-1234567890abcdef1234/scene.glb'
          : null,
      'ar_supported': arSupported,
      'ar_url': arPath,
      'fallback_label':
          interactive ? null : 'Concept preview—not to scale',
    },
    'warnings': <String>[],
  });
}
