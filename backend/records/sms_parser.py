"""Parse Indian bank UPI alert SMS into a structured transaction.

Written against the common HDFC / SBI / ICICI / Axis / Kotak alert styles. Bank templates
change over time, so anything that cannot be understood is *ignored* (never guessed):
the caller gets a reason and nothing is saved. Use the preview endpoint to check how a
real SMS from your bank is read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

MAX_SMS_CHARS = 2000


class SmsIgnored(Exception):
    """The message is not a UPI debit/credit alert we can safely turn into a record."""


@dataclass
class ParsedUpi:
    amount: Decimal
    direction: str  # "debit" (money out) or "credit" (money in)
    counterparty: str  # payee/payer UPI id when present, else their name; "" if unknown
    ref: str  # 12-digit UPI reference (RRN) when present
    when: date | None  # date printed in the SMS, if any


SKIP = re.compile(r"\b(otp|failed|declined|unsuccessful|will be debited|requested|collect request|mandate)\b", re.I)
UPI_MARK = re.compile(r"\bupi\b|\bvpa\b|@[a-z]{2,}", re.I)
DEBIT = re.compile(r"\b(?:debited|debit|sent|paid|withdrawn|spent)\b", re.I)
CREDIT = re.compile(r"\b(?:credited|credit|received|deposited|refund(?:ed)?)\b", re.I)
BALANCE = re.compile(r"\b(?:avl|available|clear|total)\.?\s*bal(?:ance)?\.?\s*[:\-]?\s*(?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d+)?", re.I)
AMOUNT_CCY = re.compile(r"(?<![a-z])(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
AMOUNT_KW = re.compile(r"\b(?:debited|credited)\s*(?:by|for|with)?\s*([\d,]+(?:\.\d{1,2})?)", re.I)
VPA = re.compile(r"\b([a-z0-9][a-z0-9._\-]{1,}@[a-z][a-z0-9]{1,})\b", re.I)
AXIS_NAME = re.compile(r"UPI/(?:P2A|P2M|P2P)/\d{9,14}/(.+?)(?=\s+SMS\b|\s+Not\b|\s+If\b|\s+-|/|$)", re.I)
ICICI_DEBIT_NAME = re.compile(r";\s*(.+?)\s+credited\b", re.I)
STOP = r"(?=\s+(?:on|ref\w*|upi|via|dated?|at|from|if|not|call|sms|avl|bal\w*|rrn|utr)\b|\s+\d|[.;,(]|$)"
NAME_TO = re.compile(r"\bto\s+(?:vpa\s+)?(.+?)" + STOP, re.I)
NAME_FROM = re.compile(r"\bfrom\s+(?:vpa\s+)?(.+?)" + STOP, re.I)
BAD_NAME = re.compile(r"\b(?:a/c|ac|acct|account|bank|your)\b|^\W|^\d", re.I)
REF_12 = re.compile(r"\b(\d{12})\b")
REF_LABELLED = re.compile(r"\b(?:ref(?:erence)?(?:\s*no\.?)?|refno|rrn|utr)\s*[:\-]?\s*(\d{8,14})\b", re.I)

MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_NUM = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2}|\d{4})\b")
DATE_MON = re.compile(r"\b(\d{1,2})[-/ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/ ]?(\d{2}|\d{4})\b", re.I)


def _year(y: str) -> int:
    return 2000 + int(y) if len(y) == 2 else int(y)


def _parse_date(text: str, today: date) -> date | None:
    candidates = []
    for m in DATE_ISO.finditer(text):
        candidates.append((int(m[1]), int(m[2]), int(m[3])))
    for m in DATE_NUM.finditer(text):  # Indian banks print day first: 02-11-26
        candidates.append((_year(m[3]), int(m[2]), int(m[1])))
    for m in DATE_MON.finditer(text):
        candidates.append((_year(m[3]), MONTHS[m[2][:3].lower()], int(m[1])))
    for y, mo, d in candidates:
        try:
            found = date(y, mo, d)
        except ValueError:
            continue
        if found <= today + timedelta(days=1):  # a date in the future means we misread something
            return found
    return None


def _amount(text: str) -> Decimal | None:
    cleaned = BALANCE.sub(" ", text)  # "Avl Bal Rs 12,000" must never be mistaken for the amount
    m = AMOUNT_CCY.search(cleaned) or AMOUNT_KW.search(cleaned)
    if not m:
        return None
    try:
        value = Decimal(m[1].replace(",", ""))
    except InvalidOperation:
        return None
    return value.quantize(Decimal("0.01")) if value > 0 else None


def _clean_name(raw: str) -> str:
    name = " ".join(raw.split()).strip(" .,:;-")
    if len(name) < 2 or len(name) > 60 or BAD_NAME.search(name):
        return ""
    return name.title() if name.isupper() else name


def _counterparty(text: str, direction: str) -> str:
    vpa = VPA.search(text)
    if vpa:  # a UPI id is the most stable identity for a person or merchant
        return vpa[1].lower()
    m = AXIS_NAME.search(text)
    if m and _clean_name(m[1]):
        return _clean_name(m[1])
    patterns = [NAME_TO, ICICI_DEBIT_NAME] if direction == "debit" else [NAME_FROM]
    for pattern in patterns:
        for m in pattern.finditer(text):
            name = _clean_name(m[1])
            if name:
                return name
    return ""


def parse_upi_sms(raw: str, today: date | None = None) -> ParsedUpi:
    text = " ".join((raw or "").split())
    if not text:
        raise SmsIgnored("Empty message.")
    if len(text) > MAX_SMS_CHARS:
        raise SmsIgnored("Message too long to be a bank alert.")
    if SKIP.search(text):
        raise SmsIgnored("Looks like an OTP, request or failed transaction, not a completed payment.")
    if not UPI_MARK.search(text):
        raise SmsIgnored("Not a UPI message.")

    d, c = DEBIT.search(text), CREDIT.search(text)
    if not d and not c:
        raise SmsIgnored("No debit or credit found.")
    # When both words appear (ICICI: "debited ...; RAHUL credited") the first one describes your account.
    direction = "debit" if d and (not c or d.start() < c.start()) else "credit"

    amount = _amount(text)
    if amount is None:
        raise SmsIgnored("Could not find the amount.")

    ref_match = REF_12.search(text) or REF_LABELLED.search(text)
    return ParsedUpi(
        amount=amount,
        direction=direction,
        counterparty=_counterparty(text, direction),
        ref=ref_match[1] if ref_match else "",
        when=_parse_date(text, today or date.today()),
    )
