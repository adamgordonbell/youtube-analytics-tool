"""Base class for all YouTube Analytics reports"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ..data import AnalyticsDatabase, VideoMetrics
from ..config import DEFAULT_MAX_RESULTS


class BaseReport(ABC):
    """Base class for all reports with automatic data fetching"""
    
    def __init__(self, db: Optional[AnalyticsDatabase] = None):
        self.db = db or AnalyticsDatabase()
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
        """Stubbed: Return existing videos from database (migration to fetcher2)"""
        # Return all videos from database, limit if requested
        all_videos = self.db.get_all_video_ids()
        if video_count and video_count < len(all_videos):
            return all_videos[:video_count]
        return all_videos
    
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
    

