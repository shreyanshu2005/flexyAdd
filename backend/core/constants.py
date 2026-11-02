ADMIN = "ADMIN"
ANALYST = "ANALYST"
VIEWER = "VIEWER"

ROLE_CHOICES = (
    (ADMIN, "Admin"),
    (ANALYST, "Analyst"),
    (VIEWER, "Viewer"),
)

INCOME = "income"
EXPENSE = "expense"
TRANSACTION_TYPE_CHOICES = (
    (INCOME, "Income"),
    (EXPENSE, "Expense"),
)

# How a record counts towards income/expense analytics.
# "lent" / "repayment" move money between you and a friend, so they are kept out of
# income/expense totals and tracked in the per-friend ledger instead.
NORMAL = "normal"
LENT = "lent"
REPAYMENT = "repayment"
RECORD_KIND_CHOICES = (
    (NORMAL, "Normal"),
    (LENT, "Lent to a friend"),
    (REPAYMENT, "Repayment from a friend"),
)
FRIEND_KINDS = (LENT, REPAYMENT)
