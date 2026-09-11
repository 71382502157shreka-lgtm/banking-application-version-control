import urllib.request
import urllib.parse
import http.cookiejar
import json
import re

BASE_URL = "http://127.0.0.1:5000"

def run_smoke_test():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Login
    req_login_page = urllib.request.Request(f"{BASE_URL}/login")
    res_login_page = opener.open(req_login_page)
    html = res_login_page.read().decode("utf-8")
    
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    csrf_token = match.group(1) if match else ""

    login_data = urllib.parse.urlencode({
        "username": "sarika",
        "password": "Password123",
        "csrf_token": csrf_token
    }).encode("utf-8")

    req_login = urllib.request.Request(f"{BASE_URL}/login", data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    res_login = opener.open(req_login)
    print("Login status:", res_login.getcode())

    # 2. Check /customer/transactions UI page
    req_tx_page = urllib.request.Request(f"{BASE_URL}/customer/transactions")
    res_tx_page = opener.open(req_tx_page)
    tx_html = res_tx_page.read().decode("utf-8")
    assert "Date Range & Export Toolbar" in tx_html or "txnDateFrom" in tx_html
    assert "Export CSV" in tx_html
    assert "Export PDF" in tx_html
    print("UI Transactions Page rendering: PASS")

    # 3. Check /api/transactions paginated query
    req_api = urllib.request.Request(f"{BASE_URL}/api/transactions?page=1&limit=10")
    res_api = opener.open(req_api)
    api_data = json.loads(res_api.read().decode("utf-8"))
    assert api_data["success"] is True
    assert "items" in api_data
    assert "pages" in api_data
    print(f"API Paginated Query: PASS (Total records: {api_data['total']}, pages: {api_data['pages']})")

    # 4. Check /api/statements/download/csv
    req_csv = urllib.request.Request(f"{BASE_URL}/api/statements/download/csv?limit=20")
    res_csv = opener.open(req_csv)
    csv_bytes = res_csv.read()
    assert len(csv_bytes) > 0
    print("API Statement CSV Download: PASS")

    print("\n--- ALL FEATURE 1 SMOKE TESTS PASSED ---")

if __name__ == "__main__":
    run_smoke_test()
