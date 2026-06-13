from flask_login import login_required, current_user
from flask import Blueprint, jsonify
from datetime import datetime, timezone

notifications = Blueprint('notifications', __name__, url_prefix='/notifications')


def _time_ago(dt: datetime) -> str:
    if not dt:
        return ''
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return 'just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours}h ago'
    days = hours // 24
    if days < 7:
        return f'{days}d ago'
    weeks = days // 7
    if weeks < 5:
        return f'{weeks}w ago'
    return dt.strftime('%d %b %Y')


@notifications.route('/api/unread')
@login_required
def api_unread():
    from ..models import Notification
    notifs = (
        Notification.query
        .filter_by(user_id=current_user.id, is_read=False)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    count = (
        Notification.query
        .filter_by(user_id=current_user.id, is_read=False)
        .count()
    )
    return jsonify({
        'count': count,
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'notification_type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat() if n.created_at else None,
            'time_ago': _time_ago(n.created_at),
        } for n in notifs],
    })


@notifications.route('/api/<int:notification_id>/read', methods=['POST'])
@login_required
def api_mark_read(notification_id):
    from ..models import Notification
    from ..extensions import db
    notif = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if not notif:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@notifications.route('/api/read-all', methods=['POST'])
@login_required
def api_mark_all_read():
    from ..models import Notification
    from ..extensions import db
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {'is_read': True}
    )
    db.session.commit()
    return jsonify({'success': True})
