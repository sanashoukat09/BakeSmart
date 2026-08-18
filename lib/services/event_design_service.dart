import 'dart:async';
import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import '../core/constants/app_constants.dart';
import '../models/event_design_model.dart';

class EventDesignServiceException implements Exception {
  final String message;

  const EventDesignServiceException(this.message);

  @override
  String toString() => message;
}

class EventDesignService {
  final FirebaseFirestore _db;
  final http.Client _client;
  final String baseUrl;

  EventDesignService({
    FirebaseFirestore? firestore,
    http.Client? client,
    this.baseUrl = AppConstants.bakeSmartAiBaseUrl,
  })  : _db = firestore ?? FirebaseFirestore.instance,
        _client = client ?? http.Client();

  Uri absoluteResourceUri(String resourcePath) {
    return resolveResourceUri(baseUrl: baseUrl, resourcePath: resourcePath);
  }

  static Uri resolveResourceUri({
    required String baseUrl,
    required String resourcePath,
  }) {
    final normalizedBase = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
    final relativePath =
        resourcePath.startsWith('/') ? resourcePath.substring(1) : resourcePath;
    return Uri.parse(normalizedBase).resolve(relativePath);
  }

  Future<EventDesignRecommendation> generate(
    EventDesignRequest request,
  ) async {
    final uri = absoluteResourceUri('/api/v1/recommendations');
    try {
      final response = await _client
          .post(
            uri,
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(request.toJson()),
          )
          .timeout(const Duration(seconds: 45));
      final decoded = _decodeObject(response.body);
      if (response.statusCode != 200) {
        throw EventDesignServiceException(
          _errorMessage(decoded, response.statusCode),
        );
      }
      return EventDesignRecommendation.fromJson(decoded);
    } on TimeoutException {
      throw const EventDesignServiceException(
        'The local BakeSmart model took too long to respond. Check that the '
        'Python service is running and try again.',
      );
    } on EventDesignServiceException {
      rethrow;
    } on FormatException {
      throw const EventDesignServiceException(
        'The BakeSmart model returned an unreadable response.',
      );
    } on http.ClientException {
      throw EventDesignServiceException(
        'Could not reach the local BakeSmart model at $baseUrl. Start the '
        'Python service or update BAKESMART_AI_BASE_URL.',
      );
    }
  }

  Future<void> openViewer(EventDesignRecommendation recommendation) async {
    final path = recommendation.viewerPath;
    if (!recommendation.interactive3dReady || path == null) {
      throw EventDesignServiceException(
        recommendation.fallbackLabel ?? 'Concept preview—not to scale',
      );
    }
    final opened = await openResource(path);
    if (!opened) {
      throw const EventDesignServiceException(
        'The interactive 3D viewer could not be opened on this device.',
      );
    }
  }

  Future<bool> openResource(String resourcePath) {
    return launchUrl(
      absoluteResourceUri(resourcePath),
      mode: LaunchMode.externalApplication,
    );
  }

  Future<SavedEventDesign> saveDesign({
    required EventDesignRequest request,
    required EventDesignRecommendation recommendation,
  }) async {
    final recordId = _recordId(request.customerId, recommendation.designId);
    final reference = _db
        .collection(AppConstants.eventDesignsCollection)
        .doc(recordId);
    final existing = await reference.get();
    final now = DateTime.now().toUtc();
    final existingData = existing.data();
    final saved = SavedEventDesign(
      recordId: recordId,
      ownerId: request.customerId,
      request: request,
      recommendation: recommendation,
      createdAt:
          (existingData?['createdAt'] as Timestamp?)?.toDate() ?? now,
      updatedAt: now,
      isShared: existingData?['isShared'] as bool? ?? false,
      shareCount: (existingData?['shareCount'] as num? ?? 0).toInt(),
    );
    await reference.set(saved.toFirestore(), SetOptions(merge: true));
    return saved;
  }

  Stream<List<SavedEventDesign>> streamSavedDesigns(String ownerId) {
    return _db
        .collection(AppConstants.eventDesignsCollection)
        .where('ownerId', isEqualTo: ownerId)
        .snapshots()
        .map((snapshot) {
      final designs = snapshot.docs
          .map(SavedEventDesign.fromFirestore)
          .toList(growable: false);
      designs.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      return designs;
    });
  }

  Future<void> markShared(SavedEventDesign design) async {
    await _db
        .collection(AppConstants.eventDesignsCollection)
        .doc(design.recordId)
        .update({
      'isShared': true,
      'shareCount': FieldValue.increment(1),
      'lastSharedAt': FieldValue.serverTimestamp(),
      'updatedAt': FieldValue.serverTimestamp(),
    });
  }

  Future<void> deleteDesign(SavedEventDesign design) async {
    await _db
        .collection(AppConstants.eventDesignsCollection)
        .doc(design.recordId)
        .delete();
  }

  static String _recordId(String ownerId, String designId) {
    final ownerKey = base64Url.encode(utf8.encode(ownerId)).replaceAll('=', '');
    return '${ownerKey}_$designId';
  }

  static Map<String, dynamic> _decodeObject(String body) {
    final decoded = jsonDecode(body);
    if (decoded is! Map) {
      throw const FormatException('Expected a JSON object');
    }
    return Map<String, dynamic>.from(decoded);
  }

  static String _errorMessage(Map<String, dynamic> body, int statusCode) {
    final detail = body['detail'];
    if (detail is Map && detail['message'] is String) {
      return detail['message'] as String;
    }
    if (detail is String) return detail;
    return 'BakeSmart could not create this design (error $statusCode).';
  }
}
