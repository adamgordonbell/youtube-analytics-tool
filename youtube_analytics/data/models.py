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
    duration_seconds: Optional[int] = None
    is_short_format: Optional[bool] = None  # True if uploaded as Short, False if regular video
    
    @property
    def is_short(self) -> bool:
        """Return True if video is a YouTube Short"""
        # Use explicit Short format flag if available
        if self.is_short_format is not None:
            return self.is_short_format
        
        # Fallback to duration-based detection using our standard function
        if self.duration_seconds is not None:
            from ..utils import is_video_short
            return is_video_short(self.duration_seconds)
        
        # If no data available, assume it's a regular video
        return False
    
    @property
    def format_type(self) -> str:
        """Return 'Short' or 'Video' based on format"""
        if self.is_short_format is None and self.duration_seconds is None:
            return "Unknown"
        return "Short" if self.is_short else "Video"

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
