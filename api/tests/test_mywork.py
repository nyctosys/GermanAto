from test_foundation import signed_in
from test_phase3_billing import CASH, ready_repair
from test_phase3_visits import checked_in


def person(admin, username, role):
    roles = {r["name"]: r["id"] for r in admin.get("/api/roles").json()}
    branch = admin.get("/api/auth/me").json()["branch"]["id"]
    r = admin.post("/api/users", json={"username": username, "full_name": username.title(), "password": f"{username}-pass-123",
                                       "role_id": roles[role], "branch_ids": [branch]})
    assert r.status_code == 201, r.text
    return signed_in(username, f"{username}-pass-123")


def queues(client):
    return {g["key"]: g for g in client.get("/api/my-work").json()["groups"]}


def test_the_standard_roles_exist_and_each_holds_only_its_own_work(admin):
    names = {r["name"] for r in admin.get("/api/roles").json()}
    assert {"Manager", "Front desk", "Technician", "Cashier", "Guard", "Accountant", "Inventory manager"} <= names
    guard = person(admin, "gatekeeper", "Guard")
    assert guard.get("/api/invoices").status_code == 403 and guard.get("/api/customers").status_code == 403
    assert guard.get("/api/gate/queue").status_code == 200


def test_a_new_car_asks_the_front_desk_for_a_job_card_and_nobody_else(admin):
    desk, guard, cashier = person(admin, "deskperson", "Front desk"), person(admin, "gatekeeper", "Guard"), person(admin, "tillperson", "Cashier")
    checked_in(admin)
    assert "job-card" in queues(desk) and queues(guard) == {} and queues(cashier) == {}


def test_a_job_travels_from_role_to_role_without_anyone_being_told(admin):
    cashier, guard = person(admin, "tillperson", "Cashier"), person(admin, "gatekeeper", "Guard")
    assert "payment" not in queues(cashier)

    visit, _, ro = ready_repair(admin)  # the repair is finished: billing is asked for the invoice
    assert "make-invoice" in queues(cashier) or "make-invoice" in queues(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    assert "issue-invoice" in queues(cashier)  # drafted: the cashier issues it
    admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]})
    pay = queues(cashier)["payment"]  # issued with a balance: the cashier collects
    assert pay["items"][0]["label"] == inv["number"]
    [owing] = guard.get("/api/gate/queue").json()  # the guard sees the car, marked as not releasable while money is owed
    assert owing["can_release"] is False and owing["balance"] > 0

    cashier.post(f"/api/invoices/{inv['id']}/payments", json={"amount": "6530", **CASH})
    assert "payment" not in queues(cashier)
    waiting = guard.get("/api/gate/queue").json()
    assert len(waiting) == 1 and waiting[0]["can_release"] is True and waiting[0]["plate"]
    assert queues(guard)["gate"]["count"] == 1

    r = guard.post(f"/api/visits/{visit['id']}/gate-pass", json={"odometer_out": 80020, "handed_to": "Owner"})  # the guard releases the car
    assert r.status_code == 200
    assert guard.get("/api/gate/queue").json() == [] and "gate" not in queues(guard)
    assert guard.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "no"}).status_code == 403  # a guard can do nothing else


def test_a_guard_cannot_release_a_car_that_still_owes_money(admin):
    visit, _, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]})
    guard = person(admin, "gatekeeper", "Guard")
    [car] = guard.get("/api/gate/queue").json()
    assert car["can_release"] is False and car["balance"] > 0
    assert guard.post(f"/api/visits/{visit['id']}/gate-pass", json={"odometer_out": 80020}).status_code == 403


def test_queues_depend_on_permissions_not_on_role_names(admin):
    tech = person(admin, "mechanic", "Technician")
    visit, _, ro = ready_repair(admin)
    assert set(queues(tech)) <= {"repairs", "job-card", "make-ro"}  # a technician is only ever offered repair work
    assert "money" not in str(queues(tech)) and "pay-bills" not in queues(tech)


def test_gate_history_lists_cars_that_left(admin):
    from tests.test_phase3_billing import ready_repair
    visit, _, ro = ready_repair(admin)
    inv = admin.post(f"/api/repair-orders/{ro['id']}/invoice").json()
    inv = admin.post(f"/api/invoices/{inv['id']}/issue", json={"version": inv["version"]}).json()
    admin.post(f"/api/invoices/{inv['id']}/payments", json={"amount": str(inv["totals"]["balance"]), "account": "cash", "no_proof_reason": "Cash at the counter"})
    assert admin.get("/api/gate/history").json() == []
    assert admin.post(f"/api/visits/{visit['id']}/gate-pass", json={"handed_to": "Ali Khan"}).status_code == 200
    rows = admin.get("/api/gate/history").json()
    assert [r["number"] for r in rows] == [visit["number"]] and rows[0]["handed_to"] == "Ali Khan" and rows[0]["on_credit"] is False
    assert admin.get("/api/gate/history", params={"q": "nobody-here"}).json() == []
