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
