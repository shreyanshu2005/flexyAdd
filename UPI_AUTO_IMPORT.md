# UPI auto-import

Your Android phone forwards each bank SMS to this app. UPI payments you make and money you
receive are added as records automatically, and money lent to friends is tracked separately
in a per-friend ledger.

## How it works

```
Bank SMS -> MacroDroid/Tasker on your phone -> POST /api/records/ingest/sms/ -> Record
```

- The SMS is parsed for amount, debit/credit, the other person (UPI id or name), the 12-digit
  UPI reference and the date. **The SMS text itself is not stored.**
- OTPs, failed payments, mandates, non-UPI messages and anything not understood are ignored
  (the endpoint answers `200 {"status":"ignored","reason":...}`), so you can forward every
  message from your bank without filtering.
- The UPI reference is unique per workspace, so the same payment is never imported twice
  (retries are safe, and a record you deleted does not come back).

## Setup

1. Log in as an **admin** and open the **UPI sync** tab. Click **Create key** and copy it
   (shown once; Replace key revokes the old one immediately).
2. In the same tab, paste a real bank SMS under **Test an SMS** to see exactly how it will be
   read. Nothing is saved by the test.
3. On the phone (needs your deployed URL, not localhost):
   - **MacroDroid:** trigger *SMS Received* (sender = your bank, e.g. contains `HDFCBK`) ->
     action *HTTP Request*, POST.
   - **Tasker:** event *Received Text* -> action *HTTP Request*, POST.
   - URL `https://<your-app>/api/records/ingest/sms/`
   - Headers `X-Ingest-Key: <key>` and `Content-Type: text/plain`
   - Body: the SMS text (`[sms_message]` in MacroDroid, `%SMSRB` in Tasker).
   - Allow SMS permission and disable battery optimisation for the app.

Test from a computer:

```bash
curl -X POST https://<your-app>/api/records/ingest/sms/ \
  -H "X-Ingest-Key: <key>" -H "Content-Type: text/plain" \
  --data-binary "Sent Rs.250.00 from Kotak Bank AC X1234 to swiggy@okicici on 02-11-26.UPI Ref 312345678901"
```

JSON (`{"message": "...", "received_at": "2026-11-02T14:30:00"}`) and form posts also work.

## Friends who pay you back

Records have a **kind**: `normal`, `lent` (you paid for a friend) or `repayment` (they paid you
back). Lent and repayment records are excluded from income, expenses, trends and budgets,
and are tracked in the **Friends** card on the dashboard: *lent - repaid = balance* per person
(positive: they owe you, negative: you owe them).

1. The first payment to or from someone arrives as a normal record. Click **Friend** on that row.
2. From then on, payments to that person are recorded as `lent` and payments from them as
   `repayment` automatically. Partial repayments just reduce the balance.

Friends are matched by the name or UPI id the bank prints. Some banks print a name on debits
and a UPI id on credits for the same person; if you see two entries for one friend, edit the
"Friend or UPI id" field on the records so they match.

## Limits to know about

- Android only (iOS does not let apps read SMS).
- Bank SMS formats change. The parser covers common HDFC, SBI, ICICI, Axis and Kotak styles;
  if your bank's SMS is ignored or misread, use the test box and share the (redacted) text so
  the parser can be extended.
- Categories for new payees are guessed from the payee name and your history; unknown ones are
  "Uncategorized" until you edit them (later payments to the same payee then follow your edit).
- Dates come from the SMS; if missing, the date it was received (India time) is used.

## Security

- The key is stored hashed; the plaintext is shown once. Anyone holding it can add records to
  your workspace, but cannot read anything. Revoke it from the UPI sync tab at any time.
- The key stops working if the admin who created it is deactivated or demoted.
- Always use the https URL.

## API summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/records/ingest/sms/` | `X-Ingest-Key` | Import one SMS |
| POST | `/api/records/ingest/preview/` | admin JWT | Dry-run parse |
| GET/POST/DELETE | `/api/records/ingest/key/` | admin JWT | Key status / create or replace / revoke |
| GET | `/api/dashboard/friends/` | any role | Friend balances (also in `/summary/` as `friends`) |
