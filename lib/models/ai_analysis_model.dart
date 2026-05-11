import 'package:cloud_firestore/cloud_firestore.dart';

class AiAnalysisModel {
  final String id;
  final String userId;
  final String imageUrl;
  final String prompt;
  final String response;
  final DateTime timestamp;

  AiAnalysisModel({
    required this.id,
    required this.userId,
    required this.imageUrl,
    required this.prompt,
    required this.response,
    required this.timestamp,
  });

  factory AiAnalysisModel.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return AiAnalysisModel(
      id: doc.id,
      userId: data['userId'] ?? '',
      imageUrl: data['imageUrl'] ?? '',
      prompt: data['prompt'] ?? '',
      response: data['response'] ?? '',
      timestamp: (data['timestamp'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'userId': userId,
      'imageUrl': imageUrl,
      'prompt': prompt,
      'response': response,
      'timestamp': FieldValue.serverTimestamp(),
    };
  }
}
