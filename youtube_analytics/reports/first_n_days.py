"""First N days performance comparison report"""

from typing import List, Dict, Any, Optional
from datetime import date

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class FirstNDaysReport(BaseReport):
    """Report comparing first N days performance across all videos"""
    
    def get_report_title(self) -> str:
        return "📊 FIRST N DAYS PERFORMANCE COMPARISON"
    
    def get_required_video_count(self) -> int:
        return 100  # We'll use all videos from backfill
    
    def prepare_data(self, video_metrics: List[VideoMetrics], traffic_source: str = TrafficSources.BROWSE_FEATURES, days: int = 7, start_day: int = 0, **kwargs) -> List[Dict[str, Any]]:
        """Prepare N days performance data with total views only"""
        # Get video IDs from metrics
        video_ids = [metrics.video_id for metrics in video_metrics]
        
        # Get total N days views from database
        first_n_days_data = self.db.get_first_n_days_total(video_ids, days, traffic_source, start_day)
        
        # Combine with video info
        results = []
        for metrics in video_metrics:
            if metrics.video_id in first_n_days_data:
                data = first_n_days_data[metrics.video_id]
                
                result = {
                    'video_id': metrics.video_id,
                    'title': data['title'],
                    'published_date': data['published_date'],
                    'total_views': data['total_views'],
                    'traffic_source': traffic_source,
                    'days': days,
                    'start_day': start_day,
                    'is_short_format': metrics.video_info.is_short_format
                }
                
                results.append(result)
        
        # Sort by total views descending (already sorted by database query)
        results.sort(key=lambda x: x['total_views'], reverse=True)
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 50},
            {'name': 'Published', 'style': 'cyan', 'width': 12},
            {'name': 'Type', 'style': 'yellow', 'width': 6},
            {'name': 'Total Views', 'style': 'bright_green', 'justify': 'right', 'width': 12}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        from datetime import datetime
        
        # Format published date with year
        pub_date = datetime.strptime(row_data['published_date'], '%Y-%m-%d')
        published = pub_date.strftime('%b %d, %Y')
        
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=48)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        # Determine content type
        content_type = "Short" if row_data.get('is_short_format') else "Long"
        
        return [
            f"{row_data['rank']}.",
            title_with_link,
            published,
            content_type,
            self.format_number(row_data['total_views'])
        ]
    
    def get_report_title(self) -> str:
        # Override to include traffic source and day range in title
        traffic_source = getattr(self, '_current_traffic_source', TrafficSources.BROWSE_FEATURES)
        days = getattr(self, '_current_days', 7)
        start_day = getattr(self, '_current_start_day', 0)
        
        # Create day range description
        if start_day == 0:
            day_range = f"FIRST {days} DAYS"
        else:
            end_day = start_day + days
            day_range = f"DAYS {start_day + 1}-{end_day}"
        
        if traffic_source.lower() == 'all':
            return f"📊 {day_range} TOTAL PERFORMANCE COMPARISON"
        elif traffic_source.lower() == 'organic':
            return f"📊 {day_range} ORGANIC PERFORMANCE COMPARISON"
        else:
            return f"📊 {day_range} {traffic_source.upper()} PERFORMANCE COMPARISON"
    
    def run_report(self, start_date, end_date, max_results=10, traffic_source=TrafficSources.BROWSE_FEATURES, days=7, start_day=0, **kwargs):
        """Override to use existing videos from database and store parameters for title"""
        self._current_traffic_source = traffic_source
        self._current_days = days
        self._current_start_day = start_day
        kwargs['traffic_source'] = traffic_source
        kwargs['days'] = days
        kwargs['start_day'] = start_day
        
        try:
            # Use all videos already in database (don't try to discover new ones)
            self.console.print(f"[dim]Analyzing {self.get_report_title()} from existing data...[/dim]")
            video_ids = self.db.get_all_video_ids()
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found in database for {self.get_report_title()}[/yellow]")
                return False
            
            # Get metrics from database
            video_metrics = []
            for video_id in video_ids:
                video_info = self.db.get_video_info(video_id)
                if video_info:
                    metrics = VideoMetrics(
                        video_info=video_info,
                        total_views=0,  # Not used in first N days report
                        organic_views=0,  # Not used in first N days report
                        search_views=0   # Not used in first N days report
                    )
                    video_metrics.append(metrics)
            
            if not video_metrics:
                self.console.print(f"[yellow]No metrics available for {self.get_report_title()}[/yellow]")
                return False
            
            # Display report
            self.display_report(video_metrics, start_date, end_date, max_results, **kwargs)
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error running {self.get_report_title()}: {e}[/red]")
            return False
