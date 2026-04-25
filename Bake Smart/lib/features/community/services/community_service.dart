import 'dart:io';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/services/cloudinary_service.dart';
import '../models/community_post_model.dart';
import '../models/comment_model.dart';

import '../../notifications/models/notification_model.dart';
import '../../notifications/services/notification_service.dart';

// ---------------------------------------------------------------------------
// Firestore & Storage providers
// ---------------------------------------------------------------------------

final firestoreProvider = Provider<FirebaseFirestore>((ref) {
  return FirebaseFirestore.instance;
});

// ---------------------------------------------------------------------------
// CommunityState — for paginated post feed
// ---------------------------------------------------------------------------

class CommunityFeedState {
  final List<CommunityPostModel> posts;
  final bool isLoading;
  final bool hasMore;
  final DocumentSnapshot? lastDoc;

  const CommunityFeedState({
    this.posts = const [],
    this.isLoading = false,
    this.hasMore = true,
    this.lastDoc,
  });

  CommunityFeedState copyWith({
    List<CommunityPostModel>? posts,
    bool? isLoading,
    bool? hasMore,
    DocumentSnapshot? lastDoc,
  }) {
    return CommunityFeedState(
      posts: posts ?? this.posts,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
      lastDoc: lastDoc ?? this.lastDoc,
    );
  }
}

// ---------------------------------------------------------------------------
// CommunityFeedNotifier — paginated post feed (15 per page, cursor-based)
// ---------------------------------------------------------------------------

class CommunityFeedNotifier extends Notifier<CommunityFeedState> {
  static const int _pageSize = 15;

  @override
  CommunityFeedState build() {
    Future.microtask(() => fetchFirstPage());
    return const CommunityFeedState();
  }

  FirebaseFirestore get _firestore => ref.read(firestoreProvider);

  Future<void> fetchFirstPage() async {
    state = state.copyWith(
      isLoading: true,
      posts: [],
      lastDoc: null,
      hasMore: true,
    );
    await _fetchPage(isNextPage: false);
  }

  Future<void> fetchNextPage() async {
    if (state.isLoading || !state.hasMore) return;
    state = state.copyWith(isLoading: true);
    await _fetchPage(isNextPage: true);
  }

  Future<void> _fetchPage({required bool isNextPage}) async {
    try {
      Query query = _firestore
          .collection('communityPosts')
          .orderBy('createdAt', descending: true)
          .limit(_pageSize);

      if (isNextPage && state.lastDoc != null) {
        query = query.startAfterDocument(state.lastDoc!);
      }

      final snapshot = await query.get();
      final fetchedPosts = snapshot.docs
          .map((doc) =>
              CommunityPostModel.fromMap(doc.data() as Map<String, dynamic>, doc.id))
          .toList();

      final newPosts =
          isNextPage ? [...state.posts, ...fetchedPosts] : fetchedPosts;

      state = state.copyWith(
        posts: newPosts,
        isLoading: false,
        hasMore: snapshot.docs.length == _pageSize,
        lastDoc: snapshot.docs.isNotEmpty ? snapshot.docs.last : state.lastDoc,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false);
      debugPrint('[CommunityFeedNotifier] Error fetching posts: $e');
    }
  }

  /// Optimistically update a single post in the local list after a like toggle.
  void updatePostLocally(CommunityPostModel updatedPost) {
    final updatedList = state.posts.map((p) {
      return p.postId == updatedPost.postId ? updatedPost : p;
    }).toList();
    state = state.copyWith(posts: updatedList);
  }

  /// Remove a deleted post from the local list immediately.
  void removePostLocally(String postId) {
    final updatedList = state.posts.where((p) => p.postId != postId).toList();
    state = state.copyWith(posts: updatedList);
  }
}

final communityFeedProvider =
    NotifierProvider<CommunityFeedNotifier, CommunityFeedState>(() {
  return CommunityFeedNotifier();
});

// ---------------------------------------------------------------------------
// Comments Stream — real-time list of comments for a single post
// ---------------------------------------------------------------------------

final commentsProvider =
    StreamProvider.family<List<CommentModel>, String>((ref, postId) {
  return FirebaseFirestore.instance
      .collection('communityPosts')
      .doc(postId)
      .collection('comments')
      .orderBy('createdAt', descending: false)
      .snapshots()
      .map((snapshot) => snapshot.docs
          .map((doc) =>
              CommentModel.fromMap(doc.data(), doc.id))
          .toList());
});

// ---------------------------------------------------------------------------
// CommunityService — all write operations
// ---------------------------------------------------------------------------

class CommunityService {
  final FirebaseFirestore _firestore;
  final CloudinaryService _cloudinary;
  final Ref _ref;

  CommunityService(this._firestore, this._cloudinary, this._ref);

  // ── Create Post ─────────────────────────────────────────────────────────

  Future<void> createPost({
    required String authorId,
    required String authorName,
    required bool authorIsVerified,
    required String content,
    File? imageFile,
  }) async {
    final docRef = _firestore.collection('communityPosts').doc();
    String? imageUrl;

    if (imageFile != null) {
      imageUrl = await _cloudinary.uploadImage(imageFile);
    }

    final now = DateTime.now();
    final post = CommunityPostModel(
      postId: docRef.id,
      authorId: authorId,
      authorName: authorName,
      authorIsVerified: authorIsVerified,
      content: content,
      imageUrl: imageUrl,
      likedBy: const [],
      commentCount: 0,
      isFlagged: false,
      createdAt: now,
    );

    await docRef.set(post.toMap());
  }

  // ── Delete Post ─────────────────────────────────────────────────────────

  Future<void> deletePost(String postId, {String? imageUrl}) async {
    // Note: Cloudinary deletion requires API Key/Secret and usually done via backend 
    // for security. Skipping for now as user requested free/simple setup.
    await _firestore.collection('communityPosts').doc(postId).delete();
  }

  // ── Toggle Like ─────────────────────────────────────────────────────────

  Future<void> toggleLike(String postId, String userId, bool isCurrentlyLiked) async {
    final docRef = _firestore.collection('communityPosts').doc(postId);
    if (isCurrentlyLiked) {
      await docRef.update({'likedBy': FieldValue.arrayRemove([userId])});
    } else {
      await docRef.update({'likedBy': FieldValue.arrayUnion([userId])});
    }
  }

  // ── Add Comment (atomic batch) ───────────────────────────────────────────

  Future<void> addComment({
    required String postId,
    required String authorId,
    required String authorName,
    required String content,
  }) async {
    // 1. Fetch Post to get AuthorId for notification
    final postDoc = await _firestore.collection('communityPosts').doc(postId).get();
    if (!postDoc.exists) throw Exception('Post not found');
    final postAuthorId = postDoc.data()?['authorId'];

    final batch = _firestore.batch();

    final commentRef = _firestore
        .collection('communityPosts')
        .doc(postId)
        .collection('comments')
        .doc();

    final now = DateTime.now();
    final comment = CommentModel(
      commentId: commentRef.id,
      postId: postId,
      authorId: authorId,
      authorName: authorName,
      content: content,
      createdAt: now,
    );

    // Write 1: add comment document
    batch.set(commentRef, comment.toMap());

    // Write 2: atomically increment commentCount on the post
    final postRef = _firestore.collection('communityPosts').doc(postId);
    batch.update(postRef, {'commentCount': FieldValue.increment(1)});

    // Write 3: Notify post author (if not the commenter)
    if (postAuthorId != null && postAuthorId != authorId) {
      _ref.read(notificationServiceProvider).sendNotificationWithBatch(
        batch,
        recipientId: postAuthorId,
        title: 'New comment on your post',
        body: '$authorName: $content',
        type: NotificationType.newComment,
        referenceId: postId,
      );
    }

    await batch.commit();
  }

  // ── Delete Comment (atomic batch) ───────────────────────────────────────

  Future<void> deleteComment(String postId, String commentId) async {
    final batch = _firestore.batch();

    final commentRef = _firestore
        .collection('communityPosts')
        .doc(postId)
        .collection('comments')
        .doc(commentId);

    // Write 1: delete comment document
    batch.delete(commentRef);

    // Write 2: atomically decrement commentCount on the post
    final postRef = _firestore.collection('communityPosts').doc(postId);
    batch.update(postRef, {'commentCount': FieldValue.increment(-1)});

    await batch.commit();
  }

  // ── Flag Post ────────────────────────────────────────────────────────────

  Future<void> flagPost(String postId) async {
    await _firestore
        .collection('communityPosts')
        .doc(postId)
        .update({'isFlagged': true});
  }
}

final communityServiceProvider = Provider<CommunityService>((ref) {
  return CommunityService(
    ref.read(firestoreProvider),
    ref.read(cloudinaryServiceProvider),
    ref,
  );
});
