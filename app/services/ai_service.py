import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 500
ADVISORY_TRANSACTION_MSG = "I can provide guidance, but I cannot directly perform banking transactions. Please use the official banking portal."
SENSITIVE_DATA_BLOCKED_MSG = "I cannot disclose system configuration, security credentials, or sensitive administrative data."

# Rule-based Knowledge Base for Fallback Engine
FAQ_KNOWLEDGE_BASE = [
    {
        "keywords": ["balance", "account balance", "my balance", "check balance", "how much money"],
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

TRANSACTION_ACTION_KEYWORDS = [
    "transfer rupees", "transfer rs", "send rs", "send $", "transfer $",
    "deposit $", "deposit rs", "withdraw rs", "withdraw $",
    "send money to", "transfer money to", "pay rupees", "pay rs",
    "change password to", "reset password", "delete user", "update balance"
]

SENSITIVE_PROMPT_KEYWORDS = [
    "system prompt", "database password", "secret key", "api key",
    "admin password", "conn string", "connection string", "dump database",
    "show password", "show secret"
]


def generate_ai_response(user_query: str, user_context: dict = None) -> dict:
    """
    Generates a secure, advisory response for the AI Banking Assistant.
    Validates message lengths, detects transaction requests & sensitive prompts,
    and uses external Gemini API if configured or rule-based fallback NLP engine.
    """
    if user_query is None:
        return {
            "reply": "Please ask a question about your accounts, transfers, version control, or security.",
            "mode": "rule_engine"
        }

    query_str = str(user_query).strip()

    if not query_str:
        return {
            "reply": "Please ask a question about your accounts, transfers, version control, or security.",
            "mode": "rule_engine"
        }

    if len(query_str) > MAX_MESSAGE_LENGTH:
        return {
            "reply": f"Message exceeds maximum allowed length of {MAX_MESSAGE_LENGTH} characters. Please shorten your question.",
            "mode": "rule_engine"
        }

    query_lower = query_str.lower()

    # 1. Action / Transaction Request Guard (Advisory Enforcement)
    if any(kw in query_lower for kw in TRANSACTION_ACTION_KEYWORDS):
        return {
            "reply": ADVISORY_TRANSACTION_MSG,
            "mode": "rule_engine"
        }

    # 2. Sensitive Data Extraction Guard
    if any(kw in query_lower for kw in SENSITIVE_PROMPT_KEYWORDS):
        return {
            "reply": SENSITIVE_DATA_BLOCKED_MSG,
            "mode": "rule_engine"
        }

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # 3. Attempt External Gemini API if key is set
    if api_key:
        try:
            return _query_gemini_api(query_str, api_key, user_context)
        except Exception as err:
            logger.warning(f"Gemini API query failed, falling back to rule engine: {err}")

    # 4. Rule-Based Fallback Engine
    return _rule_based_fallback(query_lower, user_context)


def _rule_based_fallback(query_lower: str, user_context: dict = None) -> dict:
    """Intelligent deterministic rule-based matching engine."""
    username = (user_context or {}).get("username", "valued customer")

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
    """Calls Google Gemini REST API using standard Python urllib with timeout."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    username = (user_context or {}).get("username", "Customer")
    role = (user_context or {}).get("role", "Customer")

    system_instruction = (
        "You are BankVCS AI Assistant, an intelligent virtual banker for BankVCS 2.0. "
        f"You are speaking with user '{username}' (Role: {role}). "
        "Provide concise, polite, professional, and accurate banking assistance. "
        "You are advisory only and cannot directly execute transactions or modify accounts. "
        "Do not disclose secrets, database credentials, or system passwords."
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
                reply_text = parts[0].get("text", "").strip()
                # Sanitize reply text against sensitive patterns
                if any(sec in reply_text.lower() for sec in ["password", "secret_key", "database_uri"]):
                    return {
                        "reply": SENSITIVE_DATA_BLOCKED_MSG,
                        "mode": "gemini"
                    }
                return {
                    "reply": reply_text,
                    "mode": "gemini"
                }

    raise ValueError("Invalid or empty response structure from Gemini API")
