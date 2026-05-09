import 'package:bakesmart/core/utils/validation_util.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ValidationUtil Tests', () {
    group('validateEmail', () {
      test('Returns error for empty email', () {
        expect(ValidationUtil.validateEmail(''), isNotNull);
        expect(ValidationUtil.validateEmail(null), isNotNull);
      });

      test('Returns error for short username (1 char)', () {
        expect(ValidationUtil.validateEmail('s@gmail.com'), isNotNull);
      });

      test('Returns error for emails with spaces or double dots', () {
        expect(ValidationUtil.validateEmail('test @gmail.com'), isNotNull);
        expect(ValidationUtil.validateEmail('sana @gmail.com'), isNotNull);
        expect(ValidationUtil.validateEmail('sana@gmail..com'), isNotNull);
      });

      test('Trims and validates valid emails', () {
        expect(ValidationUtil.validateEmail(' test@gmail.com '), isNull);
        expect(ValidationUtil.validateEmail('user.name@domain.co'), isNull);
        expect(ValidationUtil.validateEmail('user+label@domain.com'), isNull);
      });

      test('Returns error for multiple @ symbols', () {
        expect(ValidationUtil.validateEmail('user@@gmail.com'), isNotNull);
      });

      test('Returns error for duplicated domains and TLDs', () {
        expect(ValidationUtil.validateEmail('user@gmail.comgmail.com'), isNotNull);
        expect(ValidationUtil.validateEmail('user@gmail.com.com'), isNotNull);
        expect(ValidationUtil.validateEmail('user@gmail.comm'), isNotNull);
      });

      test('Returns error for gmail typos and invalid gmail TLDs', () {
        expect(ValidationUtil.validateEmail('sana@ggmail.com'), isNotNull);
        expect(ValidationUtil.validateEmail('sana@gamil.com'), isNotNull);
        expect(ValidationUtil.validateEmail('sana@gmal.com'), isNotNull);
        expect(ValidationUtil.validateEmail('sana@gmmaaill.coo'), isNotNull);
        expect(ValidationUtil.validateEmail('sana@gmail.co'), isNotNull);
        expect(ValidationUtil.validateEmail('sana@gmail.net'), isNotNull);
      });

      test('Returns error for missing username', () {
        expect(ValidationUtil.validateEmail('@gmail.com'), isNotNull);
      });

      test('Lowercases and validates uppercase emails', () {
        expect(ValidationUtil.validateEmail('USER@GMAIL.COM'), isNull);
      });
    });

    group('validatePassword', () {
      test('Returns error for empty password', () {
        expect(ValidationUtil.validatePassword(''), isNotNull);
      });

      test('Returns error if less than 8 characters', () {
        expect(ValidationUtil.validatePassword('Aa1!bcd'), isNotNull);
      });

      test('Returns null for valid password (min 8 chars)', () {
        expect(ValidationUtil.validatePassword('password'), isNull);
        expect(ValidationUtil.validatePassword('A1234567'), isNull);
      });
    });

    group('getPasswordStrength', () {
      test('Returns weak for invalid passwords', () {
        expect(ValidationUtil.getPasswordStrength('abc'), PasswordStrength.weak);
      });

      test('Returns medium for basic valid password', () {
        expect(ValidationUtil.getPasswordStrength('Password1!'), PasswordStrength.medium);
      });

      test('Returns strong for valid password >= 12 chars', () {
        expect(ValidationUtil.getPasswordStrength('VeryStrongPass1!'), PasswordStrength.strong);
      });
    });
  });
}
