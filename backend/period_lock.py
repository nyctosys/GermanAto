"""Month-end close for financial records.

A month closes on its own once it has ended. Past months stay readable but
cannot be edited, so last month's figures don't move after they have been
reported on. An admin can still make a correction, and can reopen a month
outright when a real one is needed.

The rule lives here rather than in each route so every financial write answers
to the same definition of "closed".
"""
from datetime import date
from functools import wraps

from flask import jsonify, request

from models import db, FinancialPeriod


def _period_of(value):
    """(year, month) for a date, a datetime, or an ISO 'YYYY-MM-DD' string."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return None
    return value.year, value.month


def is_period_open(when):
    """Is the month containing `when` still open for editing?

    The current month and anything in the future are open. Earlier months are
    closed, unless someone has explicitly reopened that month.
    """
    period = _period_of(when)
    if not period:
        return True                      # no date to judge; let normal validation handle it

    year, month = period
    today = date.today()
    if (year, month) >= (today.year, today.month):
        default_open = True
    else:
        default_open = False

    override = FinancialPeriod.query.filter_by(year=year, month=month).first()
    return override.is_open if override else default_open


def period_label(when):
    period = _period_of(when)
    return f"{period[0]}-{period[1]:02d}" if period else "that period"


def _acting_user(user):
    """The user making the request.

    Routes vary: some receive `current_user` from their auth decorator, others
    don't. Falling back to the token means the admin override works on every
    route rather than only the ones that happen to pass the user along.
    """
    if user is not None:
        return user
    try:
        from jwt_auth import get_current_user
        return get_current_user()
    except Exception:
        return None


def check_period_editable(when, user):
    """Return an error response if this date sits in a closed month.

    Admins are allowed through so a genuine correction is always possible; the
    edit still goes through the audit log.
    """
    user = _acting_user(user)
    if user is not None and getattr(user, "role", None) == "admin":
        return None
    if is_period_open(when):
        return None
    return jsonify({
        'error': (f"{period_label(when)} is closed. Records from a finished month "
                  f"cannot be changed - ask an admin if this needs a correction."),
        'period': period_label(when),
        'closed': True,
    }), 403


def guard_period(get_date):
    """Decorator for financial write routes.

    `get_date` receives the same arguments as the route and returns the date the
    record belongs to, so each route can say where its date comes from - the
    request body when creating, the stored row when editing or deleting.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            try:
                when = get_date(*args, **kwargs)
            except Exception:
                when = None
            blocked = check_period_editable(when, user)
            if blocked:
                return blocked
            return f(*args, **kwargs)
        return wrapper
    return decorator


def body_date(field='date'):
    """Date taken from the JSON body - for create and update."""
    def getter(*args, **kwargs):
        data = request.get_json(silent=True) or {}
        return data.get(field)
    return getter


def record_date(model, pk_kwarg, field='date'):
    """Date taken from the stored row - for delete, and for edits that move a
    record between months (both the old and the new month must be open)."""
    def getter(*args, **kwargs):
        row = db.session.get(model, kwargs.get(pk_kwarg))
        return getattr(row, field, None) if row else None
    return getter


def guard_both(model, pk_kwarg, field='date'):
    """An edit must not move a record out of, or into, a closed month."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            existing = record_date(model, pk_kwarg, field)(*args, **kwargs)
            blocked = check_period_editable(existing, user)
            if blocked:
                return blocked
            incoming = body_date(field)(*args, **kwargs)
            if incoming:
                blocked = check_period_editable(incoming, user)
                if blocked:
                    return blocked
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Admin API: see which months are open, and depart from the default when needed
# ---------------------------------------------------------------------------
from datetime import datetime                                    # noqa: E402
from flask import Blueprint                                      # noqa: E402
from jwt_auth import login_required, role_required               # noqa: E402
from log_utils import log_action                                 # noqa: E402

period_bp = Blueprint('financial_periods', __name__)


@period_bp.route('/financial-periods', methods=['GET'])
@login_required
def list_periods(current_user=None):
    """The last 13 months and whether each is still editable."""
    today = date.today()
    overrides = {(p.year, p.month): p for p in FinancialPeriod.query.all()}

    months, y, m = [], today.year, today.month
    for _ in range(13):
        override = overrides.get((y, m))
        default_open = (y, m) >= (today.year, today.month)
        months.append({
            'year': y,
            'month': m,
            'label': f"{y}-{m:02d}",
            'is_open': override.is_open if override else default_open,
            'is_current': (y, m) == (today.year, today.month),
            'overridden': override is not None,
            'changed_by': override.changed_by if override else None,
            'reason': override.reason if override else None,
        })
        m -= 1
        if m == 0:
            m, y = 12, y - 1

    return jsonify({'periods': months, 'can_change': current_user.role == 'admin'}), 200


@period_bp.route('/financial-periods', methods=['POST'])
@role_required(['admin'])
def set_period(current_user=None):
    """Close a month early, or reopen a closed one. Admin only."""
    data = request.get_json(silent=True) or {}
    try:
        year, month = int(data['year']), int(data['month'])
    except (KeyError, TypeError, ValueError):
        return jsonify({'error': 'year and month are required'}), 400
    if not 1 <= month <= 12:
        return jsonify({'error': 'month must be between 1 and 12'}), 400
    if 'is_open' not in data:
        return jsonify({'error': 'is_open is required'}), 400

    is_open = bool(data['is_open'])
    reason = (data.get('reason') or '').strip()
    if is_open and not reason:
        return jsonify({'error': 'Give a reason for reopening a closed month.'}), 400

    period = FinancialPeriod.query.filter_by(year=year, month=month).first()
    if not period:
        period = FinancialPeriod(year=year, month=month)
        db.session.add(period)

    period.is_open = is_open
    period.changed_by = current_user.username if current_user else None
    period.changed_at = datetime.utcnow()
    period.reason = reason or None
    db.session.flush()

    log_action(current_user, 'REOPEN' if is_open else 'CLOSE', 'financial_periods',
               period.id, f"{'Reopened' if is_open else 'Closed'} {year}-{month:02d}"
                          + (f": {reason}" if reason else ""))
    db.session.commit()

    return jsonify({'period': period.to_dict()}), 200
