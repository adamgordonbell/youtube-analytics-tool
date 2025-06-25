"""Spike detection report for identifying viral content and traffic bumps"""

from typing import List, Dict, Any, Optional
from datetime import date
import statistics

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class SpikeDetectionReport(BaseReport):
    """Report for detecting traffic spikes using 7-day moving averages"""
    
    def get_report_title(self) -> str:
        return "📈 TRAFFIC SPIKE DETECTION"
    
    def get_required_video_count(self) -> int:
        return 100  # We'll use all videos from database
    
    def calculate_moving_average(self, values: List[int], window: int = 7) -> List[float]:
        """Calculate moving average for a list of values"""
        if len(values) < window:
            return []
        
        moving_averages = []
        for i in range(window - 1, len(values)):
            window_values = values[i - window + 1:i + 1]
            avg = sum(window_values) / window
            moving_averages.append(avg)
        
        return moving_averages
    
    def detect_spikes(self, daily_data: List[Dict], window: int = 7, min_ratio: float = 2.0, max_spike_days: int = 7) -> Dict[str, Any]:
        """Detect multi-day spikes above moving average for a video"""
        if len(daily_data) < window + 1:  # Need at least window + 1 days for spike detection
            return {
                'max_spike_ratio': 0,
                'total_spike_absolute': 0,
                'spike_start_day': None,
                'spike_duration': 0,
                'peak_spike_views': 0,
                'peak_spike_day': None,
                'total_days_analyzed': len(daily_data)
            }
        
        # Sort by days since published to ensure proper order
        sorted_data = sorted(daily_data, key=lambda x: x['days_since_published'])
        daily_views = [d['views'] for d in sorted_data]
        
        # Calculate 7-day moving average
        moving_averages = self.calculate_moving_average(daily_views, window)
        
        best_total_spike_absolute = 0
        best_spike_info = {
            'max_spike_ratio': 0,
            'total_spike_absolute': 0,
            'spike_start_day': None,
            'spike_duration': 0,
            'peak_spike_views': 0,
            'peak_spike_day': None,
            'total_days_analyzed': len(daily_data)
        }
        
        # Find all potential spike periods
        i = 0
        while i < len(moving_averages):
            day_index = i + window - 1  # Actual index in daily_views
            current_views = daily_views[day_index]
            moving_avg = moving_averages[i]
            
            if moving_avg > 0 and current_views / moving_avg >= min_ratio:
                # Found start of a potential spike
                spike_start_day = sorted_data[day_index]['days_since_published']
                total_extra_views = 0
                spike_duration = 0
                peak_ratio = 0
                peak_views = 0
                peak_day = None
                
                # Follow the spike for up to max_spike_days
                for j in range(max_spike_days):
                    if i + j >= len(moving_averages):
                        break
                    
                    spike_day_index = (i + j) + window - 1
                    spike_views = daily_views[spike_day_index]
                    spike_moving_avg = moving_averages[i + j]
                    
                    if spike_moving_avg > 0 and spike_views >= spike_moving_avg:
                        # Still above moving average
                        extra_views = spike_views - spike_moving_avg
                        total_extra_views += extra_views
                        spike_duration += 1
                        
                        # Track peak within this spike period
                        spike_ratio = spike_views / spike_moving_avg
                        if spike_ratio > peak_ratio:
                            peak_ratio = spike_ratio
                            peak_views = spike_views
                            peak_day = sorted_data[spike_day_index]['days_since_published']
                    else:
                        # Spike ended
                        break
                
                # Check if this is the best spike we've found
                if total_extra_views > best_total_spike_absolute:
                    best_total_spike_absolute = total_extra_views
                    best_spike_info = {
                        'max_spike_ratio': peak_ratio,
                        'total_spike_absolute': total_extra_views,
                        'spike_start_day': spike_start_day,
                        'spike_duration': spike_duration,
                        'peak_spike_views': peak_views,
                        'peak_spike_day': peak_day,
                        'total_days_analyzed': len(daily_data)
                    }
                
                # Skip ahead past this spike to avoid overlapping
                i += spike_duration
            else:
                i += 1
        
        return best_spike_info
    
    def prepare_data(self, video_metrics: List[VideoMetrics], traffic_source: str = "organic", **kwargs) -> List[Dict[str, Any]]:
        """Prepare spike detection data"""
        # Get video IDs from metrics
        video_ids = [metrics.video_id for metrics in video_metrics]
        
        # Get daily views data for spike analysis
        daily_data = self.db.get_daily_views_for_spike_analysis(video_ids, traffic_source)
        
        results = []
        for metrics in video_metrics:
            if metrics.video_id in daily_data:
                data = daily_data[metrics.video_id]
                
                # Detect spikes for this video
                spike_info = self.detect_spikes(data['daily_data'])
                
                # Only include videos that have meaningful spike data
                if spike_info['max_spike_ratio'] >= 2.0:  # At least 2x spike above average
                    result = {
                        'video_id': metrics.video_id,
                        'title': data['title'],
                        'published_date': data['published_date'],
                        'traffic_source': traffic_source,
                        'is_short_format': metrics.video_info.is_short_format,
                        **spike_info
                    }
                    results.append(result)
        
        # Sort by total spike size (most cumulative extra views first)
        results.sort(key=lambda x: x['total_spike_absolute'], reverse=True)
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 4},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 45},
            {'name': 'Published', 'style': 'cyan', 'width': 10},
            {'name': 'Type', 'style': 'yellow', 'width': 5},
            {'name': 'Start Day', 'style': 'magenta', 'justify': 'right', 'width': 8},
            {'name': 'Duration', 'style': 'yellow', 'justify': 'right', 'width': 8},
            {'name': 'Total Extra', 'style': 'bright_green', 'justify': 'right', 'width': 10},
            {'name': 'Peak Ratio', 'style': 'bright_red', 'justify': 'right', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any]) -> List[str]:
        from datetime import datetime
        
        # Format published date 
        pub_date = datetime.strptime(row_data['published_date'], '%Y-%m-%d')
        published = pub_date.strftime('%b %Y')
        
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=43)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        # Determine content type
        content_type = "Short" if row_data.get('is_short_format') else "Long"
        
        # Format spike start day
        start_day_str = f"Day {row_data['spike_start_day']}" if row_data['spike_start_day'] else "N/A"
        
        # Format duration
        duration = row_data['spike_duration']
        if duration == 1:
            duration_str = "1 day"
        else:
            duration_str = f"{duration} days"
        
        # Format spike ratio
        spike_ratio = row_data['max_spike_ratio']
        if spike_ratio >= 10:
            spike_ratio_str = f"{spike_ratio:.1f}x"
        else:
            spike_ratio_str = f"{spike_ratio:.2f}x"
        
        return [
            f"{row_data['rank']}.",
            title_with_link,
            published,
            content_type,
            start_day_str,
            duration_str,
            self.format_number(int(row_data['total_spike_absolute'])),
            spike_ratio_str
        ]
    
    def get_report_title(self) -> str:
        # Override to include traffic source in title
        traffic_source = getattr(self, '_current_traffic_source', 'organic')
        if traffic_source.lower() == 'organic':
            return "📈 ORGANIC TRAFFIC SPIKE DETECTION"
        else:
            return f"📈 {traffic_source.upper()} TRAFFIC SPIKE DETECTION"
    
    def run_report(self, start_date, end_date, max_results=10, traffic_source="organic", **kwargs):
        """Override to use existing videos from database and store parameters for title"""
        self._current_traffic_source = traffic_source
        kwargs['traffic_source'] = traffic_source
        
        try:
            # Use all videos already in database (don't try to discover new ones)
            self.console.print(f"[dim]Analyzing {self.get_report_title()} from existing data...[/dim]")
            video_ids = self.db.get_all_video_ids()
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found in database for {self.get_report_title()}[/yellow]")
                return False
            
            # Get metrics from database
            video_metrics = []
            for video_id in video_ids:
                video_info = self.db.get_video_info(video_id)
                if video_info:
                    metrics = VideoMetrics(
                        video_info=video_info,
                        total_views=0,  # Not used in spike detection
                        organic_views=0,  # Not used in spike detection
                        search_views=0   # Not used in spike detection
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
