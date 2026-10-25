"""Reconcile invoice payment amounts with invoice status.

Historically the app marked invoices `paid` without ever recording the money:
`advance` and `paid_amount` stayed at 0 and `balance` kept its full value. That
left `status` as the only trustworthy signal, and made any amount-based figure
(receivables above all) wildly overstated - 56.2M instead of 13.1M on the
production data this was written against.

This backfills the amounts so they agree with the status, after which
receivables, the balance shown on an invoice, and the "Update Balance" flow all
work from the same numbers.

  * invoices marked `paid`      -> paid_amount raised so advance + paid = due,
                                   balance set to 0
  * every invoice               -> status recomputed from the amounts, so any
                                   row whose status disagreed is corrected

Safe to run more than once: rows already consistent are skipped.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \
        python3 backfill_invoice_payments.py [--apply]

Without --apply it reports what it would change and writes nothing.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first.")

APPLY = "--apply" in sys.argv

from app import app, db                                    # noqa: E402
from models import Invoice                                 # noqa: E402
from invoice_math import (                                 # noqa: E402
    invoice_amount_due,
    invoice_amount_paid,
    calculate_invoice_status,
)

CENT = 0.005  # tolerance for float comparisons


def main():
    with app.app_context():
        invoices = Invoice.query.filter_by(type_of="invoice").all()

        amounts_filled = 0
        status_corrected = 0
        overpayments_fixed = 0
        already_ok = 0
        money_backfilled = 0.0
        money_removed = 0.0

        for inv in invoices:
            due = invoice_amount_due(inv)
            paid = invoice_amount_paid(inv)
            changed = False

            # Marked paid but the money was never recorded: credit the shortfall
            # to paid_amount so the amounts tell the same story as the status.
            if inv.status == "paid" and paid < due - CENT:
                shortfall = round(due - paid, 2)
                inv.paid_amount = round((inv.paid_amount or 0.0) + shortfall, 2)
                inv.balance = 0.0
                money_backfilled += shortfall
                amounts_filled += 1
                changed = True

                # Record what this is. The amount is reconstructed from the
                # `paid` status, not a payment anyone actually keyed in, and the
                # audit trail should never pretend otherwise.
                try:
                    history = json.loads(inv.payments_history) if inv.payments_history else []
                except (ValueError, TypeError):
                    history = []
                history.append({
                    "amount": shortfall,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "person": "system/legacy-backfill",
                    "proof_path": None,
                    "source": "legacy_backfill",
                    "note": ("Reconstructed from status='paid'. The original payment "
                             "was never recorded in the system."),
                })
                inv.payments_history = json.dumps(history)

            # Recorded more than the invoice was ever for. Treated as a keying
            # error: the excess is taken back off, most recent figure first, and
            # the correction is written into the history so the change is not
            # silent. Anything that is genuinely a customer credit should be
            # moved to the invoice it belongs to instead of corrected here.
            excess = round(invoice_amount_paid(inv) - due, 2)
            if excess > CENT:
                removed = excess
                take = min(inv.paid_amount or 0.0, excess)
                inv.paid_amount = round((inv.paid_amount or 0.0) - take, 2)
                excess = round(excess - take, 2)
                if excess > CENT:
                    inv.advance = round((inv.advance or 0.0) - excess, 2)
                overpayments_fixed += 1
                money_removed += removed
                changed = True

                try:
                    history = json.loads(inv.payments_history) if inv.payments_history else []
                except (ValueError, TypeError):
                    history = []
                history.append({
                    "amount": -removed,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "person": "system/overpayment-correction",
                    "proof_path": None,
                    "source": "overpayment_correction",
                    "note": (f"Recorded payments exceeded the {due:.2f} PKR due by "
                             f"{removed:.2f} PKR. Corrected as a keying error."),
                })
                inv.payments_history = json.dumps(history)

            # Now that amounts are trustworthy, let them define the status.
            derived = calculate_invoice_status(inv)
            if derived != inv.status:
                inv.status = derived
                status_corrected += 1
                changed = True

            # Keep the stored balance consistent with the amounts either way.
            correct_balance = round(invoice_amount_due(inv) - invoice_amount_paid(inv), 2)
            if abs((inv.balance or 0.0) - correct_balance) > CENT:
                inv.balance = correct_balance
                changed = True

            if not changed:
                already_ok += 1

        receivable = round(
            sum(
                max(0.0, invoice_amount_due(i) - invoice_amount_paid(i))
                for i in invoices
            ),
            2,
        )

        print(f"invoices examined      : {len(invoices)}")
        print(f"payment amounts filled : {amounts_filled}")
        print(f"overpayments corrected : {overpayments_fixed}"
              + (f"   (-{money_removed:,.2f} PKR)" if money_removed else ""))
        print(f"statuses corrected     : {status_corrected}")
        print(f"already consistent     : {already_ok}")
        print(f"money backfilled       : {money_backfilled:,.2f} PKR")
        print(f"receivables afterwards : {receivable:,.2f} PKR")

        if APPLY:
            db.session.commit()
            print("\nCommitted.")
        else:
            db.session.rollback()
            print("\nDry run - nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
