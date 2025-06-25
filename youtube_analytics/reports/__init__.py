"""Modular report system for YouTube Analytics"""

from .base_report import BaseReport
from .organic_views import OrganicViewsReport
from .search_traffic import SearchTrafficReport
from .first_week import FirstWeekReport
from .traffic_breakdown import TrafficBreakdownReport

__all__ = ["BaseReport", "OrganicViewsReport", "SearchTrafficReport", "FirstWeekReport", "TrafficBreakdownReport"]
