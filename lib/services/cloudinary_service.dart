import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../core/constants/app_constants.dart';

class CloudinaryService {
  // Upload image to Cloudinary
  // Returns the secure URL of the uploaded image
  Future<String> uploadImage({
    required File imageFile,
    String? folder,
    void Function(double progress)? onProgress,
  }) async {
    final uri = Uri.parse(cloudinaryBaseUrl);

    final request = http.MultipartRequest('POST', uri);

    request.fields['upload_preset'] = cloudinaryUploadPreset;
    if (folder != null) {
      request.fields['folder'] = folder;
    }

    final fileStream = http.ByteStream(imageFile.openRead());
    final fileLength = await imageFile.length();

    final multipartFile = http.MultipartFile(
      'file',
      fileStream,
      fileLength,
      filename: imageFile.path.split('/').last,
    );

    request.files.add(multipartFile);

    try {
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return data['secure_url'] as String;
      } else {
        final error = json.decode(response.body);
        throw Exception(
            'Cloudinary upload failed: ${error['error']?['message'] ?? response.statusCode}');
      }
    } catch (e) {
      throw Exception('Image upload failed: $e');
    }
  }

  // Upload multiple images
  Future<List<String>> uploadMultipleImages({
    required List<File> imageFiles,
    String? folder,
    void Function(int current, int total)? onProgress,
  }) async {
    final urls = <String>[];
    for (int i = 0; i < imageFiles.length; i++) {
      onProgress?.call(i + 1, imageFiles.length);
      final url = await uploadImage(imageFile: imageFiles[i], folder: folder);
      urls.add(url);
    }
    return urls;
  }

  // Get optimized URL with transformations
  String getOptimizedUrl(String originalUrl,
      {int? width, int? height, String? crop}) {
    // Insert transformation parameters into Cloudinary URL
    final parts = originalUrl.split('/upload/');
    if (parts.length != 2) return originalUrl;

    final transformations = <String>[];
    if (width != null) transformations.add('w_$width');
    if (height != null) transformations.add('h_$height');
    if (crop != null) transformations.add('c_$crop');
    transformations.add('f_auto');
    transformations.add('q_auto');

    return '${parts[0]}/upload/${transformations.join(',')}/\${parts[1]}';
  }
}
