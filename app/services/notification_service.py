"""
Server-side Python notification service for user and system alerts.
"""

from typing import List, Optional
from app import db
from app.models.notification import Notification


def send_notification(user_id: int, title: str, message: str, notification_type: str = "INFO") -> Notification:
    """Send a server-side notification to a user."""
    noti = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
    )
    db.session.add(noti)
    db.session.commit()
    return noti


# Alias for create_notification
create_notification = send_notification


def get_user_notifications(user_id: int, limit: int = 20, unread_only: bool = False) -> List[Notification]:
    """Retrieve notifications for a user."""
    query = Notification.query.filter_by(user_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    """Mark a specific notification as read."""
    noti = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if noti:
        noti.is_read = True
        db.session.commit()
        return True
    return False


def mark_all_read(user_id: int) -> int:
    """Mark all unread notifications for a user as read."""
    unread = Notification.query.filter_by(user_id=user_id, is_read=False).all()
    for noti in unread:
        noti.is_read = True
    db.session.commit()
    return len(unread)
