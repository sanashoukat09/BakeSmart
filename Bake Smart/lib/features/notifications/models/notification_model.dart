import 'package:cloud_firestore/cloud_firestore.dart';

enum NotificationType {
  orderUpdate,
  verificationUpdate,
  newComment,
}

class NotificationModel {
  final String notificationId;
  final String recipientId;
  final String title;
  final String body;
  final bool isRead;
  final NotificationType type;
  final String referenceId; // orderId or postId
  final DateTime createdAt;

  NotificationModel({
    required this.notificationId,
    required this.recipientId,
    required this.title,
    required this.body,
    this.isRead = false,
    required this.type,
    required this.referenceId,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'notificationId': notificationId,
      'recipientId': recipientId,
      'title': title,
      'body': body,
      'isRead': isRead,
      'type': type.name,
      'referenceId': referenceId,
      'createdAt': Timestamp.fromDate(createdAt),
    };
  }

  factory NotificationModel.fromMap(Map<String, dynamic> map, String id) {
    return NotificationModel(
      notificationId: id,
      recipientId: map['recipientId'] ?? '',
      title: map['title'] ?? '',
      body: map['body'] ?? '',
      isRead: map['isRead'] ?? false,
      type: NotificationType.values.byName(map['type'] ?? 'orderUpdate'),
      referenceId: map['referenceId'] ?? '',
      createdAt: (map['createdAt'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }

  NotificationModel copyWith({
    String? notificationId,
    String? recipientId,
    String? title,
    String? body,
    bool? isRead,
    NotificationType? type,
    String? referenceId,
    DateTime? createdAt,
  }) {
    return NotificationModel(
      notificationId: notificationId ?? this.notificationId,
      recipientId: recipientId ?? this.recipientId,
      title: title ?? this.title,
      body: body ?? this.body,
      isRead: isRead ?? this.isRead,
      type: type ?? this.type,
      referenceId: referenceId ?? this.referenceId,
      createdAt: createdAt ?? this.createdAt,
    );
  }
}
