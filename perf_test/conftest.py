"""Conftest for perf tests — no Django DB setup needed.

These tests talk to a running dev server over HTTP via Playwright.
They don't need Django's test database or ORM access.
"""
