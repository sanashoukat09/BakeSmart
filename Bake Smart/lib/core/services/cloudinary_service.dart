import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/cloudinary_config.dart';

final cloudinaryServiceProvider = Provider((ref) => CloudinaryService());

class CloudinaryService {
  Future<String> uploadImage(dynamic imageFile) async {
    try {
      final request = http.MultipartRequest('POST', Uri.parse(CloudinaryConfig.uploadUrl));
      
      request.fields['upload_preset'] = CloudinaryConfig.uploadPreset;
      
      if (imageFile is File) {
        request.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
      } else if (imageFile is String) {
        // Assume it's a path if it's a string
        request.files.add(await http.MultipartFile.fromPath('file', imageFile));
      } else {
        throw Exception('Unsupported image file type');
      }

      final response = await request.send();
      final responseData = await response.stream.toBytes();
      final responseString = String.fromCharCodes(responseData);
      
      if (response.statusCode == 200) {
        final jsonResponse = jsonDecode(responseString);
        return jsonResponse['secure_url'];
      } else {
        print('Cloudinary Upload Error: $responseString');
        throw Exception('Failed to upload image to Cloudinary: ${response.statusCode}');
      }
    } catch (e) {
      print('Cloudinary Exception: $e');
      throw Exception('Cloudinary Exception: $e');
    }
  }

  Future<List<String>> uploadMultipleImages(List<dynamic> images) async {
    List<String> urls = [];
    for (var image in images) {
      final url = await uploadImage(image);
      urls.add(url);
    }
    return urls;
  }
}
