import 'dart:convert';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_generative_ai/google_generative_ai.dart';
import 'package:http/http.dart' as http;
import '../models/ai_analysis_model.dart';

class AiService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  Future<Map<String, dynamic>> analyzeCakeDesign({
    required String imageUrl,
    required String bakerId,
  }) async {
    try {
      // 1. Check Rate Limit (Usage Counter)
      final usageRef = _db.collection('usage_counters').doc(bakerId);
      final usageSnap = await usageRef.get();
      final usageData = usageSnap.data() ?? {'photo_analysis_today': 0};
      
      final lastAnalysisAt = (usageData['last_analysis_at'] as Timestamp?)?.toDate();
      final now = DateTime.now();
      
      int countToday = usageData['photo_analysis_today'] ?? 0;
      
      // Reset counter if it's a new day
      if (lastAnalysisAt != null && 
          (lastAnalysisAt.day != now.day || 
           lastAnalysisAt.month != now.month || 
           lastAnalysisAt.year != now.year)) {
        countToday = 0;
        await usageRef.update({'photo_analysis_today': 0});
      }

      if (countToday >= 10) {
        throw Exception('rate_limit_exceeded');
      }

      // 2. Prepare Gemini
      final apiKey = dotenv.env['GEMINI_API_KEY'];
      if (apiKey == null) throw Exception('Gemini API Key not found in .env');

      final model = GenerativeModel(
        model: 'gemini-2.5-flash',
        apiKey: apiKey,
      );

      // 3. Fetch Image Bytes
      final imageResponse = await http.get(Uri.parse(imageUrl));
      if (imageResponse.statusCode != 200) {
        throw Exception('Failed to fetch image from URL');
      }
      final imageBytes = imageResponse.bodyBytes;

      // 4. Call Gemini
      final prompt = '''
You are an expert cake decorator. Analyze this cake design image and produce a JSON object.
Keys required: steps (array), colors (array), piping_tips (array), layers (number), tools_materials (array), estimated_time_minutes (number).
If not a cake: {"error": "not_a_cake"}
If unclear: {"error": "image_too_unclear"}

Return ONLY the raw JSON object. No markdown, no "json" labels.
''';

      final content = [
        Content.multi([
          TextPart(prompt),
          DataPart('image/jpeg', imageBytes),
        ])
      ];

      final response = await model.generateContent(content);

      final String? responseText = response.text;
      if (responseText == null) throw Exception('Empty response from Gemini');

      // Cleanup JSON from markdown if present
      String cleanJson = responseText.trim();
      if (cleanJson.contains('```')) {
        cleanJson = cleanJson.split('```')[1];
        if (cleanJson.startsWith('json')) {
          cleanJson = cleanJson.substring(4);
        }
      }
      final Map<String, dynamic> analysis = jsonDecode(cleanJson);

      // 5. Save to Firestore and Update Counter
      if (analysis['error'] == null) {
        final analysisRecord = {
          'bakerId': bakerId,
          'imageUrl': imageUrl,
          ...analysis,
          'analyzedAt': FieldValue.serverTimestamp(),
          'status': 'completed',
        };

        await _db.collection('photo_analyses').add(analysisRecord);
        await usageRef.set({
          'photo_analysis_today': FieldValue.increment(1),
          'last_analysis_at': FieldValue.serverTimestamp(),
        }, SetOptions(merge: true));
      }

      return analysis;
    } catch (e) {
      print('Error in analyzeCakeDesign: $e');
      if (e.toString().contains('rate_limit_exceeded')) {
        return {'error': 'rate_limit_exceeded'};
      }
      throw Exception('AI Analysis failed: $e');
    }
  }

  // Stream history for UI
  Stream<List<Map<String, dynamic>>> streamUserHistory(String bakerId) {
    return _db
        .collection('photo_analyses')
        .where('bakerId', isEqualTo: bakerId)
        .orderBy('analyzedAt', descending: true)
        .snapshots()
        .map((snapshot) => snapshot.docs.map((doc) => {'id': doc.id, ...doc.data()}).toList());
  }
}
