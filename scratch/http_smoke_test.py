from app import create_app, db
from app.models.user import Role
from app.services import auth_service

app = create_app("testing")
with app.app_context():
    db.create_all()
    
    user = auth_service.register_user(
        "smoketest_user", "smoke@example.com", "Str0ngPass!", full_name="Smoke Test", role=Role.CUSTOMER
    )
    
    client = app.test_client()
    
    # 1. Login
    login_res = client.post("/login", data={"username": "smoketest_user", "password": "Str0ngPass!"}, follow_redirects=True)
    assert login_res.status_code == 200, f"Login failed: {login_res.status_code}"
    print("1. [PASS] Customer login successful")
    
    # 2. View Beneficiaries Page
    page_res = client.get("/customer/beneficiaries")
    assert page_res.status_code == 200
    print("2. [PASS] GET /customer/beneficiaries returned 200 OK")
    
    # 3. Add Beneficiary via API
    add_res = client.post("/api/beneficiaries", json={
        "name": "Smoke Test Payee",
        "bank_name": "State Bank of India",
        "account_number": "998877665544",
        "confirm_account_number": "998877665544",
        "ifsc": "SBIN0001234"
    })
    assert add_res.status_code == 201, f"Add failed: {add_res.get_json()}"
    b_data = add_res.get_json()
    b_id = b_data["id"]
    print(f"3. [PASS] POST /api/beneficiaries created beneficiary ID {b_id} (v{b_data['version_number']})")
    
    # 4. Search Beneficiary
    search_res = client.get("/api/beneficiaries?q=Smoke")
    assert search_res.status_code == 200
    results = search_res.get_json()
    assert len(results) >= 1
    print("4. [PASS] GET /api/beneficiaries?q=Smoke found matching payee")
    
    # 5. Update Beneficiary
    update_res = client.put(f"/api/beneficiaries/{b_id}", json={
        "name": "Smoke Test Payee Updated",
        "bank_name": "State Bank of India",
        "account_number": "998877665544",
        "confirm_account_number": "998877665544",
        "ifsc": "SBIN0001234"
    })
    assert update_res.status_code == 200
    updated_data = update_res.get_json()
    assert updated_data["version_number"] == 2
    print(f"5. [PASS] PUT /api/beneficiaries/{b_id} updated version to v{updated_data['version_number']}")
    
    # 6. View Transfer Page with preselected account
    transfer_res = client.get("/customer/transfer?account=998877665544")
    assert transfer_res.status_code == 200
    print("6. [PASS] GET /customer/transfer?account=... returned 200 OK")
    
    # 7. Delete Beneficiary
    del_res = client.delete(f"/api/beneficiaries/{b_id}")
    assert del_res.status_code == 200
    print(f"7. [PASS] DELETE /api/beneficiaries/{b_id} soft deleted payee")
    
    print("\nALL HTTP SMOKE TESTS COMPLETED SUCCESSFULLY!")
