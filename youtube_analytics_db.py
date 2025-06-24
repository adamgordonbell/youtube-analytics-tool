#!/usr/bin/env python3
"""
YouTube Analytics Database Manager

Stores historical YouTube analytics data for trend analysis and comparisons.
Allows querying by days since publication, traffic source, etc.
"""

import sqlite3
import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import googleapiclient.discovery
from google.oauth2.credentials import Credentials

@dataclass
class VideoInfo:
    video_id: str
    title: str
    published_date: date
    channel_id: str

@dataclass
class DailyMetric:
    video_id: str
    date: date
    days_since_published: int
    traffic_source: str
    views: int

class YouTubeAnalyticsDB:
    def __init__(self, db_path: str = "youtube_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Videos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                published_date DATE NOT NULL,
                channel_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Daily metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                date DATE NOT NULL,
                days_since_published INTEGER NOT NULL,
                traffic_source TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (video_id),
                UNIQUE(video_id, date, traffic_source)
            )
        ''')
        
        # Indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_metrics_video_days ON daily_metrics (video_id, days_since_published)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_metrics_source ON daily_metrics (traffic_source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_published ON videos (published_date)')
        
        conn.commit()
        conn.close()
    
    def get_youtube_analytics_client(self):
        """Get YouTube Analytics client - import from main module"""
        try:
            # Import the function from the main script to reuse the working implementation
            import youtube_stats
            return youtube_stats.get_youtube_analytics_client()
        except Exception as e:
            print(f"Error getting YouTube Analytics client: {e}")
            return None
    
    def get_youtube_data_client(self):
        """Get YouTube Data client - import from main module"""
        try:
            # Import the function from the main script to reuse the working implementation  
            import youtube_stats
            return youtube_stats.get_youtube_data_client()
        except Exception as e:
            print(f"Error getting YouTube Data client: {e}")
            return None
    
    def store_video_info(self, video: VideoInfo):
        """Store or update video information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO videos 
            (video_id, title, published_date, channel_id, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (video.video_id, video.title, video.published_date, video.channel_id))
        
        conn.commit()
        conn.close()
    
    def store_daily_metrics(self, metrics: List[DailyMetric]):
        """Store daily metrics (views by traffic source by day)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for metric in metrics:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_metrics 
                (video_id, date, days_since_published, traffic_source, views)
                VALUES (?, ?, ?, ?, ?)
            ''', (metric.video_id, metric.date, metric.days_since_published, 
                  metric.traffic_source, metric.views))
        
        conn.commit()
        conn.close()
    
    def fetch_video_data_from_youtube(self, video_id: str) -> Optional[VideoInfo]:
        """Fetch video metadata from YouTube Data API"""
        data_client = self.get_youtube_data_client()
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
    
    def fetch_daily_analytics_from_youtube(self, video_id: str, start_date: date, end_date: date) -> List[DailyMetric]:
        """Fetch daily analytics data from YouTube Analytics API"""
        analytics_client = self.get_youtube_analytics_client()
        if not analytics_client:
            return []
        
        # Get video info to calculate days since published
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT published_date FROM videos WHERE video_id = ?', (video_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"Video {video_id} not found in database. Run sync first.")
            return []
        
        published_date = datetime.strptime(result[0], '%Y-%m-%d').date()
        
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
                day_str, traffic_source, views = row
                day = datetime.strptime(day_str, '%Y-%m-%d').date()
                days_since_published = (day - published_date).days
                
                metrics.append(DailyMetric(
                    video_id=video_id,
                    date=day,
                    days_since_published=days_since_published,
                    traffic_source=traffic_source,
                    views=int(views)
                ))
            
            return metrics
        except Exception as e:
            print(f"Error fetching analytics for {video_id}: {e}")
            return []
    
    def sync_video(self, video_id: str, days_back: int = 30):
        """Sync a single video's data and analytics"""
        print(f"Syncing video {video_id}...")
        
        # Fetch and store video info
        video_info = self.fetch_video_data_from_youtube(video_id)
        if not video_info:
            print(f"Could not fetch info for video {video_id}")
            return False
        
        self.store_video_info(video_info)
        print(f"  Video: {video_info.title}")
        print(f"  Published: {video_info.published_date}")
        
        # Fetch analytics data
        end_date = date.today()
        start_date = max(video_info.published_date, end_date - timedelta(days=days_back))
        
        daily_metrics = self.fetch_daily_analytics_from_youtube(video_id, start_date, end_date)
        if daily_metrics:
            self.store_daily_metrics(daily_metrics)
            print(f"  Stored {len(daily_metrics)} daily metrics")
        
        return True
    
    def get_recent_videos(self, limit: int = 10) -> List[str]:
        """Get most recently published video IDs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT video_id FROM videos 
            ORDER BY published_date DESC 
            LIMIT ?
        ''', (limit,))
        
        result = [row[0] for row in cursor.fetchall()]
        conn.close()
        return result
    
    def analyze_first_week_performance(self, video_ids: List[str], traffic_source: str = 'BROWSE') -> Dict:
        """Compare first 7 days performance for given videos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        results = {}
        for video_id in video_ids:
            cursor.execute('''
                SELECT v.title, v.published_date, SUM(dm.views) as total_views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                WHERE v.video_id = ? 
                AND dm.days_since_published BETWEEN 0 AND 6
                AND dm.traffic_source = ?
                GROUP BY v.video_id
            ''', (video_id, traffic_source))
            
            result = cursor.fetchone()
            if result:
                title, published_date, total_views = result
                results[video_id] = {
                    'title': title,
                    'published_date': published_date,
                    'first_week_views': total_views or 0
                }
        
        conn.close()
        return results

if __name__ == "__main__":
    # Example usage
    db = YouTubeAnalyticsDB()
    print("YouTube Analytics Database initialized")
