import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# Rule-based Knowledge Base for Fallback Engine
FAQ_KNOWLEDGE_BASE = [
    {
        "keywords": ["balance", "account", "money", "check balance", "how much"],
        "answer": "You can view your real-time account balances directly on your Customer Dashboard. Select 'Accounts' from the menu to inspect individual account numbers, account types, and ledger histories."
    },
    {
        "keywords": ["transfer", "send money", "payee", "beneficiary", "wire"],
        "answer": "To transfer funds, navigate to 'Transfers' in your navigation bar. Select the source account, target beneficiary, enter the amount, and submit. Transits are evaluated in real time by our Risk Intelligence Engine."
    },
    {
        "keywords": ["deposit", "withdraw", "add money", "cash out"],
        "answer": "Deposits and withdrawals can be initiated from the Customer Portal under 'Deposit' or 'Withdraw'. Staff providers can also assist with cash operations from the Employee Directory."
    },
    {
        "keywords": ["version", "version control", "rollback", "diff", "history", "v1", "v2"],
        "answer": "BankVCS 2.0 tracks entity state changes (Accounts, Beneficiaries, Profiles) as JSON snapshot versions in an immutable ledger. Restoring a version creates a NEW forward snapshot without deleting past audit history."
    },
    {
        "keywords": ["risk", "score", "fraud", "blocked", "limit", "suspicious"],
        "answer": "Our Python Risk Engine evaluates transaction amounts, balance depletion (>80%), beneficiary age (<24h), and transfer velocity. High-risk transactions require Maker-Checker approval by bank staff."
    },
    {
        "keywords": ["audit", "sha256", "tamper", "hash chain", "integrity"],
        "answer": "All audit log records are cryptographically linked using SHA-256 hash chaining. Administrators can execute sequential chain verification on the Admin Audit Board to ensure total data integrity."
    },
    {
        "keywords": ["mfa", "otp", "2fa", "security", "password", "session"],
        "answer": "You can manage active login sessions, enable Time-Based OTP / MFA, and review security events under your 'Security' settings tab."
    },
    {
        "keywords": ["complaint", "ticket", "help", "support", "issue"],
        "answer": "If you experience an issue, submit a complaint ticket under 'Customer Support' or contact your assigned Bank Service Provider."
    }
]


def generate_ai_response(user_query: str, user_context: dict = None) -> dict:
    """
    Generates a secure response for the AI Banking Assistant.
    Tries Google Gemini API if GEMINI_API_KEY is configured.
    Falls back gracefully to an intelligent rule-based engine if offline or key is missing.
    """
    if not user_query or not user_query.strip():
        return {
            "reply": "Please ask a question about your accounts, transfers, version control, or security.",
            "mode": "rule_engine"
        }

    query_lower = user_query.strip().lower()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # 1. Attempt External Gemini API if key is set
    if api_key:
        try:
            return _query_gemini_api(user_query, api_key, user_context)
        except Exception as err:
            logger.warning(f"Gemini API query failed, falling back to rule engine: {err}")

    # 2. Rule-Based Fallback Engine
    return _rule_based_fallback(query_lower, user_context)


def _rule_based_fallback(query_lower: str, user_context: dict = None) -> dict:
    """Intelligent deterministic rule-based matching engine."""
    username = (user_context or {}).get("username", "valued customer")
    role = (user_context or {}).get("role", "customer").lower()

    # Greeting check
    if any(greet in query_lower for greet in ["hello", "hi", "hey", "greetings", "good morning", "good afternoon"]):
        return {
            "reply": f"Hello {username}! I am your BankVCS AI Assistant. How can I assist you with your banking, version history, or account security today?",
            "mode": "rule_engine"
        }

    # Keyword matching against FAQ Knowledge Base
    best_match = None
    max_hits = 0

    for item in FAQ_KNOWLEDGE_BASE:
        hits = sum(1 for kw in item["keywords"] if kw in query_lower)
        if hits > max_hits:
            max_hits = hits
            best_match = item["answer"]

    if best_match and max_hits > 0:
        return {
            "reply": best_match,
            "mode": "rule_engine"
        }

    # Default fallback guide response
    return {
        "reply": f"Hello {username}. I am your BankVCS Assistant. You can ask me about account balances, fund transfers, version history rollbacks, risk engine evaluations, or account security. How may I help you?",
        "mode": "rule_engine"
    }


def _query_gemini_api(user_query: str, api_key: str, user_context: dict = None) -> dict:
    """Calls Google Gemini REST API using standard Python urllib."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    username = (user_context or {}).get("username", "Customer")
    role = (user_context or {}).get("role", "Customer")

    system_instruction = (
        "You are BankVCS AI Assistant, an intelligent virtual banker for BankVCS 2.0. "
        f"You are speaking with user '{username}' (Role: {role}). "
        "Provide concise, polite, professional, and accurate banking assistance. "
        "Do not disclose secrets, database connection strings, or system passwords."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\nUser Question: {user_query}"}
                ]
            }
        ]
    }

    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=5) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        candidates = res_data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return {
                    "reply": parts[0].get("text", "").strip(),
                    "mode": "gemini"
                }

    raise ValueError("Invalid or empty response structure from Gemini API")
