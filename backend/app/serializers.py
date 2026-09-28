from .models import Batch, Farmer, Inspection, User


def user_out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
            "centre_id": u.centre_id, "centre": u.centre.name if u.centre else None}


def farmer_out(f: Farmer) -> dict:
    return {"id": f.id, "farmer_code": f.farmer_code, "name": f.name, "phone": f.phone, "village": f.village}


def batch_out(b: Batch) -> dict:
    last = b.inspections[0] if b.inspections else None
    return {
        "id": b.id, "batch_code": b.batch_code, "farmer": farmer_out(b.farmer), "commodity": b.commodity,
        "variety": b.variety, "quantity_kg": b.quantity_kg, "centre": b.centre.name if b.centre else None,
        "created_at": b.created_at.isoformat(),
        "latest_inspection": inspection_brief(last) if last else None,
    }


def inspection_brief(i: Inspection) -> dict:
    return {"id": i.id, "report_id": i.report_id, "batch_code": i.batch.batch_code, "farmer": i.batch.farmer.name,
            "decision": i.lot_decision, "grade_a_pct": i.percentages.get("grade_a", 0), "urs_pct": i.percentages.get("urs", 0),
            "bag_rate_50kg": i.bag_rate_50kg,
            "estimated_lot_value": round(i.batch.quantity_kg / 50 * i.bag_rate_50kg, 2) if i.bag_rate_50kg is not None else None,
            "total_onions": i.total_onions, "created_at": i.created_at.isoformat()}


def inspection_out(i: Inspection) -> dict:
    d = inspection_brief(i)
    d.update({
        "standard": i.standard_label, "standard_snapshot": i.standard_snapshot, "vision_backend": i.vision_backend,
        "counts": i.counts, "percentages": i.percentages, "excluded_onions": i.excluded_onions,
        "explanation": i.explanation, "warnings": i.warnings, "avg_confidence": i.avg_confidence,
        "integrity_hash": i.integrity_hash, "notes": i.notes,
        "operator": i.operator.full_name if i.operator else None,
        "batch": batch_out_light(i.batch),
        "images": [{"id": im.id, "calibration_method": im.calibration_method, "mm_per_pixel": im.mm_per_pixel,
                    "onion_count": im.onion_count} for im in i.images],
        "onions": [{"number": o.number, "image_id": o.image_id, "diameter_mm": o.diameter_mm, "grade": o.grade,
                    "category": o.category, "confidence": o.confidence, "damage_pct": o.damage_pct,
                    "discolouration_pct": o.discolouration_pct, "rot": o.rot, "sprouted": o.sprouted,
                    "reasons": o.reasons} for o in i.onions],
    })
    return d


def batch_out_light(b: Batch) -> dict:
    return {"id": b.id, "batch_code": b.batch_code, "farmer": farmer_out(b.farmer), "commodity": b.commodity,
            "variety": b.variety, "quantity_kg": b.quantity_kg, "centre": b.centre.name if b.centre else None}
