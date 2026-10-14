"""YouTube search traffic report"""

from typing import List, Dict, Any

from .base_report import BaseReport
from ..data import VideoMetrics


class SearchTrafficReport(BaseReport):
    """Report showing top videos by YouTube search traffic"""
    
    def get_report_title(self) -> str:
        return "🔍 TOP VIDEOS BY YOUTUBE SEARCH TRAFFIC"
    
    def get_required_video_count(self) -> int:
        return 30  # Analyze more videos to find top search performers
    
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare search traffic data for display"""
        # Filter and sort by search views
        search_data = []
        for metrics in video_metrics:
            if metrics.search_views > 0:
                search_data.append({
                    'video_id': metrics.video_id,
                    'title': metrics.title,
                    'published_date': metrics.published_date,
                    'search_views': metrics.search_views,
                    'total_views': metrics.total_views,
                    'search_percentage': (metrics.search_views / metrics.total_views * 100) if (metrics.total_views and metrics.total_views > 0 and metrics.search_views is not None) else 0
                })
        
        # Sort by search views descending
        search_data.sort(key=lambda x: x['search_views'], reverse=True)
        return search_data
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Search Views', 'style': 'blue', 'justify': 'right', 'width': 12},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 50},
            {'name': 'Date', 'style': 'cyan', 'width': 10},
            {'name': 'Search %', 'style': 'yellow', 'justify': 'right', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=48)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        return [
            f"{row_data['rank']:2d}.",
            self.format_number(row_data['search_views']),
            title_with_link,
            self.format_date(row_data['published_date']),
            f"{row_data['search_percentage']:.1f}%"
        ]
