from functools import wraps

from flask import abort, jsonify
from flask_login import current_user


def roles_required(*roles):
    """Restrict a view to one or more roles. Must be used after @login_required."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def json_errors(view_func):
    """Turn ValidationError (and generic exceptions) into clean JSON error responses."""
    from app.utils.validators import ValidationError

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except ValidationError as e:
            return jsonify(error=e.message, field=e.field), 400
    return wrapped
