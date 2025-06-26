"""YouTube Studio-style traffic source breakdown report"""

from typing import List, Dict, Any
from datetime import date

from .base_report import BaseReport
from ..data import VideoMetrics


class TrafficBreakdownReport(BaseReport):
    """Report showing traffic breakdown in YouTube Studio style"""
    
    def get_report_title(self) -> str:
        return "📊 TRAFFIC SOURCE BREAKDOWN (YOUTUBE STUDIO STYLE)"
    
    def get_required_video_count(self) -> int:
        return 1  # This report is for specific videos
    
    def get_traffic_breakdown_for_video_date(self, video_id: str, target_date: date) -> Dict[str, Any]:
        """Get traffic breakdown for a specific video and date"""
        import sqlite3
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT traffic_source, views 
            FROM daily_metrics 
            WHERE video_id = ? AND date = ?
            ORDER BY views DESC
        ''', (video_id, target_date.strftime('%Y-%m-%d')))
        
        results = cursor.fetchall()
        conn.close()
        
        breakdown = {}
        total_views = 0
        
        for traffic_source, views in results:
            # Traffic sources are now already stored in Studio format
            breakdown[traffic_source] = breakdown.get(traffic_source, 0) + views
            total_views += views
        
        # Add percentages
        for category in breakdown:
            views = breakdown[category]
            percentage = (views / total_views * 100) if total_views > 0 else 0
            breakdown[category] = {
                'views': views,
                'percentage': percentage
            }
        
        return {
            'total_views': total_views,
            'breakdown': breakdown,
            'video_id': video_id,
            'date': target_date
        }
    
    def prepare_data(self, video_metrics: List[VideoMetrics], target_date: date = None, video_id: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Prepare traffic breakdown data"""
        if not target_date or not video_id:
            return []
        
        breakdown_data = self.get_traffic_breakdown_for_video_date(video_id, target_date)
        
        # Convert to list format for table display
        results = []
        breakdown = breakdown_data['breakdown']
        
        # Sort by views descending
        sorted_categories = sorted(breakdown.items(), key=lambda x: x[1]['views'], reverse=True)
        
        for category, data in sorted_categories:
            results.append({
                'category': category,
                'views': data['views'],
                'percentage': data['percentage']
            })
        
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Traffic Source', 'style': 'white', 'width': 25},
            {'name': 'Views', 'style': 'cyan', 'justify': 'right', 'width': 8},
            {'name': 'Percentage', 'style': 'yellow', 'justify': 'right', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        return [
            f"{row_data['rank']:2d}.",
            row_data['category'],
            self.format_number(row_data['views']),
            f"{row_data['percentage']:.1f}%"
        ]
    
    def run_traffic_breakdown(self, video_id: str, target_date: date) -> bool:
        """Run traffic breakdown for specific video and date"""
        try:
            # Get video info
            video_info = self.db.get_video_info(video_id)
            if not video_info:
                self.console.print(f"[red]Video {video_id} not found in database[/red]")
                return False
            
            # Get breakdown data from database
            breakdown_data = self.get_traffic_breakdown_for_video_date(video_id, target_date)
            
            if breakdown_data['total_views'] == 0:
                self.console.print(f"[yellow]No data available for {video_id} on {target_date}[/yellow]")
                self.console.print(f"[dim]Tip: Use --backfill-oldest-complete-history or --video-complete-history {video_id} to fetch data[/dim]")
                return False
            
            # Display header with video info
            self.console.print(f"\n[bold blue]📊 TRAFFIC SOURCE BREAKDOWN[/bold blue]")
            self.console.print(f"[bold white]Video:[/bold white] {video_info.title}")
            self.console.print(f"[bold white]Date:[/bold white] {target_date}")
            self.console.print(f"[bold white]Total Views:[/bold white] {breakdown_data['total_views']:,}")
            self.console.print()
            
            # Prepare and display table
            prepared_data = self.prepare_data([], target_date=target_date, video_id=video_id)
            
            if not prepared_data:
                self.console.print("[dim]No traffic data available[/dim]")
                return False
            
            # Create table
            from rich.table import Table
            from rich import box
            
            table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
            
            columns = self.get_table_columns()
            for col in columns:
                table.add_column(col['name'], style=col.get('style', 'white'), 
                               justify=col.get('justify', 'left'), width=col.get('width'))
            
            # Add rows
            for i, row_data in enumerate(prepared_data, 1):
                row_data['rank'] = i
                formatted_row = self.format_row(row_data)
                table.add_row(*formatted_row)
            
            self.console.print(table)
            self.console.print()
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error running traffic breakdown: {e}[/red]")
            return False
