import urllib.request
import urllib.parse
import http.cookiejar
import re

BASE_URL = "http://127.0.0.1:5000"

def run_checks():
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    print("1. Checking Home & Login Pages...")
    res = opener.open(f"{BASE_URL}/")
    assert res.status == 200, f"Home page failed: {res.status}"
    print("   [PASS] Home page 200 OK")

    login_page = opener.open(f"{BASE_URL}/login").read().decode("utf-8")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page)
    assert match, "CSRF token missing from login page"
    csrf_token = match.group(1)
    print("   [PASS] Login page 200 OK & CSRF token extracted")

    print("2. Testing Customer Login (sarika)...")
    data = urllib.parse.urlencode({
        "username": "sarika",
        "password": "Password123",
        "csrf_token": csrf_token
    }).encode("utf-8")
    login_res = opener.open(f"{BASE_URL}/login", data=data)
    body = login_res.read().decode("utf-8")
    assert "Sarika M" in body or "sarika" in body
    print("   [PASS] Customer login successful, Dashboard loaded")

    # Check all customer pages
    for path in ["/customer/dashboard", "/customer/accounts", "/customer/transfer", "/customer/deposit", 
                 "/customer/withdraw", "/customer/transactions", "/customer/beneficiaries", 
                 "/customer/statements", "/customer/version-history", "/customer/security", 
                 "/customer/profile", "/customer/notifications"]:
        sub_res = opener.open(f"{BASE_URL}{path}")
        assert sub_res.status == 200, f"Customer page {path} failed with {sub_res.status}"
        print(f"   [PASS] {path} 200 OK")

    # Logout
    opener.open(f"{BASE_URL}/logout")
    print("   [PASS] Customer logged out")

    print("3. Testing Employee Login (staff1)...")
    login_page = opener.open(f"{BASE_URL}/login").read().decode("utf-8")
    csrf_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page).group(1)
    data = urllib.parse.urlencode({
        "username": "staff1",
        "password": "Password123",
        "csrf_token": csrf_token
    }).encode("utf-8")
    login_res = opener.open(f"{BASE_URL}/login", data=data)
    for path in ["/employee/dashboard", "/employee/customers", "/employee/versions", "/employee/audit-logs"]:
        sub_res = opener.open(f"{BASE_URL}{path}")
        assert sub_res.status == 200, f"Employee page {path} failed: {sub_res.status}"
        print(f"   [PASS] {path} 200 OK")

    opener.open(f"{BASE_URL}/logout")
    print("   [PASS] Employee logged out")

    print("4. Testing Admin Login (admin1)...")
    login_page = opener.open(f"{BASE_URL}/login").read().decode("utf-8")
    csrf_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page).group(1)
    data = urllib.parse.urlencode({
        "username": "admin1",
        "password": "Password123",
        "csrf_token": csrf_token
    }).encode("utf-8")
    login_res = opener.open(f"{BASE_URL}/login", data=data)
    for path in ["/admin/dashboard", "/admin/users", "/admin/audit-logs", "/admin/version-history", "/admin/settings"]:
        sub_res = opener.open(f"{BASE_URL}{path}")
        assert sub_res.status == 200, f"Admin page {path} failed: {sub_res.status}"
        print(f"   [PASS] {path} 200 OK")

    print("\nALL SYSTEM WORKFLOWS PASSED LIVE VALIDATION PERFECTLY!")

if __name__ == "__main__":
    run_checks()
