package com.bakesmart.app

import android.content.pm.PackageManager
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    companion object {
        private const val CAPABILITY_CHANNEL =
            "com.bakesmart.app/device_capabilities"
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            CAPABILITY_CHANNEL,
        ).setMethodCallHandler { call, result ->
            if (call.method != "getDeviceCapabilities") {
                result.notImplemented()
                return@setMethodCallHandler
            }

            val cameraAvailable = packageManager.hasSystemFeature(
                PackageManager.FEATURE_CAMERA_ANY,
            )
            val arHardwareSupported = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P &&
                packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_AR)

            result.success(
                mapOf(
                    "platform" to "android",
                    "api_level" to Build.VERSION.SDK_INT,
                    "camera_available" to cameraAvailable,
                    "ar_hardware_supported" to arHardwareSupported,
                    "detection_source" to "android.hardware.camera.ar",
                ),
            )
        }
    }
}
