import threading
from datetime import date, timedelta
from decimal import Decimal

from app.db import SessionLocal
from app.stock import StockError, move
from test_foundation import make_user, signed_in


def new_customer(client, name="Ali Khan", phone="0300 1234567", **extra):
    r = client.post("/api/customers", json={"name": name, "phone": phone, **extra})
    assert r.status_code == 201, r.json()
    return r.json()


def new_car(client, owner_id, plate="LEA-21-1234", **extra):
    r = client.post("/api/cars", json={"owner_id": owner_id, "make": "BMW", "model": "520i", "plate": plate, **extra})
    assert r.status_code == 201, r.json()
    return r.json()


def new_item(client, name="Oil filter", codes=(("barcode", "4006633123456"),), **extra):
    body = {"name": name, "sale_price": "1500", "codes": [{"kind": k, "code": c} for k, c in codes], **extra}
    r = client.post("/api/items", json=body)
    assert r.status_code == 201, r.json()
    return r.json()


# --- customers --------------------------------------------------------------

def test_customer_numbering_and_normalising(admin):
    c = new_customer(admin, cnic="3520212345671")
    assert c["number"] == "CUS-A1F3-000001" and c["phone"] == "+923001234567" and c["cnic"] == "35202-1234567-1"
    assert new_customer(admin, name="Sara", phone="0321 7654321")["number"] == "CUS-A1F3-000002"


def test_duplicate_phone_asks_first(admin):
    first = new_customer(admin)
    r = admin.post("/api/customers", json={"name": "Ali K.", "phone": "+92 300 1234567"})
    assert r.status_code == 409 and r.json()["detail"]["matches"][0]["id"] == str(first["id"])
    assert admin.post("/api/customers", json={"name": "Ali K.", "phone": "03001234567",
                                              "allow_duplicate_phone": True}).status_code == 201


def test_customer_search_by_phone_digits_and_plate(admin):
    c = new_customer(admin)
    new_car(admin, c["id"], plate="LEB-555")
    for q in ("0300 1234", "Ali", "leb555", "CUS-A1F3"):
        assert [x["id"] for x in admin.get("/api/customers", params={"q": q}).json()] == [c["id"]], q


# --- cars & transfers ---------------------------------------------------------

def test_car_identity_rules(admin):
    c = new_customer(admin)
    car = new_car(admin, c["id"], vin="wba 3a5c5 5df 123456")
    assert car["vin"] == "WBA3A5C55DF123456" and car["owner"]["id"] == c["id"]
    assert admin.post("/api/cars", json={"owner_id": c["id"], "make": "Audi", "plate": "lea 21 1234"}).status_code == 409
    assert admin.post("/api/cars", json={"owner_id": c["id"], "make": "Audi", "vin": "WBAO3A5C55DF12345"}).status_code == 422


def test_transfer_keeps_history_and_checks_rules(admin):
    seller, buyer = new_customer(admin), new_customer(admin, name="Buyer", phone="0333 1112223")
    car = new_car(admin, seller["id"])
    url = f"/api/cars/{car['id']}/transfer"
    today = date.today().isoformat()

    make_user(admin)  # Accountant: has "customers" but not "car-transfer"
    acct = signed_in("acct", "acct-pass-123")
    assert acct.post(url, json={"to_customer_id": buyer["id"], "on": today, "reason": "Sold"}).status_code == 403

    assert admin.post(url, json={"to_customer_id": seller["id"], "on": today, "reason": "Sold"}).status_code == 409
    future = (date.today() + timedelta(days=3)).isoformat()
    assert admin.post(url, json={"to_customer_id": buyer["id"], "on": future, "reason": "Sold"}).status_code == 422

    proof = admin.post("/api/attachments", files={"file": ("deed.pdf", b"%PDF-1.4 transfer deed", "application/pdf")}).json()
    r = admin.post(url, json={"to_customer_id": buyer["id"], "on": today, "reason": "Sold to buyer",
                              "odometer_km": 81000, "attachment_ids": [proof["id"]]})
    assert r.status_code == 200, r.json()
    detail = r.json()
    assert detail["owner"]["id"] == buyer["id"] and detail["odometer_km"] == 81000
    assert [o["customer"]["id"] for o in detail["ownerships"]] == [buyer["id"], seller["id"]]
    assert detail["ownerships"][1]["until"] == today and detail["ownerships"][0]["proofs"][0]["id"] == proof["id"]

    history = admin.get(f"/api/cars/{car['id']}/history").json()
    assert {e["title"] for e in history} >= {"Owned by Buyer", "Owned by Ali Khan"}
    seller_cars = admin.get(f"/api/customers/{seller['id']}").json()["cars"]
    assert seller_cars[0]["until"] == today  # past owners still see the car in their record


# --- labour codes -------------------------------------------------------------

def test_labour_codes(admin):
    r = admin.post("/api/labour-codes", json={"code": "pnt-door", "name": "Paint one door", "category": "Painting"})
    assert r.status_code == 201 and r.json()["code"] == "PNT-DOOR"
    assert admin.post("/api/labour-codes", json={"code": "PNT-DOOR", "name": "x", "category": "y"}).status_code == 409
    code = r.json()
    assert admin.put(f"/api/labour-codes/{code['id']}", json={**code, "code": "PNT-DOOR2"}).status_code == 422
    assert admin.put(f"/api/labour-codes/{code['id']}", json={**code, "is_active": False}).status_code == 200
    assert admin.get("/api/labour-codes").json() == []


# --- inventory ----------------------------------------------------------------

def test_item_codes_are_unique_after_normalising(admin):
    item = new_item(admin, codes=(("mpn", "11-42 7.583 220"),))
    assert item["number"] == "ITM-A1F3-000001"
    r = admin.post("/api/items", json={"name": "Copy", "sale_price": "1", "codes": [{"kind": "mpn", "code": "11427583220"}]})
    assert r.status_code == 409 and "Oil filter" in r.json()["detail"]
    found = admin.get("/api/items/lookup", params={"code": "1142 7583 220"}).json()
    assert found["id"] == item["id"]
    unknown = admin.get("/api/items/lookup", params={"code": "999-000"})
    assert unknown.status_code == 404 and unknown.json()["detail"]["code_norm"] == "999000"


def test_stock_moves_and_average_cost(admin):
    item = new_item(admin, opening_qty="10", opening_cost="100", reorder_level="12")
    assert Decimal(item["on_hand"]) == 10 and Decimal(item["avg_cost"]) == 100 and item["low_stock"]
    url = f"/api/items/{item['id']}/adjust"
    assert admin.post(url, json={"qty": "-11", "reason": "Damaged"}).status_code == 422  # never below zero
    r = admin.post(url, json={"qty": "10", "reason": "Found in store room", "unit_cost": "200"})
    detail = r.json()
    assert Decimal(detail["on_hand"]) == 20 and Decimal(detail["avg_cost"]) == 150 and not detail["low_stock"]
    assert [m["kind"] for m in detail["movements"]] == ["adjustment", "opening"]
    assert admin.get("/api/items", params={"stock": "low"}).json() == []


def test_inventory_permissions(admin):
    make_user(admin, username="store", role="Inventory manager", password="store-pass-1")
    store = signed_in("store", "store-pass-1")
    assert store.get("/api/items").status_code == 200
    assert store.get("/api/customers").status_code == 403
    make_user(admin)
    acct = signed_in("acct", "acct-pass-123")
    assert acct.get("/api/items").status_code == 403


def test_last_unit_cannot_be_issued_twice(admin):
    """Two counters selling the last oil filter at the same moment: one wins."""
    item = new_item(admin, opening_qty="1", opening_cost="100")
    results = []

    def sell():
        with SessionLocal() as db:
            db.info.update(branch_id=None)
            try:
                move(db, item["id"], "sale", Decimal("-1"), reason="counter")
                db.commit()
                results.append("sold")
            except StockError:
                db.rollback()
                results.append("refused")

    threads = [threading.Thread(target=sell) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["refused", "sold"]
    assert Decimal(admin.get(f"/api/items/{item['id']}").json()["on_hand"]) == 0
