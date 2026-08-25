import 'event_design_model.dart';

enum ArCapabilityState {
  supported,
  unsupported,
  unavailable,
}

class DeviceCapabilities {
  final String platform;
  final int? apiLevel;
  final bool cameraAvailable;
  final bool? arHardwareSupported;
  final String? diagnostic;

  const DeviceCapabilities({
    required this.platform,
    required this.apiLevel,
    required this.cameraAvailable,
    required this.arHardwareSupported,
    this.diagnostic,
  });

  ArCapabilityState get arState {
    if (arHardwareSupported == true) return ArCapabilityState.supported;
    if (arHardwareSupported == false) return ArCapabilityState.unsupported;
    return ArCapabilityState.unavailable;
  }

  factory DeviceCapabilities.fromPlatformMap(Map<Object?, Object?> values) {
    return DeviceCapabilities(
      platform: values['platform'] as String? ?? 'unknown',
      apiLevel: (values['api_level'] as num?)?.toInt(),
      cameraAvailable: values['camera_available'] as bool? ?? false,
      arHardwareSupported: values['ar_hardware_supported'] as bool?,
      diagnostic: values['diagnostic'] as String?,
    );
  }

  factory DeviceCapabilities.unavailable({
    required String platform,
    String? diagnostic,
  }) {
    return DeviceCapabilities(
      platform: platform,
      apiLevel: null,
      cameraAvailable: false,
      arHardwareSupported: null,
      diagnostic: diagnostic,
    );
  }
}

enum EventPreviewMode {
  augmentedReality,
  interactive3d,
  conceptFallback,
}

class EventPreviewDecision {
  final EventPreviewMode mode;
  final String label;
  final String? resourcePath;
  final String explanation;

  const EventPreviewDecision({
    required this.mode,
    required this.label,
    required this.resourcePath,
    required this.explanation,
  });
}

abstract final class EventPreviewPolicy {
  static EventPreviewDecision decide({
    required EventDesignRecommendation recommendation,
    required DeviceCapabilities capabilities,
  }) {
    final realArAvailable = capabilities.arState == ArCapabilityState.supported &&
        recommendation.backendArSupported == true &&
        recommendation.arPath != null;
    if (realArAvailable) {
      return EventPreviewDecision(
        mode: EventPreviewMode.augmentedReality,
        label: 'Open in AR',
        resourcePath: recommendation.arPath,
        explanation: 'This device and this BakeSmart scene both support AR.',
      );
    }

    final interactiveAvailable = recommendation.interactive3dReady &&
        recommendation.viewerPath != null;
    if (interactiveAvailable) {
      return EventPreviewDecision(
        mode: EventPreviewMode.interactive3d,
        label: 'Open Basic 3D Layout Preview',
        resourcePath: recommendation.viewerPath,
        explanation: _interactiveExplanation(capabilities, recommendation),
      );
    }

    return EventPreviewDecision(
      mode: EventPreviewMode.conceptFallback,
      label: recommendation.fallbackLabel ?? 'Concept preview—not to scale',
      resourcePath: null,
      explanation: 'A live-camera AR scene and interactive 3D viewer are not '
          'available for this result.',
    );
  }

  static String _interactiveExplanation(
    DeviceCapabilities capabilities,
    EventDesignRecommendation recommendation,
  ) {
    if (capabilities.arState == ArCapabilityState.unsupported) {
      return 'Live-camera AR is not supported by this device. The interactive '
          '3D view works without Google Play Services.';
    }
    if (capabilities.arState == ArCapabilityState.unavailable) {
      return 'AR hardware support could not be verified. The interactive 3D '
          'view remains available without live camera placement.';
    }
    if (recommendation.backendArSupported != true ||
        recommendation.arPath == null) {
      return 'The device reports AR-capable camera hardware, but this result '
          'does not include a real AR scene. Interactive 3D is shown instead.';
    }
    return 'Interactive 3D is available without live camera placement.';
  }
}
