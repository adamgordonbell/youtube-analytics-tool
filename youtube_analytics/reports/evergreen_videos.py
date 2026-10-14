"""Evergreen videos report - current performance of older videos"""

from datetime import date, timedelta
from typing import List, Dict, Any

from .base_report import BaseReport
from ..data import VideoMetrics


class EvergreenVideosReport(BaseReport):
    """Report showing current traffic performance of evergreen videos (published long ago)"""
    
    def __init__(self, days_back=30, min_age_days=60, content_type="long", **kwargs):
        super().__init__(**kwargs)
        self.days_back = days_back  # How many recent days of traffic to analyze
        self.min_age_days = min_age_days  # Minimum age of videos to consider
        self.content_type = content_type.lower()  # "short", "long", or "all"
    
    def get_report_title(self) -> str:
        if self.content_type == "short":
            return f"🌲 EVERGREEN SHORTS - LAST {self.days_back} DAYS PERFORMANCE"
        elif self.content_type == "long":
            return f"🌲 EVERGREEN LONG VIDEOS - LAST {self.days_back} DAYS PERFORMANCE"
        else:
            return f"🌲 EVERGREEN VIDEOS - LAST {self.days_back} DAYS PERFORMANCE"
    
    def get_required_video_count(self) -> int:
        return 50  # Analyze more videos since we'll filter by publication date
    
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare evergreen videos data for display"""
        # Calculate the cutoff date for "evergreen" videos
        cutoff_date = date.today() - timedelta(days=self.min_age_days)
        
        # Filter for videos published before the cutoff date and by content type
        evergreen_data = []
        
        for metrics in video_metrics:
            if metrics.published_date and metrics.published_date <= cutoff_date:
                # Check content type filter
                if self.content_type != "all":
                    is_short = getattr(metrics.video_info, 'is_short_format', None)
                    # Convert to boolean (database stores as 1/0)
                    is_short = bool(is_short) if is_short is not None else False
                    
                    if self.content_type == "short" and not is_short:
                        continue
                    elif self.content_type == "long" and is_short:
                        continue
                
                # Calculate age in days
                age_days = (date.today() - metrics.published_date).days
                
                evergreen_data.append({
                    'video_id': metrics.video_id,
                    'title': metrics.title,
                    'published_date': metrics.published_date,
                    'age_days': age_days,
                    'organic_views': metrics.organic_views
                })
        
        # Sort by organic views descending (current performance)
        evergreen_data.sort(key=lambda x: x['organic_views'], reverse=True)
        return evergreen_data
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Organic Views', 'style': 'green', 'justify': 'right', 'width': 12},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 50},
            {'name': 'Age', 'style': 'yellow', 'justify': 'right', 'width': 8},
            {'name': 'Published', 'style': 'cyan', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=48)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        # Format age in days
        age_str = f"{row_data['age_days']}d"
        
        return [
            f"{row_data['rank']:2d}.",
            self.format_number(row_data['organic_views']),
            title_with_link,
            age_str,
            self.format_date(row_data['published_date'])
        ]
    
    def run_report(self, days_back=None, min_age_days=None, content_type=None, max_results=20, csv_file=None, **kwargs) -> bool:
        """Override to use existing videos from database (no API calls)"""
        if days_back is not None:
            self.days_back = days_back
        if min_age_days is not None:
            self.min_age_days = min_age_days
        if content_type is not None:
            self.content_type = content_type.lower()
        
        # Calculate date range for analysis (exclude last 2 days for data freshness)
        end_date = date.today() - timedelta(days=2)
        start_date = end_date - timedelta(days=self.days_back - 1)
        
        try:
            # Use all videos already in database (don't try to discover new ones)
            self.console.print(f"[dim]Analyzing {self.get_report_title()} from existing data...[/dim]")
            video_ids = self.db.get_all_video_ids()
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found in database for {self.get_report_title()}[/yellow]")
                return False
            
            # Get metrics from database for the specific date range with video info
            video_metrics = []
            for video_id in video_ids:
                video_info = self.db.get_video_info(video_id)
                if video_info:
                    # Get actual metrics for this video in the date range
                    period_metrics = self.db.get_video_metrics_for_period([video_id], start_date, end_date)
                    if period_metrics:
                        # Use the period metrics but attach the video_info
                        metrics = period_metrics[0]
                        metrics.video_info = video_info
                        video_metrics.append(metrics)
            
            if not video_metrics:
                self.console.print(f"[yellow]No metrics available for {self.get_report_title()}[/yellow]")
                return False
            
            # Display report
            self.display_report(video_metrics, start_date, end_date, max_results, csv_file=csv_file, **kwargs)
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error running {self.get_report_title()}: {e}[/red]")
            return False
