enum PasswordStrength { weak, medium, strong }

class ValidationUtil {
  static String? validatePhoneNumber(String? value) {
    if (value == null || value.isEmpty) {
      return 'Phone number is required';
    }

    // Remove any spaces or dashes
    final clean = value.replaceAll(RegExp(r'[\s-]'), '');

    if (clean.startsWith('+92')) {
      if (clean.length != 13) {
        return 'Enter 10 digits after +92';
      }
      if (clean[3] != '3') {
        return 'Number must start with +923';
      }
    } else if (clean.startsWith('0')) {
      if (clean.length != 11) {
        return 'Enter 11 digits starting with 0';
      }
      if (clean[1] != '3') {
        return 'Number must start with 03';
      }
    } else {
      return 'Start with 0 (local) or +92 (intl)';
    }

    if (!RegExp(r'^[0-9+]+$').hasMatch(clean)) {
      return 'Enter a valid phone number';
    }

    return null;
  }

  static String? validateEmail(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'Email is required';
    }
    
    final email = value.trim().toLowerCase();
    
    // Explicitly reject any internal spaces
    if (email.contains(' ')) {
      return 'Enter a valid email address';
    }
    
    // 1. Basic format check (2+ chars before @, domain name, 2-3 char TLD)
    final emailRegex = RegExp(r'^[a-z0-9._%+-]{2,}@[a-z0-9.-]+\.[a-z]{2,3}$');
    if (!emailRegex.hasMatch(email)) {
      return 'Enter a valid email address';
    }

    // 2. Prevent consecutive dots anywhere
    if (email.contains('..')) {
      return 'Enter a valid email address';
    }

    final parts = email.split('@');
    final domain = parts[1];
    final domainName = domain.split('.')[0];

    // 3. Aggressive Gmail-specific typo detection
    // If it looks like gmail (starts with g, has m, ends with l), it MUST be exactly gmail.com
    final looksLikeGmail = domainName.startsWith('g') && 
                           domainName.contains('m') && 
                           domainName.endsWith('l') && 
                           domainName.length >= 4;

    if (looksLikeGmail || domain.contains('gmail') || domain.contains('gamil') || domain.contains('gmal')) {
      if (domain != 'gmail.com') {
        return 'Enter a valid email address';
      }
    }

    // 4. Prevent duplicated domain patterns
    if (RegExp(r'^(.+)\1$').hasMatch(domain)) {
      return 'Enter a valid email address';
    }
    
    return null;
  }

  static String? validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Password is required';
    }
    
    if (value.length < 8) return 'Minimum 8 characters required';
    
    return null;
  }

  static PasswordStrength getPasswordStrength(String password) {
    if (validatePassword(password) != null) {
      return PasswordStrength.weak;
    }
    // If it passes basic validation, it's at least medium
    // Make it strong if length >= 12
    if (password.length >= 12) {
      return PasswordStrength.strong;
    }
    return PasswordStrength.medium;
  }
}
