from decimal import Decimal

from test_foundation import signed_in

D = Decimal


def new_employee(admin, name="Bilal Ahmed", **extra):
    body = {"full_name": name, "joined_on": "2026-09-01", "monthly_salary": "60000", **extra}
    r = admin.post("/api/employees", json=body)
    assert r.status_code == 201, r.json()
    return r.json()


def push(client, serial, lines, token=None, **kw):
    params = {"SN": serial, "table": "ATTLOG", **({"token": token} if token else {})}
    return client.post("/iclock/cdata", params=params, content="\n".join("\t".join(l) for l in lines), **kw)


def test_employees_are_unique_by_cnic_device_number_and_login(admin):
    e = new_employee(admin, cnic="3520212345671", device_pin="7", phone="0300 1234567")
    assert e["number"] == "EMP-A1F3-000001" and e["cnic"] == "35202-1234567-1" and e["phone"] == "+923001234567"
    assert admin.post("/api/employees", json={"full_name": "Other", "joined_on": "2026-09-01", "cnic": "35202-1234567-1"}).status_code == 409
    assert admin.post("/api/employees", json={"full_name": "Other", "joined_on": "2026-09-01", "device_pin": "7"}).status_code == 409
    assert admin.post("/api/employees", json={"full_name": "Bad shift", "joined_on": "2026-09-01", "shift_start": "18:00:00", "shift_end": "09:00:00"}).status_code == 422
    me = admin.get("/api/auth/me").json()["user"]["id"]
    assert admin.post("/api/employees", json={"full_name": "Linked", "joined_on": "2026-09-01", "user_id": me}).status_code == 201
    assert admin.post("/api/employees", json={"full_name": "Again", "joined_on": "2026-09-01", "user_id": me}).status_code == 409
    assert me not in [u["id"] for u in admin.get("/api/employee-logins").json()]
    upd = admin.put(f"/api/employees/{e['id']}", json={"full_name": "Bilal Ahmed", "joined_on": "2026-09-01", "left_on": "2026-08-01", "version": e["version"]})
    assert upd.status_code == 422  # left before joining


def test_only_registered_devices_with_the_right_secret_can_push(admin, anon):
    assert push(anon, "ZK-1001", [("1", "2026-09-01 09:00:00", "0", "1")]).status_code == 403  # unknown serial
    d = admin.post("/api/attendance-devices", json={"serial": "ZK-1001", "name": "Front door", "use_secret": True}).json()
    assert d["has_secret"] and len(d["secret"]) >= 20
    assert "secret" not in admin.get("/api/attendance-devices").json()[0]  # shown once
    assert push(anon, "ZK-1001", [("1", "2026-09-01 09:00:00", "0", "1")]).status_code == 403  # no secret
    assert push(anon, "ZK-1001", [("1", "2026-09-01 09:00:00", "0", "1")], token="wrong").status_code == 403
    assert push(anon, "ZK-1001", [("1", "2026-09-01 09:00:00", "0", "1")], token=d["secret"]).text == "OK:1"
    assert admin.get("/api/attendance-devices").json()[0]["last_seen_at"]

    new = admin.post(f"/api/attendance-devices/{d['id']}/secret").json()["secret"]
    assert push(anon, "ZK-1001", [("1", "2026-09-02 09:00:00", "0", "1")], token=d["secret"]).status_code == 403  # the old secret is dead
    assert push(anon, "ZK-1001", [("1", "2026-09-02 09:00:00", "0", "1")], token=new).status_code == 200
    admin.put(f"/api/attendance-devices/{d['id']}", json={"name": "Front door", "is_active": False, "version": admin.get("/api/attendance-devices").json()[0]["version"]})
    assert push(anon, "ZK-1001", [("1", "2026-09-03 09:00:00", "0", "1")], token=new).status_code == 403  # switched off
    assert anon.get("/iclock/cdata", params={"SN": "NOPE"}).status_code == 403
    assert admin.post("/api/attendance-devices", json={"serial": "ZK-1001", "name": "Again"}).status_code == 409


def test_punches_are_deduplicated_and_unmatched_pins_are_claimed_later(admin, anon):
    admin.post("/api/attendance-devices", json={"serial": "ZK-2002", "name": "Workshop"})
    lines = [("9", "2026-09-01 09:00:00", "0", "1", "0", "0"), ("9", "2026-09-01 18:05:00", "1", "1"), ("junk",), ("9", "not a time")]
    assert push(anon, "ZK-2002", lines).text == "OK:2"
    assert push(anon, "ZK-2002", lines).text == "OK:0"  # a terminal resends what it already sent
    assert admin.get("/api/attendance/unmatched").json()[0]["device_pin"] == "9"
    e = new_employee(admin, device_pin="9")  # giving the number to an employee claims the punches
    assert admin.get("/api/attendance/unmatched").json() == []
    month = admin.get(f"/api/attendance/{e['id']}", params={"month": "2026-09"}).json()
    assert len(month["punches"]) == 2 and month["present"] == 1


def test_days_are_worked_out_from_punches_leave_and_the_weekly_off(admin, anon):
    admin.post("/api/attendance-devices", json={"serial": "ZK-3003", "name": "Door"})
    e = new_employee(admin, device_pin="5")
    push(anon, "ZK-3003", [("5", "2026-09-01 08:55:00", "0", "1"), ("5", "2026-09-01 18:10:00", "1", "1"),   # on time
                           ("5", "2026-09-02 09:30:00", "0", "1"), ("5", "2026-09-02 18:00:00", "1", "1"),   # late
                           ("5", "2026-09-03 09:00:00", "0", "1")])                                          # forgot to punch out
    admin.post("/api/attendance/marks", json={"employee_id": e["id"], "day": "2026-09-04", "kind": "paid_leave", "reason": "Family wedding"})
    m = admin.get(f"/api/attendance/{e['id']}", params={"month": "2026-09"}).json()
    days = {d["day"]: d for d in m["days"]}
    assert [days[f"2026-09-0{n}"]["status"] for n in range(1, 7)] == ["present", "late", "incomplete", "paid_leave", "absent", "off"]
    assert D(str(days["2026-09-01"]["hours"])) == D("9.25")
    # September 2026 has 30 days and four Sundays, so 26 working days: 2 attended, 1 late, 1 on leave, 22 absent.
    assert (m["present"], m["late"], m["paid_leave"], m["absent"], m["off"], m["working_days"]) == (2, 1, 1, 22, 4, 26)

    month = admin.get("/api/attendance", params={"month": "2026-09"}).json()
    assert month["employees"][0]["absent"] == 22 and "days" not in month["employees"][0]
    assert admin.get("/api/attendance", params={"month": "September"}).status_code == 422
    assert admin.delete("/api/attendance/marks", params={"employee_id": e["id"], "day": "2026-09-04"}).status_code == 200


def test_manual_punches_need_a_reason_and_can_be_voided_but_device_ones_cannot(admin, anon):
    admin.post("/api/attendance-devices", json={"serial": "ZK-4004", "name": "Door"})
    e = new_employee(admin, device_pin="3")
    push(anon, "ZK-4004", [("3", "2026-09-01 09:00:00", "0", "1")])
    base = {"employee_id": e["id"], "punched_at": "2026-09-01T18:00:00"}
    assert admin.post("/api/attendance/punches", json={**base, "reason": "x"}).status_code == 422
    assert admin.post("/api/attendance/punches", json={**base, "punched_at": "2099-01-01T09:00:00", "reason": "Wrong year"}).status_code == 422
    assert admin.post("/api/attendance/punches", json={**base, "reason": "Finger scan failed at the door"}).status_code == 201
    punches = admin.get(f"/api/attendance/{e['id']}", params={"month": "2026-09"}).json()["punches"]
    manual = next(p for p in punches if p["source"] == "manual")
    device = next(p for p in punches if p["source"] == "device")
    assert admin.post(f"/api/attendance/punches/{device['id']}/void", json={"reason": "Wrong person"}).status_code == 409
    assert admin.post(f"/api/attendance/punches/{manual['id']}/void", json={"reason": "Typed the wrong time"}).status_code == 200
    again = admin.get(f"/api/attendance/{e['id']}", params={"month": "2026-09"}).json()
    assert next(d for d in again["days"] if d["day"] == "2026-09-01")["status"] == "incomplete"  # only the device punch counts now


def test_hr_is_for_people_with_the_hr_permission(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "inv", "full_name": "Inv", "password": "inv-pass-1234", "role_id": roles["Inventory manager"], "branch_ids": [branch_id]})
    inv = signed_in("inv", "inv-pass-1234")
    assert inv.get("/api/employees").status_code == 403 and inv.get("/api/attendance").status_code == 403


# --- salary advances and payroll ---------------------------------------------------------------------------

from test_phase5_money import rows

CASH = {"account": "cash", "no_proof_reason": "Cash from the till"}


def staff(admin, name="Kashif Mehmood", joined="2026-09-25", salary="26000"):
    """September 2026 has 26 working days, so a day's pay is exactly 1000. Joined on the 25th: 5 working days (25, 26, 28, 29, 30)."""
    e = new_employee(admin, name, joined_on=joined, monthly_salary=salary)
    for day in ("2026-09-25", "2026-09-26", "2026-09-28", "2026-09-29"):
        admin.post("/api/attendance/punches", json={"employee_id": e["id"], "punched_at": f"{day}T09:00:00", "reason": "Worked, finger scan was down"})
    admin.post("/api/attendance/marks", json={"employee_id": e["id"], "day": "2026-09-30", "kind": "unpaid_leave", "reason": "Family matter"})
    return e


def test_salary_advances_are_capped_to_a_months_pay_and_hit_the_books(admin):
    e = staff(admin)
    url = "/api/salary-advances"
    assert admin.post(url, json={"employee_id": e["id"], "amount": "30000", **CASH}).status_code == 422  # more than a month's pay
    assert admin.post(url, json={"employee_id": e["id"], "amount": "1500", "account": "cash"}).status_code == 422  # no proof or reason
    done = admin.post(url, json={"employee_id": e["id"], "amount": "1500", **CASH})
    assert done.status_code == 201 and done.json()["number"].startswith("ADV-")
    assert admin.post(url, json={"employee_id": e["id"], "amount": "25000", **CASH}).status_code == 422  # 1500 + 25000 > 26000
    b = rows(admin)
    assert b["1300"] == 1500 and b["1010"] == -1500
    summary = admin.get(url).json()["employees"][0]
    assert D(str(summary["outstanding"])) == 1500
    out = admin.get("/api/money-out").json()
    assert [r["source"] for r in out["rows"]] == ["salary_advance"] and out["rows"][0]["party"] == "Kashif Mehmood"


def test_payroll_from_attendance_with_an_advance_recovered_and_the_net_paid_out(admin):
    e = staff(admin)
    admin.post("/api/salary-advances", json={"employee_id": e["id"], "amount": "1500", **CASH})
    assert admin.post("/api/payroll-runs", json={"month": date_this_month()}).status_code == 422  # the month hasn't ended
    run = admin.post("/api/payroll-runs", json={"month": "2026-09"})
    assert run.status_code == 201, run.json()
    run = run.json()
    line = run["lines"][0]
    # 5 working days of 26: base 5000; one unpaid leave day costs 1000; 1500 advance recovered by default.
    assert (D(str(line["base_pay"])), D(str(line["deduction"])), D(str(line["advance_recovery"])), D(str(line["net_pay"]))) == (5000, 1000, 1500, 2500)
    assert (line["working_days"], line["month_working_days"], line["absent_days"], line["unpaid_leave_days"]) == (5, 26, 0, 1)
    assert admin.post("/api/payroll-runs", json={"month": "2026-09"}).status_code == 409  # one run a month

    url = f"/api/payroll-runs/{run['id']}/lines/{line['id']}"
    assert admin.put(url, json={"adjustment": "500", "advance_recovery": "1500"}).status_code == 422  # a bonus needs a reason
    assert admin.put(url, json={"adjustment": "0", "advance_recovery": "2000"}).status_code == 422  # only 1500 is outstanding
    edited = admin.put(url, json={"adjustment": "500", "adjustment_reason": "Overtime on a rush job", "advance_recovery": "1500"}).json()
    assert D(str(edited["lines"][0]["net_pay"])) == 3000 and D(str(edited["totals"]["net"])) == 3000
    assert admin.post(f"{url}/pay", json=CASH).status_code == 409  # not approved yet

    approved = admin.post(f"/api/payroll-runs/{run['id']}/approve").json()
    assert approved["status"] == "approved" and approved["approved_by"] == "Administrator"
    b = rows(admin)
    assert b["6100"] == 4500 and b["1300"] == 0 and b["2400"] == -3000  # expense 4500; the advance is recovered; 3000 owed to staff
    assert admin.put(url, json={"adjustment": "0", "advance_recovery": "0"}).status_code == 409  # locked
    assert D(str(admin.get("/api/salary-advances").json()["employees"][0]["outstanding"])) == 0

    paid = admin.post(f"{url}/pay", json={"account": "bank", "no_proof_reason": "Slip to follow"})
    assert paid.status_code == 422  # a transfer needs its reference
    done = admin.post(f"{url}/pay", json={"account": "bank", "reference": "IBFT-1", "no_proof_reason": "Slip to follow"})
    assert done.status_code == 201 and done.json()["status"] == "paid"
    assert admin.post(f"{url}/pay", json=CASH).status_code == 409  # once
    b = rows(admin)
    assert b["2400"] == 0 and b["1020"] == -3000
    sal = next(r for r in admin.get("/api/money-out", params={"source": "salary"}).json()["rows"])
    assert sal["party"] == "Kashif Mehmood" and D(str(sal["amount"])) == 3000

    admin.post(f"/api/money-entries/{sal['entry_id']}/void", json={"reason": "Paid the wrong account"})
    assert admin.get(f"/api/payroll-runs/{run['id']}").json()["status"] == "approved"  # reopened for payment
    assert rows(admin)["2400"] == -3000
    slip = admin.get(url).json()
    assert slip["run"]["month"] == "2026-09" and slip["line"]["employee"]["full_name"] == "Kashif Mehmood"


def date_this_month():
    from datetime import date
    return date.today().strftime("%Y-%m")


def test_a_draft_run_follows_attendance_corrections_and_can_be_thrown_away(admin):
    e = staff(admin)
    run = admin.post("/api/payroll-runs", json={"month": "2026-09"}).json()
    assert D(str(run["lines"][0]["deduction"])) == 1000
    admin.delete("/api/attendance/marks", params={"employee_id": e["id"], "day": "2026-09-30"})  # the leave is cancelled: now an absence
    admin.post("/api/attendance/marks", json={"employee_id": e["id"], "day": "2026-09-30", "kind": "paid_leave", "reason": "Approved after all"})
    refreshed = admin.post(f"/api/payroll-runs/{run['id']}/refresh").json()
    assert D(str(refreshed["lines"][0]["deduction"])) == 0 and D(str(refreshed["lines"][0]["net_pay"])) == 5000
    assert admin.post(f"/api/payroll-runs/{run['id']}/void").status_code == 200
    assert admin.post("/api/payroll-runs", json={"month": "2026-09"}).status_code == 201  # a new run can be made once the draft is thrown away


def test_payroll_is_for_payroll_users_only(admin):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch_id = admin.get("/api/auth/me").json()["branch"]["id"]
    admin.post("/api/users", json={"username": "inv", "full_name": "Inv", "password": "inv-pass-1234", "role_id": roles["Inventory manager"], "branch_ids": [branch_id]})
    admin.post("/api/users", json={"username": "acct", "full_name": "Acct", "password": "acct-pass-1234", "role_id": roles["Accountant"], "branch_ids": [branch_id]})
    assert signed_in("inv", "inv-pass-1234").get("/api/payroll-runs").status_code == 403
    assert signed_in("acct", "acct-pass-1234").get("/api/payroll-runs").status_code == 200
