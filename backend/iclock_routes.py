# iClock ADMS routes (ZKTeco device-as-client). Kept separate from HR.

from flask import Blueprint, request, Response
from models import db, Worker, AttendanceRecord, ZKTecoDevice
from datetime import datetime, date
from collections import defaultdict
import logging

iclock_bp = Blueprint('iclock', __name__)
logger = logging.getLogger(__name__)


def _parse_attlog_body(body_text):
    """
    Parse ATTLOG POST body. Common format: one line per punch, tab-separated
    (Pin, DateTime, Verified, ...). Returns list of dicts: user_id, date, timestamp.
    """
    logs = []
    for line in (body_text or '').strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 2:
            parts = line.split(',', 1) if ',' in line else line.split(None, 1)
        if len(parts) < 2:
            continue
        user_id = (parts[0] or '').strip()
        dt_str = (parts[1] or '').strip()
        if not user_id or not dt_str:
            continue
        ts = None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d-%m-%Y %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
            try:
                ts = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue
        if ts is None:
            try:
                ts = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                continue
        log_date = ts.date() if hasattr(ts, 'date') else date(ts.year, ts.month, ts.day)
        logs.append({'user_id': user_id, 'date': log_date, 'timestamp': ts})
    return logs


@iclock_bp.route('/iclock/cdata', methods=['GET', 'POST'])
def cdata():
    """
    ADMS cdata: device handshake (GET) or pushes data (POST).
    POST with table=ATTLOG: parse body, match Pin to Worker.employee_id, upsert AttendanceRecord.
    """
    sn = request.args.get('SN', '').strip()
    table = request.args.get('table', '').strip()

    if request.method == 'GET':
        return Response('OK', mimetype='text/plain')

    if table == 'ATTLOG':
        body = request.get_data(as_text=True)
        logs = _parse_attlog_body(body)
        if not logs:
            return Response('OK', mimetype='text/plain')

        workers_by_emp = {w.employee_id: w for w in Worker.query.all() if w.employee_id}
        by_user_date = defaultdict(list)
        for log in logs:
            uid = (log.get('user_id') or '').strip()
            if not uid:
                continue
            d = log.get('date')
            ts = log.get('timestamp')
            if not d or not ts:
                continue
            by_user_date[(uid, d)].append(ts)

        created = 0
        updated = 0
        for (user_id, att_date), timestamps in by_user_date.items():
            worker = workers_by_emp.get(user_id)
            if not worker:
                continue
            timestamps.sort()
            check_in_time = timestamps[0]
            check_out_time = timestamps[-1] if len(timestamps) > 1 else None
            work_hours = None
            if check_out_time and check_in_time and check_out_time > check_in_time:
                delta = check_out_time - check_in_time
                work_hours = round(delta.total_seconds() / 3600.0, 2)

            existing = AttendanceRecord.query.filter_by(worker_id=worker.id, date=att_date).first()
            if existing:
                existing.check_in_time = check_in_time
                existing.check_out_time = check_out_time
                existing.work_hours = work_hours
                existing.notes = existing.notes or 'ZKTeco ADMS'
                updated += 1
            else:
                db.session.add(AttendanceRecord(
                    worker_id=worker.id,
                    date=att_date,
                    check_in_time=check_in_time,
                    check_out_time=check_out_time,
                    work_hours=work_hours,
                    notes='ZKTeco ADMS'
                ))
                created += 1

        device = ZKTecoDevice.query.filter_by(serial_number=sn).first() if sn else None
        if device:
            device.last_sync = datetime.utcnow()
            device.last_sync_status = 'ok'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("iclock cdata ATTLOG commit failed")
            return Response('OK', mimetype='text/plain')

    return Response('OK', mimetype='text/plain')


@iclock_bp.route('/iclock/getrequest', methods=['GET'])
def getrequest():
    """ADMS getrequest: device polls for commands. Return 200 with body so device does not 404."""
    return Response('OK\n', mimetype='text/plain')
