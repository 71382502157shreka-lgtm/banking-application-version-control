"""
CLI Diagnostics Runner for BankVCS 2.0.

Runs database integrity checks, foreign key pragma audits, SHA-256 hash chain verification,
and environment diagnostics.
"""

import sys
import json
from app import create_app
from app.utils.diagnostics import run_full_system_diagnostic


def main():
    """App context wrapper to execute full system diagnostic suite."""
    app = create_app()
    with app.app_context():
        results = run_full_system_diagnostic()
        print("=" * 60)
        print("BANKVCS 2.0 SYSTEM DIAGNOSTIC REPORT")
        print("=" * 60)
        print(f"Overall System Status : {results['status']}")
        print(f"Database Integrity    : {'PASSED' if results['database']['passed_all'] else 'FAILED'}")
        print(f"Cryptographic Audit   : {'VERIFIED' if results['cryptographic_audit']['verified'] else 'COMPROMISED'}")
        print("-" * 60)
        print("TABLE ROW COUNTS:")
        for table, count in results['database']['table_row_counts'].items():
            print(f"  - {table:<22}: {count} rows")
        print("-" * 60)
        print("CRYPTOGRAPHIC AUDIT CHAIN:")
        print(f"  - Total audit records : {results['cryptographic_audit']['total_records']}")
        print(f"  - Broken hash links   : {len(results['cryptographic_audit']['broken_links'])}")
        print("-" * 60)
        print("ENVIRONMENT:")
        print(f"  - Python Executable   : {results['environment']['executable']}")
        print(f"  - Platform            : {results['environment']['platform']}")
        print("=" * 60)

        if not results['system_ok']:
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()
