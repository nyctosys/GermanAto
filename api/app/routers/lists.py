import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, current_actor
from app.db import get_db
from app.models import PickListEntry
from app.pick_lists import DEFAULTS, PERMISSION, entries, lookalike, rename_on_records, tidy

router = APIRouter(prefix="/api", tags=["lists"])


def _kind(kind: str, actor: Actor) -> str:
    if kind not in DEFAULTS:
        raise HTTPException(404, "No such list")
    if not (actor.can(PERMISSION[kind]) or actor.user.role.is_admin):
        raise HTTPException(403, "You don't have permission to do this")
    return kind


def _out(e: PickListEntry) -> dict:
    return {"id": e.id, "name": e.name, "is_active": e.is_active}


@router.get("/lists/{kind}")
def get_list(kind: str, all: bool = False, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    kind = _kind(kind, actor)
    rows = entries(db, actor.branch.id, kind, include_retired=all and actor.user.role.is_admin)
    db.commit()  # the first open seeds the list
    return [_out(e) for e in rows]


class AddIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    confirm: bool = False  # "yes, my spelling is right" after a did-you-mean


@router.post("/lists/{kind}", status_code=201)
def add_entry(kind: str, body: AddIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    kind = _kind(kind, actor)
    name = tidy(body.name)
    if not name:
        raise HTTPException(422, "Type a name")
    rows = entries(db, actor.branch.id, kind, include_retired=True)
    same = next((e for e in rows if e.key == name.lower()), None)
    if same:  # already there (maybe retired): use it, bring it back
        if not same.is_active:
            same.is_active = True
        db.commit()
        return {**_out(same), "created": False}
    near = None if body.confirm else lookalike(db, actor.branch.id, kind, name)
    if near:
        raise HTTPException(409, f"Did you mean {near}? Use it, or add yours anyway.")
    e = PickListEntry(branch_id=actor.branch.id, kind=kind, name=name, key=name.lower())
    db.add(e)
    db.commit()
    return {**_out(e), "created": True}


class EditIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    is_active: bool | None = None


@router.put("/lists/{kind}/{entry_id}")
def edit_entry(kind: str, entry_id: uuid.UUID, body: EditIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    kind = _kind(kind, actor)
    if not actor.user.role.is_admin and not actor.can(PERMISSION[kind]):
        raise HTTPException(403, "You don't have permission to do this")
    e = db.scalar(select(PickListEntry).where(PickListEntry.id == entry_id, PickListEntry.branch_id == actor.branch.id, PickListEntry.kind == kind))
    if not e:
        raise HTTPException(404, "Not found")
    if body.name is not None:
        name = tidy(body.name)
        clash = next((x for x in entries(db, actor.branch.id, kind, include_retired=True) if x.key == name.lower() and x.id != e.id), None)
        if clash:
            raise HTTPException(409, f"{clash.name} is already in the list")
        if name != e.name:
            rename_on_records(db, kind, e.name, name, actor.branch.id)
            e.name, e.key = name, name.lower()
    if body.is_active is not None:
        e.is_active = body.is_active
    db.commit()
    return _out(e)
