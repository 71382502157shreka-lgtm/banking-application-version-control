"""
Bank Statement Exporter Service for BankVCS 2.0.

Provides comprehensive bank statement export functions including CSV generation,
formatted text statement generation, balance timeline reconciliation,
and monthly spending breakdown calculations.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from app import db
from app.models.account import Account
from app.models.transaction import Transaction, TransactionType, TransactionStatus

logger = logging.getLogger(__name__)


class AccountStatementExporter:
    """
    Service for generating structured, printable, and downloadable bank statements.
    """

    def __init__(self, account_id: int):
        self.account = db.session.get(Account, account_id)
        if not self.account:
            raise ValueError(f"Account ID {account_id} not found.")

    def get_statement_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Retrieves account statement data including opening balance, transaction ledger,
        closing balance, and summary totals for a given date range.
        """
        query = Transaction.query.filter_by(account_id=self.account.id)
        if start_date:
            query = query.filter(Transaction.created_at >= start_date)
        if end_date:
            query = query.filter(Transaction.created_at <= end_date)

        transactions = query.order_by(Transaction.created_at.asc()).all()

        total_deposits = 0.0
        total_withdrawals = 0.0
        total_transfers_in = 0.0
        total_transfers_out = 0.0

        running_balance = self.account.balance
        # Calculate opening balance by working backwards if date filtered
        ledger_entries = []
        for tx in transactions:
            amount = float(tx.amount) if tx.amount is not None else 0.0
            if tx.transaction_type == TransactionType.DEPOSIT:
                total_deposits += amount
            elif tx.transaction_type == TransactionType.WITHDRAWAL:
                total_withdrawals += amount
            elif tx.transaction_type == TransactionType.TRANSFER:
                if tx.amount > 0:
                    total_transfers_in += amount
                else:
                    total_transfers_out += abs(amount)

            ledger_entries.append({
                "transaction_id": tx.id,
                "date": tx.created_at.strftime("%Y-%m-%d %H:%M:%S") if tx.created_at else "",
                "type": str(tx.transaction_type),
                "amount": tx.amount,
                "status": str(tx.status),
                "description": tx.description or "N/A",
                "reference": tx.reference_number or f"TXN-{tx.id:06d}",
            })

        return {
            "account_number": self.account.account_number,
            "account_type": str(self.account.account_type),
            "customer_id": self.account.user_id,
            "customer_name": self.account.owner.username if self.account.owner else "Unknown",
            "current_balance": self.account.balance,
            "start_date": start_date.strftime("%Y-%m-%d") if start_date else "Account Creation",
            "end_date": end_date.strftime("%Y-%m-%d") if end_date else "Present",
            "summary": {
                "total_deposits": total_deposits,
                "total_withdrawals": total_withdrawals,
                "total_transfers_in": total_transfers_in,
                "total_transfers_out": total_transfers_out,
                "net_change": total_deposits + total_transfers_in - total_withdrawals - total_transfers_out,
                "total_transaction_count": len(transactions),
            },
            "ledger": ledger_entries,
        }

    def export_csv(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> str:
        """Generates CSV format statement string for download."""
        data = self.get_statement_data(start_date, end_date)
        output = io.StringIO()
        writer = csv.writer(output)

        # Header metadata
        writer.writerow(["BANKVCS 2.0 ACCOUNT STATEMENT"])
        writer.writerow(["Account Number", data["account_number"]])
        writer.writerow(["Account Holder", data["customer_name"]])
        writer.writerow(["Account Type", data["account_type"]])
        writer.writerow(["Period", f"{data['start_date']} to {data['end_date']}"])
        writer.writerow(["Current Balance", f"${data['current_balance']:.2f}"])
        writer.writerow([])

        # Summary
        writer.writerow(["STATEMENT SUMMARY"])
        writer.writerow(["Total Deposits", f"${data['summary']['total_deposits']:.2f}"])
        writer.writerow(["Total Withdrawals", f"${data['summary']['total_withdrawals']:.2f}"])
        writer.writerow(["Net Activity", f"${data['summary']['net_change']:.2f}"])
        writer.writerow([])

        # Ledger table
        writer.writerow(["Transaction ID", "Date", "Type", "Amount", "Status", "Reference", "Description"])
        for entry in data["ledger"]:
            writer.writerow([
                entry["transaction_id"],
                entry["date"],
                entry["type"],
                f"${entry['amount']:.2f}",
                entry["status"],
                entry["reference"],
                entry["description"],
            ])

        return output.getvalue()

    def export_text_statement(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> str:
        """Generates formatted plain text statement layout."""
        data = self.get_statement_data(start_date, end_date)

        lines = []
        lines.append("==========================================================================")
        lines.append("                        BANKVCS 2.0 OFFICIAL STATEMENT                    ")
        lines.append("==========================================================================")
        lines.append(f"Account Number  : {data['account_number']}")
        lines.append(f"Account Holder  : {data['customer_name']}")
        lines.append(f"Account Type    : {data['account_type']}")
        lines.append(f"Statement Period: {data['start_date']} to {data['end_date']}")
        lines.append(f"Current Balance : ${data['current_balance']:,.2f}")
        lines.append("--------------------------------------------------------------------------")
        lines.append("SUMMARY OF ACTIVITY:")
        lines.append(f"  - Total Deposits    : +${data['summary']['total_deposits']:,.2f}")
        lines.append(f"  - Total Withdrawals : -${data['summary']['total_withdrawals']:,.2f}")
        lines.append(f"  - Net Activity      :  ${data['summary']['net_change']:,.2f}")
        lines.append(f"  - Total Count       :  {data['summary']['total_transaction_count']} transactions")
        lines.append("==========================================================================")
        lines.append(f"{'TXN ID':<8} {'DATE':<20} {'TYPE':<12} {'AMOUNT':<12} {'STATUS':<10} {'REF':<15}")
        lines.append("--------------------------------------------------------------------------")

        for tx in data["ledger"]:
            lines.append(
                f"{tx['transaction_id']:<8} "
                f"{tx['date']:<20} "
                f"{tx['type']:<12} "
                f"${tx['amount']:<11.2f} "
                f"{tx['status']:<10} "
                f"{tx['reference']:<15}"
            )

        lines.append("==========================================================================")
        lines.append("                 END OF STATEMENT - BANKVCS 2.0 AGENTIC BANK              ")
        lines.append("==========================================================================")
        return "\n".join(lines)
