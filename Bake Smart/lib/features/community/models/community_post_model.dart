import 'package:cloud_firestore/cloud_firestore.dart';

class CommunityPostModel {
  final String postId;
  final String authorId;
  final String authorName;
  final bool authorIsVerified;
  final String content;
  final String? imageUrl;
  final List<String> likedBy; // UIDs of users who liked the post
  final int commentCount;
  final bool isFlagged;
  final DateTime createdAt;

  CommunityPostModel({
    required this.postId,
    required this.authorId,
    required this.authorName,
    required this.authorIsVerified,
    required this.content,
    this.imageUrl,
    required this.likedBy,
    required this.commentCount,
    this.isFlagged = false,
    required this.createdAt,
  });

  int get likesCount => likedBy.length;

  bool isLikedBy(String userId) => likedBy.contains(userId);

  CommunityPostModel copyWith({
    String? postId,
    String? authorId,
    String? authorName,
    bool? authorIsVerified,
    String? content,
    String? imageUrl,
    List<String>? likedBy,
    int? commentCount,
    bool? isFlagged,
    DateTime? createdAt,
  }) {
    return CommunityPostModel(
      postId: postId ?? this.postId,
      authorId: authorId ?? this.authorId,
      authorName: authorName ?? this.authorName,
      authorIsVerified: authorIsVerified ?? this.authorIsVerified,
      content: content ?? this.content,
      imageUrl: imageUrl ?? this.imageUrl,
      likedBy: likedBy ?? this.likedBy,
      commentCount: commentCount ?? this.commentCount,
      isFlagged: isFlagged ?? this.isFlagged,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'postId': postId,
      'authorId': authorId,
      'authorName': authorName,
      'authorIsVerified': authorIsVerified,
      'content': content,
      'imageUrl': imageUrl,
      'likedBy': likedBy,
      'commentCount': commentCount,
      'isFlagged': isFlagged,
      'createdAt': Timestamp.fromDate(createdAt),
    };
  }

  factory CommunityPostModel.fromMap(Map<String, dynamic> map, String docId) {
    return CommunityPostModel(
      postId: map['postId'] ?? docId,
      authorId: map['authorId'] ?? '',
      authorName: map['authorName'] ?? 'Unknown',
      authorIsVerified: map['authorIsVerified'] ?? false,
      content: map['content'] ?? '',
      imageUrl: map['imageUrl'],
      likedBy: List<String>.from(map['likedBy'] ?? []),
      commentCount: (map['commentCount'] ?? 0) as int,
      isFlagged: map['isFlagged'] ?? false,
      createdAt: (map['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }
}
