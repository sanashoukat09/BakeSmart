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

  static const obstacleTypes = [
    EventDesignOption('door', 'Door'),
    EventDesignOption('window', 'Window'),
    EventDesignOption('furniture', 'Furniture'),
    EventDesignOption('outlet', 'Electrical outlet'),
    EventDesignOption('stairs', 'Stairs'),
    EventDesignOption('walkway', 'Required walkway'),
    EventDesignOption('other', 'Other obstacle'),
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

class VenueVisionCandidate {
  final String label;
  final double confidence;
  final List<double> boundingBox;
  final double areaFraction;
  final bool confirmed;
  final String source;

  const VenueVisionCandidate({
    required this.label,
    required this.confidence,
    required this.boundingBox,
    required this.areaFraction,
    required this.confirmed,
    required this.source,
  });

  factory VenueVisionCandidate.fromJson(Map<String, dynamic> json) {
    return VenueVisionCandidate(
      label: json['label'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      boundingBox: (json['bounding_box'] as List)
          .map((value) => (value as num).toDouble())
          .toList(growable: false),
      areaFraction: (json['area_fraction'] as num).toDouble(),
      confirmed: json['confirmed'] as bool? ?? false,
      source: json['source'] as String? ?? 'synthetic_bootstrap_model',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'label': label,
      'confidence': confidence,
      'bounding_box': boundingBox,
      'area_fraction': areaFraction,
      'confirmed': false,
      'source': source,
    };
  }
}

class ManualOutletMark {
  final double xFraction;
  final double yFraction;

  const ManualOutletMark({
    required this.xFraction,
    required this.yFraction,
  });

  factory ManualOutletMark.fromJson(Map<String, dynamic> json) {
    return ManualOutletMark(
      xFraction: (json['x_fraction'] as num).toDouble(),
      yFraction: (json['y_fraction'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'x_fraction': xFraction,
      'y_fraction': yFraction,
      'source': 'customer_manual',
    };
  }
}

class VenuePhotoAnalysis {
  final String photoId;
  final String angle;
  final int pixelWidth;
  final int pixelHeight;
  final int fileSizeBytes;
  final String orientation;
  final String quality;
  final double brightnessScore;
  final double contrastScore;
  final double sharpnessScore;
  final double horizontalStructureScore;
  final String? visionModelVersion;
  final List<VenueVisionCandidate> unconfirmedCandidates;
  final List<ManualOutletMark> manualOutlets;
  final List<String> observations;
  final List<String> limitations;

  const VenuePhotoAnalysis({
    required this.photoId,
    required this.angle,
    required this.pixelWidth,
    required this.pixelHeight,
    required this.fileSizeBytes,
    required this.orientation,
    required this.quality,
    required this.brightnessScore,
    required this.contrastScore,
    required this.sharpnessScore,
    required this.horizontalStructureScore,
    this.visionModelVersion,
    this.unconfirmedCandidates = const [],
    this.manualOutlets = const [],
    required this.observations,
    required this.limitations,
  });

  factory VenuePhotoAnalysis.fromJson(Map<String, dynamic> json) {
    return VenuePhotoAnalysis(
      photoId: json['photo_id'] as String,
      angle: json['angle'] as String,
      pixelWidth: (json['pixel_width'] as num).toInt(),
      pixelHeight: (json['pixel_height'] as num).toInt(),
      fileSizeBytes: (json['file_size_bytes'] as num).toInt(),
      orientation: json['orientation'] as String,
      quality: json['quality'] as String,
      brightnessScore: (json['brightness_score'] as num).toDouble(),
      contrastScore: (json['contrast_score'] as num).toDouble(),
      sharpnessScore: (json['sharpness_score'] as num).toDouble(),
      horizontalStructureScore:
          (json['horizontal_structure_score'] as num).toDouble(),
      visionModelVersion: json['vision_model_version'] as String?,
      unconfirmedCandidates:
          (json['unconfirmed_candidates'] as List? ?? const [])
              .map((item) => VenueVisionCandidate.fromJson(
                    Map<String, dynamic>.from(item as Map),
                  ))
              .toList(growable: false),
      manualOutlets: (json['manual_outlets'] as List? ?? const [])
          .map((item) => ManualOutletMark.fromJson(
                Map<String, dynamic>.from(item as Map),
              ))
          .toList(growable: false),
      observations:
          List<String>.from(json['observations'] as List? ?? const []),
      limitations:
          List<String>.from(json['limitations'] as List? ?? const []),
    );
  }

  Map<String, dynamic> toEvidenceJson() {
    return {
      'photo_id': photoId,
      'angle': angle,
      'pixel_width': pixelWidth,
      'pixel_height': pixelHeight,
      'file_size_bytes': fileSizeBytes,
      'quality': quality,
      'brightness_score': brightnessScore,
      'contrast_score': contrastScore,
      'sharpness_score': sharpnessScore,
      'observations': observations,
      'vision_model_version': visionModelVersion,
      'unconfirmed_candidates':
          unconfirmedCandidates.map((candidate) => candidate.toJson()).toList(),
      'manual_outlets': manualOutlets.map((mark) => mark.toJson()).toList(),
    };
  }

  VenuePhotoAnalysis withManualOutlets(List<ManualOutletMark> marks) {
    return VenuePhotoAnalysis(
      photoId: photoId,
      angle: angle,
      pixelWidth: pixelWidth,
      pixelHeight: pixelHeight,
      fileSizeBytes: fileSizeBytes,
      orientation: orientation,
      quality: quality,
      brightnessScore: brightnessScore,
      contrastScore: contrastScore,
      sharpnessScore: sharpnessScore,
      horizontalStructureScore: horizontalStructureScore,
      visionModelVersion: visionModelVersion,
      unconfirmedCandidates: unconfirmedCandidates,
      manualOutlets: List.unmodifiable(marks),
      observations: observations,
      limitations: limitations,
    );
  }
}

class VenueObstacle {
  final String type;
  final String label;
  final double xM;
  final double yM;
  final double zM;
  final double widthM;
  final double depthM;
  final double heightM;

  const VenueObstacle({
    required this.type,
    required this.label,
    required this.xM,
    required this.yM,
    required this.zM,
    required this.widthM,
    required this.depthM,
    required this.heightM,
  });

  Map<String, dynamic> toJson() {
    return {
      'obstacle_type': type,
      'label': label.isEmpty ? null : label,
      'position': {'x_m': xM, 'y_m': yM, 'z_m': zM},
      'dimensions': {
        'width_m': widthM,
        'depth_m': depthM,
        'height_m': heightM,
      },
    };
  }

  factory VenueObstacle.fromJson(Map<String, dynamic> json) {
    final position = Map<String, dynamic>.from(json['position'] as Map);
    final dimensions = Map<String, dynamic>.from(json['dimensions'] as Map);
    return VenueObstacle(
      type: json['obstacle_type'] as String,
      label: json['label'] as String? ?? '',
      xM: (position['x_m'] as num).toDouble(),
      yM: (position['y_m'] as num).toDouble(),
      zM: (position['z_m'] as num).toDouble(),
      widthM: (dimensions['width_m'] as num).toDouble(),
      depthM: (dimensions['depth_m'] as num? ?? 0.2).toDouble(),
      heightM: (dimensions['height_m'] as num).toDouble(),
    );
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
  final List<VenuePhotoAnalysis> venuePhotos;
  final List<VenueObstacle> obstacles;
  final bool obstacleMapConfirmed;
  final double? knownReferenceM;
  final double minimumClearanceM;
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
    this.venuePhotos = const [],
    this.obstacles = const [],
    this.obstacleMapConfirmed = false,
    this.knownReferenceM,
    this.minimumClearanceM = 0.9,
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
        'obstacles': obstacles.map((item) => item.toJson()).toList(),
        'obstacle_map_confirmed': obstacleMapConfirmed,
        'known_reference_m': knownReferenceM,
        'photo_references':
            venuePhotos.map((photo) => photo.photoId).toList(),
        'photo_evidence':
            venuePhotos.map((photo) => photo.toEvidenceJson()).toList(),
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
      'minimum_clearance_m': minimumClearanceM,
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
      venuePhotos: (space['photo_evidence'] as List? ?? const [])
          .map((item) {
            final evidence = Map<String, dynamic>.from(item as Map);
            evidence.putIfAbsent('orientation', () => 'landscape');
            evidence.putIfAbsent('horizontal_structure_score', () => 0.0);
            evidence.putIfAbsent('limitations', () => <String>[]);
            return VenuePhotoAnalysis.fromJson(evidence);
          })
          .toList(growable: false),
      obstacles: (space['obstacles'] as List? ?? const [])
          .map((item) => VenueObstacle.fromJson(
                Map<String, dynamic>.from(item as Map),
              ))
          .toList(growable: false),
      obstacleMapConfirmed:
          space['obstacle_map_confirmed'] as bool? ?? false,
      knownReferenceM:
          (space['known_reference_m'] as num?)?.toDouble(),
      minimumClearanceM:
          (json['minimum_clearance_m'] as num? ?? 0.9).toDouble(),
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
  final VenueAssessment? venueAssessment;
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
    required this.venueAssessment,
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
      venueAssessment: json['venue_assessment'] is Map
          ? VenueAssessment.fromJson(
              Map<String, dynamic>.from(json['venue_assessment'] as Map),
            )
          : null,
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

class VenueAssessment {
  final int photoCount;
  final String evidenceConfidence;
  final String placementStatus;
  final String scaleSource;
  final double selectedFocalCenterXM;
  final double availableFrontClearanceM;
  final double minimumClearanceM;
  final int obstacleCount;
  final bool obstacleMapConfirmed;
  final List<String> blockingObstacles;
  final List<String> observedFacts;
  final List<String> assumptions;

  const VenueAssessment({
    required this.photoCount,
    required this.evidenceConfidence,
    required this.placementStatus,
    required this.scaleSource,
    required this.selectedFocalCenterXM,
    required this.availableFrontClearanceM,
    required this.minimumClearanceM,
    required this.obstacleCount,
    required this.obstacleMapConfirmed,
    required this.blockingObstacles,
    required this.observedFacts,
    required this.assumptions,
  });

  bool get clearanceVerified => placementStatus == 'clearance_verified';

  factory VenueAssessment.fromJson(Map<String, dynamic> json) {
    return VenueAssessment(
      photoCount: (json['photo_count'] as num? ?? 0).toInt(),
      evidenceConfidence:
          json['evidence_confidence'] as String? ?? 'low',
      placementStatus:
          json['placement_status'] as String? ?? 'manual_review_required',
      scaleSource: json['scale_source'] as String? ?? 'unverified',
      selectedFocalCenterXM:
          (json['selected_focal_center_x_m'] as num? ?? 0).toDouble(),
      availableFrontClearanceM:
          (json['available_front_clearance_m'] as num? ?? 0).toDouble(),
      minimumClearanceM:
          (json['minimum_clearance_m'] as num? ?? 0.9).toDouble(),
      obstacleCount: (json['obstacle_count'] as num? ?? 0).toInt(),
      obstacleMapConfirmed:
          json['obstacle_map_confirmed'] as bool? ?? false,
      blockingObstacles:
          List<String>.from(json['blocking_obstacles'] as List? ?? const []),
      observedFacts:
          List<String>.from(json['observed_facts'] as List? ?? const []),
      assumptions:
          List<String>.from(json['assumptions'] as List? ?? const []),
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
