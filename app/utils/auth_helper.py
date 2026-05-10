from flask import abort
from flask_login import current_user

def authorize_defect_access(defect):
    """
    Check if the current_user is authorized to access the given defect.
    Aborts with 403 Forbidden if not authorized.
    """
    if not current_user.is_authenticated:
        abort(401)

    user_type = getattr(current_user, 'user_type', '') or ''
    user_type = user_type.lower()
    
    role = getattr(current_user, 'role', '') or ''
    role = role.lower()

    if user_type == 'admin' or role == 'admin':
        return

    if user_type == 'homeowner' or role == 'homeowner':
        if defect.user_id != current_user.id:
            abort(403)
        return

    if user_type == 'developer' or role == 'developer':
        if defect.assigned_developer_id != current_user.id:
            abort(403)
        return

    if user_type in ['lawyer', 'legal'] or role in ['lawyer', 'legal']:
        if defect.assigned_lawyer_id != current_user.id:
            abort(403)
        return

    # If role is unknown or not set correctly, default deny
    abort(403)
