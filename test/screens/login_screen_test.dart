import 'package:bakesmart/screens/auth/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Widget createWidgetUnderTest() {
    return const ProviderScope(
      child: MaterialApp(
        home: LoginScreen(),
      ),
    );
  }

  group('LoginScreen Widget Tests', () {
    testWidgets('Login button is initially disabled', (WidgetTester tester) async {
      await tester.pumpWidget(createWidgetUnderTest());
      final signInButton = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(signInButton.onPressed, isNull);
    });

    testWidgets('Sign In button is enabled when EITHER field has text', (WidgetTester tester) async {
      await tester.pumpWidget(createWidgetUnderTest());

      // Case 1: Only email has text
      await tester.enterText(find.byType(TextFormField).first, 'a');
      await tester.pump();
      expect(tester.widget<ElevatedButton>(find.byType(ElevatedButton)).onPressed, isNotNull);

      // Case 2: Only password has text
      await tester.enterText(find.byType(TextFormField).first, '');
      await tester.enterText(find.byType(TextFormField).last, 'b');
      await tester.pump();
      expect(tester.widget<ElevatedButton>(find.byType(ElevatedButton)).onPressed, isNotNull);
      
      // Case 3: Both empty
      await tester.enterText(find.byType(TextFormField).last, '');
      await tester.pump();
      expect(tester.widget<ElevatedButton>(find.byType(ElevatedButton)).onPressed, isNull);
    });

    testWidgets('No live validation errors while typing', (WidgetTester tester) async {
      await tester.pumpWidget(createWidgetUnderTest());

      // Enter "invalid" email format and some password
      await tester.enterText(find.byType(TextFormField).first, 'not-an-email');
      await tester.pump();

      // Should NOT show "Enter a valid email"
      expect(find.text('Enter a valid email'), findsNothing);
      expect(find.text('Email required'), findsNothing);
    });
  });
}
