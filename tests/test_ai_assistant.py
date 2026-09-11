import pytest
from app.services import ai_service
from app.models.user import User, Role


def test_ai_service_rule_based_responses():
    """Test AI Service rule-based NLP fallback engine."""
    # Test balance query
    res = ai_service.generate_ai_response("How do I check my account balance?", user_context={"username": "testuser", "role": "customer"})
    assert "Customer Dashboard" in res["reply"] or "balance" in res["reply"].lower()
    assert res["mode"] == "rule_engine"

    # Test transfer query
    res = ai_service.generate_ai_response("How to transfer money to beneficiary?", user_context={"username": "testuser", "role": "customer"})
    assert "Transfers" in res["reply"] or "beneficiary" in res["reply"].lower()

    # Test version control query
    res = ai_service.generate_ai_response("What is version control rollback?", user_context={"username": "testuser", "role": "customer"})
    assert "snapshot" in res["reply"].lower() or "version" in res["reply"].lower()

    # Test blank query
    res = ai_service.generate_ai_response("", user_context={"username": "testuser", "role": "customer"})
    assert "Please ask a question" in res["reply"]


def test_ai_chat_endpoint_unauthenticated(client):
    """Test that unauthenticated requests to /api/ai/chat are rejected."""
    res = client.post('/api/ai/chat', json={'message': 'Hello'})
    assert res.status_code in (302, 401)


def test_ai_chat_endpoint_authenticated(client, app, customer):
    """Test authenticated customer sending message to /api/ai/chat."""
    client.post('/login', data={'username': 'janedoe', 'password': 'Str0ngPass!'})
    res = client.post('/api/ai/chat', json={'message': 'How do I check my balance?'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'reply' in data
    assert data['mode'] in ('rule_engine', 'gemini')
    assert 'password' not in data['reply'].lower()
    assert 'secret' not in data['reply'].lower()


def test_ai_chat_endpoint_empty_message(client, app, customer):
    """Test empty message validation on /api/ai/chat."""
    client.post('/login', data={'username': 'janedoe', 'password': 'Str0ngPass!'})
    res = client.post('/api/ai/chat', json={'message': '  '})
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False


