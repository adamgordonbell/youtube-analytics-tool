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
    
    def _get_all_published_videos(self) -> list:
        """Get ALL published video IDs from channel using API pagination"""
        data_client = self.client_manager.get_data_client()
        if not data_client:
            return []
        
        try:
            # Get channel ID from an existing video or discover it
            existing_video = self.db.get_recent_videos(1)
            if existing_video:
                video_info = self.db.get_video_info(existing_video[0])
                if video_info:
                    channel_id = video_info.channel_id
                else:
                    print("Could not get channel ID from database")
                    return []
            else:
                print("No existing videos found to determine channel ID")
                return []
            
            # Get ALL videos from channel using pagination
            all_video_ids = []
            next_page_token = None
            
            while True:
                request = data_client.search().list(
                    part="snippet",
                    channelId=channel_id,
                    order="date",
                    type="video",  
                    maxResults=50,  # API limit per request
                    pageToken=next_page_token
                )
                response = request.execute()
                
                # Extract video IDs from this page
                for item in response.get('items', []):
                    video_id = item['id']['videoId']
                    all_video_ids.append(video_id)
                
                # Check if there are more pages
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                
                print(f"Discovered {len(all_video_ids)} videos so far...")
                
            print(f"Total videos discovered: {len(all_video_ids)}")
            return all_video_ids
            
        except Exception as e:
            print(f"Error getting all published videos: {e}")
            return []
    
    def _update_content_types(self, video_ids: list) -> int:
        """Update content type information for videos missing it"""
        import sqlite3
        from ..utils import is_video_short
        
        # Get videos that don't have content type set
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        cursor.execute(f'''
            SELECT video_id, title, duration_seconds FROM videos 
            WHERE video_id IN ({placeholders}) AND is_short_format IS NULL 
            ORDER BY published_date DESC
        ''', video_ids)
        
        videos_to_update = cursor.fetchall()
        conn.close()
        
        if not videos_to_update:
            return 0
        
        print(f"Updating content type for {len(videos_to_update)} videos...")
        
        success_count = 0
        for i, (video_id, title, duration_seconds) in enumerate(videos_to_update, 1):
            print(f"[{i}/{len(videos_to_update)}] Getting content type for {video_id[:11]}... ({title[:50]})")
            
            try:
                # Use duration-based detection if we have duration data
                if duration_seconds is not None:
                    is_short_format = is_video_short(duration_seconds)
                else:
                    # If no duration, fetch video info
                    video_info = self._fetch_video_info(video_id)
                    if video_info and video_info.duration_seconds is not None:
                        is_short_format = is_video_short(video_info.duration_seconds)
                        # Also update duration in database
                        conn = sqlite3.connect(self.db.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE videos 
                            SET duration_seconds = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE video_id = ?
                        ''', (video_info.duration_seconds, video_id))
                        conn.commit()
                        conn.close()
                    else:
                        is_short_format = None
                
                # Update the database with Short status
                if is_short_format is not None:
                    conn = sqlite3.connect(self.db.db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE videos 
                        SET is_short_format = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE video_id = ?
                    ''', (is_short_format, video_id))
                    conn.commit()
                    conn.close()
                    
                    format_type = "Short" if is_short_format else "Video"
                    duration_info = f" ({duration_seconds}s)" if duration_seconds else ""
                    print(f"    ✓ {format_type}{duration_info}")
                    success_count += 1
                else:
                    print(f"    ? Could not determine format (no duration data)")
                    
            except Exception as e:
                print(f"    ✗ Error: {e}")
        
        return success_count
    
    def ensure_all_channel_videos(self) -> dict:
        """Ensure we have complete video metadata for all channel videos
        
        Returns:
            Dict with total, added, and updated counts
        """
        import sqlite3
        
        print("Ensuring complete video catalog...")
        
        # 1. Get all video IDs from channel
        all_video_ids = self._get_all_published_videos()
        if not all_video_ids:
            print("No videos found from channel API")
            return {"total": 0, "added": 0, "updated": 0}
        
        # 2. Check which ones we're missing in database
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(all_video_ids))
        cursor.execute(f'''
            SELECT video_id FROM videos 
            WHERE video_id IN ({placeholders})
        ''', all_video_ids)
        
        existing_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        missing_ids = set(all_video_ids) - existing_ids
        
        print(f"Found {len(all_video_ids)} total videos, {len(missing_ids)} missing from database")
        
        # 3. Fetch video info for missing videos
        added_count = 0
        if missing_ids:
            print(f"Fetching metadata for {len(missing_ids)} missing videos...")
            for i, video_id in enumerate(missing_ids, 1):
                print(f"[{i}/{len(missing_ids)}] Fetching info for {video_id}")
                video_info = self._fetch_video_info(video_id)
                if video_info:
                    self.db.store_video_info(video_info)
                    added_count += 1
                    print(f"    ✓ Added {video_info.title[:50]}...")
                else:
                    print(f"    ✗ Failed to fetch info")
        
        # 4. Update content types for videos missing it
        updated_count = self._update_content_types(all_video_ids)
        
        result = {
            "total": len(all_video_ids),
            "added": added_count, 
            "updated": updated_count
        }
        
        print(f"Video catalog complete: {result['total']} total, {result['added']} added, {result['updated']} updated")
        return result
