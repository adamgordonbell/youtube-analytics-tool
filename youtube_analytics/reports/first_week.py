"""First week performance comparison report"""

from typing import List, Dict, Any

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class FirstWeekReport(BaseReport):
    """Report comparing first week performance across recent videos"""
    
    def get_report_title(self) -> str:
        return "📊 FIRST WEEK PERFORMANCE COMPARISON"
    
    def get_required_video_count(self) -> int:
        return 10  # Compare recent videos
    
    def prepare_data(self, video_metrics: List[VideoMetrics], traffic_source: str = TrafficSources.BROWSE_FEATURES, **kwargs) -> List[Dict[str, Any]]:
        """Prepare first week performance data"""
        # Get video IDs from metrics
        video_ids = [metrics.video_id for metrics in video_metrics]
        
        # Get first week performance from database
        first_week_data = self.db.get_first_week_performance(video_ids, traffic_source)
        
        # Combine with video info
        results = []
        for metrics in video_metrics:
            if metrics.video_id in first_week_data:
                data = first_week_data[metrics.video_id]
                results.append({
                    'video_id': metrics.video_id,
                    'title': data['title'],
                    'published_date': data['published_date'],
                    'first_week_views': data['first_week_views'],
                    'traffic_source': traffic_source
                })
        
        # Sort by first week views descending
        results.sort(key=lambda x: x['first_week_views'], reverse=True)
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title', 'style': 'white', 'width': 40},
            {'name': 'Published', 'style': 'cyan', 'width': 12},
            {'name': 'First Week Views', 'style': 'green', 'justify': 'right'}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        from datetime import datetime
        published = datetime.strptime(row_data['published_date'], '%Y-%m-%d').strftime('%b %d')
        
        return [
            f"{row_data['rank']}.",
            self.truncate_title(row_data['title']),
            published,
            self.format_number(row_data['first_week_views'])
        ]
    
    def get_report_title(self) -> str:
        # Override to include traffic source in title
        traffic_source = getattr(self, '_current_traffic_source', TrafficSources.BROWSE_FEATURES)
        return f"📊 FIRST WEEK {traffic_source.upper()} PERFORMANCE COMPARISON"
    
    def run_report(self, start_date, end_date, max_results=10, traffic_source=TrafficSources.BROWSE_FEATURES, **kwargs):
        """Override to store traffic source for title"""
        self._current_traffic_source = traffic_source
        kwargs['traffic_source'] = traffic_source
        return super().run_report(start_date, end_date, max_results, **kwargs)
