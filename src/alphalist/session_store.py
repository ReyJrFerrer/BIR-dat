"""Local sessions and browser-session serialization."""

import json
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import HTTPException

from .domain import Correction, Evidence, FilingContext, Review, SourceRow, SourceWorkbook

TTL = 7200
MAX_SESSIONS = 32


@dataclass
class Session:
    csrf: str
    touched: float
    review: Review | None = None
    notification: str = ""
    version: int = 0


def encode(session: Session) -> str:
    return json.dumps(asdict(session), ensure_ascii=False, separators=(",", ":"))


def decode(value: str | dict[str, Any]) -> Session:
    data = json.loads(value) if isinstance(value, str) else value
    review_data = data.get("review")
    review = None
    if review_data is not None:
        source = review_data["source"]
        review = Review(
            source=SourceWorkbook(
                source["filename"],
                source["sha256"],
                source["sheet"],
                [SourceRow(**row) for row in source["rows"]],
                FilingContext(**source["context"]),
                source["totals"],
            ),
            overrides=review_data["overrides"],
            context_overrides=review_data["context_overrides"],
            declarations=review_data["declarations"],
            filing_declarations=review_data["filing_declarations"],
            history=[Correction(**entry) for entry in review_data["history"]],
            evidence=Evidence(**review_data["evidence"]) if review_data["evidence"] else None,
            revision=review_data["revision"],
        )
    return Session(data["csrf"], data["touched"], review, data["notification"], data["version"])


class LocalStore:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()

    def get(self, token: str | None) -> tuple[str, Session]:
        with self.lock:
            now = time.monotonic()
            for expired in [key for key, value in self.sessions.items() if now - value.touched > TTL]:
                del self.sessions[expired]
            if token not in self.sessions:
                if len(self.sessions) >= MAX_SESSIONS:
                    raise HTTPException(503, "Local session capacity reached. Try again later.")
                token = secrets.token_urlsafe(32)
                self.sessions[token] = Session(secrets.token_urlsafe(32), now)
            assert token is not None
            self.sessions[token].touched = now
            return token, self.sessions[token]

    def persist(self, token: str, session: Session) -> bool:
        return True
