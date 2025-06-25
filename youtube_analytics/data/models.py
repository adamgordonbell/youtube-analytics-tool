"""Data models for YouTube Analytics"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class VideoInfo:
    video_id: str
    title: str
    published_date: date
    channel_id: str

@dataclass
class DailyMetric:
    video_id: str
    date: date
    days_since_published: int
    traffic_source: str
    views: int

@dataclass
class VideoMetrics:
    """Complete metrics for a video"""
    video_info: VideoInfo
    total_views: int
    organic_views: int
    search_views: int
    first_week_views: Optional[int] = None
    
    @property
    def video_id(self) -> str:
        return self.video_info.video_id
    
    @property
    def title(self) -> str:
        return self.video_info.title
    
    @property
    def published_date(self) -> date:
        return self.video_info.published_date
