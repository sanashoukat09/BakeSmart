import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user_model.dart';

final firebaseAuthProvider = Provider<FirebaseAuth>((ref) {
  return FirebaseAuth.instance;
});

final firestoreProvider = Provider<FirebaseFirestore>((ref) {
  return FirebaseFirestore.instance;
});

final authStateProvider = StreamProvider<User?>((ref) {
  return ref.watch(firebaseAuthProvider).authStateChanges();
});

final userDataProvider = FutureProvider<UserModel?>((ref) async {
  final user = ref.watch(authStateProvider).value;
  if (user == null) return null;

  final doc = await ref.watch(firestoreProvider).collection('users').doc(user.uid).get();
  if (doc.exists) {
    return UserModel.fromMap(doc.data()!);
  }
  return null;
});

class AuthController {
  final FirebaseAuth _auth;
  final FirebaseFirestore _firestore;

  AuthController(this._auth, this._firestore);

  Future<void> signIn(String email, String password) async {
    await _auth.signInWithEmailAndPassword(email: email, password: password);
  }

  Future<void> registerCustomer({
    required String name,
    required String email,
    required String password,
  }) async {
    final cred = await _auth.createUserWithEmailAndPassword(email: email, password: password);
    final userModel = UserModel(
      uid: cred.user!.uid,
      name: name,
      email: email,
      role: 'customer',
      createdAt: DateTime.now(),
      dietaryPreferences: [],
      allergies: [],
    );
    await _firestore.collection('users').doc(cred.user!.uid).set(userModel.toMap());
  }

  Future<void> registerBaker({
    required String name,
    required String email,
    required String password,
    required String bakeryName,
    required String city,
  }) async {
    final cred = await _auth.createUserWithEmailAndPassword(email: email, password: password);
    final userModel = UserModel(
      uid: cred.user!.uid,
      name: name,
      email: email,
      role: 'baker',
      createdAt: DateTime.now(),
      bakeryName: bakeryName,
      city: city,
      verificationStatus: 'unverified',
      verificationBadge: false,
    );
    await _firestore.collection('users').doc(cred.user!.uid).set(userModel.toMap());
  }

  Future<void> resetPassword(String email) async {
    await _auth.sendPasswordResetEmail(email: email);
  }

  Future<void> signOut() async {
    await _auth.signOut();
  }
}

final authControllerProvider = Provider<AuthController>((ref) {
  return AuthController(ref.watch(firebaseAuthProvider), ref.watch(firestoreProvider));
});
