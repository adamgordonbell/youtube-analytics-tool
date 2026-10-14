"""First N Days Traffic Source Breakdown Report"""

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import sqlite3

from .base_report import BaseReport
from ..data import VideoMetrics


class FirstNDaysTrafficBreakdownReport(BaseReport):
    """Report showing traffic source breakdown for first N days of each video"""
    
    def __init__(self, days: int = 7, **kwargs):
        super().__init__(**kwargs)
        self.days = days
    
    def get_report_title(self) -> str:
        return f"📊 FIRST {self.days} DAYS TRAFFIC SOURCE BREAKDOWN"
    
    def get_required_video_count(self) -> int:
        return 50  # Analyze more videos since we'll aggregate
    
    def prepare_data(self, video_metrics: List[VideoMetrics], **kwargs) -> List[Dict[str, Any]]:
        """Prepare traffic source breakdown data for display"""
        breakdown_data = []
        
        # Get all videos from database instead of using video_metrics which is filtered by date range
        all_video_ids = self.db.get_all_video_ids()
        
        # Get traffic source breakdown for each video
        for video_id in all_video_ids:
            video_info = self.db.get_video_info(video_id)
            if not video_info or not video_info.published_date:
                continue
                
            # Calculate first N days date range for this video
            start_date = video_info.published_date
            end_date = start_date + timedelta(days=self.days - 1)
            
            # Get traffic breakdown from database
            traffic_breakdown = self._get_video_traffic_breakdown(
                video_id, start_date, end_date
            )
            
            if traffic_breakdown and traffic_breakdown['total'] > 0:
                breakdown_data.append({
                    'video_id': video_id,
                    'title': video_info.title,
                    'published_date': video_info.published_date,
                    'video_info': video_info,
                    **traffic_breakdown
                })
        
        # Sort by total views descending
        breakdown_data.sort(key=lambda x: x['total'], reverse=True)
        return breakdown_data
    
    def _get_video_traffic_breakdown(self, video_id: str, start_date: date, end_date: date) -> Optional[Dict[str, int]]:
        """Get traffic source breakdown for a specific video and date range"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            # Query to get traffic breakdown with proper aggregation
            cursor.execute('''
                SELECT 
                    traffic_source,
                    SUM(views) as views
                FROM daily_metrics 
                WHERE video_id = ? 
                    AND date BETWEEN ? AND ?
                GROUP BY traffic_source
            ''', (video_id, start_date.isoformat(), end_date.isoformat()))
            
            rows = cursor.fetchall()
            
            # Initialize all traffic sources to 0
            breakdown = {
                'external': 0,
                'direct': 0,
                'search': 0,
                'browse': 0,
                'suggested': 0,
                'channel': 0,
                'playlists': 0,
                'other': 0,
                'notifications': 0,
                'endscreens': 0,
                'shorts': 0,
                'advertising': 0,
                'total': 0
            }
            
            # Map traffic sources to our breakdown columns
            traffic_mapping = {
                'External': 'external',
                'Direct or unknown': 'direct', 
                'YouTube search': 'search',
                'Browse features': 'browse',
                'Suggested videos': 'suggested',
                'Channel pages': 'channel',
                'Playlists': 'playlists',
                'Other YouTube features': 'other',
                'Notifications': 'notifications',
                'End screens': 'endscreens',
                'Shorts': 'shorts',
                'Advertising': 'advertising'
            }
            
            # Populate breakdown from query results
            for traffic_source, views in rows:
                mapped_key = traffic_mapping.get(traffic_source, 'other')
                breakdown[mapped_key] += views
                # Only add to total if it's not advertising
                if traffic_source != 'Advertising':
                    breakdown['total'] += views
            
            return breakdown
            
        except Exception as e:
            print(f"Error getting traffic breakdown for {video_id}: {e}")
            return None
        finally:
            conn.close()
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 40},
            {'name': 'Published', 'style': 'cyan', 'width': 10},
            {'name': 'Type', 'style': 'magenta', 'width': 5},
            {'name': 'External', 'style': 'blue', 'justify': 'right', 'width': 8},
            {'name': 'Direct', 'style': 'green', 'justify': 'right', 'width': 8},
            {'name': 'Search', 'style': 'yellow', 'justify': 'right', 'width': 8},
            {'name': 'Browse', 'style': 'cyan', 'justify': 'right', 'width': 8},
            {'name': 'Suggested', 'style': 'magenta', 'justify': 'right', 'width': 8},
            {'name': 'Channel', 'style': 'red', 'justify': 'right', 'width': 8},
            {'name': 'Playlists', 'style': 'blue', 'justify': 'right', 'width': 8},
            {'name': 'Other', 'style': 'dim', 'justify': 'right', 'width': 6},
            {'name': 'Notify', 'style': 'dim', 'justify': 'right', 'width': 6},
            {'name': 'End', 'style': 'dim', 'justify': 'right', 'width': 5},
            {'name': 'Total', 'style': 'bold white', 'justify': 'right', 'width': 8}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=35)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        # Determine video type
        video_type = "Short" if (row_data.get('video_info') and 
                                getattr(row_data['video_info'], 'is_short_format', False)) else "Long"
        
        return [
            f"{row_data['rank']:2d}.",
            title_with_link,
            row_data['published_date'].strftime("%Y-%m-%d"),
            video_type,
            self.format_number(row_data['external']),
            self.format_number(row_data['direct']),
            self.format_number(row_data['search']),
            self.format_number(row_data['browse']),
            self.format_number(row_data['suggested']),
            self.format_number(row_data['channel']),
            self.format_number(row_data['playlists']),
            self.format_number(row_data['other']),
            self.format_number(row_data['notifications']),
            self.format_number(row_data['endscreens']),
            f"[bold]{self.format_number(row_data['total'])}[/bold]"
        ]
