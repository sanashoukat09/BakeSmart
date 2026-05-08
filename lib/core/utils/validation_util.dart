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
}
