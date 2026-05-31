"""So sánh hai phiên bản đề cương (SPEC 4.3, 7 — versioning + diff)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Assessment, Clo, CourseOutline, LessonPlan


def _outline_snapshot(db: Session, outline_id: int) -> dict:
    o = db.get(CourseOutline, outline_id)
    if not o:
        return {}
    clos = {c.code: c.description for c in db.query(Clo).filter(Clo.outline_id == outline_id).all()}
    assessments = {
        a.name: a.weight_percent
        for a in db.query(Assessment).filter(Assessment.outline_id == outline_id).all()
    }
    lessons = {
        lp.week: lp.topic
        for lp in db.query(LessonPlan).filter(LessonPlan.outline_id == outline_id).all()
    }
    return {
        "description": o.description or "",
        "clos": clos,
        "assessments": assessments,
        "lessons": lessons,
    }


def _diff_dict(a: dict, b: dict) -> dict:
    """Trả về added / removed / changed giữa hai dict."""
    keys = set(a) | set(b)
    added, removed, changed = {}, {}, {}
    for k in keys:
        if k not in a:
            added[str(k)] = b[k]
        elif k not in b:
            removed[str(k)] = a[k]
        elif a[k] != b[k]:
            changed[str(k)] = {"from": a[k], "to": b[k]}
    return {"added": added, "removed": removed, "changed": changed}


def diff_outlines(db: Session, from_id: int, to_id: int) -> dict:
    s1 = _outline_snapshot(db, from_id)
    s2 = _outline_snapshot(db, to_id)
    return {
        "from_id": from_id,
        "to_id": to_id,
        "description_changed": s1.get("description") != s2.get("description"),
        "description": {"from": s1.get("description"), "to": s2.get("description")},
        "clos": _diff_dict(s1.get("clos", {}), s2.get("clos", {})),
        "assessments": _diff_dict(s1.get("assessments", {}), s2.get("assessments", {})),
        "lessons": _diff_dict(s1.get("lessons", {}), s2.get("lessons", {})),
    }
