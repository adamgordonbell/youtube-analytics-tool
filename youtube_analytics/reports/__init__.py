"""Modular report system for YouTube Analytics"""

from .base_report import BaseReport
from .search_traffic import SearchTrafficReport
from .first_week import FirstWeekReport
from .first_n_days import FirstNDaysReport
from .traffic_breakdown import TrafficBreakdownReport
from .first_90_days_traffic import First90DaysTrafficReport
from .first_180_days_search import First180DaysSearchReport
from .shorts_detection import ShortsDetectionReport

__all__ = ["BaseReport", "SearchTrafficReport", "FirstWeekReport", "FirstNDaysReport", "TrafficBreakdownReport", "First90DaysTrafficReport", "First180DaysSearchReport", "ShortsDetectionReport"]
