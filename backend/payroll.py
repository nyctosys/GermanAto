"""Working out what a worker earned, and turning that into an expense.

Two callers need the same arithmetic and must never disagree: the salary slip
someone hands a worker, and the payroll run that books the cost. So it lives
here rather than inside a route.

What gets booked, and why gross rather than net
----------------------------------------------
An advance is money that already left the till, and it is deliberately not an
expense when it is taken - see SalaryAdvance. If payroll then booked only the
net still owed, the advance would never be booked at all and the month's
labour cost would be understated by exactly the amount drawn early.

    earned 30,000, drew 10,000 on the 5th, 20,000 handed over at month end
    expense booked = 30,000   (cash out over the month = 30,000)

So payroll books the full earned amount. The net is what the worker is handed
on the day; the expense is what the month actually cost.
"""
from datetime import date, timedelta

from models import db, AttendanceRecord, Expense, PayrollRun, SalaryAdvance, Worker

# Kept off the Daily Expenses till, which is petty cash - see petty_cash.py.
PAYROLL_CATEGORY = 'Labor'

# The workshop pays a flat monthly salary pro-rated over a 30-day month,
# regardless of how many days that month actually has.
DAYS_IN_PAY_MONTH = 30.0


def month_bounds(year, month):
    start = date(year, month, 1)
    end = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(days=1)
    return start, end


def advances_for_month(worker_id, year, month):
    start, end = month_bounds(year, month)
    return SalaryAdvance.query.filter(
        SalaryAdvance.worker_id == worker_id,
        SalaryAdvance.date >= start,
        SalaryAdvance.date <= end,
    ).order_by(SalaryAdvance.date).all()


def compute_salary(worker, year, month):
    """What one worker earned in one month, and what is still owed to them."""
    start, end = month_bounds(year, month)
    base_salary = float(worker.salary) if worker.salary else 0.0

    records = AttendanceRecord.query.filter(
        AttendanceRecord.worker_id == worker.id,
        AttendanceRecord.date >= start,
        AttendanceRecord.date <= end,
    ).all()

    days_worked = len({r.date for r in records})
    total_hours = sum(r.work_hours or 0 for r in records)

    # A day with only a check-in or only a check-out cannot be trusted to have
    # been a full day, so payroll should not run until someone has looked.
    incomplete = [
        r for r in records
        if (r.check_in_time is None) != (r.check_out_time is None)
    ]

    daily_rate = base_salary / DAYS_IN_PAY_MONTH if base_salary else 0.0
    earned = round(daily_rate * days_worked, 2)

    advances = advances_for_month(worker.id, year, month)
    advances_total = round(sum(float(a.amount) for a in advances), 2)
    net = round(earned - advances_total, 2)

    return {
        'worker_id': worker.id,
        'employee_id': worker.employee_id,
        'name': f"{worker.first_name} {worker.last_name}".strip(),
        'position': worker.position,
        'department': worker.department,
        'base_salary': base_salary,
        'daily_rate': round(daily_rate, 2),
        'days_worked': days_worked,
        'total_hours': round(total_hours, 2),
        'earned_salary': earned,
        'advances': [a.to_dict() for a in advances],
        'advances_total': advances_total,
        'net_salary': net,
        'overdrawn': net < 0,
        'incomplete_records_count': len(incomplete),
        'incomplete_dates': sorted({r.date.strftime('%Y-%m-%d') for r in incomplete}),
        'requires_manual_review': bool(incomplete),
    }


def already_run(worker_id, year, month):
    return PayrollRun.query.filter_by(worker_id=worker_id, year=year, month=month).first()


def preview(year, month):
    """Every active worker's figures for a month, and whether payroll can run.

    Reports rather than decides: a worker who earned nothing, or whose
    attendance is incomplete, or who has already been paid, is listed with the
    reason so whoever runs payroll can see the whole month at once.
    """
    workers = Worker.query.filter(Worker.status == 'active').order_by(Worker.employee_id).all()
    rows, payable = [], []

    for worker in workers:
        row = compute_salary(worker, year, month)
        run = already_run(worker.id, year, month)

        if run:
            row['blocked'] = 'Already paid for this month'
        elif row['earned_salary'] <= 0:
            row['blocked'] = 'No attendance recorded'
        elif row['requires_manual_review']:
            row['blocked'] = (f"{row['incomplete_records_count']} day(s) missing a "
                              "check-in or check-out")
        else:
            row['blocked'] = None
            payable.append(row)

        row['already_paid'] = bool(run)
        rows.append(row)

    return {
        'year': year,
        'month': month,
        'workers': rows,
        'payable_count': len(payable),
        'blocked_count': len(rows) - len(payable),
        'total_earned': round(sum(r['earned_salary'] for r in payable), 2),
        'total_advances': round(sum(r['advances_total'] for r in payable), 2),
        'total_to_hand_over': round(sum(r['net_salary'] for r in payable), 2),
    }


def run_payroll(year, month, pay_date, username=None):
    """Book each payable worker's earned salary as an expense.

    Idempotent through PayrollRun's unique (worker, year, month): a second run
    for the same month skips anyone already paid rather than paying twice.
    """
    summary = preview(year, month)
    posted, skipped = [], []

    for row in summary['workers']:
        if row['blocked']:
            skipped.append({'name': row['name'], 'reason': row['blocked']})
            continue

        expense = Expense(
            date=pay_date,
            category=PAYROLL_CATEGORY,
            description=f"Salary {month:02d}/{year} - {row['name']} ({row['employee_id']})",
            amount=row['earned_salary'],
            notes=(
                f"{row['days_worked']} days worked. "
                f"Advances already drawn: {row['advances_total']:,.2f}. "
                f"Handed over at month end: {row['net_salary']:,.2f}."
            ),
        )
        db.session.add(expense)
        db.session.flush()

        db.session.add(PayrollRun(
            worker_id=row['worker_id'],
            year=year,
            month=month,
            earned_salary=row['earned_salary'],
            advances_total=row['advances_total'],
            net_paid=row['net_salary'],
            expense_id=expense.id,
            run_by=username,
        ))

        posted.append({
            'name': row['name'],
            'earned': row['earned_salary'],
            'advances': row['advances_total'],
            'handed_over': row['net_salary'],
            'expense_id': expense.id,
        })

    db.session.commit()
    return {
        'posted': posted,
        'skipped': skipped,
        'total_expensed': round(sum(p['earned'] for p in posted), 2),
        'total_handed_over': round(sum(p['handed_over'] for p in posted), 2),
    }
