"""The Germanato Vehicle Inspection Report (docs/reference/...pdf) as data.

The form, the validation and the printout are all driven from this, so adding
an item is an edit here plus a new VERSION. A saved inspection keeps the
version it was filled in on and always prints with that version.
"""

VERSION = 1

RATINGS = {"good": "Good", "average": "Average", "attention": "Needs attention", "not_checked": "Not checked"}

# Rated checklists: (section key, title, [(item key, label), ...])
RATED_SECTIONS = [
    ("exterior", "Exterior, body and paint", [
        ("front_bumper", "Front bumper"), ("bonnet", "Bonnet / hood"), ("roof", "Roof"), ("boot", "Boot / tailgate"),
        ("lf_fender", "Left front fender"), ("rf_fender", "Right front fender"), ("lf_door", "Left front door"),
        ("rf_door", "Right front door"), ("lr_door", "Left rear door / quarter"), ("rr_door", "Right rear door / quarter"),
        ("windshield", "Windshield"), ("glass", "Rear / side glass"), ("headlamps", "Headlamps / fog lamps"),
        ("tail_lamps", "Tail lamps"), ("mirrors", "Mirrors"), ("panel_gaps", "Body alignment / panel gaps"),
    ]),
    ("mechanical", "Engine, transmission and mechanical", [
        ("engine_start", "Engine start / idle"), ("engine_noise", "Engine noise / vibration"), ("oil_leaks", "Oil leaks"),
        ("coolant_leaks", "Coolant leaks"), ("oil_condition", "Engine oil condition"), ("coolant_condition", "Coolant condition"),
        ("belts", "Belts / pulleys"), ("engine_mounts", "Engine mounts"), ("transmission", "Transmission operation"),
        ("transmission_leaks", "Transmission leaks"), ("drive_shafts", "Drive shafts / CV joints"),
        ("differential", "Differential / transfer case"), ("exhaust", "Exhaust system"), ("cooling_fan", "Cooling fan operation"),
        ("turbo", "Turbo / supercharger (if fitted)"), ("fuel_system", "Fuel system visible checks"),
    ]),
    ("chassis", "Suspension, steering and brakes", [
        ("shocks", "Shocks / struts"), ("air_suspension", "Air suspension"), ("control_arms", "Control arms / bushes"),
        ("ball_joints", "Ball joints"), ("steering", "Steering rack / EPS"), ("wheel_bearings", "Wheel bearings"),
        ("brakes", "Brake pads / discs"), ("brake_fluid", "Brake fluid"), ("parking_brake", "Parking brake"),
        ("abs", "ABS warning"),
    ]),
    ("electrical", "Electrical and interior", [
        ("cluster", "Cluster warnings"), ("windows", "Windows"), ("central_locking", "Central locking"),
        ("seats", "Seats / memory"), ("lights", "Lights and signals"), ("wipers", "Wipers / washers"),
        ("infotainment", "Infotainment"), ("cameras", "Cameras / sensors"), ("ac", "AC / heater"), ("horn", "Horn / controls"),
    ]),
    ("road_test", "Road test", [
        ("rt_engine", "Engine performance"), ("rt_shift", "Transmission shift quality"), ("rt_steering", "Steering response"),
        ("rt_brakes", "Brake performance"), ("rt_suspension", "Suspension noise"), ("rt_alignment", "Wheel alignment / pulling"),
        ("rt_vibration", "Vibration"), ("rt_assist", "Cruise / driver assistance"), ("rt_hybrid", "HV / hybrid operation"),
        ("rt_temperature", "Temperature / overheating"), ("rt_wind", "Wind / body noise"), ("rt_drivability", "Overall drivability"),
    ]),
]

ITEM_KEYS = {key for _, _, items in RATED_SECTIONS for key, _ in items}
PAINT_FINDINGS = ["original", "repaint", "filler", "replaced"]
WARNING_LIGHTS = ["check_engine", "abs", "airbag", "chassis", "other"]
OVERALL = {"excellent": "Excellent", "good": "Good", "average": "Average", "poor": "Poor"}
RECOMMENDATION = {"recommended": "Recommended", "after_repairs": "Recommended after repairs", "not_recommended": "Not recommended"}
DISCLAIMER = ("Condition is recorded as observed at inspection time; this is not a warranty. Hidden, intermittent or "
              "future faults may not be detectable without dismantling or further testing.")


def as_dict() -> dict:
    return {
        "version": VERSION, "ratings": RATINGS, "overall": OVERALL, "recommendation": RECOMMENDATION,
        "paint_findings": PAINT_FINDINGS, "warning_lights": WARNING_LIGHTS, "disclaimer": DISCLAIMER,
        "sections": [{"key": k, "title": t, "items": [{"key": ik, "label": il} for ik, il in items]}
                     for k, t, items in RATED_SECTIONS],
    }


if __name__ == "__main__":
    counts = {k: len(items) for k, _, items in RATED_SECTIONS}
    assert counts == {"exterior": 16, "mechanical": 16, "chassis": 10, "electrical": 10, "road_test": 12}, counts
    assert len(ITEM_KEYS) == 64  # every key unique
    print("ok", counts)
