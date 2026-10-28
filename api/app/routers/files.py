"""Proof files: receipts, payment screenshots, signatures, PDFs."""

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, require
from app.config import MAX_UPLOAD_BYTES, STORAGE_DIR
from app.db import get_db
from app.models import Attachment

router = APIRouter(prefix="/api/attachments", tags=["attachments"])
can_use = require("attachments")

# Type comes from the file's first bytes, not from the name or the browser's
# claim, so a renamed executable can't be stored as a "receipt".
_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_mime(head: bytes) -> str | None:
    for magic, mime in _SIGNATURES:
        if head.startswith(magic):
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"mif1", b"heif"):
        return "image/heic"  # iPhone photos
    return None


def storage_path(sha256: str):
    return STORAGE_DIR / sha256[:2] / sha256


def out(a: Attachment) -> dict:
    return {"id": a.id, "original_name": a.original_name, "mime": a.mime, "size": a.size, "sha256": a.sha256,
            "entity_type": a.entity_type, "entity_id": a.entity_id, "note": a.note, "created_at": a.created_at,
            "url": f"/api/attachments/{a.id}/file"}


@router.post("", status_code=201)
async def upload(
    file: UploadFile = File(...),
    entity_type: str | None = Form(None, max_length=60),
    entity_id: uuid.UUID | None = Form(None),
    note: str = Form("", max_length=500),
    _: Actor = Depends(can_use),
    db: Session = Depends(get_db),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(422, "The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Files can be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    mime = sniff_mime(data[:16])
    if not mime:
        raise HTTPException(415, "Only photos (JPG, PNG, WEBP, HEIC, GIF) and PDFs can be attached")

    sha = hashlib.sha256(data).hexdigest()
    path = storage_path(sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)  # atomic: never a half-written proof
    att = Attachment(sha256=sha, mime=mime, size=len(data), original_name=(file.filename or "file")[:255],
                     entity_type=entity_type, entity_id=entity_id, note=note.strip())
    db.add(att)
    db.commit()
    return out(att)


def _get(db: Session, actor: Actor, attachment_id: uuid.UUID) -> Attachment:
    att = db.get(Attachment, attachment_id)
    if not att or att.branch_id != actor.branch.id:
        raise HTTPException(404, "File not found")
    return att


@router.get("")
def list_for(entity_type: str, entity_id: uuid.UUID, actor: Actor = Depends(can_use), db: Session = Depends(get_db)):
    q = (select(Attachment).where(Attachment.branch_id == actor.branch.id, Attachment.entity_type == entity_type,
                                  Attachment.entity_id == entity_id).order_by(Attachment.created_at))
    return [out(a) for a in db.scalars(q)]


@router.get("/{attachment_id}")
def meta(attachment_id: uuid.UUID, actor: Actor = Depends(can_use), db: Session = Depends(get_db)):
    return out(_get(db, actor, attachment_id))


@router.get("/{attachment_id}/file")
def download(attachment_id: uuid.UUID, actor: Actor = Depends(can_use), db: Session = Depends(get_db)):
    att = _get(db, actor, attachment_id)
    path = storage_path(att.sha256)
    if not path.exists():
        raise HTTPException(404, "The file is missing from storage (it may not have synced yet)")
    return FileResponse(path, media_type=att.mime, filename=att.original_name, content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})
