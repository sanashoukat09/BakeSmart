import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/device_capability_model.dart';
import '../services/device_capability_service.dart';

final deviceCapabilityServiceProvider = Provider<DeviceCapabilityService>((ref) {
  return DeviceCapabilityService();
});

final deviceCapabilitiesProvider = FutureProvider<DeviceCapabilities>((ref) {
  return ref.watch(deviceCapabilityServiceProvider).detect();
});
