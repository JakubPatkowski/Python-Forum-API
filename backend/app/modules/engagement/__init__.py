"""Engagement module: lightweight social features (likes, statistics).

Deliberately a thin SQL-query-based module (same pattern as admin list users),
without the full Clean Architecture stack -- these are simple counters, not
domain aggregates. If it grew (e.g. reaction types, notifications), it could be
moved into the modular monolith with use cases.
"""
