"""Shorts Detection Report using duration-based detection"""

from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .base_report import BaseReport
from ..data import AnalyticsDatabase, DataFetcher, VideoMetrics
from ..utils import is_video_short, get_video_type_label, get_video_type_emoji, format_duration


class ShortsDetectionReport(BaseReport):
    """Report to detect which videos are Shorts using duration-based detection (≤60 seconds)"""
    
    def get_report_title(self) -> str:
        """Return the report title for display"""
        return "🎬 SHORTS DETECTION REPORT"
    
    def get_required_video_count(self) -> int:
        """Return how many videos this report needs to analyze"""
        return 50  # Analyze more videos to find Shorts
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        """Return table column definitions"""
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title', 'style': 'white', 'width': 40},
            {'name': 'Date', 'style': 'cyan', 'width': 8},
            {'name': 'Duration', 'style': 'yellow', 'justify': 'right', 'width': 8},
            {'name': 'Views', 'style': 'green', 'justify': 'right'},
            {'name': 'Type', 'style': 'blue', 'width': 8}
        ]
    
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare data for display using video info from database"""
        if not video_metrics:
            return []
        
        prepared_data = []
        
        for metrics in video_metrics:
            video_info = self.db.get_video_info(metrics.video_id)
            if not video_info or video_info.duration_seconds is None:
                continue  # Skip videos without duration data
            
            # Use our reliable duration-based detection
            is_short = is_video_short(video_info.duration_seconds)
            
            prepared_data.append({
                'video_id': metrics.video_id,
                'title': self.truncate_title(video_info.title, 40),
                'date': self.format_date(video_info.published_date),
                'duration': video_info.duration_seconds,
                'views': metrics.total_views,
                'is_short': is_short
            })
        
        # Sort by whether it's a Short first, then by views
        prepared_data.sort(key=lambda x: (not x['is_short'], -x['views']))
        
        return prepared_data
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Format a single row for display"""
        emoji = get_video_type_emoji(row_data['duration'])
        type_label = get_video_type_label(row_data['duration'])
        duration_str = format_duration(row_data['duration'])
        
        return [
            f"{row_data['rank']}.",
            row_data['title'],
            row_data['date'],
            duration_str,
            f"{row_data['views']:,}",
            f"{emoji} {type_label}"
        ]
    

    
    def display_report(self, video_metrics: List[VideoMetrics], start_date: date, end_date: date, max_results: int, **kwargs):
        """Display the formatted report with enhanced summary"""
        # Call parent method to display main report
        super().display_report(video_metrics, start_date, end_date, max_results, **kwargs)
        
        # Add enhanced summary for Shorts analysis
        if video_metrics:
            prepared_data = self.prepare_data(video_metrics, **kwargs)
            
            if prepared_data:
                shorts_count = sum(1 for data in prepared_data if data['is_short'])
                total_count = len(prepared_data)
                regular_count = total_count - shorts_count
                
                # Calculate view statistics
                shorts_views = sum(data['views'] for data in prepared_data if data['is_short'])
                total_views = sum(data['views'] for data in prepared_data)
                
                self.console.print(Panel(
                    f"[bold white]Analysis Summary:[/bold white]\n"
                    f"🎬 [bold yellow]Shorts:[/bold yellow] {shorts_count} videos ({shorts_count/total_count*100:.1f}%)\n"
                    f"📺 [bold blue]Regular Videos:[/bold blue] {regular_count} videos ({regular_count/total_count*100:.1f}%)\n\n"
                    f"👀 [bold green]Shorts Views:[/bold green] {shorts_views:,} ({shorts_views/total_views*100:.1f}% of total views)\n"
                    f"[dim]Detection method: Duration-based (≤3 minutes = Short)[/dim]",
                    style="green",
                    box=box.ROUNDED,
                    title="🎬 Shorts Analysis"
                ))
    
    def get_shorts_list(self, start_date: date, end_date: date) -> List[Tuple[str, bool]]:
        """
        Get a list of video IDs that are Shorts
        
        Returns:
            List of tuples (video_id, is_short)
        """
        # Get video IDs from the period
        video_ids = self.ensure_data_available(start_date, end_date, 100)
        
        shorts_list = []
        for video_id in video_ids:
            video_info = self.db.get_video_info(video_id)
            if video_info and video_info.duration_seconds is not None:
                is_short = is_video_short(video_info.duration_seconds)
                shorts_list.append((video_id, is_short))
        
        # Sort by whether it's a Short first
        shorts_list.sort(key=lambda x: not x[1])
        
        return shorts_list
