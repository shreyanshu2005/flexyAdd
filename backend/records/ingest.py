"""Turn a forwarded bank SMS into a Record (or explain why it was skipped)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from core.constants import ADMIN, EXPENSE, FRIEND_KINDS, INCOME, LENT, NORMAL, REPAYMENT
from records.models import IngestKey, Record
from records.nlp import suggest_category
from records.services import RecordService
from records.sms_parser import ParsedUpi, SmsIgnored, parse_upi_sms

FRIENDS_CATEGORY = "Friends"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def today_local() -> date:
    """'Today' where the user lives (India has no DST, so a fixed offset is exact)."""
    offset = timedelta(minutes=getattr(settings, "INGEST_UTC_OFFSET_MINUTES", 330))
    return datetime.now(dt_timezone.utc).astimezone(dt_timezone(offset)).date()


class IngestKeyService:
    @staticmethod
    def rotate(user) -> str:
        """Replace the workspace's key. The plaintext is returned once and never stored."""
        raw = "fin_" + secrets.token_urlsafe(32)
        IngestKey.objects.filter(workspace_id=user.workspace_id).delete()
        IngestKey.objects.create(workspace_id=user.workspace_id, user=user, key_hash=_hash(raw), prefix=raw[:8])
        return raw

    @staticmethod
    def authenticate(raw: str | None) -> IngestKey | None:
        if not raw:
            return None
        key = IngestKey.objects.select_related("user").filter(key_hash=_hash(raw.strip())).first()
        if key:
            IngestKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key


def describe(parsed: ParsedUpi, when: date) -> dict:
    return {
        "type": EXPENSE if parsed.direction == "debit" else INCOME,
        "amount": str(parsed.amount),
        "counterparty": parsed.counterparty,
        "upi_ref": parsed.ref,
        "date": when.isoformat(),
    }


def ingest_sms(key: IngestKey, text: str, received_on: date | None = None) -> tuple[str, dict]:
    """Returns (status, payload) where status is created | duplicate | ignored."""
    user = key.user
    if not (user.is_active and user.role == ADMIN and user.workspace_id == key.workspace_id):
        raise PermissionDenied("The user who created this key is no longer an active admin.")
    ws = key.workspace_id

    try:
        parsed = parse_upi_sms(text, today_local())
    except SmsIgnored as exc:
        return "ignored", {"reason": str(exc)}

    # Real UPI reference when the bank prints one; otherwise a fingerprint of the SMS so a
    # forwarder retry can never create the same record twice.
    ref = parsed.ref or "sms-" + hashlib.sha1(" ".join(text.split()).encode()).hexdigest()[:20]
    existing = Record.all_objects.filter(workspace_id=ws, upi_ref=ref).values_list("id", flat=True).first()
    if existing:
        return "duplicate", {"id": existing}

    kind_type = EXPENSE if parsed.direction == "debit" else INCOME
    # Someone you have already marked as a friend is classified automatically from now on.
    is_friend = bool(parsed.counterparty) and Record.all_objects.filter(
        workspace_id=ws, counterparty__iexact=parsed.counterparty, is_deleted=False, kind__in=FRIEND_KINDS
    ).exists()
    if is_friend:
        kind, category = (LENT if kind_type == EXPENSE else REPAYMENT), FRIENDS_CATEGORY
    else:
        kind = NORMAL
        category = suggest_category(parsed.counterparty or "upi payment", kind_type, ws)[0] or "Uncategorized"

    verb = "to" if parsed.direction == "debit" else "from"
    note = f"UPI {verb} {parsed.counterparty}" if parsed.counterparty else "UPI payment"
    data = {
        "amount": parsed.amount, "type": kind_type, "category": category,
        "date": parsed.when or received_on or today_local(), "note": note,
        "kind": kind, "counterparty": parsed.counterparty, "upi_ref": ref,
    }
    try:
        record = RecordService.create_record(user, data)
    except IntegrityError:  # two identical requests raced; the unique constraint caught the second
        return "duplicate", {}
    return "created", {"record": record}
