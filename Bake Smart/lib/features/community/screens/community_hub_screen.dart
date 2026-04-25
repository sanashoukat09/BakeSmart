import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/services/auth_provider.dart';
import '../models/community_post_model.dart';
import '../services/community_service.dart';
import 'create_post_screen.dart';
import 'post_detail_screen.dart';
import 'package:cached_network_image/cached_network_image.dart';

class CommunityHubScreen extends ConsumerStatefulWidget {
  const CommunityHubScreen({super.key});

  @override
  ConsumerState<CommunityHubScreen> createState() => _CommunityHubScreenState();
}

class _CommunityHubScreenState extends ConsumerState<CommunityHubScreen> {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 250) {
      ref.read(communityFeedProvider.notifier).fetchNextPage();
    }
  }

  Future<void> _onRefresh() async {
    await ref.read(communityFeedProvider.notifier).fetchFirstPage();
  }

  void _openCreatePost(String authorId, String authorName, bool isVerified) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CreatePostScreen(
          authorId: authorId,
          authorName: authorName,
          authorIsVerified: isVerified,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final feedState = ref.watch(communityFeedProvider);
    final userData = ref.watch(userDataProvider);

    return userData.when(
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(body: Center(child: Text('Error: $e'))),
      data: (user) {
        final currentUserId = user?.uid ?? '';
        final currentUserName = user?.name ?? 'Unknown';
        final isVerified = user?.verificationStatus == 'verified';

        return Scaffold(
          backgroundColor: const Color(0xFFF5F0EB),
          appBar: AppBar(
            title: const Text(
              'Community Hub',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 20),
            ),
            backgroundColor: const Color(0xFF5D4037),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: () => _openCreatePost(currentUserId, currentUserName, isVerified),
            backgroundColor: const Color(0xFF5D4037),
            foregroundColor: Colors.white,
            icon: const Icon(Icons.edit_rounded),
            label: const Text('Post', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
          body: RefreshIndicator(
            onRefresh: _onRefresh,
            color: const Color(0xFF5D4037),
            child: feedState.posts.isEmpty && !feedState.isLoading
                ? _buildEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.only(top: 12, bottom: 100),
                    itemCount: feedState.posts.length + (feedState.hasMore ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == feedState.posts.length) {
                        return const Padding(
                          padding: EdgeInsets.all(24),
                          child: Center(child: CircularProgressIndicator(color: Color(0xFF5D4037))),
                        );
                      }
                      final post = feedState.posts[index];
                      return _PostCard(
                        post: post,
                        currentUserId: currentUserId,
                      );
                    },
                  ),
          ),
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.7,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.cake_rounded, size: 80, color: Colors.brown[200]),
              const SizedBox(height: 16),
              const Text(
                'No posts yet!',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF5D4037),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Be the first to share your baking journey.',
                style: TextStyle(color: Colors.grey[600], fontSize: 14),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _PostCard Widget
// ---------------------------------------------------------------------------

class _PostCard extends ConsumerWidget {
  final CommunityPostModel post;
  final String currentUserId;

  const _PostCard({required this.post, required this.currentUserId});

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Post'),
        content: const Text('Are you sure you want to delete this post? This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      try {
        await ref.read(communityServiceProvider).deletePost(
          post.postId,
          imageUrl: post.imageUrl,
        );
        ref.read(communityFeedProvider.notifier).removePostLocally(post.postId);
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to delete post: $e'), backgroundColor: Colors.red),
          );
        }
      }
    }
  }

  Future<void> _flagPost(BuildContext context, WidgetRef ref) async {
    if (post.isFlagged) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('This post has already been reported.')),
      );
      return;
    }
    try {
      await ref.read(communityServiceProvider).flagPost(post.postId);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Post reported. Our team will review it.'),
            backgroundColor: Color(0xFF5D4037),
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to report: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _toggleLike(WidgetRef ref) {
    final isLiked = post.isLikedBy(currentUserId);

    // Optimistic update — reflect immediately in UI
    final updatedLikedBy = isLiked
        ? (List<String>.from(post.likedBy)..remove(currentUserId))
        : [...post.likedBy, currentUserId];

    ref.read(communityFeedProvider.notifier).updatePostLocally(
          post.copyWith(likedBy: updatedLikedBy),
        );

    ref.read(communityServiceProvider).toggleLike(post.postId, currentUserId, isLiked);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOwner = post.authorId == currentUserId;
    final isLiked = post.isLikedBy(currentUserId);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.06),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ────────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 8, 0),
            child: Row(
              children: [
                // Avatar
                CircleAvatar(
                  radius: 22,
                  backgroundColor: const Color(0xFF5D4037),
                  child: Text(
                    post.authorName.isNotEmpty
                        ? post.authorName[0].toUpperCase()
                        : '?',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            post.authorName,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                              color: Color(0xFF2C1810),
                            ),
                          ),
                          if (post.authorIsVerified) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: const Color(0xFF00897B),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.verified_rounded,
                                      size: 10, color: Colors.white),
                                  SizedBox(width: 2),
                                  Text(
                                    'Verified Baker',
                                    style: TextStyle(
                                        color: Colors.white,
                                        fontSize: 9,
                                        fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                            ),
                          ],
                          if (post.isFlagged) ...[
                            const SizedBox(width: 6),
                            const Icon(Icons.flag_rounded,
                                size: 14, color: Colors.orange),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _relativeTime(post.createdAt),
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ),
                ),
                // Three-dot menu
                PopupMenuButton<String>(
                  icon: Icon(Icons.more_vert, color: Colors.grey[500]),
                  onSelected: (value) {
                    if (value == 'delete') _confirmDelete(context, ref);
                    if (value == 'flag') _flagPost(context, ref);
                  },
                  itemBuilder: (ctx) => [
                    if (isOwner)
                      const PopupMenuItem(
                        value: 'delete',
                        child: Row(
                          children: [
                            Icon(Icons.delete_outline, color: Colors.red, size: 18),
                            SizedBox(width: 8),
                            Text('Delete Post', style: TextStyle(color: Colors.red)),
                          ],
                        ),
                      ),
                    if (!isOwner)
                      const PopupMenuItem(
                        value: 'flag',
                        child: Row(
                          children: [
                            Icon(Icons.flag_outlined, color: Colors.orange, size: 18),
                            SizedBox(width: 8),
                            Text('Report Post'),
                          ],
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),

          // ── Content ───────────────────────────────────────────────────
          if (post.content.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Text(
                post.content,
                style: const TextStyle(
                  fontSize: 14.5,
                  height: 1.45,
                  color: Color(0xFF3E2723),
                ),
              ),
            ),

          // ── Image ─────────────────────────────────────────────────────
          if (post.imageUrl != null) ...[
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () => _showFullImage(context, post.imageUrl!),
              child: ClipRRect(
                borderRadius:
                    const BorderRadius.vertical(bottom: Radius.zero),
                child: CachedNetworkImage(
                  imageUrl: post.imageUrl!,
                  width: double.infinity,
                  height: 220,
                  fit: BoxFit.cover,
                  placeholder: (context, url) => Container(
                    height: 220,
                    color: Colors.grey[200],
                    child: const Center(child: CircularProgressIndicator(color: Color(0xFF5D4037))),
                  ),
                  errorWidget: (context, url, error) => Container(
                    height: 220,
                    color: Colors.grey[200],
                    child: const Icon(Icons.broken_image, color: Colors.grey, size: 40),
                  ),
                ),
              ),
            ),
          ],

          // ── Action Row ────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 6, 4, 4),
            child: Row(
              children: [
                // Like button
                _ActionButton(
                  icon: isLiked
                      ? Icons.favorite_rounded
                      : Icons.favorite_border_rounded,
                  label: '${post.likesCount}',
                  color: isLiked ? Colors.red : Colors.grey[600]!,
                  onTap: () => _toggleLike(ref),
                ),
                const SizedBox(width: 4),
                // Comment button
                _ActionButton(
                  icon: Icons.chat_bubble_outline_rounded,
                  label: '${post.commentCount}',
                  color: Colors.grey[600]!,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => PostDetailScreen(
                        post: post,
                        currentUserId: currentUserId,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showFullImage(BuildContext context, String imageUrl) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(12),
        child: GestureDetector(
          onTap: () => Navigator.pop(ctx),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: CachedNetworkImage(
              imageUrl: imageUrl,
              fit: BoxFit.contain,
              placeholder: (context, url) => const Center(child: CircularProgressIndicator(color: Colors.white)),
              errorWidget: (context, url, error) => const Icon(Icons.error, color: Colors.white),
            ),
          ),
        ),
      ),
    );
  }

  String _relativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inSeconds < 60) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.day}/${dt.month}/${dt.year}';
  }
}

// ---------------------------------------------------------------------------
// _ActionButton — small icon + label tap area
// ---------------------------------------------------------------------------

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 20, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: color,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
