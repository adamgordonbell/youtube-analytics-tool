"""Data fetching and synchronization for YouTube Analytics"""

import sqlite3
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
                part='snippet,contentDetails,status,processingDetails',
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            content_details = item['contentDetails']
            
            # Parse published date
            published_str = snippet['publishedAt']
            published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00')).date()
            
            # Parse duration (ISO 8601 format like PT4M13S)
            duration_str = content_details['duration']
            duration_seconds = self._parse_duration(duration_str)
            
            # Get content type (Short vs Video) from Analytics API
            is_short_format = self._get_video_content_type(video_id)
            
            return VideoInfo(
                video_id=video_id,
                title=snippet['title'],
                published_date=published_date,
                channel_id=snippet['channelId'],
                duration_seconds=duration_seconds,
                is_short_format=is_short_format
            )
        except Exception as e:
            print(f"Error fetching video data for {video_id}: {e}")
            return None
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration format (PT4M13S) to seconds"""
        import re
        
        # Remove PT prefix
        duration_str = duration_str[2:]
        
        # Parse hours, minutes, seconds
        hours = 0
        minutes = 0
        seconds = 0
        
        # Extract hours
        if 'H' in duration_str:
            hours_match = re.search(r'(\d+)H', duration_str)
            if hours_match:
                hours = int(hours_match.group(1))
        
        # Extract minutes
        if 'M' in duration_str:
            minutes_match = re.search(r'(\d+)M', duration_str)
            if minutes_match:
                minutes = int(minutes_match.group(1))
        
        # Extract seconds
        if 'S' in duration_str:
            seconds_match = re.search(r'(\d+)S', duration_str)
            if seconds_match:
                seconds = int(seconds_match.group(1))
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _get_video_content_type(self, video_id: str) -> Optional[bool]:
        """Get video content type using duration-based detection
        
        Note: The playbackLocationType=10 (Shorts feed) dimension is not available
        in our current API access level. Using duration as a reliable fallback:
        - Videos ≤ 60 seconds are very likely Shorts
        - Videos > 180 seconds are definitely not Shorts
        
        Returns:
            True if video is a Short (≤60s duration)
            False if video is a regular video (>60s duration)
            None if unable to determine (no duration data)
        """
        # Get video info to check duration
        video_info = self.db.get_video_info(video_id)
        if video_info and video_info.duration_seconds is not None:
            # YouTube Shorts must be 60 seconds or less
            # This is the most reliable indicator we have access to
            return video_info.duration_seconds <= 60
        
        # If we don't have duration info, we can't determine format
        # (Avoid recursion by not calling fetch_video_info from within _get_video_content_type)
        return None  # Cannot determine without duration data
    
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
            
            # Skip fetching data that's more than 2 days old (should be final)
            # Exception: Always fetch for first week analysis regardless of age
            today = datetime.now().date()
            if range_end < today - timedelta(days=2):
                # Check if this is within 7 days of publish date (first week analysis)
                days_from_publish = (range_end - video_info.published_date).days
                if days_from_publish > 6:
                    continue  # Data is too old to change, skip refetching
            
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
    
    def get_recent_published_videos(self, max_videos: int = 40) -> List[str]:
        """Get most recently published video IDs from YouTube Data API"""
        data_client = self.client_manager.get_data_client()
        if not data_client:
            return []
        
        try:
            # Get channel ID from an existing video in the database
            existing_video = self.db.get_recent_videos(1)
            if not existing_video:
                print("No existing videos found to determine channel ID")
                return []
            
            video_info = self.db.get_video_info(existing_video[0])
            if not video_info:
                print("Could not get channel ID from existing video")
                return []
            
            channel_id = video_info.channel_id
            
            # Get channel's most recent uploads
            request = data_client.search().list(
                part="snippet",
                channelId=channel_id,
                order="date",  # Most recent first
                type="video",
                maxResults=min(max_videos, 50)  # API limit is 50
            )
            response = request.execute()
            
            video_ids = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                video_ids.append(video_id)
            
            return video_ids[:max_videos]
            
        except Exception as e:
            print(f"Error fetching recent published videos: {e}")
            return []
    
    def sync_recent_videos(self, max_videos: int = 10, days_back: int = DEFAULT_DAYS_BACK) -> List[str]:
        """Sync recent videos to the database"""
        video_ids = self.get_recent_videos_from_api(max_videos, days_back)
        if not video_ids:
            return []
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        return self.ensure_videos_data(video_ids, start_date, end_date)
    
    def backfill_video_complete_history(self, video_id: str) -> bool:
        """Backfill all historical data for a video from publish date to today"""
        # Get video info
        video_info = self.db.get_video_info(video_id)
        if not video_info:
            video_info = self.fetch_video_info(video_id)
            if not video_info:
                print(f"Could not fetch info for video {video_id}")
                return False
            self.db.store_video_info(video_info)
        
        # Fetch from publish date to today
        today = datetime.now().date()
        print(f"Backfilling complete history for {video_id} from {video_info.published_date} to {today}")
        
        daily_metrics = self.fetch_daily_analytics(video_id, video_info.published_date, today)
        if daily_metrics:
            # Clear existing data to avoid conflicts
            self.db.clear_video_metrics(video_id)
            self.db.store_daily_metrics(daily_metrics)
            print(f"Stored {len(daily_metrics)} daily metrics for {video_id}")
            return True
        
        return False
    
    def backfill_recent_videos_complete_history(self, max_videos: int = 50) -> List[str]:
        """Backfill complete history for the most recent videos"""
        # Get recent published videos
        video_ids = self.get_recent_published_videos(max_videos)
        if not video_ids:
            print("No videos found for backfill")
            return []
        
        successful = []
        for i, video_id in enumerate(video_ids, 1):
            print(f"[{i}/{len(video_ids)}] Processing {video_id}")
            if self.backfill_video_complete_history(video_id):
                successful.append(video_id)
        
        print(f"Successfully backfilled {len(successful)} out of {len(video_ids)} videos")
        return successful
    
    def backfill_video_content_types(self, video_count: int = 50) -> bool:
        """Backfill content type information for videos missing it"""
        # Get videos that don't have content type set
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT video_id, title FROM videos 
            WHERE is_short_format IS NULL 
            ORDER BY published_date DESC
            LIMIT ?
        ''', (video_count,))
        
        videos_to_update = cursor.fetchall()
        conn.close()
        
        if not videos_to_update:
            print("All videos already have content type information")
            return True
        
        print(f"Updating content type for {len(videos_to_update)} videos...")
        
        success_count = 0
        for i, (video_id, title) in enumerate(videos_to_update, 1):
            print(f"[{i}/{len(videos_to_update)}] Getting content type for {video_id[:11]}... ({title[:50]})")
            
            try:
                is_short_format = self._get_video_content_type(video_id)
                
                # Update the database
                conn = sqlite3.connect(self.db.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE videos 
                    SET is_short_format = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE video_id = ?
                ''', (is_short_format, video_id))
                conn.commit()
                conn.close()
                
                if is_short_format is not None:
                    format_type = "Short" if is_short_format else "Long"
                    print(f"    ✓ {format_type}")
                    success_count += 1
                else:
                    print(f"    ? Could not determine format (no recent views data)")
                    
            except Exception as e:
                print(f"    ✗ Error: {e}")
        
        print(f"Content type backfill completed: {success_count}/{len(videos_to_update)} videos updated")
        return success_count > 0
