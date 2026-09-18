import base64
from datetime import datetime
from uuid import UUID


class InvalidCursor(ValueError):
    pass


def encode_cursor(created_at: datetime, item_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = raw.split("|")
        return datetime.fromisoformat(created_at_str), UUID(id_str)
    except (ValueError, TypeError) as exc:
        raise InvalidCursor("Cursor inválido") from exc
