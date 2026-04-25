import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../services/admin_service.dart';
import '../models/community_post_model.dart';

class CommunityModerationScreen extends ConsumerStatefulWidget {
  const CommunityModerationScreen({super.key});

  @override
  ConsumerState<CommunityModerationScreen> createState() => _CommunityModerationScreenState();
}

class _CommunityModerationScreenState extends ConsumerState<CommunityModerationScreen> {
  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(
        children: [
          Container(
            color: Colors.white,
            child: const TabBar(
              tabs: [
                Tab(text: 'Flagged Posts'),
                Tab(text: 'All Posts'),
              ],
              labelColor: Colors.brown,
              indicatorColor: Colors.brown,
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                _buildPostTable(ref.watch(flaggedPostsProvider)),
                _buildPostTable(ref.watch(allPostsProvider)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPostTable(AsyncValue<List<CommunityPostModel>> postsAsync) {
    return postsAsync.when(
      data: (posts) => SingleChildScrollView(
        padding: const EdgeInsets.all(40),
        child: Container(
          width: double.infinity,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFEEEEEE)),
          ),
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: const Color(0xFFEEEEEE)),
            child: DataTable(
              columns: const [
                DataColumn(label: Text('Author', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Content', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Date', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Status', style: TextStyle(fontWeight: FontWeight.bold))),
                DataColumn(label: Text('Actions', style: TextStyle(fontWeight: FontWeight.bold))),
              ],
              rows: posts.map((post) => DataRow(cells: [
                DataCell(Text(post.authorName)),
                DataCell(Text(
                  post.content.length > 100 ? '${post.content.substring(0, 100)}...' : post.content,
                  style: const TextStyle(fontSize: 13),
                )),
                DataCell(Text(DateFormat('MMM dd, yyyy').format(post.createdAt))),
                DataCell(
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: (post.isFlagged ? Colors.red : Colors.green).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      post.isFlagged ? 'FLAGGED' : 'SAFE',
                      style: TextStyle(color: post.isFlagged ? Colors.red : Colors.green, fontSize: 10, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                DataCell(Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.visibility_outlined, size: 20),
                      onPressed: () => _viewPost(post),
                      tooltip: 'View Full Post',
                    ),
                    if (post.isFlagged)
                      IconButton(
                        icon: const Icon(Icons.check_circle_outline, color: Colors.green, size: 20),
                        onPressed: () => ref.read(adminServiceProvider).restorePost('current_admin', post.postId),
                        tooltip: 'Restore/Clear Flag',
                      ),
                    IconButton(
                      icon: const Icon(Icons.delete_outline, color: Colors.red, size: 20),
                      onPressed: () => _confirmDelete(post.postId),
                      tooltip: 'Remove Post',
                    ),
                  ],
                )),
              ])).toList(),
            ),
          ),
        ),
      ),
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
    );
  }

  void _viewPost(CommunityPostModel post) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Post by ${post.authorName}'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (post.imageUrl != null)
                Image.network(post.imageUrl!, height: 300, width: double.infinity, fit: BoxFit.cover),
              const SizedBox(height: 16),
              Text(post.content),
              const SizedBox(height: 16),
              Text('Posted on: ${DateFormat('MMM dd, yyyy HH:mm').format(post.createdAt)}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
        ],
      ),
    );
  }

  void _confirmDelete(String postId) {
    // Note: Use ref.read(adminServiceProvider).removePost passing the current admin ID
    ref.read(adminServiceProvider).removePost('current_admin', postId);
  }
}
