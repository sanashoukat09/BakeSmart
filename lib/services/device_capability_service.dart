import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/device_capability_model.dart';

class DeviceCapabilityService {
  static const _channel =
      MethodChannel('com.bakesmart.app/device_capabilities');

  Future<DeviceCapabilities> detect() async {
    if (kIsWeb) {
      return DeviceCapabilities.unavailable(
        platform: 'web',
        diagnostic: 'Native AR hardware detection is unavailable on web.',
      );
    }
    if (defaultTargetPlatform != TargetPlatform.android) {
      return DeviceCapabilities.unavailable(
        platform: defaultTargetPlatform.name,
        diagnostic: 'Native AR hardware detection is currently implemented '
            'for Android only.',
      );
    }
    try {
      final values = await _channel.invokeMapMethod<Object?, Object?>(
        'getDeviceCapabilities',
      );
      if (values == null) {
        return DeviceCapabilities.unavailable(
          platform: 'android',
          diagnostic: 'Android returned no capability information.',
        );
      }
      return DeviceCapabilities.fromPlatformMap(values);
    } on PlatformException catch (error) {
      return DeviceCapabilities.unavailable(
        platform: 'android',
        diagnostic: error.message ?? error.code,
      );
    } on MissingPluginException {
      return DeviceCapabilities.unavailable(
        platform: 'android',
        diagnostic: 'The BakeSmart capability channel is unavailable.',
      );
    }
  }
}
