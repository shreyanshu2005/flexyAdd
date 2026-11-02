"""CSV export / import helpers for financial records."""
from __future__ import annotations

import csv
import io

from rest_framework.exceptions import ValidationError

from records.serializers import RecordWriteSerializer

HEADERS = ["date", "type", "category", "amount", "note"]
REQUIRED = ["date", "type", "category", "amount"]
MAX_ROWS = 1000
MAX_BYTES = 1_000_000
OPTIONAL = ["kind", "counterparty"]  # extra columns written by export, optional on import
FORMULA_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _escape(value) -> str:
    """Neutralise spreadsheet formula injection (=, +, -, @) in exported text."""
    text = str(value or "")
    return "'" + text if text[:1] in FORMULA_CHARS else text


def _unescape(text: str) -> str:
    return text[1:] if text[:1] == "'" and text[1:2] in FORMULA_CHARS else text


def export_csv(queryset) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS + ["created_by"] + OPTIONAL)
    for r in queryset.iterator():
        writer.writerow([r.date.isoformat(), r.type, _escape(r.category), r.amount, _escape(r.note), r.user.email, r.kind, _escape(r.counterparty)])
    return buffer.getvalue()


def parse_csv(text: str, request):
    """Validate every row. Returns (valid_rows, error_messages)."""
    if not text or not text.strip():
        raise ValidationError({"csv": "CSV is empty."})
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValidationError({"csv": "File too large (max 1 MB)."})
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    reader.fieldnames = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    missing = [h for h in REQUIRED if h not in reader.fieldnames]
    if missing:
        raise ValidationError({"csv": f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(HEADERS)}."})

    rows, errors = [], []
    for line, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue
        if len(rows) + len(errors) >= MAX_ROWS:
            raise ValidationError({"csv": f"Too many rows (max {MAX_ROWS})."})
        data = {k: _unescape((row.get(k) or "").strip()) for k in HEADERS}
        data["type"] = data["type"].lower()
        for extra in OPTIONAL:  # blank/missing means "use the default"
            value = _unescape((row.get(extra) or "").strip())
            if value:
                data[extra] = value.lower() if extra == "kind" else value
        serializer = RecordWriteSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            rows.append(serializer.validated_data)
        else:
            detail = "; ".join(f"{k}: {' '.join(map(str, v))}" for k, v in serializer.errors.items())
            errors.append(f"Row {line}: {detail}")
    return rows, errors
