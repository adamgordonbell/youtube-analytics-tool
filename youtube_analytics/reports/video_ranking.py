"""Video performance ranking report - shows where a specific video ranks vs all others"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta

from .base_report import BaseReport
from ..data import VideoMetrics
from ..config import TrafficSources


class VideoRankingReport(BaseReport):
    """Report showing where a specific video ranks vs all others for same time period"""
    
    def get_report_title(self) -> str:
        return "📊 VIDEO PERFORMANCE RANKING"
    
    def get_required_video_count(self) -> int:
        return 100  # We'll use all videos from database
    
    def calculate_days_since_published(self, video_id: str) -> int:
        """Calculate days since video was published (excluding today)"""
        video_info = self.db.get_video_info(video_id)
        if not video_info:
            return 0
        
        today = date.today()
        published_date = video_info.published_date
        days_since = (today - published_date).days
        
        # Exclude today - we want complete days only
        return max(0, days_since)
    
    def get_video_ranking_for_traffic_source(self, video_id: str, days: int, traffic_source: str) -> Dict[str, Any]:
        """Get ranking of all videos for specific traffic source and time period"""
        # Get all video IDs
        all_video_ids = self.db.get_all_video_ids()
        
        if not all_video_ids:
            return {
                'rankings': [],
                'target_position': None,
                'total_videos': 0,
                'traffic_source': traffic_source,
                'days': days
            }
        
        # Get performance data for all videos for this time period
        performance_data = self.db.get_first_n_days_total(all_video_ids, days, traffic_source, start_day=0)
        
        # Convert to list with video info
        rankings = []
        for vid_id in all_video_ids:
            if vid_id in performance_data:
                data = performance_data[vid_id]
                video_info = self.db.get_video_info(vid_id)
                if video_info:
                    rankings.append({
                        'video_id': vid_id,
                        'title': data['title'],
                        'published_date': data['published_date'],
                        'views': data['total_views'],
                        'is_short_format': video_info.is_short_format
                    })
        
        # Sort by views (highest first)
        rankings.sort(key=lambda x: x['views'], reverse=True)
        
        # Add rank numbers
        for i, ranking in enumerate(rankings):
            ranking['rank'] = i + 1
        
        # Find target video position
        target_position = None
        for i, ranking in enumerate(rankings):
            if ranking['video_id'] == video_id:
                target_position = i + 1
                break
        
        return {
            'rankings': rankings,
            'target_position': target_position,
            'total_videos': len(rankings),
            'traffic_source': traffic_source,
            'days': days
        }
    
    def prepare_data(self, video_metrics: List[VideoMetrics], video_id: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Prepare ranking data for multiple traffic sources"""
        if not video_id:
            # Default to most recent video
            recent_videos = self.db.get_recent_videos(1)
            if not recent_videos:
                return []
            video_id = recent_videos[0]
        
        # Calculate days since published
        days = self.calculate_days_since_published(video_id)
        if days <= 0:
            return []
        
        # Get target video info
        target_video = self.db.get_video_info(video_id)
        if not target_video:
            return []
        
        # Traffic sources to analyze
        traffic_sources = ["Browse features", "YouTube search", "External"]
        
        results = []
        for traffic_source in traffic_sources:
            ranking_data = self.get_video_ranking_for_traffic_source(video_id, days, traffic_source)
            ranking_data['target_video_title'] = target_video.title
            ranking_data['target_video_id'] = video_id
            results.append(ranking_data)
        
        return results
    
    def get_table_columns(self) -> List[Dict[str, str]]:
        return [
            {'name': 'Rank', 'style': 'dim', 'width': 5},
            {'name': 'Title & Studio Link', 'style': 'white', 'width': 55},
            {'name': 'Published', 'style': 'cyan', 'width': 10},
            {'name': 'Type', 'style': 'yellow', 'width': 5},
            {'name': 'Views', 'style': 'bright_green', 'justify': 'right', 'width': 10}
        ]
    
    def format_row(self, row_data: Dict[str, Any], is_target: bool = False) -> List[str]:
        from datetime import datetime
        
        # Format published date
        pub_date = datetime.strptime(row_data['published_date'], '%Y-%m-%d')
        published = pub_date.strftime('%b %Y')
        
        # Create multi-line title with YouTube Studio link
        title = self.truncate_title(row_data['title'], max_length=53)
        studio_url = f"https://studio.youtube.com/video/{row_data['video_id']}/"
        title_with_link = f"{title}\n[dim blue]{studio_url}[/dim blue]"
        
        # Determine content type
        content_type = "Short" if row_data.get('is_short_format') else "Long"
        
        # Format rank with highlighting for target video
        rank_str = f"{row_data['rank']}."
        if is_target:
            rank_str = f"[bold bright_yellow]► {rank_str} ◄[/bold bright_yellow]"
            title_with_link = f"[bold]{title_with_link}[/bold]"
        
        return [
            rank_str,
            title_with_link,
            published,
            content_type,
            self.format_number(row_data['views'])
        ]
    
    def display_traffic_source_ranking(self, ranking_data: Dict[str, Any], max_results: int = 10):
        """Display ranking for a single traffic source"""
        target_position = ranking_data['target_position']
        total_videos = ranking_data['total_videos']
        traffic_source = ranking_data['traffic_source']
        days = ranking_data['days']
        target_title = ranking_data['target_video_title']
        target_video_id = ranking_data['target_video_id']
        
        # Display header with ranking summary
        if target_position:
            self.console.print(f"\n[bold bright_cyan]📊 {traffic_source.upper()} TRAFFIC - FIRST {days} DAYS[/bold bright_cyan]")
            self.console.print(f"[dim]Target: \"{target_title}\" ranks #{target_position} of {total_videos} videos[/dim]\n")
        else:
            self.console.print(f"\n[bold bright_cyan]📊 {traffic_source.upper()} TRAFFIC - FIRST {days} DAYS[/bold bright_cyan]")
            self.console.print(f"[dim]Target video not found in rankings[/dim]\n")
            return
        
        # Show rankings around the target video
        rankings = ranking_data['rankings']
        
        # Calculate range to show (show some context around target)
        start_idx = max(0, target_position - 6)  # Show 5 above target
        end_idx = min(len(rankings), target_position + 5)  # Show 4 below target
        
        # Always show top 3 if target is not in top 10
        if target_position > 10:
            # Show top 3, then gap, then context around target
            display_rankings = rankings[:3]
            if start_idx > 3:
                # Add separator
                display_rankings.append({
                    'rank': '...',
                    'title': '...',
                    'video_id': 'separator',
                    'published_date': '1970-01-01',
                    'views': 0,
                    'is_short_format': False
                })
            display_rankings.extend(rankings[start_idx:end_idx])
        else:
            # Target is in top 10, just show top results
            display_rankings = rankings[:max_results]
        
        # Create and display table
        from rich.table import Table
        table = Table(show_header=True, header_style="bold bright_white")
        
        columns = self.get_table_columns()
        for col in columns:
            table.add_column(
                col['name'],
                style=col.get('style', 'white'),
                justify=col.get('justify', 'left'),
                width=col.get('width')
            )
        
        for ranking in display_rankings:
            if ranking['video_id'] == 'separator':
                table.add_row('...', '...', '...', '...', '...')
            else:
                is_target = ranking['video_id'] == target_video_id
                row = self.format_row(ranking, is_target=is_target)
                table.add_row(*row)
        
        self.console.print(table)
    
    def run_report(self, start_date, end_date, max_results=10, video_id=None, **kwargs):
        """Override to display multiple traffic source rankings"""
        try:
            # Use all videos already in database
            self.console.print(f"[dim]Analyzing video performance rankings from existing data...[/dim]")
            video_ids = self.db.get_all_video_ids()
            
            if not video_ids:
                self.console.print(f"[yellow]No videos found in database[/yellow]")
                return False
            
            # Get metrics (not really used, but required by base class)
            video_metrics = []
            for vid_id in video_ids[:10]:  # Just need a few for interface
                video_info = self.db.get_video_info(vid_id)
                if video_info:
                    metrics = VideoMetrics(
                        video_info=video_info,
                        total_views=0,
                        organic_views=0,
                        search_views=0
                    )
                    video_metrics.append(metrics)
            
            if not video_metrics:
                self.console.print(f"[yellow]No metrics available[/yellow]")
                return False
            
            # Prepare ranking data for all traffic sources
            ranking_results = self.prepare_data(video_metrics, video_id=video_id, **kwargs)
            
            if not ranking_results:
                self.console.print(f"[yellow]Could not prepare ranking data[/yellow]")
                return False
            
            # Display header
            self.console.print(f"\n[bold bright_white]{self.get_report_title()}[/bold bright_white]")
            
            # Display each traffic source ranking
            for ranking_data in ranking_results:
                self.display_traffic_source_ranking(ranking_data, max_results)
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error running {self.get_report_title()}: {e}[/red]")
            return False
