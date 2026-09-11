"""
Server-side Python statement generation and financial transaction filtering service.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional
import io
import csv

from app import db
from app.models.transaction import Transaction
from app.models.account import Account


def generate_account_statement(account_id: int, start_date: Optional[date] = None,
                                end_date: Optional[date] = None,
                                transaction_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate server-side financial statement summary and transaction list for an account.
    """
    account = db.session.get(Account, account_id)
    if not account:
        return {"success": False, "error": "Account not found"}

    query = Transaction.query.filter_by(account_id=account_id)

    if start_date:
        query = query.filter(Transaction.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(Transaction.created_at <= datetime.combine(end_date, datetime.max.time()))
    if transaction_type and transaction_type != "ALL":
        query = query.filter_by(transaction_type=transaction_type)

    transactions = query.order_by(Transaction.created_at.desc()).all()

    total_deposits = sum(t.amount for t in transactions if t.transaction_type in ["DEPOSIT", "REVERSAL"])
    total_withdrawals = sum(t.amount for t in transactions if t.transaction_type in ["WITHDRAWAL", "TRANSFER"])

    return {
        "success": True,
        "account_number": account.account_number,
        "account_type": account.account_type,
        "current_balance": account.balance,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "transaction_count": len(transactions),
        "transactions": transactions,
    }


def export_statement_csv(account_id: int, start_date: Optional[date] = None,
                         end_date: Optional[date] = None,
                         transaction_type: Optional[str] = None) -> str:
    """
    Generate CSV formatted string server-side for account statements.
    """
    statement = generate_account_statement(account_id, start_date, end_date, transaction_type)
    if not statement.get("success"):
        return ""

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference Number", "Date", "Type", "Amount", "Balance After", "Status", "Description"])

    for tx in statement["transactions"]:
        writer.writerow([
            tx.reference_number,
            tx.created_at.strftime("%Y-%m-%d %H:%M:%S") if tx.created_at else "",
            tx.transaction_type,
            f"{tx.amount:.2f}",
            f"{tx.balance_after:.2f}",
            tx.status,
            tx.description or ""
        ])

    return output.getvalue()
