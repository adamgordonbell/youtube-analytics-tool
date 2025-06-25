"""First 90 days search performance report"""

from typing import List, Dict, Any, Optional
from datetime import date

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class First90DaysSearchReport(BaseReport):
    """Report showing YouTube search performance in first 90 days after publication"""
    
    def get_report_title(self) -> str:
        return "🔍 FIRST 90 DAYS SEARCH PERFORMANCE"
    
    def get_required_video_count(self) -> int:
        return 50  # Look at more videos to find patterns
    
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare first 90 days search performance data"""
        # Get video IDs from metrics
        video_ids = [metrics.video_id for metrics in video_metrics]
        
        # Get 90-day search breakdown from database
        search_data = self.db.get_first_90_days_search(video_ids)
        
        # Combine with video info
        results = []
        for metrics in video_metrics:
            if metrics.video_id in search_data:
                data = search_data[metrics.video_id]
                
                result = {
                    'video_id': metrics.video_id,
                    'title': data['title'],
                    'published_date': data['published_date'],
                    'format_type': metrics.video_info.format_type,
                    'total_90_day_search': data['total_search_views'],
                    'week_1_search': data['week_breakdowns'].get(0, 0),
                    'week_2_search': data['week_breakdowns'].get(1, 0),
                    'week_3_search': data['week_breakdowns'].get(2, 0),
                    'week_4_search': data['week_breakdowns'].get(3, 0),
                    'weeks_5_8_search': sum(data['week_breakdowns'].get(w, 0) for w in range(4, 8)),
                    'weeks_9_13_search': sum(data['week_breakdowns'].get(w, 0) for w in range(8, 13))
                }
                
                results.append(result)
        
        # Sort by total 90-day search views descending
        results.sort(key=lambda x: x['total_90_day_search'], reverse=True)
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 35},
            {'name': 'Published', 'style': 'cyan', 'width': 8},
            {'name': 'Type', 'style': 'magenta', 'width': 7},
            {'name': 'Wk 1', 'style': 'green', 'justify': 'right', 'width': 5},
            {'name': 'Wk 2', 'style': 'green', 'justify': 'right', 'width': 5},
            {'name': 'Wk 3', 'style': 'green', 'justify': 'right', 'width': 5},
            {'name': 'Wk 4', 'style': 'green', 'justify': 'right', 'width': 5},
            {'name': 'Wks 5-8', 'style': 'yellow', 'justify': 'right', 'width': 7},
            {'name': 'Wks 9-13', 'style': 'yellow', 'justify': 'right', 'width': 8},
            {'name': '90d Total', 'style': 'bright_green', 'justify': 'right', 'width': 9}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        from datetime import datetime
        published = datetime.strptime(row_data['published_date'], '%Y-%m-%d').strftime('%b %d')
        
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=43)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        return [
            f"{row_data['rank']}.",
            title_with_link,
            published,
            row_data['format_type'],
            self.format_number(row_data['week_1_search']),
            self.format_number(row_data['week_2_search']),
            self.format_number(row_data['week_3_search']),
            self.format_number(row_data['week_4_search']),
            self.format_number(row_data['weeks_5_8_search']),
            self.format_number(row_data['weeks_9_13_search']),
            self.format_number(row_data['total_90_day_search'])
        ]
    
    def ensure_data_available(self, start_date: date, end_date: date, video_count: Optional[int] = None) -> List[str]:
        """Override - assume we have data from backfill, only fetch very recent days"""
        from datetime import timedelta
        
        # Get 50 most recently published videos  
        video_ids = self.fetcher.get_recent_published_videos(50)
        
        if not video_ids:
            return []
        
        # Only fetch very recent data (last 3 days) to keep current
        # Assume we have historical data from backfill operations
        today = date.today()
        recent_start = today - timedelta(days=3)
        
        # Quick sync for just recent days
        self.fetcher.ensure_videos_data(video_ids[:10], recent_start, today)
        
        return video_ids

    def run_report(self, start_date, end_date, max_results=10, **kwargs):
        """Override to use custom data fetching for 90-day search analysis"""
        try:
            # Custom data fetching for 90-day search report
            self.console.print(f"[dim]Ensuring data is available for {self.get_report_title()}...[/dim]")
            video_ids = self.ensure_data_available(start_date, end_date, 50)
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found for {self.get_report_title()}[/yellow]")
                return False
            
            # Get metrics from database
            video_metrics = []
            for video_id in video_ids:
                video_info = self.db.get_video_info(video_id)
                if video_info:
                    metrics = VideoMetrics(
                        video_info=video_info,
                        total_views=0,  # Not used in this report
                        organic_views=0,  # Not used in this report
                        search_views=0   # Not used in this report
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
