#!/usr/bin/env python3
"""Adversarial concurrency harness for SQLite "database is locked" 500s.

Creates a receipt (mock OCR), finalizes it, subdivides one item into many
portions, then hammers the server concurrently:

  - N claimer threads: each iteration uses a FRESH session (view page ->
    register viewer name -> POST /claim/ finalizing a 1-portion claim).
    The claim POST runs ClaimService.finalize_claims: an @transaction.atomic
    read-then-write transaction (the suspected deadlock path).
  - M poller threads: GET /claim/<slug>/status/ every ~50ms per open page.
    Because SESSION_SAVE_EVERY_REQUEST=True, every poll also UPDATEs the
    session row, so "read" traffic is actually write traffic too.
  - 1 subdivider thread: POST /claim/<slug>/subdivide/ with target_parts equal
    to the current numerator — a valid no-op re-split that rewrites the item
    row plus EVERY claim row inside one atomic read-then-write transaction
    (long writer, maximum deadlock exposure).

Counts status codes, captures 500 bodies, and reports p50/p95/max latency.

Usage:
  python scripts/lock_harness.py --base http://127.0.0.1:8001 \
      --claimers 8 --pollers 8 --duration 45
Requires the dev server (or gunicorn) running with rate limiting disabled
(see harness settings module) and mock OCR (no GEMINI_API_KEY).
"""
import argparse
import io
import json
import random
import string
import threading
import time
from collections import Counter, defaultdict

import requests


def make_image_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 140), (240, 236, 226)).save(buf, "JPEG")
    return buf.getvalue()


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.codes = Counter()          # (label, status) -> count
        self.latency = defaultdict(list)  # label -> [seconds]
        self.errors = []                # sample of 5xx bodies / exceptions

    def record(self, label, status, seconds, body=None):
        with self.lock:
            self.codes[(label, status)] += 1
            self.latency[label].append(seconds)
            if status >= 500 or status == 0:
                if len(self.errors) < 30:
                    self.errors.append((label, status, (body or "")[:300]))

    def report(self):
        print("\n=== status codes ===")
        for (label, status), n in sorted(self.codes.items()):
            print(f"  {label:22s} {status:>3} : {n}")
        print("=== latency (s) ===")
        for label, vals in sorted(self.latency.items()):
            vals = sorted(vals)
            if not vals:
                continue
            p = lambda q: vals[min(len(vals) - 1, int(q * len(vals)))]
            print(f"  {label:22s} n={len(vals):5d} p50={p(0.50):.3f} "
                  f"p95={p(0.95):.3f} max={vals[-1]:.3f}")
        n500 = sum(n for (l, s), n in self.codes.items() if s >= 500 or s == 0)
        print(f"=== total 5xx/exception responses: {n500} ===")
        for label, status, body in self.errors:
            print(f"  [{label} {status}] {body}")
        return n500


def csrf(session, base, path="/"):
    session.get(base + path, timeout=30)
    return session.cookies.get("csrftoken", "")


def headers(session, base):
    return {"X-CSRFToken": session.cookies.get("csrftoken", ""), "Referer": base + "/"}


def setup_receipt(base, parts):
    s = requests.Session()
    csrf(s, base)
    r = s.post(
        base + "/upload/",
        data={"uploader_name": "LoadTester"},
        files={"receipt_image": ("r.jpg", make_image_bytes(), "image/jpeg")},
        headers=headers(s, base),
        timeout=30,
        allow_redirects=False,
    )
    assert r.status_code == 302, f"upload failed: {r.status_code} {r.text[:200]}"
    slug = r.headers["Location"].strip("/").split("/")[-1]
    # wait for mock OCR
    for _ in range(60):
        st = s.get(f"{base}/status/{slug}/", timeout=30).json()
        if st.get("is_complete"):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("OCR never completed")
    r = s.post(f"{base}/finalize/{slug}/", json={}, headers=headers(s, base), timeout=30)
    assert r.status_code == 200, f"finalize failed: {r.status_code} {r.text[:300]}"
    # pick an item and subdivide it into `parts` portions
    st = s.get(f"{base}/claim/{slug}/status/", timeout=30).json()
    items = st["items_with_claims"]
    item = items[0]
    r = s.post(
        f"{base}/claim/{slug}/subdivide/",
        json={"line_item_id": item["item_id"], "target_parts": parts},
        headers=headers(s, base),
        timeout=30,
    )
    assert r.status_code == 200, f"subdivide failed: {r.status_code} {r.text[:300]}"
    denom = r.json()["quantity_denominator"]
    print(f"receipt {slug}: item {item['item_id']} split into {parts} portions")
    return s, slug, item["item_id"], denom


def rand_name(prefix):
    return prefix + "".join(random.choices(string.ascii_letters + string.digits, k=8))


def timed(stats, label, fn):
    t0 = time.monotonic()
    try:
        r = fn()
        stats.record(label, r.status_code, time.monotonic() - t0, r.text)
        return r
    except Exception as e:  # connection errors etc.
        stats.record(label, 0, time.monotonic() - t0, repr(e))
        return None


def claimer(base, slug, item_id, denom, stats, deadline):
    while time.monotonic() < deadline:
        s = requests.Session()
        try:
            timed(stats, "view GET", lambda: s.get(f"{base}/r/{slug}/", timeout=30))
            timed(stats, "register POST", lambda: s.post(
                f"{base}/r/{slug}/",
                data={"viewer_name": rand_name("C")},
                headers=headers(s, base), timeout=30))
            timed(stats, "claim POST", lambda: s.post(
                f"{base}/claim/{slug}/",
                json={"claims": [{"line_item_id": item_id,
                                  "quantity_numerator": 1,
                                  "quantity_denominator": denom}]},
                headers=headers(s, base), timeout=30))
        finally:
            s.close()


def poller(base, slug, stats, deadline):
    s = requests.Session()
    csrf(s, base, f"/r/{slug}/")
    # register once so the session is non-empty -> SESSION_SAVE_EVERY_REQUEST
    # makes every subsequent poll write the session row
    s.post(f"{base}/r/{slug}/", data={"viewer_name": rand_name("P")},
           headers=headers(s, base), timeout=30)
    while time.monotonic() < deadline:
        timed(stats, "status GET", lambda: s.get(f"{base}/claim/{slug}/status/", timeout=30))
        time.sleep(0.05)


def subdivider(base, slug, item_id, uploader, stats, deadline, parts):
    while time.monotonic() < deadline:
        timed(stats, "subdivide POST", lambda: uploader.post(
            f"{base}/claim/{slug}/subdivide/",
            json={"line_item_id": item_id, "target_parts": parts},
            headers=headers(uploader, base), timeout=30))
        time.sleep(0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--claimers", type=int, default=8)
    ap.add_argument("--pollers", type=int, default=8)
    ap.add_argument("--duration", type=int, default=45)
    ap.add_argument("--parts", type=int, default=20000)
    args = ap.parse_args()

    uploader, slug, item_id, denom = setup_receipt(args.base, args.parts)
    stats = Stats()
    deadline = time.monotonic() + args.duration

    threads = []
    for _ in range(args.claimers):
        threads.append(threading.Thread(
            target=claimer, args=(args.base, slug, item_id, denom, stats, deadline)))
    for _ in range(args.pollers):
        threads.append(threading.Thread(
            target=poller, args=(args.base, slug, stats, deadline)))
    threads.append(threading.Thread(
        target=subdivider,
        args=(args.base, slug, item_id, uploader, stats, deadline, args.parts)))

    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - t0
    print(f"\nran {elapsed:.1f}s with {args.claimers} claimers, "
          f"{args.pollers} pollers, 1 subdivider")
    n500 = stats.report()
    raise SystemExit(1 if n500 else 0)


if __name__ == "__main__":
    main()
