import 'package:bakesmart/models/event_design_model.dart';
import 'package:bakesmart/services/event_design_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('EventDesignRequest', () {
    test('serializes a round cake for the local BakeSmart contract', () {
      final request = _request();

      final json = request.toJson();
      final cake = json['cake'] as Map<String, dynamic>;
      final event = json['event'] as Map<String, dynamic>;

      expect(json['customer_id'], 'customer-001');
      expect(cake['diameter_m'], 0.30);
      expect(cake.containsKey('width_m'), isFalse);
      expect(event['theme_id'], 'floral-romantic');
      expect(event['required_decor_categories'], contains('table-setting'));
    });

    test('round trips through the persisted request map', () {
      final original = _request();

      final restored = EventDesignRequest.fromJson(original.toJson());

      expect(restored.customerId, original.customerId);
      expect(restored.areaType, original.areaType);
      expect(restored.depthM, original.depthM);
      expect(restored.cakeShape, original.cakeShape);
      expect(restored.cakeWidthM, original.cakeWidthM);
      expect(restored.decorationBudgetPkr, original.decorationBudgetPkr);
    });

    test('omits room depth for a wall design', () {
      final request = EventDesignRequest(
        customerId: 'customer-001',
        areaType: 'wall',
        venueType: 'hall',
        environment: 'indoor',
        widthM: 4,
        depthM: null,
        heightM: 2.8,
        eventType: 'wedding',
        guestCount: 80,
        themeId: 'classic-elegant',
        preferredColors: const ['ivory'],
        cakeImageReference: 'cake-photo.jpg',
        cakeShape: 'square',
        cakeTiers: 3,
        servingsRequired: 90,
        cakeWidthM: 0.45,
        cakeDepthM: 0.45,
        cakeHeightM: 0.55,
        decorationBudgetPkr: 120000,
      );

      final space = request.toJson()['space'] as Map<String, dynamic>;
      final dimensions = space['dimensions'] as Map<String, dynamic>;
      final cake = request.toJson()['cake'] as Map<String, dynamic>;

      expect(dimensions.containsKey('depth_m'), isFalse);
      expect(cake['width_m'], 0.45);
      expect(cake['depth_m'], 0.45);
      expect(cake.containsKey('diameter_m'), isFalse);
    });
  });

  test('parses the real Phase 7 preview links and costs', () {
    final recommendation = EventDesignRecommendation.fromJson(
      _recommendationJson(),
    );

    expect(recommendation.designId, 'design-1234567890abcdef1234');
    expect(recommendation.themeLabel, 'Floral Romantic');
    expect(recommendation.interactive3dReady, isTrue);
    expect(recommendation.backendArSupported, isFalse);
    expect(recommendation.arPath, isNull);
    expect(
      recommendation.viewerPath,
      '/viewer/design-1234567890abcdef1234',
    );
    expect(recommendation.decorations.single.name, 'Blush chiffon arch');
    expect(recommendation.remainingBudgetPkr, 8000);
  });

  test('resolves a relative viewer path against the configured service', () {
    final uri = EventDesignService.resolveResourceUri(
      baseUrl: 'http://10.0.2.2:8000',
      resourcePath: '/viewer/design-1234567890abcdef1234',
    );

    expect(
      uri.toString(),
      'http://10.0.2.2:8000/viewer/design-1234567890abcdef1234',
    );
  });
}

EventDesignRequest _request() {
  return const EventDesignRequest(
    customerId: 'customer-001',
    areaType: 'room',
    venueType: 'living_room',
    environment: 'indoor',
    widthM: 3,
    depthM: 2.4,
    heightM: 2.7,
    eventType: 'birthday',
    guestCount: 35,
    themeId: 'floral-romantic',
    preferredColors: ['blush-pink', 'cream'],
    cakeImageReference: 'cake-photo.jpg',
    cakeShape: 'round',
    cakeTiers: 2,
    servingsRequired: 41,
    cakeWidthM: 0.30,
    cakeDepthM: 0.30,
    cakeHeightM: 0.35,
    decorationBudgetPkr: 50000,
  );
}

Map<String, dynamic> _recommendationJson() {
  return {
    'design_id': 'design-1234567890abcdef1234',
    'created_at': '2026-08-18T08:00:00Z',
    'model_version': 'bootstrap-v1',
    'selected_theme_id': 'floral-romantic',
    'decorations': [
      {
        'name': 'Blush chiffon arch',
        'category': 'backdrop',
        'quantity': 1,
        'unit_cost_pkr': 25000,
      },
    ],
    'costs': {
      'decoration_cost_pkr': 42000,
      'cake_cost_pkr': 18000,
      'total_cost_pkr': 60000,
      'budget_pkr': 50000,
      'remaining_budget_pkr': 8000,
    },
    'preview': {
      'interactive_3d_ready': true,
      'viewer_3d_url': '/viewer/design-1234567890abcdef1234',
      'scene_glb_url':
          '/api/v1/designs/design-1234567890abcdef1234/scene.glb',
      'ar_supported': false,
      'ar_url': null,
      'fallback_label': null,
    },
    'warnings': ['Procedural concept preview.'],
  };
}
