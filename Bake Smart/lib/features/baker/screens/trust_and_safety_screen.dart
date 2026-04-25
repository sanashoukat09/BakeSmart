import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class TrustAndSafetyScreen extends StatelessWidget {
  const TrustAndSafetyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text('Trust & Safety'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.brown,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Your Privacy and Safety',
              style: GoogleFonts.outfit(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.brown),
            ),
            const SizedBox(height: 16),
            const Text(
              'At BakeSmart, we believe in building a platform based on transparency and community trust. Here is how we handle your data.',
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
            const SizedBox(height: 32),
            
            _buildSection(
              'What we collect',
              'We collect bakery details, your kitchen photo, and product examples to verify you are a genuine home baker.',
            ),
            _buildSection(
              'What we do NOT collect',
              'We do NOT collect CNIC or national ID at this stage. Identity documents are only requested if you choose to enable bank transfer withdrawals in the future.',
            ),
            _buildSection(
              'How your data is protected',
              'All photos are stored securely on Google Firebase Storage and are only visible to BakeSmart administrators for verification purposes. Your photos are never shared publicly or with third parties.',
            ),
            _buildSection(
              'Your rights',
              'You can delete your account and all associated data at any time from your profile settings.',
            ),
            
            const Divider(height: 64),
            
            Text(
              'Terms and Conditions',
              style: GoogleFonts.outfit(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.brown),
            ),
            const SizedBox(height: 16),
            _buildPoint('BakeSmart is a marketplace platform connecting home bakers with customers. We do not employ bakers or guarantee their products.'),
            _buildPoint('Bakers are responsible for food quality, hygiene, and accurate product descriptions.'),
            _buildPoint('BakeSmart reserves the right to remove any baker account found to be providing false information or receiving consistent negative reviews.'),
            _buildPoint('Customer disputes are handled through the in-app order management system.'),
            _buildPoint('BakeSmart does not currently charge commission on sales during the beta period.'),
            
            const SizedBox(height: 48),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.brown,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Back'),
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildSection(String title, String content) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.brown)),
          const SizedBox(height: 8),
          Text(content, style: TextStyle(color: Colors.grey[700], height: 1.5)),
        ],
      ),
    );
  }

  Widget _buildPoint(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.check_circle, color: Colors.green, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 14, height: 1.4))),
        ],
      ),
    );
  }
}
