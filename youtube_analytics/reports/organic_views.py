"""Organic views report (excluding advertising)"""

from typing import List, Dict, Any

from .base_report import BaseReport
from ..data import VideoMetrics


class OrganicViewsReport(BaseReport):
    """Report showing top videos by organic views (excluding advertising)"""
    
    def get_report_title(self) -> str:
        return "🌱 TOP VIDEOS BY ORGANIC VIEWS"
    
    def get_required_video_count(self) -> int:
        return 30  # Analyze more videos to find top organic performers
    
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare organic views data for display"""
        # Filter and sort by organic views
        organic_data = []
        for metrics in video_metrics:
            if metrics.organic_views > 0:
                organic_data.append({
                    'video_id': metrics.video_id,
                    'title': metrics.title,
                    'published_date': metrics.published_date,
                    'organic_views': metrics.organic_views,
                    'total_views': metrics.total_views,
                    'organic_percentage': (metrics.organic_views / metrics.total_views * 100) if metrics.total_views > 0 else 0
                })
        
        # Sort by organic views descending
        organic_data.sort(key=lambda x: x['organic_views'], reverse=True)
        return organic_data
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Organic Views', 'style': 'green', 'justify': 'right', 'width': 12},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 50},
            {'name': 'Date', 'style': 'cyan', 'width': 10},
            {'name': 'Organic %', 'style': 'yellow', 'justify': 'right', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=48)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        return [
            f"{row_data['rank']:2d}.",
            self.format_number(row_data['organic_views']),
            title_with_link,
            self.format_date(row_data['published_date']),
            f"{row_data['organic_percentage']:.1f}%"
        ]
