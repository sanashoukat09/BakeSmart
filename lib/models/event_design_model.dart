import 'package:cloud_firestore/cloud_firestore.dart';

class EventDesignOption {
  final String value;
  final String label;

  const EventDesignOption(this.value, this.label);
}

abstract final class EventDesignOptions {
  static const areaTypes = [
    EventDesignOption('wall', 'Wall'),
    EventDesignOption('room', 'Room'),
    EventDesignOption('table', 'Table area'),
    EventDesignOption('outdoor_area', 'Outdoor area'),
  ];

  static const venueTypes = [
    EventDesignOption('hall', 'Hall'),
    EventDesignOption('living_room', 'Living room'),
    EventDesignOption('bedroom', 'Bedroom'),
    EventDesignOption('restaurant', 'Restaurant'),
    EventDesignOption('garden', 'Garden'),
    EventDesignOption('rooftop', 'Rooftop'),
    EventDesignOption('other', 'Other'),
  ];

  static const environments = [
    EventDesignOption('indoor', 'Indoor'),
    EventDesignOption('outdoor', 'Outdoor'),
    EventDesignOption('semi_outdoor', 'Semi-outdoor'),
  ];

  static const eventTypes = [
    EventDesignOption('birthday', 'Birthday'),
    EventDesignOption('wedding', 'Wedding'),
    EventDesignOption('kids_birthday', "Kids' birthday"),
    EventDesignOption('baby_shower', 'Baby shower'),
    EventDesignOption('engagement', 'Engagement'),
    EventDesignOption('corporate', 'Corporate event'),
    EventDesignOption('anniversary', 'Anniversary'),
    EventDesignOption('other', 'Other'),
  ];

  static const cakeShapes = [
    EventDesignOption('round', 'Round'),
    EventDesignOption('square', 'Square'),
    EventDesignOption('rectangle', 'Rectangle'),
  ];

  static const themes = [
    EventDesignOption('rustic-boho', 'Rustic Boho'),
    EventDesignOption('modern-minimalist', 'Modern Minimalist'),
    EventDesignOption('classic-elegant', 'Classic Elegant'),
    EventDesignOption('tropical', 'Tropical'),
    EventDesignOption('vintage-garden', 'Vintage Garden'),
    EventDesignOption('glam-gold', 'Glam Gold'),
    EventDesignOption('pastel-dreamy', 'Pastel Dreamy'),
    EventDesignOption('dark-moody', 'Dark Moody'),
    EventDesignOption('whimsical-kids', 'Whimsical Kids'),
    EventDesignOption('beach-coastal', 'Beach Coastal'),
    EventDesignOption('industrial', 'Industrial'),
    EventDesignOption('floral-romantic', 'Floral Romantic'),
    EventDesignOption('retro-70s', 'Retro 70s'),
    EventDesignOption('winter-wonderland', 'Winter Wonderland'),
    EventDesignOption('south-asian-mehndi', 'South Asian Mehndi'),
    EventDesignOption('south-asian-wedding', 'South Asian Wedding Elegance'),
    EventDesignOption('arabian-majlis', 'Arabian Majlis'),
    EventDesignOption('sports-hobby', 'Sports & Hobby'),
    EventDesignOption('rainbow-bright-pop', 'Rainbow Bright Pop'),
    EventDesignOption('farmhouse', 'Farmhouse'),
    EventDesignOption('art-deco', 'Art Deco'),
    EventDesignOption('enchanted-forest', 'Enchanted Forest'),
    EventDesignOption('celestial-night', 'Celestial Night'),
    EventDesignOption('corporate-brand', 'Corporate Brand Showcase'),
    EventDesignOption('baby-safari', 'Baby Safari'),
    EventDesignOption('candy-pop', 'Candy Pop'),
  ];

  static String labelFor(List<EventDesignOption> options, String value) {
    for (final option in options) {
      if (option.value == value) return option.label;
    }
    return value.replaceAll('_', ' ').replaceAll('-', ' ');
  }
}

class EventDesignRequest {
  final String customerId;
  final String areaType;
  final String venueType;
  final String environment;
  final double widthM;
  final double? depthM;
  final double heightM;
  final String eventType;
  final int guestCount;
  final String themeId;
  final List<String> preferredColors;
  final String cakeImageReference;
  final String cakeShape;
  final int cakeTiers;
  final int servingsRequired;
  final double cakeWidthM;
  final double cakeDepthM;
  final double cakeHeightM;
  final int decorationBudgetPkr;

  const EventDesignRequest({
    required this.customerId,
    required this.areaType,
    required this.venueType,
    required this.environment,
    required this.widthM,
    required this.depthM,
    required this.heightM,
    required this.eventType,
    required this.guestCount,
    required this.themeId,
    required this.preferredColors,
    required this.cakeImageReference,
    required this.cakeShape,
    required this.cakeTiers,
    required this.servingsRequired,
    required this.cakeWidthM,
    required this.cakeDepthM,
    required this.cakeHeightM,
    required this.decorationBudgetPkr,
  });

  bool get requiresDepth => areaType != 'wall';

  Map<String, dynamic> toJson() {
    final dimensions = <String, dynamic>{
      'width_m': widthM,
      'height_m': heightM,
    };
    if (requiresDepth && depthM != null) {
      dimensions['depth_m'] = depthM;
    }

    final cake = <String, dynamic>{
      'cake_image_reference': cakeImageReference,
      'shape': cakeShape,
      'tiers': cakeTiers,
      'servings_required': servingsRequired,
      'height_m': cakeHeightM,
    };
    if (cakeShape == 'round') {
      cake['diameter_m'] = cakeWidthM;
    } else {
      cake['width_m'] = cakeWidthM;
      cake['depth_m'] = cakeDepthM;
    }

    return {
      'customer_id': customerId,
      'space': {
        'area_type': areaType,
        'venue_type': venueType,
        'environment': environment,
        'dimensions': dimensions,
        'obstacles': <Map<String, dynamic>>[],
        'known_reference_m': null,
        'photo_references': <String>[],
      },
      'event': {
        'event_type': eventType,
        'guest_count': guestCount,
        'theme_id': themeId,
        'preferred_colors': preferredColors,
        'excluded_colors': <String>[],
        'required_decor_categories': [
          'backdrop',
          'table-setting',
          'lighting',
          'signage',
        ],
        'excluded_decor_categories': <String>[],
      },
      'cake': cake,
      'decoration_budget_pkr': decorationBudgetPkr,
      'minimum_clearance_m': 0.9,
    };
  }

  factory EventDesignRequest.fromJson(Map<String, dynamic> json) {
    final space = Map<String, dynamic>.from(json['space'] as Map);
    final dimensions =
        Map<String, dynamic>.from(space['dimensions'] as Map);
    final event = Map<String, dynamic>.from(json['event'] as Map);
    final cake = Map<String, dynamic>.from(json['cake'] as Map);
    final shape = cake['shape'] as String;
    return EventDesignRequest(
      customerId: json['customer_id'] as String,
      areaType: space['area_type'] as String,
      venueType: space['venue_type'] as String,
      environment: space['environment'] as String,
      widthM: (dimensions['width_m'] as num).toDouble(),
      depthM: (dimensions['depth_m'] as num?)?.toDouble(),
      heightM: (dimensions['height_m'] as num).toDouble(),
      eventType: event['event_type'] as String,
      guestCount: (event['guest_count'] as num).toInt(),
      themeId: event['theme_id'] as String,
      preferredColors:
          List<String>.from(event['preferred_colors'] as List? ?? const []),
      cakeImageReference: cake['cake_image_reference'] as String,
      cakeShape: shape,
      cakeTiers: (cake['tiers'] as num).toInt(),
      servingsRequired: (cake['servings_required'] as num).toInt(),
      cakeWidthM: ((shape == 'round'
              ? cake['diameter_m']
              : cake['width_m']) as num)
          .toDouble(),
      cakeDepthM: ((cake['depth_m'] ?? cake['diameter_m']) as num).toDouble(),
      cakeHeightM: (cake['height_m'] as num).toDouble(),
      decorationBudgetPkr:
          (json['decoration_budget_pkr'] as num).toInt(),
    );
  }
}

class EventDecoration {
  final String name;
  final String category;
  final int quantity;
  final int unitCostPkr;

  const EventDecoration({
    required this.name,
    required this.category,
    required this.quantity,
    required this.unitCostPkr,
  });

  factory EventDecoration.fromJson(Map<String, dynamic> json) {
    return EventDecoration(
      name: json['name'] as String? ?? 'Decoration',
      category: json['category'] as String? ?? 'decor',
      quantity: (json['quantity'] as num? ?? 1).toInt(),
      unitCostPkr: (json['unit_cost_pkr'] as num? ?? 0).toInt(),
    );
  }
}

class EventDesignRecommendation {
  final String designId;
  final DateTime createdAt;
  final String modelVersion;
  final String themeId;
  final List<EventDecoration> decorations;
  final int decorationCostPkr;
  final int cakeCostPkr;
  final int totalCostPkr;
  final int budgetPkr;
  final int remainingBudgetPkr;
  final bool interactive3dReady;
  final String? viewerPath;
  final String? sceneGlbPath;
  final bool? backendArSupported;
  final String? arPath;
  final String? fallbackLabel;
  final List<String> warnings;
  final Map<String, dynamic> rawJson;

  const EventDesignRecommendation({
    required this.designId,
    required this.createdAt,
    required this.modelVersion,
    required this.themeId,
    required this.decorations,
    required this.decorationCostPkr,
    required this.cakeCostPkr,
    required this.totalCostPkr,
    required this.budgetPkr,
    required this.remainingBudgetPkr,
    required this.interactive3dReady,
    required this.viewerPath,
    required this.sceneGlbPath,
    required this.backendArSupported,
    required this.arPath,
    required this.fallbackLabel,
    required this.warnings,
    required this.rawJson,
  });

  String get themeLabel =>
      EventDesignOptions.labelFor(EventDesignOptions.themes, themeId);

  factory EventDesignRecommendation.fromJson(Map<String, dynamic> json) {
    final costs = Map<String, dynamic>.from(json['costs'] as Map);
    final preview = Map<String, dynamic>.from(json['preview'] as Map);
    return EventDesignRecommendation(
      designId: json['design_id'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      modelVersion: json['model_version'] as String,
      themeId: json['selected_theme_id'] as String,
      decorations: (json['decorations'] as List? ?? const [])
          .map((item) => EventDecoration.fromJson(
                Map<String, dynamic>.from(item as Map),
              ))
          .toList(growable: false),
      decorationCostPkr:
          (costs['decoration_cost_pkr'] as num? ?? 0).toInt(),
      cakeCostPkr: (costs['cake_cost_pkr'] as num? ?? 0).toInt(),
      totalCostPkr: (costs['total_cost_pkr'] as num? ?? 0).toInt(),
      budgetPkr: (costs['budget_pkr'] as num? ?? 0).toInt(),
      remainingBudgetPkr:
          (costs['remaining_budget_pkr'] as num? ?? 0).toInt(),
      interactive3dReady:
          preview['interactive_3d_ready'] as bool? ?? false,
      viewerPath: preview['viewer_3d_url'] as String?,
      sceneGlbPath: preview['scene_glb_url'] as String?,
      backendArSupported: preview['ar_supported'] as bool?,
      arPath: preview['ar_url'] as String?,
      fallbackLabel: preview['fallback_label'] as String?,
      warnings: List<String>.from(json['warnings'] as List? ?? const []),
      rawJson: Map<String, dynamic>.from(json),
    );
  }
}

class SavedEventDesign {
  final String recordId;
  final String ownerId;
  final EventDesignRequest request;
  final EventDesignRecommendation recommendation;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isShared;
  final int shareCount;

  const SavedEventDesign({
    required this.recordId,
    required this.ownerId,
    required this.request,
    required this.recommendation,
    required this.createdAt,
    required this.updatedAt,
    required this.isShared,
    required this.shareCount,
  });

  factory SavedEventDesign.fromFirestore(
    DocumentSnapshot<Map<String, dynamic>> document,
  ) {
    final data = document.data();
    if (data == null) {
      throw StateError('Saved event design data is missing');
    }
    final createdAt = _dateFromFirestore(data['createdAt']);
    return SavedEventDesign(
      recordId: document.id,
      ownerId: data['ownerId'] as String,
      request: EventDesignRequest.fromJson(
        Map<String, dynamic>.from(data['request'] as Map),
      ),
      recommendation: EventDesignRecommendation.fromJson(
        Map<String, dynamic>.from(data['recommendation'] as Map),
      ),
      createdAt: createdAt,
      updatedAt: _dateFromFirestore(data['updatedAt'], fallback: createdAt),
      isShared: data['isShared'] as bool? ?? false,
      shareCount: (data['shareCount'] as num? ?? 0).toInt(),
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'ownerId': ownerId,
      'designId': recommendation.designId,
      'themeId': recommendation.themeId,
      'request': request.toJson(),
      'recommendation': recommendation.rawJson,
      'createdAt': Timestamp.fromDate(createdAt),
      'updatedAt': Timestamp.fromDate(updatedAt),
      'isShared': isShared,
      'shareCount': shareCount,
    };
  }

  static DateTime _dateFromFirestore(
    Object? value, {
    DateTime? fallback,
  }) {
    if (value is Timestamp) return value.toDate();
    return fallback ?? DateTime.now().toUtc();
  }
}

class EventDesignResultArgs {
  final EventDesignRequest request;
  final EventDesignRecommendation recommendation;
  final bool fromSavedDesign;

  const EventDesignResultArgs({
    required this.request,
    required this.recommendation,
    this.fromSavedDesign = false,
  });
}
