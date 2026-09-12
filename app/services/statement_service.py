import csv
import io
from datetime import datetime
from app.models.transaction import Transaction, TransactionType, TransactionStatus


def generate_statement_data(account, start_date: datetime = None, end_date: datetime = None, transaction_type: str = None):
    query = Transaction.query.filter(
        (Transaction.account_id == account.id) | (Transaction.counterparty_account_id == account.id)
    )

    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
    if end_date:
        query = query.filter(Transaction.created_at <= end_date)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)

    transactions = query.order_by(Transaction.created_at.asc()).all()

    total_credits = 0.0
    total_debits = 0.0
    statement_rows = []

    for tx in transactions:
        is_credit = (tx.counterparty_account_id == account.id or tx.transaction_type == TransactionType.DEPOSIT)
        amt = float(tx.amount)
        if is_credit:
            total_credits += amt
            flow = "CREDIT"
        else:
            total_debits += amt
            flow = "DEBIT"

        statement_rows.append({
            "id": tx.id,
            "reference_number": tx.reference_number,
            "timestamp": tx.created_at.strftime("%Y-%m-%d %H:%M:%S") if tx.created_at else "",
            "type": tx.transaction_type,
            "flow": flow,
            "amount": amt,
            "fee": 0.0,
            "status": tx.status,
            "description": tx.description or "",
            "balance_after": float(tx.balance_after or 0.0),
        })

    opening_balance = float(account.balance) - total_credits + total_debits
    closing_balance = float(account.balance)

    return {
        "account_number": account.account_number,
        "account_type": account.account_type,
        "currency": "INR",
        "opening_balance": max(0.0, opening_balance),
        "total_credits": total_credits,
        "total_debits": total_debits,
        "closing_balance": closing_balance,
        "transactions": statement_rows,
    }


def export_statement_csv(statement_data: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BANKVCS 2.0 ACCOUNT STATEMENT"])
    writer.writerow(["Account Number", statement_data["account_number"]])
    writer.writerow(["Account Type", statement_data["account_type"]])
    writer.writerow(["Opening Balance", f"INR {statement_data['opening_balance']:.2f}"])
    writer.writerow(["Total Credits", f"INR {statement_data['total_credits']:.2f}"])
    writer.writerow(["Total Debits", f"INR {statement_data['total_debits']:.2f}"])
    writer.writerow(["Closing Balance", f"INR {statement_data['closing_balance']:.2f}"])
    writer.writerow([])
    writer.writerow(["Date & Time", "Reference No", "Type", "Flow", "Amount (INR)", "Fee", "Status", "Description"])

    for row in statement_data["transactions"]:
        writer.writerow([
            row["timestamp"],
            row["reference_number"],
            row["type"],
            row["flow"],
            f"{row['amount']:.2f}",
            f"{row['fee']:.2f}",
            row["status"],
            row["description"],
        ])

    return output.getvalue()
