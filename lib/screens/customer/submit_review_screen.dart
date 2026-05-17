import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import 'package:go_router/go_router.dart';
import '../../providers/customer_order_provider.dart';
import '../../providers/auth_provider.dart';
import '../../models/review_model.dart';

// ════════════════════════════════════════════════════════════════════════════
//  DESIGN TOKENS
// ════════════════════════════════════════════════════════════════════════════

abstract class _T {
  static const canvas    = Color(0xFFFFFDF8);
  static const brown     = Color(0xFFB05E27);
  static const surface   = Color(0xFFFFFFFF);
  static const rimLight  = Color(0xFFF2EAE0);

  static const ink       = Color(0xFF4A2B20);
  static const inkMid    = Color(0xFF8C6D5F);
  static const inkFaint  = Color(0xFFD6C8BE);

  static const statusPink = Color(0xFFFF6B81);
  static const statusRed   = Color(0xFFE74C3C);

  static List<BoxShadow> shadowSm = [
    BoxShadow(color: brown.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4)),
  ];
}

class SubmitReviewScreen extends ConsumerStatefulWidget {
  final String orderId;
  const SubmitReviewScreen({super.key, required this.orderId});

  @override
  ConsumerState<SubmitReviewScreen> createState() => _SubmitReviewScreenState();
}

class _SubmitReviewScreenState extends ConsumerState<SubmitReviewScreen> {
  double _rating = 5.0;
  final _commentController = TextEditingController();

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final user = ref.read(currentUserProvider).valueOrNull!;
    final orders = ref.read(customerOrdersProvider).valueOrNull ?? [];
    final order = orders.firstWhere((o) => o.id == widget.orderId);

    if (order.isReviewed) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('You have already reviewed this order.')),
        );
        context.pop();
      }
      return;
    }

    final review = ReviewModel(
      id: const Uuid().v4(),
      orderId: widget.orderId,
      customerId: user.uid,
      customerName: user.displayName ?? 'Customer',
      bakerId: order.bakerId,
      productIds: order.items.map((item) => item.productId).toSet().toList(),
      rating: _rating,
      comment: _commentController.text.trim(),
      createdAt: DateTime.now(),
    );

    await ref.read(reviewNotifierProvider.notifier).submitReview(review);

    if (mounted) {
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSaving = ref.watch(reviewNotifierProvider).isLoading;

    return Scaffold(
      backgroundColor: _T.canvas,
      appBar: AppBar(
        backgroundColor: _T.canvas,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _T.ink),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'Rate & Review',
          style: TextStyle(
            color: _T.ink,
            fontSize: 19,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
        child: Column(
          children: [
            const Text(
              'How was your order?', 
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: _T.ink),
            ),
            const SizedBox(height: 8),
            const Text(
              'Your rating and feedback help us stay delicious!',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: _T.inkMid),
            ),
            const SizedBox(height: 28),
            
            // Stars Selector Row
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(5, (index) => IconButton(
                icon: Icon(
                  index < _rating ? Icons.star_rounded : Icons.star_outline_rounded,
                  color: Colors.amber,
                  size: 42,
                ),
                onPressed: () => setState(() => _rating = index + 1.0),
              )),
            ),
            const SizedBox(height: 36),
            
            // Comments Field
            TextField(
              controller: _commentController,
              maxLines: 5,
              cursorColor: _T.brown,
              style: const TextStyle(color: _T.ink, fontWeight: FontWeight.w600, fontSize: 14.5),
              decoration: InputDecoration(
                hintText: 'Write your feedback here...',
                hintStyle: const TextStyle(color: _T.inkFaint, fontWeight: FontWeight.w500, fontSize: 13.5),
                fillColor: _T.surface,
                filled: true,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: const BorderSide(color: _T.rimLight, width: 1.5),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: const BorderSide(color: _T.brown, width: 1.5),
                ),
                contentPadding: const EdgeInsets.all(20),
              ),
            ),
            const SizedBox(height: 48),
            
            ElevatedButton(
              onPressed: isSaving ? null : _submit,
              style: ElevatedButton.styleFrom(
                backgroundColor: _T.brown,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 54),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                elevation: 0,
              ),
              child: isSaving 
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) 
                  : const Text('Submit Review', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
            ),
          ],
        ),
      ),
    );
  }
}
