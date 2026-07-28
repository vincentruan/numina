"""Literacy weekly report — Pydantic schemas for parent-facing report endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class WeeklyReportResponse(SnowflakeBase):
    """A single weekly literacy report."""

    id: int
    child_id: int
    week_start: date
    report_json: dict
    narrative: str
    generated_at: datetime


class ReportChildItem(SnowflakeBase):
    """A child with their latest report week."""

    child_id: int
    display_name: str
    latest_week_start: date | None = None


class ReportChildListResponse(BaseModel):
    """Response for GET /literacy-reports/children."""

    children: list[ReportChildItem]


class ReportHistoryItem(BaseModel):
    """A single week in the report history."""

    week_start: date
    has_report: bool


class ReportHistoryResponse(BaseModel):
    """Response for GET /literacy-reports/history."""

    weeks: list[ReportHistoryItem]
