"""First week performance comparison report"""

from typing import List, Dict, Any, Optional
from datetime import date

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class FirstWeekReport(BaseReport):
    """Report comparing first week performance across recent videos"""
    
    def get_report_title(self) -> str:
        return "📊 FIRST WEEK PERFORMANCE COMPARISON"
    
    def get_required_video_count(self) -> int:
        return 40  # Look at more videos to find top performers
    
    def prepare_data(self, video_metrics: List[VideoMetrics], traffic_source: str = TrafficSources.BROWSE_FEATURES, **kwargs) -> List[Dict[str, Any]]:
        """Prepare first week performance data with daily breakdown"""
        # Get video IDs from metrics
        video_ids = [metrics.video_id for metrics in video_metrics]
        
        # Get day-by-day first week breakdown from database
        first_week_data = self.db.get_first_week_daily_breakdown(video_ids, traffic_source)
        
        # Combine with video info
        results = []
        for metrics in video_metrics:
            if metrics.video_id in first_week_data:
                data = first_week_data[metrics.video_id]
                # Calculate total first week views
                total_views = sum(data['daily_views'].values())
                
                result = {
                    'video_id': metrics.video_id,
                    'title': data['title'],
                    'published_date': data['published_date'],
                    'total_first_week_views': total_views,
                    'traffic_source': traffic_source
                }
                
                # Add individual day views
                for day in range(7):
                    result[f'day_{day}_views'] = data['daily_views'].get(day, 0)
                
                results.append(result)
        
        # Sort by total first week views descending
        results.sort(key=lambda x: x['total_first_week_views'], reverse=True)
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 50},
            {'name': 'Published', 'style': 'cyan', 'width': 10},
            {'name': 'Day 1', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Day 2', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Day 3', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Day 4', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Day 5', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Day 6', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Day 7', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Total', 'style': 'bright_green', 'justify': 'right', 'width': 8}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        from datetime import datetime
        published = datetime.strptime(row_data['published_date'], '%Y-%m-%d').strftime('%b %d')
        
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=48)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        return [
            f"{row_data['rank']}.",
            title_with_link,
            published,
            self.format_number(row_data['day_0_views']),
            self.format_number(row_data['day_1_views']),
            self.format_number(row_data['day_2_views']),
            self.format_number(row_data['day_3_views']),
            self.format_number(row_data['day_4_views']),
            self.format_number(row_data['day_5_views']),
            self.format_number(row_data['day_6_views']),
            self.format_number(row_data['total_first_week_views'])
        ]
    
    def get_report_title(self) -> str:
        # Override to include traffic source in title
        traffic_source = getattr(self, '_current_traffic_source', TrafficSources.BROWSE_FEATURES)
        if traffic_source.lower() == 'all':
            return "📊 FIRST WEEK TOTAL PERFORMANCE COMPARISON"
        else:
            return f"📊 FIRST WEEK {traffic_source.upper()} PERFORMANCE COMPARISON"
    
    def ensure_data_available(self, start_date: date, end_date: date, video_count: Optional[int] = None) -> List[str]:
        """Override to only fetch first week data for each video"""
        from datetime import timedelta
        
        if video_count is None:
            video_count = self.get_required_video_count()
        
        # Get 40 most recently published videos (not by performance)
        video_ids = self.fetcher.get_recent_published_videos(40)
        
        if not video_ids:
            return []
        
        # Take all 40 videos for analysis
        video_ids = video_ids[:40]
        
        # For each video, only ensure we have data for its first 7 days
        successful_videos = []
        for video_id in video_ids:
            # Get video info to find publish date
            video_info = self.db.get_video_info(video_id)
            if not video_info:
                video_info = self.fetcher.fetch_video_info(video_id)
                if video_info:
                    self.db.store_video_info(video_info)
            
            if video_info:
                # Only fetch first 7 days after publish
                first_week_end = video_info.published_date + timedelta(days=6)
                if self.fetcher.ensure_video_data(video_id, video_info.published_date, first_week_end):
                    successful_videos.append(video_id)
        
        return successful_videos

    def run_report(self, start_date, end_date, max_results=10, traffic_source=TrafficSources.BROWSE_FEATURES, **kwargs):
        """Override to store traffic source for title and use custom data fetching"""
        self._current_traffic_source = traffic_source
        kwargs['traffic_source'] = traffic_source
        
        try:
            # Custom data fetching for first week report
            self.console.print(f"[dim]Ensuring data is available for {self.get_report_title()}...[/dim]")
            video_ids = self.ensure_data_available(start_date, end_date, 40)
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found for {self.get_report_title()}[/yellow]")
                return False
            
            # Get metrics from database (we don't use the date range here since we want all data)
            video_metrics = []
            for video_id in video_ids:
                video_info = self.db.get_video_info(video_id)
                if video_info:
                    metrics = VideoMetrics(
                        video_info=video_info,
                        total_views=0,  # Not used in first week report
                        organic_views=0,  # Not used in first week report
                        search_views=0   # Not used in first week report
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
