from test_phase2 import new_car, new_customer

PNG = b"\x89PNG\r\n\x1a\n" + b"\x01" * 80


def upload(client, data=PNG, name="photo.png"):
    r = client.post("/api/attachments", files={"file": (name, data, "image/png")})
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def checked_in(client, odometer=80000, **extra):
    owner = new_customer(client)
    car = new_car(client, owner["id"], odometer_km=78000)
    r = client.post("/api/visits", json={"car_id": car["id"], "odometer_in": odometer, "fuel_eighths": 4,
                                         "complaint": "Noise from front left", **extra})
    assert r.status_code == 201, r.json()
    return r.json(), car, owner


def test_check_in_takes_owner_photos_and_signature(admin):
    photo, signature = upload(admin), upload(admin, PNG + b"sig")
    visit, car, owner = checked_in(admin, photo_ids=[photo], signature_id=signature)
    assert visit["number"] == "VIS-A1F3-000001" and visit["customer"]["id"] == owner["id"]
    assert [p["id"] for p in visit["photos"]] == [photo] and visit["signature"]["id"] == signature
    assert admin.get(f"/api/cars/{car['id']}").json()["odometer_km"] == 80000


def test_one_open_visit_per_car_and_odometer_sanity(admin):
    visit, car, _ = checked_in(admin)
    again = admin.post("/api/visits", json={"car_id": car["id"]})
    assert again.status_code == 409 and again.json()["detail"]["visit_id"] == visit["id"]
    admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Customer left"})
    assert admin.post("/api/visits", json={"car_id": car["id"], "odometer_in": 1000}).status_code == 422  # went backwards
    assert admin.post("/api/visits", json={"car_id": car["id"], "odometer_in": 80500}).status_code == 201
    assert [v["status"] for v in admin.get("/api/visits", params={"status": "all"}).json()] == ["open", "cancelled"]


def test_inspection_lifecycle(admin):
    visit, _, _ = checked_in(admin)
    url = f"/api/visits/{visit['id']}/inspections"
    assert admin.post(url, json={"kind": "pre_purchase"}).status_code == 422  # wrong kind for a workshop visit
    ins = admin.post(url, json={"kind": "workshop"}).json()
    assert ins["number"].startswith("INS-") and ins["data"]["assessment"]["odometer_km"] == 80000

    data = ins["data"]
    data["items"] = {"front_bumper": {"rating": "attention", "note": "Scratched", "photo_ids": []},
                     "engine_start": {"rating": "good"}}
    data["tyres"]["fl"] = {"mm": "3.5", "pct": 40}
    data["scan"]["dtcs"] = [{"module": "DME", "code": "P0300", "description": "Random misfire", "priority": "high"}]
    data["repairs"] = [{"priority": "high", "repair": "Replace ignition coils", "estimated_cost": "45000"}]
    r = admin.put(f"/api/inspections/{ins['id']}", json={"data": data, "version": ins["version"]})
    assert r.status_code == 200, r.json()
    version = r.json()["version"]

    bad = {**data, "items": {"flux_capacitor": {"rating": "good"}}}
    assert admin.put(f"/api/inspections/{ins['id']}", json={"data": bad, "version": version}).status_code == 422
    stale = admin.put(f"/api/inspections/{ins['id']}", json={"data": data, "version": version - 1})
    assert stale.status_code == 409

    sig = upload(admin, PNG + b"inspector")
    sign = f"/api/inspections/{ins['id']}/sign"
    assert admin.post(sign, json={"inspector_signature_id": sig, "version": version}).status_code == 422  # no verdict yet
    data["assessment"].update(overall="average", recommendation="after_repairs", budget="45000")
    version = admin.put(f"/api/inspections/{ins['id']}", json={"data": data, "version": version}).json()["version"]
    signed = admin.post(sign, json={"inspector_signature_id": sig, "version": version}).json()
    assert signed["status"] == "signed" and signed["inspector"] == "Administrator"
    items = signed["data"]["items"]
    assert len(items) == 64 and items["roof"]["rating"] == "not_checked" and items["front_bumper"]["rating"] == "attention"

    assert admin.put(f"/api/inspections/{ins['id']}", json={"data": data, "version": signed["version"]}).status_code == 409
    rev = admin.post(f"/api/inspections/{ins['id']}/revise")
    assert rev.status_code == 201 and rev.json()["supersedes_id"] == ins["id"] and rev.json()["status"] == "draft"
    assert admin.post(f"/api/inspections/{ins['id']}/revise").status_code == 409
    listed = admin.get(f"/api/visits/{visit['id']}").json()["inspections"]
    assert [(i["status"], i["supersedes_id"]) for i in listed] == [("signed", None), ("draft", ins["id"])]


def test_closed_visit_takes_nothing_more(admin):
    visit, _, _ = checked_in(admin)
    admin.post(f"/api/visits/{visit['id']}/cancel", json={"reason": "Duplicate"})
    assert admin.post(f"/api/visits/{visit['id']}/inspections", json={"kind": "workshop"}).status_code == 409
