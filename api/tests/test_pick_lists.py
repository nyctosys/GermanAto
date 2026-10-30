def names(client, kind):
    return [e["name"] for e in client.get(f"/api/lists/{kind}").json()]


def test_lists_start_from_defaults_and_team_adds(admin):
    brands = names(admin, "part_brand")
    for name in ("Audi", "BMW", "Mercedes-Benz", "Toyota", "Honda", "MINI", "Volkswagen", "Bosch"):
        assert name in brands
    r = admin.post("/api/lists/part_brand", json={"name": "  ravenol   oils "})
    assert r.status_code == 201 and r.json()["name"] == "Ravenol Oils" and r.json()["created"]
    assert "Ravenol Oils" in names(admin, "part_brand")


def test_new_defaults_join_an_already_seeded_list(admin):
    """A branch seeded before a brand was in DEFAULTS still gets it the next time the list opens."""
    assert "Bosch" in names(admin, "part_brand")
    gone = next(e for e in admin.get("/api/lists/part_brand").json() if e["name"] == "BMW")
    from app.db import SessionLocal
    from app.models import PickListEntry
    with SessionLocal() as db:
        db.delete(db.get(PickListEntry, gone["id"]))
        db.commit()
    assert "BMW" in names(admin, "part_brand")


def test_same_name_in_other_case_is_not_a_second_entry(admin):
    r = admin.post("/api/lists/part_brand", json={"name": "bosch"})
    assert r.status_code == 201 and r.json()["created"] is False and r.json()["name"] == "Bosch"
    assert names(admin, "part_brand").count("Bosch") == 1


def test_typo_asks_did_you_mean_then_allows_confirm(admin):
    r = admin.post("/api/lists/part_brand", json={"name": "Bosh"})
    assert r.status_code == 409 and "Did you mean Bosch" in r.json()["detail"]
    assert "Bosh" not in names(admin, "part_brand")
    r = admin.post("/api/lists/part_brand", json={"name": "Bosh", "confirm": True})
    assert r.status_code == 201 and r.json()["created"]


def test_rename_carries_to_items_and_retire_hides(admin):
    item = admin.post("/api/items", json={"name": "Wiper", "sale_price": "100", "brand": "Optimax",
                                          "codes": [{"kind": "barcode", "code": "9990001112223"}]}).json()
    entry = next(e for e in admin.get("/api/lists/part_brand").json() if e["name"] == "Optimax")
    assert admin.put(f"/api/lists/part_brand/{entry['id']}", json={"name": "Optimax Pro"}).status_code == 200
    assert admin.get(f"/api/items/{item['id']}").json()["brand"] == "Optimax Pro"
    admin.put(f"/api/lists/part_brand/{entry['id']}", json={"is_active": False})
    assert "Optimax Pro" not in names(admin, "part_brand")


def test_unknown_list_is_404(admin):
    assert admin.get("/api/lists/nothing").status_code == 404


def test_spacing_and_punctuation_variants_reuse_the_entry(admin):
    r = admin.post("/api/lists/part_brand", json={"name": "liqui-moly"})
    assert r.status_code == 201 and r.json()["name"] == "Liqui Moly" and r.json()["created"] is False
    r = admin.post("/api/lists/part_brand", json={"name": "Denzo"})
    assert r.status_code == 409 and "Denso" in r.json()["detail"]


def test_fitment_list_grows_from_items_and_delete_only_when_unused(admin):
    r = admin.post("/api/lists/fitment", json={"name": "audi e-tron"})
    assert r.status_code == 201 and r.json()["name"] == "Audi E-Tron"
    eid = r.json()["id"]
    item = {"name": "Brake pad", "category": "Brakes", "unit": "pcs", "sale_price": "10", "reorder_level": "0", "reorder_qty": "0",
            "fitment": "Audi E-Tron; BMW 5 Series", "codes": [{"kind": "barcode", "code": "FIT-1"}]}
    assert admin.post("/api/items", json=item).status_code == 201
    assert "BMW 5 Series" in names(admin, "fitment")  # a car typed on an item joins the list the next time it opens
    assert admin.delete(f"/api/lists/fitment/{eid}").status_code == 409  # used on an item
    other = admin.post("/api/lists/fitment", json={"name": "Skoda Octavia"}).json()["id"]
    assert admin.delete(f"/api/lists/fitment/{other}").status_code == 200


def test_unused_records_delete_used_ones_refuse(admin):
    item = {"name": "Wiper", "category": "Body and glass", "unit": "pcs", "sale_price": "10", "reorder_level": "0", "reorder_qty": "0",
            "codes": [{"kind": "barcode", "code": "DEL-1"}]}
    made = admin.post("/api/items", json=item).json()
    assert admin.delete(f"/api/items/{made['id']}").status_code == 200
    assert admin.get(f"/api/items/{made['id']}").status_code == 404
    kept = admin.post("/api/items", json={**item, "codes": [{"kind": "barcode", "code": "DEL-2"}], "opening_qty": "5", "opening_cost": "3"}).json()
    r = admin.delete(f"/api/items/{kept['id']}")
    assert r.status_code == 409 and "inactive" in r.json()["detail"]


def test_phone_with_letters_is_refused(admin):
    r = admin.post("/api/customers", json={"name": "Test Phone", "phone": "+92317881123kkjjj", "cnic": "35202-1234567-1"})
    assert r.status_code == 422 and "digits only" in str(r.json())


def test_vendor_contact_person_is_a_name_not_a_number(admin):
    r = admin.post("/api/vendors", json={"name": "Parts Co", "contact_person": "0316112211"})
    assert r.status_code == 422 and "no numbers" in str(r.json())
    assert admin.post("/api/vendors", json={"name": "Parts Co", "contact_person": "Ijmaal Jhatu"}).status_code == 201
