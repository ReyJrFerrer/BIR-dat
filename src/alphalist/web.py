"""Local browser interface with isolated, expiring in-memory reviews."""

import copy
import json
import secrets
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData, UploadFile
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .conversion import SUMMARY_FIELDS, build_snapshot, effective_declarations
from .dat import digest, filename, serialize
from .domain import Evidence, Review
from .pdf import display, render
from .presentation import (
    ANSWER_LABELS,
    FIELD_GROUPS,
    QUESTION_HELP,
    data_tasks,
    question_options,
    workspace_state,
)
from .review import audit, correct, load_reference
from .workbook import HEADERS, MAX_UPLOAD, read_workbook

PACKAGE = Path(__file__).parent
TTL = 7200
MAX_SESSIONS = 32


@dataclass
class Session:
    csrf: str
    touched: float
    review: Review | None = None
    notification: str = ""


class Store:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()

    def get(self, token: str | None) -> tuple[str, Session]:
        with self.lock:
            now = time.monotonic()
            for expired in [k for k, v in self.sessions.items() if now - v.touched > TTL]:
                del self.sessions[expired]
            if token not in self.sessions:
                if len(self.sessions) >= MAX_SESSIONS:
                    raise HTTPException(503, "Local session capacity reached. Try again later.")
                token = secrets.token_urlsafe(32)
                self.sessions[token] = Session(secrets.token_urlsafe(32), now)
            assert token is not None
            self.sessions[token].touched = now
            return token, self.sessions[token]


store = Store()
app = FastAPI(title="Alphalist review", docs_url=None, redoc_url=None)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
)
app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE / "templates")
templates.env.filters["amount"] = display


@app.middleware("http")
async def session_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method == "POST":
        length = request.headers.get("content-length", "")
        if not length.isdigit() or int(length) > MAX_UPLOAD + 200_000:
            return JSONResponse(
                {"detail": "Request must declare a size below 10 MB."}, status_code=413
            )
    token, session = store.get(request.cookies.get("alphalist_session"))
    request.state.session = session
    response = await call_next(request)
    response.set_cookie("alphalist_session", token, httponly=True, samesite="strict", max_age=TTL)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.exception_handler(ValueError)
async def invalid_input(request: Request, exc: ValueError) -> HTMLResponse:
    return templates.TemplateResponse(request, "error.html", {"message": str(exc)}, status_code=400)


async def checked_form(request: Request) -> FormData:
    form = await request.form(max_files=1, max_fields=100, max_part_size=MAX_UPLOAD)
    if not secrets.compare_digest(str(form.get("csrf", "")), request.state.session.csrf):
        raise HTTPException(403, "Session token is invalid. Reload the page and try again.")
    return form


def current(request: Request) -> Review:
    with store.lock:
        review = request.state.session.review
        if review is None:
            raise HTTPException(404, "No active review. Import a workbook first.")
        return copy.deepcopy(review)


def save(request: Request, review: Review, revision: str) -> None:
    with store.lock:
        existing = request.state.session.review
        if existing is None or str(existing.revision) != revision:
            raise HTTPException(409, "This review changed in another tab. Reload before saving.")
        request.state.session.review = review


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> Response:
    review = request.state.session.review
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "csrf": request.state.session.csrf,
            "active": review is not None,
            "workspace": workspace_state(build_snapshot(review)) if review else None,
        },
    )


@app.post("/reference/{kind}")
async def reference(request: Request, kind: str) -> Response:
    await checked_form(request)
    review = load_reference(kind)
    with store.lock:
        request.state.session.review = review
        request.state.session.notification = (
            f"Workbook prepared. {len(review.source.rows)} employees imported."
        )
    return RedirectResponse("/review", status_code=303)


@app.post("/upload")
async def upload(request: Request) -> Response:
    form = await checked_form(request)
    file = form.get("workbook")
    if not isinstance(file, UploadFile):
        raise ValueError("Select a workbook.")
    try:
        data = await file.read(MAX_UPLOAD + 1)
        review = Review(read_workbook(data, Path(file.filename or "").name))
    except ValueError as exc:
        if request.headers.get("accept") == "application/json":
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "csrf": request.state.session.csrf,
                "active": request.state.session.review is not None,
                "error": str(exc),
                "failed_filename": file.filename,
            },
            status_code=400,
        )
    finally:
        await file.close()
    with store.lock:
        request.state.session.review = review
        request.state.session.notification = (
            f"Workbook prepared. {len(review.source.rows)} employees imported."
        )
    if request.headers.get("accept") == "application/json":
        return JSONResponse({"redirect": "/review"})
    return RedirectResponse("/review", status_code=303)


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request) -> Response:
    review = current(request)
    snapshot = build_snapshot(review)
    originals = build_snapshot(Review(review.source))
    notification = request.state.session.notification
    request.state.session.notification = ""
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "csrf": request.state.session.csrf,
            "review": review,
            "snapshot": snapshot,
            "workspace": workspace_state(snapshot),
            "notification": notification,
            "summary_fields": SUMMARY_FIELDS,
            "originals": originals,
            "headers": HEADERS,
            "row_names": {r.key: r.name for r in snapshot.records},
        },
    )


@app.get("/employee/{key}", response_class=HTMLResponse)
def employee_page(request: Request, key: str) -> Response:
    review = current(request)
    row = next((row for row in review.source.rows if row.key == key), None)
    if row is None:
        raise HTTPException(404)
    snapshot = build_snapshot(review)
    tasks = data_tasks(snapshot, key)
    correction_fields = {item.issues[0].field for item in tasks} | {"V"}
    employee_issues = [i for i in snapshot.issues if i.row_key == key and i.severity == "error"]
    return templates.TemplateResponse(
        request,
        "employee.html",
        {
            "csrf": request.state.session.csrf,
            "review": review,
            "snapshot": snapshot,
            "workspace": workspace_state(snapshot),
            "fragment": request.query_params.get("fragment") == "1",
            "row": row,
            "values": row.values | review.overrides.get(key, {}),
            "headers": HEADERS,
            "declarations": question_options(),
            "answer_labels": ANSWER_LABELS,
            "question_help": QUESTION_HELP,
            "effective": effective_declarations(review, row),
            "tasks": tasks,
            "correction_fields": correction_fields,
            "field_groups": FIELD_GROUPS,
            "required_questions": {
                i.field for i in employee_issues if i.field in question_options()
            },
            "profile_issues": [
                i
                for i in snapshot.issues
                if i.row_key == key and i.category == "profile" and i.severity == "error"
            ],
            "answers": review.declarations.get(key, {}),
            "issues": employee_issues,
        },
    )


@app.post("/correct/{scope}")
async def correction(request: Request, scope: str) -> Response:
    form = await checked_form(request)
    review = current(request)
    history_length = len(review.history)
    changes = {
        key.removeprefix("value_"): str(value)
        for key, value in form.items()
        if key.startswith("value_")
    }
    if "employee_tin" in form:
        changes["V"] = (
            str(form["employee_tin"]).strip() + str(form.get("employee_branch", "")).strip()
        )
    try:
        correct(review, scope, changes, str(form.get("reason", "")))
        snapshot = build_snapshot(review)
    except ValueError as exc:
        if request.headers.get("accept") == "application/json":
            return JSONResponse({"detail": str(exc)}, status_code=400)
        raise
    save(request, review, str(form.get("revision", "")))
    state = workspace_state(snapshot)
    completion = "Changes saved." if len(review.history) > history_length else "Review checked."
    request.state.session.notification = (
        f"{completion} Your files are ready to export."
        if snapshot.valid
        else f"{completion} {state['count']} field{'s' if state['count'] != 1 else ''} left to complete."
    )
    row_key = "" if scope == "context" else scope
    remaining = [i for i in snapshot.issues if i.severity == "error" and i.row_key == row_key]
    destination = "/review"
    if remaining:
        destination += "" if scope == "context" else f"?employee={scope}"
        destination += f"#field-{remaining[0].field}"
    if request.headers.get("accept") == "application/json":
        return JSONResponse({"redirect": destination})
    return RedirectResponse(destination, status_code=303)


@app.post("/evidence")
async def evidence(request: Request) -> Response:
    form = await checked_form(request)
    review = current(request)
    snapshot = build_snapshot(review)
    if not snapshot.valid:
        raise ValueError(
            "Resolve final-export blockers before attaching evidence to a generated DAT."
        )
    output_hash = digest(serialize(snapshot))
    if str(form.get("dat_hash", "")).strip() != output_hash:
        raise ValueError("The tested DAT hash does not match the current output.")
    if form.get("attest") != "yes" or not str(form.get("version", "")).strip():
        raise ValueError(
            "Supply the validator version and confirm this is the log for the exact tested DAT."
        )
    file = form.get("log")
    if not isinstance(file, UploadFile):
        raise ValueError("Attach the actual validator TXT log.")
    try:
        data = await file.read(200_001)
        if len(data) > 200_000:
            raise ValueError("Validator log must be smaller than 200 KB.")
        try:
            log = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Use an ASCII or UTF-8 validator text log.") from exc
        if "No Errors Encountered" not in log or snapshot.context.tin not in log.replace("-", ""):
            raise ValueError(
                "Log does not contain a successful result for this employer. Review it in the official application."
            )
    finally:
        await file.close()
    review.evidence = Evidence(
        output_hash,
        digest(data),
        str(form["version"])[:100],
        log,
        "User-attached; association attested by uploader, not independently authenticated",
    )
    review.revision += 1
    save(request, review, str(form.get("revision", "")))
    return RedirectResponse("/review#evidence", status_code=303)


@app.get("/download/{kind}")
def download(request: Request, kind: str) -> Response:
    review = current(request)
    snapshot = build_snapshot(review)
    if kind == "dat":
        content, media, name = serialize(snapshot), "application/octet-stream", filename(snapshot)
    elif kind in ("pdf", "draft"):
        content, media, name = (
            render(snapshot, draft=kind == "draft"),
            "application/pdf",
            f"alphalist-{kind}.pdf",
        )
    elif kind == "audit":
        content = json.dumps(audit(review), ensure_ascii=False, indent=2).encode("utf-8")
        media, name = "application/json", "alphalist-review.json"
    elif kind == "log" and review.evidence:
        content, media, name = (
            review.evidence.text.encode("utf-8"),
            "text/plain",
            "attached-validator-evidence.txt",
        )
    else:
        raise HTTPException(404)
    return Response(
        content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@app.post("/clear")
async def clear(request: Request) -> Response:
    await checked_form(request)
    with store.lock:
        request.state.session.review = None
    return RedirectResponse("/", status_code=303)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
