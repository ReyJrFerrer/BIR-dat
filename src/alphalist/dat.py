"""Pinned byte serializer. Only validated snapshots can reach this writer."""

import csv
import hashlib
from decimal import Decimal

from .domain import ZERO, Snapshot

CONTROL_INDICES = (*range(12, 23), *range(25, 44), 48)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def serialize(snapshot: Snapshot) -> bytes:
    if not snapshot.valid:
        raise ValueError("Final export is blocked by unresolved issues.")
    context = snapshot.context
    lines = [f"H1604C,{context.tin},{context.branch},12/31/{context.year}"]
    details = []
    for sequence, record in enumerate(
        sorted(snapshot.records, key=lambda r: (r.name.upper(), r.employee_id)), 1
    ):
        if record.detail is None:
            raise ValueError("Missing normalized employee details.")
        fields = list(record.detail)
        fields[5] = str(sequence)
        if len(fields) != 49:
            raise ValueError("Profile requires exactly 49 D1 fields.")
        details.append(fields)
        lines.append(
            ",".join(f'"{v}"' if index in (8, 9, 10) else v for index, v in enumerate(fields))
        )
    controls = [f"{sum((Decimal(row[i]) for row in details), ZERO):.2f}" for i in CONTROL_INDICES]
    lines.append(
        ",".join(["C1", "1604C", context.tin, context.branch, f"12/31/{context.year}", *controls])
    )
    output = ("\r\n".join(lines) + "\r\n").encode("ascii")
    verify(output)
    return output


def verify(data: bytes) -> None:
    rows = list(csv.reader(data.decode("ascii").splitlines()))
    if (
        len(rows) < 3
        or len(rows[0]) != 4
        or rows[0][0] != "H1604C"
        or len(rows[-1]) != 36
        or rows[-1][0] != "C1"
    ):
        raise ValueError("Invalid header/control shape.")
    details = rows[1:-1]
    if any(len(row) != 49 or row[0] != "D1" for row in details):
        raise ValueError("Invalid detail shape.")
    for index, control in zip(CONTROL_INDICES, rows[-1][5:], strict=True):
        if sum((Decimal(row[index]) for row in details), ZERO) != Decimal(control):
            raise ValueError("Control total mismatch.")
    if not data.endswith(b"\r\n") or data.count(b"\n") != data.count(b"\r\n"):
        raise ValueError("CRLF required, including after the final record.")


def filename(snapshot: Snapshot) -> str:
    c = snapshot.context
    return f"{c.tin}{c.branch}1231{c.year}1604C.DAT"
