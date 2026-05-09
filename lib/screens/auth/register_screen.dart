import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/router/app_router.dart';
import '../../core/utils/validation_util.dart';
import '../../providers/auth_provider.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _obscurePassword = true;
  bool _obscureConfirm = true;
  bool _isLoading = false;
  bool _isFormValid = false;
  PasswordStrength _passwordStrength = PasswordStrength.weak;
  String? _errorMessage;
  String _selectedRole = 'baker'; // Default role

  late AnimationController _slideController;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _slideController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.05),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOut,
    ));
    _slideController.forward();

    _nameController.addListener(_validateForm);
    _emailController.addListener(_validateForm);
    _passwordController.addListener(_validatePasswordAndForm);
    _confirmPasswordController.addListener(_validateForm);
  }

  void _validatePasswordAndForm() {
    setState(() {
      _passwordStrength = ValidationUtil.getPasswordStrength(_passwordController.text);
    });
    _validateForm();
  }

  void _validateForm() {
    final isNameValid = _nameController.text.trim().isNotEmpty;
    final isEmailValid = ValidationUtil.validateEmail(_emailController.text) == null;
    final isPasswordValid = ValidationUtil.validatePassword(_passwordController.text) == null;
    final isConfirmValid = _confirmPasswordController.text == _passwordController.text;

    setState(() {
      _isFormValid = isNameValid && isEmailValid && isPasswordValid && isConfirmValid;
    });
  }

  @override
  void dispose() {
    _nameController.removeListener(_validateForm);
    _emailController.removeListener(_validateForm);
    _passwordController.removeListener(_validatePasswordAndForm);
    _confirmPasswordController.removeListener(_validateForm);
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _slideController.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final error = await ref.read(authNotifierProvider.notifier).signUp(
          email: _emailController.text.trim().toLowerCase(),
          password: _passwordController.text,
          role: _selectedRole,
          displayName: _nameController.text.trim(),
        );

    if (mounted) {
      setState(() => _isLoading = false);
      if (error != null) {
        setState(() => _errorMessage = error);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    const isDark = false;
    const primaryColor = Color(0xFF78350F);
    const bgColor = Color(0xFFFDFCF9);
    const textColor = Color(0xFF451A03);
    const subtextColor = Color(0xFF92400E);
    const borderColor = Color(0xFFFEF3C7);

    return Scaffold(
      backgroundColor: bgColor,
      appBar: AppBar(
        backgroundColor: bgColor,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: textColor),
          onPressed: () => context.pop(),
        ),
      ),
      body: SlideTransition(
        position: _slideAnimation,
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 8),
                Text(
                  'Create account',
                  style: TextStyle(
                    color: textColor,
                    fontSize: 40,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -1.0,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _selectedRole == 'baker' 
                    ? 'Join our community of professional bakers' 
                    : 'Discover fresh bakes from the best local bakers',
                  style: TextStyle(color: subtextColor, fontSize: 16),
                ),
                const SizedBox(height: 28),

                // Role Selector
                Row(
                  children: [
                    Expanded(
                      child: _buildRoleCard(
                        title: 'Baker',
                        subtitle: 'I want to sell',
                        icon: Icons.bakery_dining_rounded,
                        role: 'baker',
                        primaryColor: primaryColor,
                        textColor: textColor,
                        subtextColor: subtextColor,
                        borderColor: borderColor,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildRoleCard(
                        title: 'Customer',
                        subtitle: 'I want to buy',
                        icon: Icons.shopping_bag_outlined,
                        role: 'customer',
                        primaryColor: primaryColor,
                        textColor: textColor,
                        subtextColor: subtextColor,
                        borderColor: borderColor,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 24),

                // Error message
                if (_errorMessage != null)
                  Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFEF4444).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                          color: const Color(0xFFEF4444).withOpacity(0.3)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline,
                            color: Color(0xFFEF4444), size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(_errorMessage!,
                              style: const TextStyle(
                                  color: Color(0xFFEF4444), fontSize: 13)),
                        ),
                      ],
                    ),
                  ),

                // Form
                Form(
                  key: _formKey,
                  autovalidateMode: AutovalidateMode.onUserInteraction,
                  child: Column(
                    children: [
                      _buildField(
                        controller: _nameController,
                        label: 'Full name',
                        hint: 'Your name',
                        icon: Icons.person_outline,
                        isDark: isDark,
                        primaryColor: primaryColor,
                        borderColor: borderColor,
                        textColor: textColor,
                        subtextColor: subtextColor,
                        validator: (v) =>
                            v == null || v.isEmpty ? 'Name required' : null,
                      ),
                      const SizedBox(height: 14),
                      _buildField(
                        controller: _emailController,
                        label: 'Email address',
                        hint: 'you@example.com',
                        icon: Icons.email_outlined,
                        isDark: isDark,
                        primaryColor: primaryColor,
                        borderColor: borderColor,
                        textColor: textColor,
                        subtextColor: subtextColor,
                        keyboardType: TextInputType.emailAddress,
                        validator: ValidationUtil.validateEmail,
                      ),
                      const SizedBox(height: 14),
                      _buildField(
                        controller: _passwordController,
                        label: 'Password',
                        hint: 'At least 8 characters',
                        icon: Icons.lock_outline,
                        isDark: isDark,
                        primaryColor: primaryColor,
                        borderColor: borderColor,
                        textColor: textColor,
                        subtextColor: subtextColor,
                        obscureText: _obscurePassword,
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                            size: 20,
                            color: subtextColor,
                          ),
                          onPressed: () => setState(
                              () => _obscurePassword = !_obscurePassword),
                        ),
                        validator: ValidationUtil.validatePassword,
                      ),
                      const SizedBox(height: 8),
                      _buildPasswordStrengthIndicator(),
                      const SizedBox(height: 14),
                      _buildField(
                        controller: _confirmPasswordController,
                        label: 'Confirm password',
                        hint: 'Repeat your password',
                        icon: Icons.lock_outline,
                        isDark: isDark,
                        primaryColor: primaryColor,
                        borderColor: borderColor,
                        textColor: textColor,
                        subtextColor: subtextColor,
                        obscureText: _obscureConfirm,
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscureConfirm
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                            size: 20,
                            color: subtextColor,
                          ),
                          onPressed: () => setState(
                              () => _obscureConfirm = !_obscureConfirm),
                        ),
                        validator: (v) {
                          if (v != _passwordController.text)
                            return 'Passwords do not match';
                          return null;
                        },
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                // Register button
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: (_isLoading || !_isFormValid) ? null : _register,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor:
                          isDark ? const Color(0xFF0D1117) : Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: _isLoading
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.5,
                              valueColor:
                                  AlwaysStoppedAnimation<Color>(Colors.white),
                            ),
                          )
                        : const Text(
                            'Create Account',
                            style: TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w700),
                          ),
                  ),
                ),

                const SizedBox(height: 24),

                Center(
                  child: GestureDetector(
                    onTap: () => context.pop(),
                    child: RichText(
                      text: TextSpan(
                        text: 'Already have an account? ',
                        style: TextStyle(color: subtextColor, fontSize: 14),
                        children: [
                          TextSpan(
                            text: 'Sign in',
                            style: TextStyle(
                              color: primaryColor,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRoleCard({
    required String title,
    required String subtitle,
    required IconData icon,
    required String role,
    required Color primaryColor,
    required Color textColor,
    required Color subtextColor,
    required Color borderColor,
  }) {
    final isSelected = _selectedRole == role;
    return GestureDetector(
      onTap: () => setState(() => _selectedRole = role),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? Colors.white : Colors.white.withOpacity(0.5),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? primaryColor : borderColor,
            width: isSelected ? 2 : 1.5,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: primaryColor.withOpacity(0.1),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  )
                ]
              : null,
        ),
        child: Column(
          children: [
            Icon(
              icon,
              color: isSelected ? primaryColor : subtextColor,
              size: 28,
            ),
            const SizedBox(height: 8),
            Text(
              title,
              style: TextStyle(
                color: isSelected ? primaryColor : textColor,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: subtextColor,
                fontSize: 11,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    required bool isDark,
    required Color primaryColor,
    required Color borderColor,
    required Color textColor,
    required Color subtextColor,
    bool obscureText = false,
    Widget? suffixIcon,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      style: TextStyle(color: textColor, fontSize: 15),
      validator: validator,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, size: 20),
        suffixIcon: suffixIcon,
        filled: true,
        fillColor: Colors.white,
        labelStyle: TextStyle(color: subtextColor),
        hintStyle: const TextStyle(color: Color(0xFFA8A29E)),
        prefixIconColor: subtextColor,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: borderColor, width: 1.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: borderColor, width: 1.5),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFFEF4444), width: 2),
        ),
      ),
    );
  }

  Widget _buildPasswordStrengthIndicator() {
    Color color;
    String text;
    double progress;

    if (_passwordController.text.isEmpty) {
      return const SizedBox.shrink();
    }

    switch (_passwordStrength) {
      case PasswordStrength.weak:
        color = Colors.red;
        text = 'Weak';
        progress = 0.33;
        break;
      case PasswordStrength.medium:
        color = Colors.orange;
        text = 'Medium';
        progress = 0.66;
        break;
      case PasswordStrength.strong:
        color = Colors.green;
        text = 'Strong';
        progress = 1.0;
        break;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Password Strength',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
            ),
            Text(
              text,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: progress,
          backgroundColor: Colors.grey.shade300,
          valueColor: AlwaysStoppedAnimation<Color>(color),
          borderRadius: BorderRadius.circular(4),
          minHeight: 6,
        ),
      ],
    );
  }
}
