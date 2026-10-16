#!/usr/bin/env python3
"""Build realistic test files with known answers planted in them.

Usage: python3 make_fixtures.py OUT_DIR
Writes app.log, orders.json, events.jsonl and sales.csv plus answers.json (the planted facts).
Output is deterministic (fixed seed) so results can be compared across versions.
"""
import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta

rnd = random.Random(20261015)
out = sys.argv[1] if len(sys.argv) > 1 else "fixtures"
os.makedirs(out, exist_ok=True)
answers = {}

# ---------------------------------------------------------------- app.log
t0 = datetime(2026, 10, 14, 8, 0, 0)
lines = []
endpoints = ["/api/orders", "/api/cart", "/api/users/me", "/api/search", "/health"]
redis_failures = 0
trace_line = None
for i in range(24000):
    ts = (t0 + timedelta(milliseconds=i * 1350)).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    rid = f"{rnd.getrandbits(64):016x}"
    r = rnd.random()
    if i == 15873:
        trace_line = len(lines) + 1
        lines += [
            f"{ts} ERROR [payment-worker-3] Unhandled exception while settling order 88412",
            "Traceback (most recent call last):",
            '  File "/srv/app/payments/settle.py", line 142, in settle_order',
            "    customer = order.payload['customer_id']",
            '  File "/srv/app/payments/models.py", line 57, in __getitem__',
            "    return self._data[key]",
            "KeyError: 'customer_id'",
        ]
        continue
    if 15874 <= i <= 16340 and i % 2 == 0:
        redis_failures += 1
        lines.append(f"{ts} ERROR [cache] redis.exceptions.ConnectionError: Error 111 connecting to 10.0.4.17:6379. Connection refused.")
        continue
    if 15874 <= i <= 16340:
        lines.append(f"{ts} WARN  [payment-worker-{rnd.randint(1, 4)}] retrying order {rnd.randint(80000, 90000)} (attempt {rnd.randint(1, 5)}/5)")
        continue
    if r < 0.70:
        ep = rnd.choice(endpoints)
        lines.append(f"{ts} INFO  [http] GET {ep} 200 {rnd.randint(3, 180)}ms rid={rid}")
    elif r < 0.93:
        lines.append(f"{ts} DEBUG [cache] hit key=user:{rnd.randint(1, 99999)} ttl={rnd.randint(10, 600)}s")
    elif r < 0.995:
        lines.append(f"{ts} INFO  [scheduler] heartbeat ok workers={rnd.randint(3, 4)} queue_depth={rnd.randint(0, 40)}")
    else:
        lines.append(f"{ts} WARN  [db] slow query {rnd.randint(1200, 4800)}ms: SELECT * FROM orders WHERE status = $1")
lines.append((t0 + timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S,000") + " INFO  [main] shutdown complete")
with open(os.path.join(out, "app.log"), "w") as fh:
    fh.write("\n".join(lines) + "\n")
answers["app.log"] = {
    "first_error_cause": "KeyError: 'customer_id' in payments/settle.py line 142 (order 88412)",
    "traceback_line": trace_line,
    "redis_connection_errors": redis_failures,
    "redis_host": "10.0.4.17:6379",
    "total_lines": len(lines),
}

# ---------------------------------------------------------------- orders.json
statuses = ["paid"] * 40 + ["shipped"] * 50 + ["delivered"] * 60 + ["refunded"] * 3
orders = []
failed = {37: "card_declined", 211: "fraud_check_timeout", 402: "card_declined", 588: "address_invalid"}
for i in range(640):
    o = {
        "id": f"ord_{100000 + i}",
        "created_at": (t0 - timedelta(minutes=37 * i)).isoformat() + "Z",
        "status": rnd.choice(statuses),
        "currency": "USD",
        "total_cents": rnd.randint(899, 48900),
        "customer": {"id": f"cus_{rnd.randint(1000, 9999)}", "email": f"user{rnd.randint(1, 5000)}@example.com",
                     "tier": rnd.choice(["free", "free", "pro", "team"])},
        "items": [{"sku": f"SKU-{rnd.randint(100, 999)}", "qty": rnd.randint(1, 4)} for _ in range(rnd.randint(1, 5))],
        "shipping": {"carrier": rnd.choice(["UPS", "USPS", "FedEx"]), "tracking": None if rnd.random() < 0.2 else f"1Z{rnd.getrandbits(40):010X}"},
    }
    if i in failed:
        o["status"] = "failed"
        o["error"] = {"code": failed[i], "message": f"Payment failed: {failed[i].replace('_', ' ')}"}
    if i == 133:
        o["refund"] = {"amount_cents": 2500, "reason": "damaged item"}
    orders.append(o)
doc = {"object": "list", "url": "/v1/orders", "has_more": True, "data": orders,
       "meta": {"request_id": "req_8f2a1c", "page": 1, "page_size": 640}}
with open(os.path.join(out, "orders.json"), "w") as fh:
    json.dump(doc, fh, indent=2)
answers["orders.json"] = {
    "order_count": len(orders),
    "failed_orders": {f"ord_{100000 + i}": c for i, c in failed.items()},
    "rare_field": "refund on ord_100133",
}

# ---------------------------------------------------------------- events.jsonl
with open(os.path.join(out, "events.jsonl"), "w") as fh:
    for i in range(5000):
        ev = {"ts": (t0 + timedelta(seconds=7 * i)).isoformat() + "Z", "type": rnd.choice(["page_view"] * 8 + ["click"] * 3 + ["signup"]),
              "user": f"u{rnd.randint(1, 1500)}", "path": rnd.choice(["/", "/pricing", "/docs", "/blog", "/signup"]),
              "ms": rnd.randint(20, 900)}
        if i in (1200, 3300):
            ev["status_code"] = 500
            ev["error"] = "upstream timeout from /api/pricing"
        fh.write(json.dumps(ev) + "\n")
answers["events.jsonl"] = {"event_count": 5000, "error_events": [1200, 3300], "error_message": "upstream timeout from /api/pricing"}

# ---------------------------------------------------------------- sales.csv
regions = ["North", "South", "East", "West"]
reps = {r: [f"{r[0]}-rep-{k}" for k in range(1, 6)] for r in regions}
total = 0.0
null_reps = 0
with open(os.path.join(out, "sales.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["date", "region", "rep", "product", "units", "unit_price", "revenue"])
    for i in range(9000):
        region = rnd.choice(regions)
        rep = rnd.choice(reps[region])
        if i % 750 == 11:
            rep = ""
            null_reps += 1
        units = rnd.randint(1, 40)
        price = rnd.choice([19.99, 49.0, 129.5, 349.0])
        revenue = round(units * price, 2)
        if i == 6061:
            revenue = 987654.32  # bad row: decimal shifted
        total += revenue
        w.writerow([(datetime(2026, 1, 1) + timedelta(hours=i)).date().isoformat(), region, rep,
                    rnd.choice(["Starter", "Pro", "Team", "Enterprise"]), units, price, revenue])
answers["sales.csv"] = {"rows": 9000, "revenue_total": round(total, 2), "null_reps": null_reps,
                        "outlier": "revenue 987654.32 on data row 6062 (line 6063)", "regions": regions}

# ---------------------------------------------------------------- run_tests.py (prints verbose test output)
RUN_TESTS = r'''#!/usr/bin/env python3
"""Stand-in for a large test suite: prints pytest-style verbose output and exits 1."""
import random, sys
rnd = random.Random(42)
mods = ["billing", "cart", "catalog", "auth", "search", "shipping", "tax", "users", "orders", "webhooks"]
fails = {1311: ("tests/test_tax.py::test_vat_rounding_eu[DE-19.99]",
                ["    def test_vat_rounding_eu(country, price):",
                 "        total = tax.apply_vat(price, country)",
                 ">       assert total == Decimal(\"23.79\")",
                 "E       AssertionError: assert Decimal(\'23.78\') == Decimal(\'23.79\')",
                 "tests/test_tax.py:88: AssertionError"]),
         2702: ("tests/test_webhooks.py::test_retry_backoff_caps_at_five_minutes",
                ["    def test_retry_backoff_caps_at_five_minutes():",
                 "        delays = [backoff(n) for n in range(12)]",
                 ">       assert max(delays) <= 300",
                 "E       assert 640 <= 300",
                 "E        +  where 640 = max([5, 10, 20, 40, 80, 160, ...])",
                 "tests/test_webhooks.py:41: AssertionError"]),
         3555: ("tests/test_auth.py::test_refresh_token_rotation",
                ["    def test_refresh_token_rotation(client):",
                 "        r = client.post(\"/auth/refresh\", json={\"token\": old})",
                 ">       assert r.status_code == 200",
                 "E       assert 500 == 200",
                 "E        +  where 500 = <Response [500]>.status_code",
                 "src/auth/tokens.py:117: KeyError: \'kid\'",
                 "tests/test_auth.py:64: AssertionError"])}
N = 4000
print("============================= test session starts ==============================")
print("platform linux -- Python 3.12.4, pytest-8.3.2, pluggy-1.5.0")
print("rootdir: /srv/shop")
print(f"collected {N} items")
print()
for i in range(N):
    if i in fails:
        print(f"{fails[i][0]} FAILED [{100 * (i + 1) // N:3d}%]")
    else:
        m = mods[i % len(mods)]
        print(f"tests/test_{m}.py::test_{m}_case_{i:04d} PASSED [{100 * (i + 1) // N:3d}%]")
print()
print("=================================== FAILURES ===================================")
for i, (name, body) in fails.items():
    print(f"_____ {name.split('::')[1]} _____")
    print("\n".join(body))
print("=========================== short test summary info ============================")
for i, (name, body) in fails.items():
    print(f"FAILED {name} - {[l for l in body if l.startswith('E ')][0][8:]}")
print(f"======================= 3 failed, {N - 3} passed in 41.27s ========================")
sys.exit(1)
'''
with open(os.path.join(out, "run_tests.py"), "w") as fh:
    fh.write(RUN_TESTS)
os.chmod(os.path.join(out, "run_tests.py"), 0o755)
answers["run_tests.py"] = {"failed": ["test_vat_rounding_eu", "test_retry_backoff_caps_at_five_minutes", "test_refresh_token_rotation"]}

# ---------------------------------------------------------------- fetch_orders.py (prints the orders JSON)
with open(os.path.join(out, "fetch_orders.py"), "w") as fh:
    fh.write("#!/usr/bin/env python3\n\"\"\"Stand-in for an API call: prints today's orders as JSON.\"\"\"\n"
             "import sys\nsys.stdout.write(" + repr(json.dumps(doc)) + ")\n")
os.chmod(os.path.join(out, "fetch_orders.py"), 0o755)

# ---------------------------------------------------------------- mid-size versions (under Read's 256 KB limit)
with open(os.path.join(out, "app.log")) as fh:
    all_lines = fh.read().split("\n")
with open(os.path.join(out, "mid-app.log"), "w") as fh:
    fh.write("\n".join(all_lines[15200:16400]) + "\n")
mid_doc = dict(doc, data=orders[:240], meta=dict(doc["meta"], page_size=240))
with open(os.path.join(out, "mid-orders.json"), "w") as fh:
    json.dump(mid_doc, fh, indent=2)
with open(os.path.join(out, "sales.csv")) as fh:
    rows = fh.read().split("\n")
with open(os.path.join(out, "mid-sales.csv"), "w") as fh:
    fh.write("\n".join(rows[:2001]) + "\n")
mid_total = round(sum(float(r.split(",")[-1]) for r in rows[1:2001]), 2)
answers["mid"] = {"app_traceback_line": 15874 - 15200, "orders_failed": ["ord_100037", "ord_100211"],
                  "sales_total": mid_total, "sales_null_reps": sum(1 for r in rows[1:2001] if r.split(",")[2] == "")}

with open(os.path.join(out, "answers.json"), "w") as fh:
    json.dump(answers, fh, indent=2)
print(json.dumps(answers, indent=2))
