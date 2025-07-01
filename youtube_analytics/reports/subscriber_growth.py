"""Subscriber Growth Report - Track subscriber growth/loss between dates"""

from datetime import date
from typing import List, Dict, Any, Optional

from .base_report import BaseReport
from ..data import AnalyticsDatabase


class SubscriberGrowthReport(BaseReport):
    """Report showing subscriber growth between two dates"""
    
    def __init__(self, db: Optional[AnalyticsDatabase] = None):
        super().__init__(db)
        self._subscriber_data = None
    
    def get_report_title(self) -> str:
        return "SUBSCRIBER GROWTH REPORT"
    
    def get_required_video_count(self) -> int:
        return 0  # This is a channel-level report, not video-specific
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Date', 'style': 'cyan', 'width': 12},
            {'name': 'Gained', 'style': 'green', 'justify': 'right', 'width': 10},
            {'name': 'Lost', 'style': 'red', 'justify': 'right', 'width': 10},
            {'name': 'Net Growth', 'style': 'bold', 'justify': 'right', 'width': 12},
            {'name': 'Cumulative', 'style': 'yellow', 'justify': 'right', 'width': 12},
            {'name': 'Videos Published', 'style': 'blue', 'justify': 'right', 'width': 16},
            {'name': 'Organic Views', 'style': 'magenta', 'justify': 'right', 'width': 14}
        ]
    
    def prepare_data(self, video_metrics, **kwargs) -> List[Dict[str, Any]]:
        """Prepare subscriber data for display"""
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if not self._subscriber_data:
            return []
        
        # Process daily subscriber data
        rows = []
        cumulative_change = 0
        
        # Create dicts for quick lookup of data by date
        organic_views_by_date = {}
        if hasattr(self, '_organic_views_data') and self._organic_views_data:
            for date_str, organic_views in self._organic_views_data:
                organic_views_by_date[date_str] = organic_views
        
        videos_published_by_date = {}
        if hasattr(self, '_videos_published_data') and self._videos_published_data:
            for date_str, video_count in self._videos_published_data:
                videos_published_by_date[date_str] = video_count
        
        for date_str, gained, lost in self._subscriber_data:
            net_growth = gained - lost
            cumulative_change += net_growth
            organic_views = organic_views_by_date.get(date_str, 0)
            videos_published = videos_published_by_date.get(date_str, 0)
            
            rows.append({
                'date': date_str,
                'gained': gained,
                'lost': lost,
                'net_growth': net_growth,
                'cumulative': cumulative_change,
                'videos_published': videos_published,
                'organic_views': organic_views
            })
        
        return rows
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Format a single row for display"""
        net_color = 'green' if row_data['net_growth'] >= 0 else 'red'
        cum_color = 'green' if row_data['cumulative'] >= 0 else 'red'
        
        return [
            self.format_date_str(row_data['date']),
            f"+{self.format_number(row_data['gained'])}",
            f"-{self.format_number(row_data['lost'])}",
            f"[{net_color}]{'+' if row_data['net_growth'] >= 0 else ''}{self.format_number(row_data['net_growth'])}[/{net_color}]",
            f"[{cum_color}]{'+' if row_data['cumulative'] >= 0 else ''}{self.format_number(row_data['cumulative'])}[/{cum_color}]",
            self.format_number(row_data['videos_published']),
            self.format_number(row_data['organic_views'])
        ]
    
    def fetch_subscriber_data(self, start_date: date, end_date: date) -> bool:
        """Fetch subscriber data from YouTube Analytics API"""
        from ..auth import YouTubeClientManager
        
        client_manager = YouTubeClientManager()
        analytics_client = client_manager.get_analytics_client()
        
        if not analytics_client:
            self.console.print("[red]Unable to get Analytics API client[/red]")
            return False
        
        try:
            response = analytics_client.reports().query(
                ids='channel==MINE',
                startDate=start_date.strftime('%Y-%m-%d'),
                endDate=end_date.strftime('%Y-%m-%d'),
                metrics='subscribersGained,subscribersLost',
                dimensions='day'
            ).execute()
            
            # Process response
            rows = response.get('rows', [])
            self._subscriber_data = []
            
            for row in rows:
                date_str = row[0]  # Day dimension
                gained = row[1]    # subscribersGained
                lost = row[2]      # subscribersLost
                self._subscriber_data.append((date_str, gained, lost))
            
            return True
            
        except Exception as e:
            if self.is_quota_exceeded_error(e):
                self.console.print("[yellow]Quota exceeded for Analytics API[/yellow]")
            else:
                self.console.print(f"[red]Error fetching subscriber data: {e}[/red]")
            return False
    
    def get_organic_views_from_db(self, start_date: date, end_date: date) -> bool:
        """Get daily organic views from database"""
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT 
                dm.date,
                SUM(CASE WHEN dm.traffic_source != 'Advertising' THEN dm.views ELSE 0 END) as organic_views
            FROM daily_metrics dm
            WHERE dm.date BETWEEN ? AND ?
            GROUP BY dm.date
            ORDER BY dm.date
            """
            
            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()
            self._organic_views_data = [(row[0], row[1]) for row in rows]
            
            conn.close()
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error getting organic views from database: {e}[/red]")
            self._organic_views_data = []
            return False
    
    def get_videos_published_from_db(self, start_date: date, end_date: date) -> bool:
        """Get daily video publication counts from database"""
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT 
                v.published_date,
                COUNT(*) as video_count
            FROM videos v
            WHERE v.published_date BETWEEN ? AND ?
            GROUP BY v.published_date
            ORDER BY v.published_date
            """
            
            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()
            self._videos_published_data = [(row[0], row[1]) for row in rows]
            
            conn.close()
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error getting videos published from database: {e}[/red]")
            self._videos_published_data = []
            return False
    
    def run_report(self, start_date: date, end_date: date, max_results: int = 100, **kwargs) -> bool:
        """Run the subscriber growth report"""
        try:
            self.console.print("[dim]Fetching subscriber data...[/dim]")
            
            # Fetch subscriber data
            if not self.fetch_subscriber_data(start_date, end_date):
                return False
            
            if not self._subscriber_data:
                self.console.print("[yellow]No subscriber data available for the specified period[/yellow]")
                return False
            
            self.console.print("[dim]Getting organic views from database...[/dim]")
            
            # Get organic views from database
            self.get_organic_views_from_db(start_date, end_date)
            
            self.console.print("[dim]Getting videos published from database...[/dim]")
            
            # Get videos published from database
            self.get_videos_published_from_db(start_date, end_date)
            
            # Display report  
            self.display_report([], start_date, end_date, max_results)
            
            # Show summary
            self._show_summary()
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error running {self.get_report_title()}: {e}[/red]")
            return False
    
    def _show_summary(self):
        """Show summary statistics"""
        if not self._subscriber_data:
            return
        
        total_gained = sum(row[1] for row in self._subscriber_data)
        total_lost = sum(row[2] for row in self._subscriber_data)
        net_growth = total_gained - total_lost
        
        total_organic_views = 0
        if hasattr(self, '_organic_views_data') and self._organic_views_data:
            total_organic_views = sum(row[1] for row in self._organic_views_data)
        
        total_videos_published = 0
        if hasattr(self, '_videos_published_data') and self._videos_published_data:
            total_videos_published = sum(row[1] for row in self._videos_published_data)
        
        growth_color = 'green' if net_growth >= 0 else 'red'
        
        self.console.print(f"[bold]Summary:[/bold]")
        self.console.print(f"Total Gained: [green]+{self.format_number(total_gained)}[/green]")
        self.console.print(f"Total Lost: [red]-{self.format_number(total_lost)}[/red]")
        self.console.print(f"Net Growth: [{growth_color}]{'+' if net_growth >= 0 else ''}{self.format_number(net_growth)}[/{growth_color}]")
        self.console.print(f"Total Videos Published: [blue]{self.format_number(total_videos_published)}[/blue]")
        self.console.print(f"Total Organic Views: [magenta]{self.format_number(total_organic_views)}[/magenta]")
        self.console.print()
    
    @staticmethod
    def format_date_str(date_str: str) -> str:
        """Format date string from API (YYYY-MM-DD) for display"""
        from datetime import datetime
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return date_obj.strftime("%b %d")
        except:
            return date_str
