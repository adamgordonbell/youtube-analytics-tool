"""First 90 days traffic performance report"""

from typing import List, Dict, Any, Optional
from datetime import date

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class First90DaysTrafficReport(BaseReport):
    """Report showing traffic performance in first 90 days after publication"""
    
    def get_report_title(self) -> str:
        # Override to include traffic source in title
        traffic_source = getattr(self, '_current_traffic_source', 'YouTube search')
        if traffic_source.lower() == 'all':
            return "📊 FIRST 90 DAYS TOTAL TRAFFIC PERFORMANCE"
        elif traffic_source.lower() == 'organic':
            return "🌱 FIRST 90 DAYS ORGANIC TRAFFIC PERFORMANCE"
        else:
            return f"📊 FIRST 90 DAYS {traffic_source.upper()} PERFORMANCE"
    
    def get_required_video_count(self) -> int:
        return None  # Analyze ALL videos ever published
    
    def prepare_data(self, video_metrics: List[VideoMetrics], traffic_source: str = 'YouTube search', **kwargs) -> List[Dict[str, Any]]:
        """Prepare first 90 days traffic performance data"""
        # Get video IDs from metrics
        video_ids = [metrics.video_id for metrics in video_metrics]
        
        # Get 90-day traffic breakdown from database
        traffic_data = self.db.get_first_90_days_traffic(video_ids, traffic_source)
        
        # Combine with video info
        results = []
        for metrics in video_metrics:
            if metrics.video_id in traffic_data:
                data = traffic_data[metrics.video_id]
                
                result = {
                    'video_id': metrics.video_id,
                    'title': data['title'],
                    'published_date': data['published_date'],
                    'format_type': metrics.video_info.format_type,
                    'total_90_day_traffic': data['total_traffic_views'],
                    'week_1_traffic': data['week_breakdowns'].get(0, 0),
                    'week_2_traffic': data['week_breakdowns'].get(1, 0),
                    'week_3_traffic': data['week_breakdowns'].get(2, 0),
                    'week_4_traffic': data['week_breakdowns'].get(3, 0),
                    'weeks_5_8_traffic': sum(data['week_breakdowns'].get(w, 0) for w in range(4, 8)),
                    'weeks_9_13_traffic': sum(data['week_breakdowns'].get(w, 0) for w in range(8, 13)),
                    'traffic_source': traffic_source
                }
                
                results.append(result)
        
        # Sort by total 90-day traffic views descending
        results.sort(key=lambda x: x['total_90_day_traffic'], reverse=True)
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 60},
            {'name': 'Published', 'style': 'cyan', 'width': 12},
            {'name': 'Type', 'style': 'magenta', 'width': 8},
            {'name': 'Wk 1', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Wk 2', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Wk 3', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Wk 4', 'style': 'green', 'justify': 'right', 'width': 6},
            {'name': 'Wks 5-8', 'style': 'yellow', 'justify': 'right', 'width': 8},
            {'name': 'Wks 9-13', 'style': 'yellow', 'justify': 'right', 'width': 9},
            {'name': '90d Total', 'style': 'bright_green', 'justify': 'right', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        from datetime import datetime
        published = datetime.strptime(row_data['published_date'], '%Y-%m-%d').strftime('%b %d %Y')
        
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=43)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        return [
            f"{row_data['rank']}.",
            title_with_link,
            published,
            row_data['format_type'],
            self.format_number(row_data['week_1_traffic']),
            self.format_number(row_data['week_2_traffic']),
            self.format_number(row_data['week_3_traffic']),
            self.format_number(row_data['week_4_traffic']),
            self.format_number(row_data['weeks_5_8_traffic']),
            self.format_number(row_data['weeks_9_13_traffic']),
            self.format_number(row_data['total_90_day_traffic'])
        ]
    


    def run_report(self, start_date, end_date, max_results=10, traffic_source='YouTube search', **kwargs):
        """Override to use custom data fetching for 90-day traffic analysis"""
        self._current_traffic_source = traffic_source
        kwargs['traffic_source'] = traffic_source
        
        # Check if max_videos was passed from CLI (takes precedence over max_results)
        if 'max_videos' in kwargs:
            max_results = kwargs['max_videos']
        
        try:
            # Custom data fetching for 90-day traffic report - ALL VIDEOS
            self.console.print(f"[dim]Ensuring comprehensive historical data is available for {self.get_report_title()}...[/dim]")
            video_ids = self.ensure_data_available(start_date, end_date, None)
            
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
