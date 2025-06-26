"""Enhanced data fetching for YouTube Analytics - version 2"""

import sqlite3
from datetime import datetime, date
from typing import Optional

from .models import VideoInfo, DailyMetric
from .database import AnalyticsDatabase
from ..auth import YouTubeClientManager


class DataFetcher2:
    """Enhanced data fetcher with streamlined complete history fetching"""
    
    def __init__(self, db: Optional[AnalyticsDatabase] = None):
        self.db = db or AnalyticsDatabase()
        self.client_manager = YouTubeClientManager()
    
    def get_video_complete_history(self, video_id: str, refresh: bool = False) -> bool:
        """Get complete analytics history for a video from published date to current date
        
        Args:
            video_id: YouTube video ID
            refresh: If False, check database first and skip if data exists
        
        Returns:
            True if successful, False otherwise
        """
        print(f"Getting complete history for video {video_id} (refresh={refresh})")
        
        # Get or fetch video info
        video_info = self.db.get_video_info(video_id)
        if not video_info:
            video_info = self._fetch_video_info(video_id)
            if not video_info:
                print(f"Could not fetch info for video {video_id}")
                return False
            self.db.store_video_info(video_info)
        
        # Check if we already have complete data (unless refresh=True)
        if not refresh:
            today = date.today()
            if self._has_complete_data(video_id, video_info.published_date, today):
                print(f"Complete data already exists for {video_id}, skipping fetch")
                return True
        
        # Fetch complete analytics history in single API call
        today = date.today()
        print(f"Fetching analytics from {video_info.published_date} to {today}")
        
        daily_metrics = self._fetch_daily_analytics(video_id, video_info.published_date, today)
        if daily_metrics:
            # Clear existing data if refresh=True
            if refresh:
                self.db.clear_video_metrics(video_id)
            
            self.db.store_daily_metrics(daily_metrics)
            print(f"Stored {len(daily_metrics)} daily metrics for {video_id}")
            return True
        else:
            print(f"No analytics data retrieved for {video_id}")
            return False
    
    def _has_complete_data(self, video_id: str, start_date: date, end_date: date) -> bool:
        """Check if we have complete data for the video in the date range
        
        Since we now add zero records for missing dates, we can simply check
        if we have records covering the full date range
        """
        import sqlite3
        from datetime import timedelta
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Check if we have data for the full date range
        cursor.execute('''
            SELECT MIN(date), MAX(date), COUNT(DISTINCT date) 
            FROM daily_metrics 
            WHERE video_id = ? AND date BETWEEN ? AND ?
        ''', (video_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result or result[2] == 0:
            return False  # No data at all
        
        min_date_str, max_date_str, distinct_days = result
        min_date = datetime.strptime(min_date_str, '%Y-%m-%d').date()
        max_date = datetime.strptime(max_date_str, '%Y-%m-%d').date()
        
        # Calculate expected number of days in the range
        expected_days = (end_date - start_date).days + 1
        
        # Check if we have the exact date range coverage
        return (min_date == start_date and 
                max_date == end_date and 
                distinct_days == expected_days)
    
    def _fetch_video_info(self, video_id: str) -> Optional[VideoInfo]:
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
            
            # Determine if video is a Short based on duration (≤3 minutes)
            from ..utils import is_video_short
            is_short_format = is_video_short(duration_seconds)
            
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
    
    def _fetch_daily_analytics(self, video_id: str, start_date: date, end_date: date) -> list:
        """Fetch daily analytics data from YouTube Analytics API and add zero records for missing dates"""
        from datetime import timedelta
        
        analytics_client = self.client_manager.get_analytics_client()
        if not analytics_client:
            return []
        
        # Get video info to calculate days since published
        video_info = self.db.get_video_info(video_id)
        if not video_info:
            print(f"Video {video_id} not found in database. Fetch video info first.")
            return []
        
        # Get mapping for converting API sources to Studio categories
        studio_mapping = self._get_studio_category_mapping()
        
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
            
            # Generate all dates in the range
            all_dates = set()
            current_date = start_date
            while current_date <= end_date:
                all_dates.add(current_date)
                current_date += timedelta(days=1)
            
            # Find existing dates in our metrics
            existing_dates = {metric.date for metric in metrics}
            
            # Add zero records for missing dates
            missing_dates = all_dates - existing_dates
            for missing_date in missing_dates:
                days_since_published = (missing_date - video_info.published_date).days
                metrics.append(DailyMetric(
                    video_id=video_id,
                    date=missing_date,
                    days_since_published=days_since_published,
                    traffic_source='Direct or unknown',  # Default traffic source for zero views
                    views=0
                ))
            
            print(f"Added {len(missing_dates)} zero-view records for missing dates")
            return metrics
        except Exception as e:
            print(f"Error fetching analytics for {video_id}: {e}")
            return []
    
    def _get_studio_category_mapping(self) -> dict:
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
    
    def backfill_oldest_videos_complete_history(self, max_videos: int = 10) -> int:
        """Backfill complete history for oldest videos in database
        
        Args:
            max_videos: Maximum number of videos to backfill
            
        Returns:
            Number of videos successfully backfilled
        """
        import sqlite3
        
        print(f"Backfilling complete history for up to {max_videos} oldest videos...")
        
        # Get oldest videos from database
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT video_id, title, published_date 
            FROM videos 
            ORDER BY published_date ASC 
            LIMIT ?
        ''', (max_videos,))
        
        videos = cursor.fetchall()
        conn.close()
        
        if not videos:
            print("No videos found in database")
            return 0
        
        print(f"Found {len(videos)} videos to process")
        
        successful_count = 0
        for i, (video_id, title, published_date) in enumerate(videos, 1):
            print(f"[{i}/{len(videos)}] Processing {video_id} - {title[:50]}... ({published_date})")
            
            if self.get_video_complete_history(video_id, refresh=False):
                successful_count += 1
                print(f"    ✅ Success")
            else:
                print(f"    ❌ Failed")
        
        print(f"Backfill completed: {successful_count}/{len(videos)} videos processed")
        return successful_count
