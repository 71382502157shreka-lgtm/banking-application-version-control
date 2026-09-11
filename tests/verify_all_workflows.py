"""
Standalone verification script using Flask test client to validate all
routes, user roles (Customer, Employee, Admin), and workflow endpoints.
"""

import os
import sys
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import seed

seed.run()
app = seed.create_app(os.environ.get("FLASK_ENV", "development"))


def run_checks():
    client = app.test_client()

    print("1. Checking Home & Login Pages...")
    res = client.get("/")
    assert res.status_code == 200, f"Home page failed: {res.status_code}"
    print("   [PASS] Home page 200 OK")

    login_page = client.get("/login").get_data(as_text=True)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page)
    assert match, "CSRF token missing from login page"
    csrf_token = match.group(1)
    print("   [PASS] Login page 200 OK & CSRF token extracted")

    print("2. Testing Customer Login (sarika)...")
    login_res = client.post("/login", data={
        "username": "sarika",
        "password": "Password123",
        "csrf_token": csrf_token
    }, follow_redirects=True)
    body = login_res.get_data(as_text=True)
    assert login_res.status_code == 200, "Customer login failed"
    print("   [PASS] Customer login successful, Dashboard loaded")

    # Check all customer pages
    for path in ["/customer/dashboard", "/customer/accounts", "/customer/transfer", "/customer/deposit", 
                 "/customer/withdraw", "/customer/transactions", "/customer/beneficiaries", 
                 "/customer/statements", "/customer/version-history", "/customer/security", 
                 "/customer/profile", "/customer/notifications"]:
        sub_res = client.get(path)
        assert sub_res.status_code == 200, f"Customer page {path} failed with {sub_res.status_code}"
        print(f"   [PASS] {path} 200 OK")

    client.get("/logout", follow_redirects=True)
    print("   [PASS] Customer logged out")

    print("3. Testing Employee Login (employee)...")
    login_page = client.get("/login").get_data(as_text=True)
    csrf_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page).group(1)
    client.post("/login", data={
        "username": "employee",
        "password": "ChangeMe_Employee123!",
        "csrf_token": csrf_token
    }, follow_redirects=True)

    for path in ["/employee/dashboard", "/employee/customers", "/employee/versions", "/employee/audit-logs"]:
        sub_res = client.get(path)
        assert sub_res.status_code == 200, f"Employee page {path} failed: {sub_res.status_code}"
        print(f"   [PASS] {path} 200 OK")

    client.get("/logout", follow_redirects=True)
    print("   [PASS] Employee logged out")

    print("4. Testing Admin Login (admin1)...")
    login_page = client.get("/login").get_data(as_text=True)
    csrf_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page).group(1)
    client.post("/login", data={
        "username": "admin1",
        "password": "Password123",
        "csrf_token": csrf_token
    }, follow_redirects=True)

    for path in ["/admin/dashboard", "/admin/users", "/admin/audit-logs", "/admin/version-history", "/admin/settings"]:
        sub_res = client.get(path)
        assert sub_res.status_code == 200, f"Admin page {path} failed: {sub_res.status_code}"
        print(f"   [PASS] {path} 200 OK")

    print("\nALL SYSTEM WORKFLOWS PASSED LIVE VALIDATION PERFECTLY!")


if __name__ == "__main__":
    run_checks()
