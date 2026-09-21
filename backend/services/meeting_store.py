"""Local recovery copies for the existing Supabase-backed meeting workflow."""
import json
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


def path_for(file_id, name):
    # IDs originate from uuid4 on upload; never accept arbitrary filesystem paths.
    canonical = str(UUID(str(file_id)))
    root = Path(os.getenv("DATA_DIR", "data")).resolve()
    return root / canonical / name


def read_local(file_id, name):
    try:
        value = json.loads(path_for(file_id, name).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (ValueError, OSError):
        return None


def save_local(file_id, name, value):
    target = path_for(file_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(name + "." + uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def load_meeting(file_id, db=None):
    local = read_local(file_id, "transcript.json")
    if db is not None:
        try:
            row = db.table("meetings").select("id,filename,duration_sec,language,transcript,uploaded_at").eq("id", file_id).single().execute().data
            if row:
                segments = (local or {}).get("segments", [])
                try:
                    rows = db.table("transcript_segments").select("start_sec,end_sec,text").eq("meeting_id", file_id).order("start_sec").execute().data or []
                    if rows and not segments:
                        segments = [{"start": s["start_sec"], "end": s["end_sec"], "text": s["text"]} for s in rows]
                except Exception:
                    logger.warning("Segment lookup unavailable; retaining cached segments.")
                return {"file_id": file_id, "filename": row.get("filename"), "duration": row.get("duration_sec"),
                        "language": row.get("language"), "full_text": row.get("transcript") or "",
                        "uploaded_at": row.get("uploaded_at"), "segments": segments}
        except Exception:
            logger.warning("Meeting lookup unavailable; using local recovery copy.")
    return local


def list_local_meetings():
    root = Path(os.getenv("DATA_DIR", "data")).resolve()
    meetings = []
    for path in root.glob("*/transcript.json"):
        value = read_local(path.parent.name, "transcript.json")
        if value:
            meetings.append({"id": path.parent.name, "filename": value.get("filename") or "Recording",
                             "duration": value.get("duration"), "language": value.get("language"),
                             "uploaded_at": value.get("uploaded_at"), "status": "done"})
    return sorted(meetings, key=lambda m: m.get("uploaded_at") or "", reverse=True)
