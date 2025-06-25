"""Base class for all YouTube Analytics reports"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ..data import AnalyticsDatabase, DataFetcher, VideoMetrics
from ..config import DEFAULT_MAX_RESULTS


class BaseReport(ABC):
    """Base class for all reports with automatic data fetching"""
    
    def __init__(self, db: Optional[AnalyticsDatabase] = None, fetcher: Optional[DataFetcher] = None):
        self.db = db or AnalyticsDatabase()
        self.fetcher = fetcher or DataFetcher(self.db)
        self.console = Console()
    
    @abstractmethod
    def get_report_title(self) -> str:
        """Return the report title for display"""
        pass
    
    @abstractmethod
    def get_required_video_count(self) -> int:
        """Return how many videos this report needs to analyze"""
        pass
    
    @abstractmethod
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare data for display. Return list of row dictionaries"""
        pass
    
    @abstractmethod
    def get_table_columns(self) -> List[Dict[str, str]]:
        """Return table column definitions as list of dicts with 'name', 'style', etc."""
        pass
    
    @abstractmethod
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Format a single row for display"""
        pass
    
    def ensure_data_available(self, start_date: date, end_date: date, video_count: Optional[int] = None) -> List[str]:
        """Ensure we have data for the required videos and date range with quota fallback"""
        if video_count is None:
            video_count = self.get_required_video_count()
        
        # Try to get video IDs from API for the period
        try:
            video_ids = self.fetcher.get_recent_videos_from_api(video_count * 2, (end_date - start_date).days)
            if not video_ids:
                self.console.print("[yellow]No videos found via API, falling back to database videos[/yellow]")
                db_videos = self.db.get_recent_videos(video_count * 2)
                video_ids = db_videos[:video_count] if db_videos else []
        except Exception as e:
            if self.is_quota_exceeded_error(e):
                self.console.print("[yellow]API quota exceeded. Using recent videos from database instead.[/yellow]")
                db_videos = self.db.get_recent_videos(video_count * 2)
                video_ids = db_videos[:video_count] if db_videos else []
            else:
                self.console.print(f"[red]Error fetching videos from API: {e}[/red]")
                self.console.print("[yellow]Falling back to database videos[/yellow]")
                db_videos = self.db.get_recent_videos(video_count * 2)
                video_ids = db_videos[:video_count] if db_videos else []
        
        if not video_ids:
            return []
        
        # Take the top videos we need
        video_ids = video_ids[:video_count]
        
        # Ensure we have data for these videos (quota-aware)
        try:
            successful_videos = self.fetcher.ensure_videos_data(video_ids, start_date, end_date)
        except Exception as e:
            if self.is_quota_exceeded_error(e):
                self.console.print("[yellow]API quota exceeded during data fetching. Using existing data only.[/yellow]")
                # Return videos that exist in database
                successful_videos = [v for v in video_ids if v in self.db.get_all_video_ids()]
            else:
                self.console.print(f"[red]Error ensuring video data: {e}[/red]")
                successful_videos = [v for v in video_ids if v in self.db.get_all_video_ids()]
        
        return successful_videos
    
    def run_report(self, start_date: date, end_date: date, max_results: int = DEFAULT_MAX_RESULTS, **kwargs) -> bool:
        """Run the complete report with data fetching and display"""
        try:
            # Ensure data is available
            self.console.print(f"[dim]Ensuring data is available for {self.get_report_title()}...[/dim]")
            video_ids = self.ensure_data_available(start_date, end_date, max_results * 2)
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found for {self.get_report_title()}[/yellow]")
                return False
            
            # Get metrics from database
            video_metrics = self.db.get_video_metrics_for_period(video_ids, start_date, end_date)
            
            if not video_metrics:
                self.console.print(f"[yellow]No metrics available for {self.get_report_title()}[/yellow]")
                return False
            
            # Prepare and display report
            self.display_report(video_metrics, start_date, end_date, max_results, **kwargs)
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error running {self.get_report_title()}: {e}[/red]")
            return False
    
    def display_report(self, video_metrics: List[VideoMetrics], start_date: date, end_date: date, max_results: int, **kwargs):
        """Display the formatted report"""
        # Header
        title = self.get_report_title()
        # Don't show date range for first week reports since they show recent videos
        if "FIRST WEEK" in title:
            self.console.print(Panel(f"[bold blue]{title}[/bold blue]", 
                                    box=box.ROUNDED, style="blue"))
        else:
            subtitle = f"{start_date} to {end_date}"
            self.console.print(Panel(f"[bold blue]{title}[/bold blue]\n[dim]{subtitle}[/dim]", 
                                    box=box.ROUNDED, style="blue"))
        
        # Prepare data
        prepared_data = self.prepare_data(video_metrics, **kwargs)
        
        if not prepared_data:
            self.console.print("[dim]No data available for this report[/dim]")
            return
        
        # Limit results
        prepared_data = prepared_data[:max_results]
        
        # Create table
        table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
        
        # Add columns
        columns = self.get_table_columns()
        for col in columns:
            table.add_column(col['name'], style=col.get('style', 'white'), 
                           justify=col.get('justify', 'left'), width=col.get('width'))
        
        # Add rows
        for i, row_data in enumerate(prepared_data, 1):
            row_data['rank'] = i  # Add rank for convenience
            formatted_row = self.format_row(row_data)
            table.add_row(*formatted_row)
        
        self.console.print(table)
        self.console.print()
    
    @staticmethod
    def truncate_title(title: str, max_length: int = 40) -> str:
        """Truncate video title for display"""
        if len(title) <= max_length:
            return title
        return title[:max_length-3] + "..."
    
    @staticmethod
    def format_date(date_obj: date) -> str:
        """Format date for display"""
        return date_obj.strftime("%b %d")
    
    @staticmethod
    def format_number(number: int) -> str:
        """Format number with thousands separator"""
        return f"{number:,}"
    
    def is_quota_exceeded_error(self, error) -> bool:
        """Check if an error is due to quota being exceeded"""
        # Convert error to string to check content
        error_str = str(error).lower()
        
        # Check for quota exceeded in error message
        if 'quota' in error_str and 'exceeded' in error_str:
            return True
            
        # Check for specific HTTP 403 quota errors
        if hasattr(error, 'resp') and hasattr(error, 'content'):
            if error.resp.status == 403:
                error_content = str(error.content) if error.content else ""
                return 'quota' in error_content.lower() and 'exceeded' in error_content.lower()
                
        return False
    
    def ensure_comprehensive_data_available(self, days: int) -> List[str]:
        """Generic backfill for N days after publication with quota fallback"""
        from datetime import timedelta, date
        
        # Try to get ALL videos ever published (not just recent ones)
        try:
            video_ids = self.fetcher.get_all_published_videos()
            if not video_ids:
                self.console.print("[yellow]No new videos discovered, falling back to existing database videos[/yellow]")
                return self.db.get_all_video_ids()
        except Exception as e:
            if self.is_quota_exceeded_error(e):
                self.console.print("[yellow]API quota exceeded. Using existing videos from database instead of discovering new ones.[/yellow]")
                return self.db.get_all_video_ids()
            else:
                self.console.print(f"[red]Error discovering videos: {e}[/red]")
                self.console.print("[yellow]Falling back to existing database videos[/yellow]")
                return self.db.get_all_video_ids()
        
        self.console.print(f"[dim]Found {len(video_ids)} total videos. Backfilling {days}-day historical data...[/dim]")
        
        # Backfill all historical data for all videos (quota-aware)
        # This will ensure we have complete N-day data for every video
        successful_videos = []
        quota_exceeded = False
        
        for i, video_id in enumerate(video_ids):
            if i % 10 == 0:  # Progress indicator
                self.console.print(f"[dim]Processing video {i+1}/{len(video_ids)}...[/dim]")
            
            # Get video info to find publish date
            video_info = self.db.get_video_info(video_id)
            if not video_info and not quota_exceeded:
                try:
                    video_info = self.fetcher.fetch_video_info(video_id)
                    if video_info:
                        self.db.store_video_info(video_info)
                except Exception as e:
                    if self.is_quota_exceeded_error(e):
                        self.console.print("[yellow]API quota exceeded during video info fetching. Continuing with database-only analysis.[/yellow]")
                        quota_exceeded = True
                        # Still add video to successful list if we have basic info
                        if video_id in self.db.get_all_video_ids():
                            successful_videos.append(video_id)
                        continue
            
            if video_info:
                # Ensure we have full N days of data after publish date (but not beyond today)
                end_date = video_info.published_date + timedelta(days=days-1)
                actual_end = min(end_date, date.today())  # Don't fetch future data
                
                try:
                    if not quota_exceeded and self.fetcher.ensure_video_data(video_id, video_info.published_date, actual_end):
                        successful_videos.append(video_id)
                    elif quota_exceeded:
                        # Just add to successful list if we have the video in database
                        successful_videos.append(video_id)
                except Exception as e:
                    if self.is_quota_exceeded_error(e):
                        if not quota_exceeded:
                            self.console.print("[yellow]API quota exceeded during data fetching. Continuing with existing data.[/yellow]")
                            quota_exceeded = True
                        successful_videos.append(video_id)  # Still include in analysis
            elif video_id in self.db.get_all_video_ids():
                # Video exists in database even without detailed info
                successful_videos.append(video_id)
        
        self.console.print(f"[green]Successfully backfilled data for {len(successful_videos)} videos.[/green]")
        return successful_videos
