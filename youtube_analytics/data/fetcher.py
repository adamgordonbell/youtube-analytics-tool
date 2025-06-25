"""Data fetching and synchronization for YouTube Analytics"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Set, Dict

from .models import VideoInfo, DailyMetric
from .database import AnalyticsDatabase
from ..auth import YouTubeClientManager
from ..config import DEFAULT_DAYS_BACK


class DataFetcher:
    """Handles fetching data from YouTube APIs and storing in database"""
    
    def __init__(self, db: Optional[AnalyticsDatabase] = None):
        self.db = db or AnalyticsDatabase()
        self.client_manager = YouTubeClientManager()
    
    def fetch_video_info(self, video_id: str) -> Optional[VideoInfo]:
        """Fetch video metadata from YouTube Data API"""
        data_client = self.client_manager.get_data_client()
        if not data_client:
            return None
        
        try:
            response = data_client.videos().list(
                part='snippet',
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            
            # Parse published date
            published_str = snippet['publishedAt']
            published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00')).date()
            
            return VideoInfo(
                video_id=video_id,
                title=snippet['title'],
                published_date=published_date,
                channel_id=snippet['channelId']
            )
        except Exception as e:
            print(f"Error fetching video data for {video_id}: {e}")
            return None
    
    def get_studio_category_mapping(self) -> Dict[str, str]:
        """Map API traffic sources to YouTube Studio categories"""
        return {
            'SUBSCRIBER': 'Browse features',
            'EXT_URL': 'External', 
            'NO_LINK_OTHER': 'Direct or unknown',
            'NOTIFICATION': 'Notifications',
            'RELATED_VIDEO': 'Suggested videos',
            'YT_SEARCH': 'YouTube search',
            'YT_OTHER_PAGE': 'Other YouTube features',
            'PLAYLIST': 'Playlists',
            'YT_CHANNEL': 'Channel pages',
            'END_SCREEN': 'End screens',
            'ADVERTISING': 'Advertising',
            'SHORTS': 'Shorts',
            'SHORTS_CONTENT_LINKS': 'Shorts content links'
        }

    def fetch_daily_analytics(self, video_id: str, start_date: date, end_date: date) -> List[DailyMetric]:
        """Fetch daily analytics data from YouTube Analytics API"""
        analytics_client = self.client_manager.get_analytics_client()
        if not analytics_client:
            return []
        
        # Get video info to calculate days since published
        video_info = self.db.get_video_info(video_id)
        if not video_info:
            print(f"Video {video_id} not found in database. Fetch video info first.")
            return []
        
        # Get mapping for converting API sources to Studio categories
        studio_mapping = self.get_studio_category_mapping()
        
        try:
            response = analytics_client.reports().query(
                ids='channel==MINE',
                startDate=start_date.strftime('%Y-%m-%d'),
                endDate=end_date.strftime('%Y-%m-%d'),
                metrics='views',
                dimensions='day,insightTrafficSourceType',
                filters=f'video=={video_id}',
                sort='day,-views'
            ).execute()
            
            metrics = []
            for row in response.get('rows', []):
                day_str, api_traffic_source, views = row
                day = datetime.strptime(day_str, '%Y-%m-%d').date()
                days_since_published = (day - video_info.published_date).days
                
                # Convert API traffic source to Studio category
                studio_category = studio_mapping.get(api_traffic_source, f'Unknown ({api_traffic_source})')
                
                metrics.append(DailyMetric(
                    video_id=video_id,
                    date=day,
                    days_since_published=days_since_published,
                    traffic_source=studio_category,
                    views=int(views)
                ))
            
            return metrics
        except Exception as e:
            print(f"Error fetching analytics for {video_id}: {e}")
            return []
    
    def ensure_video_data(self, video_id: str, start_date: date, end_date: date) -> bool:
        """Ensure we have complete data for a video in the given date range"""
        # First ensure we have video info
        video_info = self.db.get_video_info(video_id)
        if not video_info:
            video_info = self.fetch_video_info(video_id)
            if not video_info:
                print(f"Could not fetch info for video {video_id}")
                return False
            self.db.store_video_info(video_info)
        
        # Check what date ranges we're missing
        missing_ranges = self.db.get_missing_date_ranges(video_id, start_date, end_date)
        
        if not missing_ranges:
            return True  # We have all the data we need
        
        # Fetch data for missing ranges
        for range_start, range_end in missing_ranges:
            # Adjust range to not go before publication date
            actual_start = max(range_start, video_info.published_date)
            if actual_start > range_end:
                continue  # This range is before publication
            
            print(f"Fetching data for {video_id} from {actual_start} to {range_end}")
            daily_metrics = self.fetch_daily_analytics(video_id, actual_start, range_end)
            if daily_metrics:
                self.db.store_daily_metrics(daily_metrics)
        
        return True
    
    def ensure_videos_data(self, video_ids: List[str], start_date: date, end_date: date) -> List[str]:
        """Ensure we have data for multiple videos, return list of successfully processed videos"""
        successful = []
        
        for video_id in video_ids:
            if self.ensure_video_data(video_id, start_date, end_date):
                successful.append(video_id)
        
        return successful
    
    def get_recent_videos_from_api(self, max_videos: int = 30, days_back: int = DEFAULT_DAYS_BACK) -> List[str]:
        """Get recent video IDs from YouTube using Analytix"""
        analytix_client = self.client_manager.get_analytix_client()
        if not analytix_client:
            return []
        
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Get top videos by views in the recent period
            report = analytix_client.fetch_report(
                dimensions=("video",),
                metrics=("views",),
                start_date=start_date,
                end_date=end_date,
                sort_options=("-views",),
                max_results=max_videos,
            )
            
            df = report.to_pandas()
            if df.empty:
                return []
            
            return df['video'].tolist()
            
        except Exception as e:
            print(f"Error getting recent videos: {e}")
            return []
    
    def sync_recent_videos(self, max_videos: int = 10, days_back: int = DEFAULT_DAYS_BACK) -> List[str]:
        """Sync recent videos to the database"""
        video_ids = self.get_recent_videos_from_api(max_videos, days_back)
        if not video_ids:
            return []
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        return self.ensure_videos_data(video_ids, start_date, end_date)
