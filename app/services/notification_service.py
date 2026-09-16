from app import db
from app.models.notification import Notification


def send_notification(user_id: int, title: str, message: str, notification_type: str = "INFO"):
    """
    Create a user notification for security events, OTP issuance, transfers, or maker-checker alerts.
    """
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
    )
    db.session.add(notif)
    return notif


def mark_notifications_read(user_id: int):
    notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
    for n in notifications:
        n.is_read = True
    db.session.commit()
