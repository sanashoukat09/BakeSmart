import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/auth_service.dart';
import '../services/firestore_service.dart';
import '../models/user_model.dart';

// ─── Service Providers ────────────────────────────────────────
final authServiceProvider = Provider<AuthService>((ref) => AuthService());
final firestoreServiceProvider =
    Provider<FirestoreService>((ref) => FirestoreService());

// ─── Firebase Auth State ──────────────────────────────────────
final firebaseAuthStateProvider = StreamProvider<User?>((ref) {
  return ref.watch(authServiceProvider).authStateChanges;
});

// ─── Current UserModel from Firestore ─────────────────────────
final currentUserProvider = StreamProvider<UserModel?>((ref) {
  final authState = ref.watch(firebaseAuthStateProvider);
  return authState.when(
    data: (user) {
      if (user == null) return Stream.value(null);
      return ref.watch(firestoreServiceProvider).streamUser(user.uid);
    },
    loading: () => Stream.value(null),
    error: (_, __) => Stream.value(null),
  );
});

// ─── Auth Loading State ────────────────────────────────────────
final authLoadingProvider = StateProvider<bool>((ref) => false);

// ─── Auth Error ────────────────────────────────────────────────
final authErrorProvider = StateProvider<String?>((ref) => null);

// ─── Auth Notifier ─────────────────────────────────────────────
class AuthNotifier extends StateNotifier<AsyncValue<void>> {
  final AuthService _authService;
  final FirestoreService _firestoreService;
  final Ref _ref;

  AuthNotifier(this._authService, this._firestoreService, this._ref)
      : super(const AsyncValue.data(null));

  Future<String?> signUp({
    required String email,
    required String password,
    required String role,
    String? displayName,
  }) async {
    state = const AsyncValue.loading();
    try {
      final credential = await _authService.signUpWithEmail(
        email: email,
        password: password,
      );
      final user = credential.user!;

      // Update display name
      if (displayName != null) {
        await user.updateDisplayName(displayName);
      }

      // Create Firestore user document
      final userModel = UserModel(
        uid: user.uid,
        email: email,
        role: role,
        displayName: displayName ?? email.split('@').first,
        createdAt: DateTime.now(),
        onboardingComplete: false,
      );
      await _firestoreService.createUser(userModel);

      state = const AsyncValue.data(null);
      return null;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return e.toString();
    }
  }

  Future<String?> signIn({
    required String email,
    required String password,
  }) async {
    state = const AsyncValue.loading();
    try {
      await _authService.signInWithEmail(email: email, password: password);
      state = const AsyncValue.data(null);
      return null;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return e.toString();
    }
  }

  Future<String?> signInWithGoogle({required String role}) async {
    state = const AsyncValue.loading();
    try {
      final credential = await _authService.signInWithGoogle();
      if (credential == null) {
        state = const AsyncValue.data(null);
        return null;
      }

      final user = credential.user!;
      final exists = await _firestoreService.userExists(user.uid);

      if (!exists) {
        // New Google user — create Firestore document
        final userModel = UserModel(
          uid: user.uid,
          email: user.email!,
          role: role,
          displayName: user.displayName ?? user.email!.split('@').first,
          photoUrl: user.photoURL,
          createdAt: DateTime.now(),
          onboardingComplete: false,
        );
        await _firestoreService.createUser(userModel);
      }

      state = const AsyncValue.data(null);
      return null;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return e.toString();
    }
  }

  Future<String?> sendPasswordReset(String email) async {
    state = const AsyncValue.loading();
    try {
      await _authService.sendPasswordResetEmail(email);
      state = const AsyncValue.data(null);
      return null;
    } catch (e) {
      state = AsyncValue.error(e, StackTrace.current);
      return e.toString();
    }
  }

  Future<void> signOut() async {
    await _authService.signOut();
  }
}

final authNotifierProvider =
    StateNotifierProvider<AuthNotifier, AsyncValue<void>>((ref) {
  return AuthNotifier(
    ref.watch(authServiceProvider),
    ref.watch(firestoreServiceProvider),
    ref,
  );
});
