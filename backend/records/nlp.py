"""Plain-language entry: 'spent 450 on lunch yesterday' -> structured record suggestion.

Categories are learned from the workspace's own history (word -> category frequencies),
with built-in keyword defaults for new workspaces.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from records.models import Record

WORD = re.compile(r"[a-z]{3,}")
STOP = set("the and for with spent paid bought got received earned yesterday today ago days day from this that was rupees".split())
INCOME_WORDS = {"earned", "got", "received", "credited", "salary", "income", "bonus", "dividend", "dividends", "interest", "refund", "freelance", "payout"}
INCOME_CATS = {"Salary", "Freelance", "Bonus", "Interest", "Dividends"}
DEFAULTS = {
    "Dining": "lunch dinner breakfast restaurant cafe coffee food swiggy zomato pizza snack",
    "Groceries": "grocery groceries vegetables fruits milk supermarket bigbasket",
    "Transport": "uber ola cab taxi fuel petrol diesel metro bus auto train ride parking",
    "Rent": "rent", "Utilities": "electricity water gas bill recharge", "Salary": "salary payroll",
    "Freelance": "freelance client project invoice", "Shopping": "amazon flipkart clothes shirt shoes shopping",
    "Health": "doctor medicine pharmacy hospital medical", "Entertainment": "movie netflix concert game games",
    "Travel": "flight hotel trip ticket", "Subscriptions": "subscription prime spotify",
    "Education": "course book books tuition fees", "Gifts": "gift", "Bonus": "bonus",
    "Interest": "interest", "Dividends": "dividend dividends",
}
MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_date(text: str, today: date):
    t = text.lower()
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])), m.span()
        except ValueError:
            pass
    for word, delta in (("day before yesterday", 2), ("yesterday", 1), ("today", 0)):
        i = t.find(word)
        if i >= 0:
            return today - timedelta(days=delta), (i, i + len(word))
    m = re.search(r"\b(\d{1,2})\s+days?\s+ago\b", t)
    if m:
        return today - timedelta(days=int(m[1])), m.span()
    for pattern, day_first in ((rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{MONTH}\b", True), (rf"\b{MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", False)):
        m = re.search(pattern, t)
        if m:
            day, mon = (int(m[1]), MONTHS[m[2][:3]]) if day_first else (int(m[2]), MONTHS[m[1][:3]])
            try:
                found = date(today.year, mon, day)
            except ValueError:
                continue
            return (found if found <= today else date(today.year - 1, mon, day)), m.span()
    m = re.search(rf"\b(?:last\s+|on\s+)?({'|'.join(DAYS)})\b", t)
    if m:
        return today - timedelta(days=(today.weekday() - DAYS.index(m[1])) % 7 or 7), m.span()
    return today, None


def parse_amount(text: str):
    m = re.search(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?)?\b", text, re.I)
    if not m:
        return None
    value = Decimal(m[1].replace(",", ""))
    unit = (m[2] or "").lower()
    value *= 1000 if unit in ("k", "thousand") else 100000 if unit else 1
    return value.quantize(Decimal("0.01")) if value > 0 else None


def suggest_category(text: str, kind: str, workspace_id):
    tokens = set(WORD.findall(text.lower())) - STOP
    learned, ctype = defaultdict(Counter), defaultdict(Counter)
    for r in Record.all_objects.filter(workspace_id=workspace_id, is_deleted=False).order_by("-id").values("category", "note", "type")[:3000]:
        ctype[r["category"]][r["type"]] += 1
        for w in set(WORD.findall(f"{r['note']} {r['category']}".lower())) - STOP:
            learned[w][r["category"]] += 1

    def fits(cat):
        return not ctype.get(cat) or ctype[cat].most_common(1)[0][0] == kind

    for cat in ctype:  # the category is named in the sentence
        if fits(cat) and re.search(rf"\b{re.escape(cat.lower())}\b", text.lower()):
            return cat, "mention"
    score = Counter()
    for w in tokens & learned.keys():
        total = sum(learned[w].values())
        for cat, n in learned[w].items():
            if fits(cat):
                score[cat] += n / total
    if score:
        return score.most_common(1)[0][0], "learned"
    for cat, words in DEFAULTS.items():
        if (cat in INCOME_CATS) == (kind == "income") and tokens & set(words.split()):
            return cat, "keywords"
    return "", "none"


def parse_entry(text: str, workspace_id):
    when, span = parse_date(text, date.today())
    rest = text if span is None else text[: span[0]] + " " + text[span[1]:]
    amount = parse_amount(rest)
    if amount is None:
        raise ValidationError({"text": "Couldn't find an amount. Try: spent 450 on lunch yesterday"})
    kind = "income" if set(re.findall(r"[a-z]+", text.lower())) & INCOME_WORDS else "expense"
    category, source = suggest_category(text, kind, workspace_id)
    return {"amount": str(amount), "type": kind, "category": category, "date": when.isoformat(), "note": text.strip()[:200], "source": source}
