"""FastAPI router ported from Flask. Preserves URL paths and JSON shapes."""
from __future__ import annotations

import json
import logging
import os
import re as _re
from datetime import datetime, timedelta, date
from functools import wraps
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import desc, or_, and_, func, text, extract
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import *  # noqa: F403,F401
from app.invoice_math import *
from app.log_utils import log_action, document_log_entries, save_uploaded_file
from app.petty_cash import wants_till, till_expenses, till_receipts
from app.period_lock import (
    guard_period, guard_both, body_date, record_date, check_period_editable, is_period_open,
)
from app.document_links import apply_links, resolve_customer, resolve_car
from app.search_suggestions import suggestions_for
from app.inventory_utils import find_inventory_item_by_name as _inv_find_by_name
from app.inventory_transaction_utils import (
    log_inventory_transaction, log_issue_out, log_received, log_adjustment, get_inventory_transactions,
)
from app.repair_order_inventory_utils import (
    deduct_inventory_quantity, process_repair_order_parts,
    handle_repair_order_edit_inventory, restore_inventory_for_deleted_repair_order,
    calculate_inventory_changes, find_inventory_item_by_part_number, find_inventory_item_by_name,
)
from app.payroll import preview as payroll_preview, run_payroll, compute_salary
from app.whatsapp_notifications import whatsapp_notifier

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

from datetime import datetime, date, time, timedelta
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError
from collections import defaultdict
import logging
from app import payroll

# Create blueprint for HR routes

# Set up logging
logger = logging.getLogger(__name__)

# ===== HR MANAGEMENT ROUTES =====

@router.get('/api/attendance')
def get_attendance(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """List attendance records with optional worker_id, start_date, end_date"""
    try:
        worker_id = int(request.query_params.get('worker_id', 0))
        start_date_str = request.query_params.get('start_date', '').strip()
        end_date_str = request.query_params.get('end_date', '').strip()

        query = db.query(AttendanceRecord).order_by(AttendanceRecord.date.desc(), AttendanceRecord.check_in_time.desc())

        if worker_id:
            query = query.filter(AttendanceRecord.worker_id == worker_id)
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(AttendanceRecord.date >= start_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(AttendanceRecord.date <= end_date)
            except ValueError:
                pass

        records = query.all()
        # Include worker name for display
        out = []
        for r in records:
            d = r.to_dict()
            if r.worker:
                d['worker_name'] = f"{r.worker.first_name or ''} {r.worker.last_name or ''}".strip() or r.worker.employee_id
                d['employee_id'] = r.worker.employee_id
            out.append(d)
        return _json({'attendance': out, 'total': len(out)})
    except Exception as e:
        logger.error(f"Error fetching attendance: {e}", exc_info=True)
        return _json({'error': 'Failed to fetch attendance'}, 500)


@router.post('/api/attendance')
def create_attendance(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Create an attendance record (manual entry)."""
    try:
        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)

        worker_id = data.get('worker_id')
        date_str = data.get('date')
        check_in = data.get('check_in_time')
        check_out = data.get('check_out_time')
        notes = data.get('notes', '').strip()

        if not worker_id or not date_str:
            return _json({'error': 'worker_id and date are required'}, 400)

        worker = db.get(Worker, worker_id)
        if not worker:
            return _json({'error': 'Worker not found'}, 404)

        try:
            att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return _json({'error': 'Invalid date format (use YYYY-MM-DD)'}, 400)

        check_in_time = None
        if check_in:
            try:
                if isinstance(check_in, str) and len(check_in) <= 5:
                    h, m = map(int, check_in.split(':'))
                    check_in_time = datetime.combine(att_date, time(h, m))
                else:
                    check_in_time = datetime.strptime(check_in, '%H:%M').time()
                    check_in_time = datetime.combine(att_date, check_in_time)
            except (ValueError, TypeError):
                pass

        check_out_time = None
        if check_out:
            try:
                if isinstance(check_out, str) and len(check_out) <= 5:
                    h, m = map(int, check_out.split(':'))
                    check_out_time = datetime.combine(att_date, time(h, m))
                else:
                    check_out_time = datetime.strptime(check_out, '%H:%M').time()
                    check_out_time = datetime.combine(att_date, check_out_time)
            except (ValueError, TypeError):
                pass

        work_hours = None
        if check_in_time and check_out_time and check_out_time > check_in_time:
            delta = check_out_time - check_in_time
            work_hours = delta.total_seconds() / 3600.0

        record = AttendanceRecord(
            worker_id=worker_id,
            date=att_date,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            work_hours=work_hours,
            notes=notes or None,
            source="manual",
        )
        db.add(record)
        db.commit()
        out = record.to_dict()
        out['worker_name'] = f"{worker.first_name or ''} {worker.last_name or ''}".strip() or worker.employee_id
        out['employee_id'] = worker.employee_id
        return _json({'message': 'Attendance record created', 'attendance': out}, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating attendance: {e}", exc_info=True)
        return _json({'error': 'Failed to create attendance'}, 500)


@router.get('/api/attendance/summary')
def get_attendance_summary(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Get attendance summary for a worker in a month (days_worked, total_hours). Used for salary calculation."""
    try:
        today = date.today()
        worker_id = int(request.query_params['worker_id']) if 'worker_id' in request.query_params else None
        month = int(request.query_params['month']) if 'month' in request.query_params else today.month
        year = int(request.query_params['year']) if 'year' in request.query_params else today.year
        if month < 1 or month > 12:
            return _json({'error': 'Invalid month'}, 400)
        if not worker_id:
            return _json({
                'worker_id': None,
                'month': month,
                'year': year,
                'days_worked': 0,
                'total_hours': 0,
                'records_count': 0,
                'incomplete_records_count': 0,
                'incomplete_dates': [],
                'requires_manual_review': False,
            })

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        records = db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.worker_id == worker_id,
                AttendanceRecord.date >= start_date,
                AttendanceRecord.date <= end_date)
        ).all()

        days_worked = len(set(r.date for r in records))
        total_hours = sum(r.work_hours or 0 for r in records)
        incomplete_records = [
            r for r in records
            if (
                (r.check_in_time is not None and r.check_out_time is None) or
                (r.check_in_time is None and r.check_out_time is not None)
            )
        ]
        incomplete_dates = sorted({r.date.strftime('%Y-%m-%d') for r in incomplete_records})
        requires_manual_review = len(incomplete_records) > 0

        return _json({
            'worker_id': worker_id,
            'month': month,
            'year': year,
            'days_worked': days_worked,
            'total_hours': round(total_hours, 2),
            'records_count': len(records),
            'incomplete_records_count': len(incomplete_records),
            'incomplete_dates': incomplete_dates,
            'requires_manual_review': requires_manual_review
        })
    except Exception as e:
        logger.error(f"Error fetching attendance summary: {e}", exc_info=True)
        return _json({'error': 'Failed to fetch summary'}, 500)


@router.put('/api/attendance/{record_id:int}')
def update_attendance(record_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Update an attendance record."""
    try:
        record = db.get(AttendanceRecord, record_id)
        if not record:
            return _json({'error': 'Attendance record not found'}, 404)
        data = body or {}
        date_str = data.get('date')
        check_in = data.get('check_in_time')
        check_out = data.get('check_out_time')
        notes = data.get('notes')

        if date_str:
            try:
                record.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if check_in is not None:
            try:
                if isinstance(check_in, str) and len(check_in) <= 5:
                    h, m = map(int, check_in.split(':'))
                    record.check_in_time = datetime.combine(record.date, time(h, m))
                else:
                    t = datetime.strptime(check_in, '%H:%M').time()
                    record.check_in_time = datetime.combine(record.date, t)
            except (ValueError, TypeError):
                record.check_in_time = None
        if check_out is not None:
            try:
                if isinstance(check_out, str) and len(check_out) <= 5:
                    h, m = map(int, check_out.split(':'))
                    record.check_out_time = datetime.combine(record.date, time(h, m))
                else:
                    t = datetime.strptime(check_out, '%H:%M').time()
                    record.check_out_time = datetime.combine(record.date, t)
            except (ValueError, TypeError):
                record.check_out_time = None
        if notes is not None:
            record.notes = notes.strip() or None

        if record.check_in_time and record.check_out_time and record.check_out_time > record.check_in_time:
            record.work_hours = (record.check_out_time - record.check_in_time).total_seconds() / 3600.0
        else:
            record.work_hours = None

        db.commit()
        out = record.to_dict()
        if record.worker:
            out['worker_name'] = f"{record.worker.first_name or ''} {record.worker.last_name or ''}".strip() or record.worker.employee_id
            out['employee_id'] = record.worker.employee_id
        return _json({'message': 'Attendance updated', 'attendance': out})
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating attendance: {e}", exc_info=True)
        return _json({'error': 'Failed to update attendance'}, 500)


@router.delete('/api/attendance/{record_id:int}')
def delete_attendance(record_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete an attendance record."""
    try:
        record = db.get(AttendanceRecord, record_id)
        if not record:
            return _json({'error': 'Attendance record not found'}, 404)
        db.delete(record)
        db.commit()
        return _json({'message': 'Attendance record deleted'})
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting attendance: {e}", exc_info=True)
        return _json({'error': 'Failed to delete attendance'}, 500)


@router.get('/api/salary/advances')
def list_salary_advances(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Advances, optionally narrowed to one worker and one month."""
    try:
        worker_id = int(request.query_params['worker_id']) if 'worker_id' in request.query_params else None
        year = int(request.query_params['year']) if 'year' in request.query_params else None
        month = int(request.query_params.get('month', 0))

        query = db.query(SalaryAdvance)
        if worker_id:
            query = query.filter(SalaryAdvance.worker_id == worker_id)
        if year and month:
            start, end = _month_bounds(year, month)
            query = query.filter(SalaryAdvance.date >= start, SalaryAdvance.date <= end)

        rows = query.order_by(SalaryAdvance.date.desc(), SalaryAdvance.id.desc()).all()
        return _json({
            'advances': [r.to_dict() for r in rows],
            'total': round(sum(float(r.amount) for r in rows), 2),
            'count': len(rows),
        }, 200)
    except Exception as e:
        logger.error(f"Error listing salary advances: {e}", exc_info=True)
        return _json({'error': 'Failed to load salary advances'}, 500)


@router.post('/api/salary/advances')
@guard_period(body_date('date'))
def create_salary_advance(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None)):
    """Record a partial salary payment."""
    try:
        data = body or {}

        worker_id = data.get('worker_id')
        if not worker_id:
            return _json({'error': 'Choose a worker'}, 400)

        worker = db.get(Worker, worker_id)
        if not worker:
            return _json({'error': 'Worker not found'}, 404)

        try:
            amount = round(float(data.get('amount')), 2)
        except (TypeError, ValueError):
            return _json({'error': 'Enter a valid amount'}, 400)
        if amount <= 0:
            return _json({'error': 'An advance must be more than zero'}, 400)

        try:
            when = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return _json({'error': 'Enter a valid date (YYYY-MM-DD)'}, 400)

        # A worker cannot draw more than a month's salary in that month -
        # payroll would otherwise owe them nothing and still be short.
        base = float(worker.salary) if worker.salary else 0.0
        if base <= 0:
            return _json({'error': f'{worker.first_name} has no monthly salary set, '
                                     'so there is nothing to advance against'}, 400)

        already = sum(float(a.amount) for a in advances_for_month(worker.id, when.year, when.month))
        if already + amount > base + 0.01:
            remaining = round(base - already, 2)
            return _json({
                'error': f'That would take {worker.first_name} to '
                         f'{already + amount:,.2f} against a monthly salary of {base:,.2f}. '
                         f'At most {remaining:,.2f} can still be advanced this month.'
            }, 400)

        advance = SalaryAdvance(
            worker_id=worker.id,
            date=when,
            amount=amount,
            payment_method=(data.get('payment_method') or 'Cash').strip(),
            notes=(data.get('notes') or '').strip() or None,
            created_by=getattr(current_user, 'username', None),
        )
        db.add(advance)
        db.commit()

        log_action(db, current_user, 'CREATE', 'salary_advances', advance.id,
                   f'Advance of {amount:.2f} PKR to {worker.employee_id} dated {when}')
        return _json({'message': 'Advance recorded', 'advance': advance.to_dict()}, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording salary advance: {e}", exc_info=True)
        return _json({'error': 'Failed to record the advance'}, 500)


@router.delete('/api/salary/advances/{advance_id:int}')
@guard_period(record_date(SalaryAdvance, 'advance_id'))
def delete_salary_advance(advance_id, request: Request, db: Session = Depends(get_db)):
    """Remove an advance - use this to correct a wrong amount, then re-add it."""
    try:
        advance = db.get(SalaryAdvance, advance_id)
        if not advance:
            return _json({'error': 'Advance not found'}, 404)

        summary = f'Advance {float(advance.amount)} on {advance.date}'
        db.delete(advance)
        db.commit()

        log_action(db, current_user, 'DELETE', 'salary_advances', advance_id, summary)
        return _json({'message': 'Advance removed'}, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting salary advance: {e}", exc_info=True)
        return _json({'error': 'Failed to remove the advance'}, 500)


# ===== PAYROLL =====
# Running payroll is what turns a month of attendance into a cost in the
# books. It books the *earned* salary, not the net handed over: an advance
# already left the till without being expensed, so booking only the net would
# understate the month by exactly what was drawn early. See payroll.py.

@router.get('/api/salary/calculate')
def calculate_salary(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """One worker's salary for one month, for the slip.

    Delegates to payroll.compute_salary so the figure on the slip and the
    figure payroll books are the same number, not two implementations that
    agree today.
    """
    try:
        worker_id = int(request.query_params['worker_id']) if 'worker_id' in request.query_params else None
        month = int(request.query_params['month']) if 'month' in request.query_params else None
        year = int(request.query_params.get('year', 0))
        if not worker_id or not month or not year:
            return _json({'error': 'worker_id, month, and year are required'}, 400)

        worker = db.get(Worker, worker_id)
        if not worker:
            return _json({'error': 'Worker not found'}, 404)

        figures = payroll.compute_salary(db, worker, year, month)
        run = payroll.already_run(db, worker_id, year, month)

        return _json({
            **figures,
            'first_name': worker.first_name,
            'last_name': worker.last_name,
            'month': month,
            'year': year,
            # The slip calls advances deductions, because that is what they are
            # from the worker's side.
            'deductions': figures['advances_total'],
            'bonuses': 0,
            'already_paid': bool(run),
            'paid_on': run.run_at.strftime('%Y-%m-%d') if run and run.run_at else None,
            'review_notes': (
                'Incomplete attendance exists. Please review missing '
                'check-in/check-out entries before final payroll.'
            ) if figures['requires_manual_review'] else None,
            'advance_notes': (
                f"{worker.first_name} drew {figures['advances_total']:,.2f} in advances "
                f"but only earned {figures['earned_salary']:,.2f} this month. "
                f"Recover {abs(figures['net_salary']):,.2f} rather than paying it."
            ) if figures['overdrawn'] else None,
        })
    except Exception as e:
        logger.error(f"Error calculating salary: {e}", exc_info=True)
        return _json({'error': 'Failed to calculate salary'}, 500)

# ===== SALARY ADVANCES =====
# Partial salary drawn during the month. Recorded against the worker only -
# the expense is the full month's salary at payroll, and calculate_salary()
# nets these off so the same rupee is never paid or booked twice.

# Shared with the payroll run so the slip and the books cannot disagree.
_month_bounds = payroll.month_bounds
advances_for_month = payroll.advances_for_month


@router.get('/api/salary/payroll')
def payroll_history(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """What has already been paid, newest first."""
    try:
        query = db.query(PayrollRun)
        year = int(request.query_params['year']) if 'year' in request.query_params else None
        month = int(request.query_params['month']) if 'month' in request.query_params else None
        if year:
            query = query.filter(PayrollRun.year == year)
        if month:
            query = query.filter(PayrollRun.month == month)

        rows = query.order_by(PayrollRun.year.desc(), PayrollRun.month.desc(),
                              PayrollRun.id.desc()).all()
        return _json({
            'runs': [r.to_dict() for r in rows],
            'total_expensed': round(sum(float(r.earned_salary) for r in rows), 2),
        }, 200)
    except Exception as e:
        logger.error(f"Error loading payroll history: {e}", exc_info=True)
        return _json({'error': 'Failed to load payroll history'}, 500)


# ===== ZKTECO PUSH PROTOCOL (device sends data to server; no auth) =====

def _iclock_ok():
    """Return 200 OK with plain text body for ZKTeco device."""
    return Response(content="OK", status_code=200, media_type="text/plain; charset=utf-8")


def _update_device_last_seen(db: Session, sn):
    """Update last_seen_at for device with given serial_number. Swallow errors."""
    if not sn or not str(sn).strip():
        return
    try:
        device = db.query(ZKTecoDevice).filter_by(serial_number=sn.strip(), is_active=True).first()
        if device:
            device.last_seen_at = datetime.utcnow()
            db.commit()
    except Exception as e:
        logger.warning("Could not update ZKTecoDevice last_seen_at for SN=%s: %s", sn, e)
        try:
            db.rollback()
        except Exception:
            pass


@router.get('/api/salary/payroll/preview')
def payroll_preview(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """What running payroll for a month would do - writes nothing."""
    try:
        year = int(request.query_params['year']) if 'year' in request.query_params else None
        month = int(request.query_params['month']) if 'month' in request.query_params else None
        if not year or not month or not 1 <= month <= 12:
            return _json({'error': 'Provide a valid year and month'}, 400)
        return _json(payroll.preview(db, year, month), 200)
    except Exception as e:
        logger.error(f"Error building payroll preview: {e}", exc_info=True)
        return _json({'error': 'Failed to build the payroll preview'}, 500)


@router.post('/api/salary/payroll/run')
@guard_period(body_date('pay_date'))
def payroll_run(
    request: Request,
    db: Session = Depends(get_db),
    body: dict | None = Body(None),
    current_user=Depends(require_roles(["admin"])),
):
    """Book the month's salaries. Safe to re-run: nobody is paid twice."""
    try:
        data = body or {}
        year, month = data.get('year'), data.get('month')
        try:
            year, month = int(year), int(month)
        except (TypeError, ValueError):
            return _json({'error': 'Provide a valid year and month'}, 400)
        if not 1 <= month <= 12:
            return _json({'error': 'Provide a valid month'}, 400)

        try:
            pay_date = datetime.strptime(data.get('pay_date'), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return _json({'error': 'Enter a valid pay date (YYYY-MM-DD)'}, 400)

        summary = payroll.run_payroll(db, year, month, pay_date,
                                      getattr(current_user, 'username', None))

        if not summary['posted']:
            return _json({
                'error': 'Nothing to pay for this month.',
                'skipped': summary['skipped'],
            }, 400)

        log_action(db, current_user, 'CREATE', 'payroll', None,
                   f"Payroll {month:02d}/{year}: {len(summary['posted'])} workers, "
                   f"{summary['total_expensed']:,.2f} booked")
        return _json({
            'message': f"Payroll booked for {len(summary['posted'])} worker(s)",
            **summary,
        }, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error running payroll: {e}", exc_info=True)
        return _json({'error': 'Failed to run payroll'}, 500)


@router.get('/api/workers')
def get_workers(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Get all workers with optional search and filter"""
    try:
        search_query = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip()
        department_filter = request.query_params.get('department', '').strip()
        
        logger.info(f"Fetching workers with filters - search: '{search_query}', status: '{status_filter}', department: '{department_filter}'")
        
        query = db.query(Worker)

        # Apply search filter
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                or_(
                    Worker.first_name.ilike(search_term),
                    Worker.last_name.ilike(search_term),
                    Worker.employee_id.ilike(search_term),
                    Worker.phone.ilike(search_term),
                    Worker.position.ilike(search_term)
                )
            )

        # Apply status filter
        if status_filter:
            query = query.filter(Worker.status == status_filter)

        # Apply department filter
        if department_filter:
            query = query.filter(Worker.department.ilike(f"%{department_filter}%"))

        # Order by hire date (newest first)
        workers = query.order_by(Worker.hire_date.desc()).all()
        
        logger.info(f"Successfully fetched {len(workers)} workers")

        return _json({
            'workers': [worker.to_dict() for worker in workers],
            'total': len(workers)
        })

    except Exception as e:
        logger.error(f"Error fetching workers: {e}", exc_info=True)
        return _json({'error': 'Failed to fetch workers'}, 500)

@router.post('/api/workers')
def create_worker(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Create a new worker"""
    try:
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)

        # Validate required fields
        required_fields = ['employee_id', 'first_name', 'last_name', 'phone', 'address', 'cnic', 'date_of_birth', 'hire_date', 'position', 'department']
        for field in required_fields:
            if not data.get(field):
                return _json({'error': f'{field.replace("_", " ").title()} is required'}, 400)

        # Check if employee ID already exists
        existing_worker = db.query(Worker).filter_by(employee_id=data['employee_id']).first()
        if existing_worker:
            return _json({'error': 'Employee ID already exists'}, 400)

        # Check if CNIC already exists
        existing_cnic = db.query(Worker).filter_by(cnic=data['cnic']).first()
        if existing_cnic:
            return _json({'error': 'CNIC already exists'}, 400)

        # Create new worker
        worker = Worker(
            employee_id=data['employee_id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email'),
            phone=data['phone'],
            address=data['address'],
            cnic=data['cnic'],
            date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date(),
            hire_date=datetime.strptime(data['hire_date'], '%Y-%m-%d').date(),
            position=data['position'],
            department=data['department'],
            salary=float(data['salary']) if data.get('salary') else None,
            status=data.get('status', 'active'),
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_phone=data.get('emergency_contact_phone'),
            notes=data.get('notes')
        )
        if 'skills' in data:
            from app.assignments import set_worker_skills

            skills = data.get('skills')
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(',') if s.strip()]
            set_worker_skills(db, worker, skills if isinstance(skills, list) else [])

        db.add(worker)
        db.commit()

        return _json({
            'message': 'Worker created successfully',
            'worker': worker.to_dict()
        }, 201)

    except ValueError as e:
        db.rollback()
        logger.error(f"Invalid date format: {e}")
        return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating worker: {e}")
        return _json({'error': 'Failed to create worker'}, 500)

@router.get('/api/workers/debug')
def debug_workers(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin']))):
    """Debug endpoint to help diagnose worker endpoint issues"""
    try:
        debug_info = {}
        
        # Test database connection
        try:
            from sqlalchemy import text
            db.execute(text('SELECT 1'))
            debug_info['database_connection'] = 'OK'
        except Exception as e:
            debug_info['database_connection'] = f'ERROR: {str(e)}'
        
        # Test Worker model
        try:
            worker_count = db.query(Worker).count()
            debug_info['worker_count'] = worker_count
            debug_info['worker_model'] = 'OK'
        except Exception as e:
            debug_info['worker_model'] = f'ERROR: {str(e)}'
        
        # Test JWT token
        try:
            current_user_id = current_user.id if current_user else None
            debug_info['jwt_user_id'] = current_user_id
            debug_info['jwt_token'] = 'OK'
        except Exception as e:
            debug_info['jwt_token'] = f'ERROR: {str(e)}'
        
        # Test user lookup
        try:
            current_user_id = current_user.id if current_user else None
            user = db.get(User, int(current_user_id))
            if user:
                debug_info['user_lookup'] = f'OK - User: {user.username}, Role: {user.role}'
            else:
                debug_info['user_lookup'] = 'ERROR: User not found'
        except Exception as e:
            debug_info['user_lookup'] = f'ERROR: {str(e)}'
        
        return _json(debug_info)
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return _json({'error': f'Debug failed: {str(e)}'}, 500)

@router.get('/api/workers/departments')
def get_departments(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Get list of all departments"""
    try:
        departments = db.query(Worker.department).distinct().all()
        department_list = [dept[0] for dept in departments if dept[0]]
        return _json({'departments': sorted(department_list)})

    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return _json({'error': 'Failed to fetch departments'}, 500)

@router.get('/api/workers/positions')
def get_positions(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Get list of all positions"""
    try:
        positions = db.query(Worker.position).distinct().all()
        position_list = [pos[0] for pos in positions if pos[0]]
        return _json({'positions': sorted(position_list)})

    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return _json({'error': 'Failed to fetch positions'}, 500)

@router.get('/api/workers/test-auth')
def test_auth(request: Request, db: Session = Depends(get_db)):
    """Simple test endpoint to check JWT authentication"""
    try:
        current_user_id = current_user.id if current_user else None
        user = db.get(User, int(current_user_id))
        
        if not user:
            return _json({'error': 'User not found'}, 401)
            
        return _json({
            'message': 'Authentication successful',
            'user_id': current_user_id,
            'username': user.username,
            'role': user.role
        })
        
    except Exception as e:
        logger.error(f"Error in test auth endpoint: {e}", exc_info=True)
        return _json({'error': f'Auth test failed: {str(e)}'}, 500)


# ===== ATTENDANCE ROUTES =====

@router.get('/api/workers/{worker_id:int}')
def get_worker(worker_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Get specific worker by ID"""
    try:
        worker = db.get(Worker, worker_id)
        if not worker:
            return _json({'error': 'Worker not found'}, 404)

        return _json(worker.to_dict())

    except Exception as e:
        logger.error(f"Error fetching worker {worker_id}: {e}")
        return _json({'error': 'Failed to fetch worker'}, 500)

@router.put('/api/workers/{worker_id:int}')
def update_worker(worker_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Update an existing worker"""
    try:
        worker = db.get(Worker, worker_id)
        if not worker:
            return _json({'error': 'Worker not found'}, 404)

        data = body
        if not data:
            return _json({'error': 'No data provided'}, 400)

        # Update fields
        if 'employee_id' in data:
            # Check if new employee ID already exists (excluding current worker)
            existing = db.query(Worker).filter(Worker.employee_id == data['employee_id'], Worker.id != worker_id).first()
            if existing:
                return _json({'error': 'Employee ID already exists'}, 400)
            worker.employee_id = data['employee_id']

        if 'first_name' in data:
            worker.first_name = data['first_name']
        if 'last_name' in data:
            worker.last_name = data['last_name']
        if 'email' in data:
            worker.email = data['email']
        if 'phone' in data:
            worker.phone = data['phone']
        if 'address' in data:
            worker.address = data['address']
        if 'cnic' in data:
            # Check if new CNIC already exists (excluding current worker)
            existing = db.query(Worker).filter(Worker.cnic == data['cnic'], Worker.id != worker_id).first()
            if existing:
                return _json({'error': 'CNIC already exists'}, 400)
            worker.cnic = data['cnic']
        if 'date_of_birth' in data:
            worker.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        if 'hire_date' in data:
            worker.hire_date = datetime.strptime(data['hire_date'], '%Y-%m-%d').date()
        if 'position' in data:
            worker.position = data['position']
        if 'department' in data:
            worker.department = data['department']
        if 'salary' in data:
            worker.salary = float(data['salary']) if data['salary'] else None
        if 'status' in data:
            worker.status = data['status']
        if 'emergency_contact_name' in data:
            worker.emergency_contact_name = data['emergency_contact_name']
        if 'emergency_contact_phone' in data:
            worker.emergency_contact_phone = data['emergency_contact_phone']
        if 'notes' in data:
            worker.notes = data['notes']
        if 'skills' in data:
            from app.assignments import set_worker_skills

            skills = data.get('skills')
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(',') if s.strip()]
            set_worker_skills(db, worker, skills if isinstance(skills, list) else [])

        worker.updated_at = datetime.utcnow()
        db.commit()

        return _json({
            'message': 'Worker updated successfully',
            'worker': worker.to_dict()
        })

    except ValueError as e:
        db.rollback()
        logger.error(f"Invalid date format: {e}")
        return _json({'error': 'Invalid date format. Use YYYY-MM-DD'}, 400)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating worker {worker_id}: {e}")
        return _json({'error': 'Failed to update worker'}, 500)

@router.delete('/api/workers/{worker_id:int}')
def delete_worker(worker_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a worker"""
    try:
        worker = db.get(Worker, worker_id)
        if not worker:
            return _json({'error': 'Worker not found'}, 404)

        db.delete(worker)
        db.commit()

        return _json({'message': 'Worker deleted successfully'})

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting worker {worker_id}: {e}")
        return _json({'error': 'Failed to delete worker'}, 500)

@router.get('/api/zkteco/devices')
def list_zkteco_devices(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """List registered ZKTeco devices (PUSH: identified by serial number)."""
    try:
        devices = db.query(ZKTecoDevice).filter_by(is_active=True).all()
        return _json({'devices': [d.to_dict() for d in devices]})
    except Exception as e:
        logger.error(f"Error listing ZKTeco devices: {e}", exc_info=True)
        return _json({'error': 'Failed to list devices'}, 500)


@router.post('/api/zkteco/devices')
def create_zkteco_device(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Register a ZKTeco device (PUSH). Requires serial_number; set Cloud Server on device to this server."""
    try:
        data = body
        if not data:
            return _json({'error': 'Request body required'}, 400)
        serial_number = (data.get('serial_number') or '').strip()
        if not serial_number:
            return _json({'error': 'serial_number is required'}, 400)
        name = (data.get('name') or '').strip() or serial_number
        ip_address = (data.get('ip_address') or '').strip() or None
        port = data.get('port')
        if port is not None:
            try:
                port = int(port)
            except (TypeError, ValueError):
                port = None
        timeout = 30
        if data.get('timeout') is not None:
            try:
                timeout = max(5, min(120, int(data.get('timeout'))))
            except (TypeError, ValueError):
                pass
        existing = db.query(ZKTecoDevice).filter_by(serial_number=serial_number).first()
        if existing:
            if existing.is_active:
                return _json({'error': 'A device with this serial number is already registered'}, 400)
            existing.name = name
            existing.ip_address = ip_address
            existing.port = port
            existing.timeout = timeout
            existing.is_active = True
            db.commit()
            return _json({'message': 'Device re-added', 'device': existing.to_dict()}, 201)
        device = ZKTecoDevice(
            name=name,
            serial_number=serial_number,
            ip_address=ip_address,
            port=port,
            timeout=timeout,
            is_active=True,
        )
        db.add(device)
        db.commit()
        return _json({'message': 'Device added', 'device': device.to_dict()}, 201)
    except IntegrityError as e:
        db.rollback()
        logger.warning("ZKTeco device create IntegrityError (duplicate SN?): %s", e)
        return _json({'error': 'A device with this serial number already exists'}, 400)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating ZKTeco device: {e}", exc_info=True)
        return _json({'error': 'Failed to add device'}, 500)


@router.delete('/api/zkteco/devices/{device_id:int}')
def delete_zkteco_device(device_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Remove a ZKTeco device (soft-delete: set is_active=False)."""
    try:
        device = db.get(ZKTecoDevice, device_id)
        if not device:
            return _json({'error': 'Device not found'}, 404)
        device.is_active = False
        db.commit()
        return _json({'message': 'Device removed'})
    except Exception as e:
        db.rollback()
        logger.error(f"Error removing ZKTeco device: {e}", exc_info=True)
        return _json({'error': 'Failed to remove device'}, 500)
@router.get('/iclock/cdata')
@router.post('/iclock/cdata')
async def iclock_cdata(request: Request, db: Session = Depends(get_db)):
    """ZKTeco device push (options, ATTLOG, OPERLOG, etc.). No auth. Persist ATTLOG to AttendanceRecord."""
    try:
        sn = request.query_params.get("SN", "").strip()
        table = request.query_params.get("table", "").strip()
        if sn:
            _update_device_last_seen(db, sn)
        if request.method == "GET":
            return _iclock_ok()
        raw = await request.body()
        body = raw.decode("utf-8", errors="replace") if raw else ""
        if not body.strip():
            return _iclock_ok()
        if table == "ATTLOG":
            _process_attlog(db, body, sn)
        else:
            logger.debug("iclock/cdata table=%s SN=%s (not ATTLOG, no DB write)", table, sn)
        return _iclock_ok()
    except Exception as e:
        logger.error("iclock/cdata error: %s", e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return _iclock_ok()


def _process_attlog(db: Session, body, sn):
    """Parse ATTLOG body (tab-separated: user_id, timestamp, punch) and merge into AttendanceRecord."""
    workers_by_emp = {w.employee_id: w for w in db.query(Worker).all() if w.employee_id}
    zkteco_device_id = None
    if sn:
        dev = db.query(ZKTecoDevice).filter_by(serial_number=sn.strip(), is_active=True).first()
        if dev:
            zkteco_device_id = dev.id
    TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
    for line in body.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            logger.warning("ATTLOG invalid line (expected at least 3 fields): %s", line[:100])
            continue
        user_id = (parts[0] or "").strip()
        ts_str = (parts[1] or "").strip()
        punch = (parts[2] or "").strip()
        if punch not in ("0", "1", "255"):
            logger.warning("ATTLOG invalid punch (expected 0, 1, or 255): user_id=%s punch=%s", user_id, punch)
            continue
        try:
            ts = datetime.strptime(ts_str, TIMESTAMP_FMT)
        except ValueError:
            logger.warning("ATTLOG invalid timestamp: user_id=%s ts=%s", user_id, ts_str)
            continue
        worker = workers_by_emp.get(user_id)
        if not worker:
            logger.warning("ATTLOG unknown user_id=%s SN=%s (no Worker with this employee_id)", user_id, sn)
            continue
        att_date = ts.date()
        record = db.query(AttendanceRecord).filter_by(worker_id=worker.id, date=att_date).first()
        if not record:
            record = AttendanceRecord(
                worker_id=worker.id,
                date=att_date,
                check_in_time=None,
                check_out_time=None,
                work_hours=None,
                notes="ZKTeco push",
                source="ZKTeco push",
                zkteco_device_id=zkteco_device_id,
            )
            db.add(record)
        if punch == "0":
            if record.check_in_time is None or ts < record.check_in_time:
                record.check_in_time = ts
        elif punch == "1":
            if record.check_out_time is None or ts > record.check_out_time:
                record.check_out_time = ts
        else:
            # Some ZKTeco setups send 255 for generic punch (no explicit in/out).
            # Fallback: earliest punch becomes check-in, later punch becomes check-out.
            if record.check_in_time is None:
                record.check_in_time = ts
            elif ts < record.check_in_time:
                record.check_in_time = ts
            elif record.check_out_time is None or ts > record.check_out_time:
                record.check_out_time = ts
        if record.check_in_time and record.check_out_time and record.check_out_time > record.check_in_time:
            delta = record.check_out_time - record.check_in_time
            record.work_hours = round(delta.total_seconds() / 3600.0, 2)
        else:
            record.work_hours = None
        record.notes = record.notes or "ZKTeco push"
        record.source = record.source or "ZKTeco push"
        record.zkteco_device_id = zkteco_device_id
    db.commit()


# ===== ZKTECO DEVICE API (PUSH: register by serial number) =====

@router.get('/iclock/getrequest')
def iclock_getrequest(request: Request, db: Session = Depends(get_db)):
    """ZKTeco device heartbeat. No auth. Update last_seen_at and return OK."""
    try:
        sn = request.query_params.get("SN", "").strip()
        if sn:
            _update_device_last_seen(db, sn)
        return _iclock_ok()
    except Exception as e:
        logger.error("iclock/getrequest error: %s", e, exc_info=True)
        return _iclock_ok()


