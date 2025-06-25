"""Database operations for YouTube Analytics"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set
from pathlib import Path

from .models import VideoInfo, DailyMetric, VideoMetrics
from ..config import DEFAULT_DB_PATH, TrafficSources


class AnalyticsDatabase:
    """SQLite database for storing YouTube analytics data"""
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics (date)')
        
        conn.commit()
        conn.close()
    
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
        if not metrics:
            return
        
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
    
    def get_video_info(self, video_id: str) -> Optional[VideoInfo]:
        """Get video information from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT video_id, title, published_date, channel_id FROM videos WHERE video_id = ?', 
                      (video_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            video_id, title, published_date_str, channel_id = result
            published_date = datetime.strptime(published_date_str, '%Y-%m-%d').date()
            return VideoInfo(video_id, title, published_date, channel_id)
        return None
    
    def get_videos_needing_data(self, video_ids: List[str], start_date: date, end_date: date) -> Set[str]:
        """Find which videos need data fetched for the given date range"""
        if not video_ids:
            return set()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check which videos exist in the database
        placeholders = ','.join(['?'] * len(video_ids))
        cursor.execute(f'SELECT video_id FROM videos WHERE video_id IN ({placeholders})', video_ids)
        existing_videos = {row[0] for row in cursor.fetchall()}
        
        videos_needing_data = set(video_ids) - existing_videos
        
        # For existing videos, check if we have complete data for the date range
        for video_id in existing_videos:
            cursor.execute('''
                SELECT COUNT(DISTINCT date) 
                FROM daily_metrics 
                WHERE video_id = ? AND date BETWEEN ? AND ?
            ''', (video_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            days_with_data = cursor.fetchone()[0]
            expected_days = (end_date - start_date).days + 1
            
            # If we don't have data for all days, we need to fetch
            if days_with_data < expected_days:
                videos_needing_data.add(video_id)
        
        conn.close()
        return videos_needing_data
    
    def get_video_metrics_for_period(self, video_ids: List[str], start_date: date, end_date: date) -> List[VideoMetrics]:
        """Get aggregated metrics for videos in the given period"""
        if not video_ids:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        query = f'''
            SELECT 
                v.video_id,
                v.title,
                v.published_date,
                v.channel_id,
                COALESCE(SUM(dm.views), 0) as total_views,
                COALESCE(SUM(CASE WHEN dm.traffic_source != 'ADVERTISING' THEN dm.views ELSE 0 END), 0) as organic_views,
                COALESCE(SUM(CASE WHEN dm.traffic_source = 'YT_SEARCH' THEN dm.views ELSE 0 END), 0) as search_views
            FROM videos v
            LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id 
                AND dm.date BETWEEN ? AND ?
            WHERE v.video_id IN ({placeholders})
            GROUP BY v.video_id, v.title, v.published_date, v.channel_id
        '''
        
        params = [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')] + video_ids
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            video_id, title, published_date_str, channel_id, total_views, organic_views, search_views = row
            published_date = datetime.strptime(published_date_str, '%Y-%m-%d').date()
            
            video_info = VideoInfo(video_id, title, published_date, channel_id)
            metrics = VideoMetrics(
                video_info=video_info,
                total_views=int(total_views),
                organic_views=int(organic_views),
                search_views=int(search_views)
            )
            results.append(metrics)
        
        conn.close()
        return results
    
    def get_first_week_performance(self, video_ids: List[str], traffic_source: str = TrafficSources.BROWSE_FEATURES) -> Dict[str, Dict]:
        """Get first 7 days performance for given videos"""
        if not video_ids:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        query = f'''
            SELECT 
                v.video_id,
                v.title, 
                v.published_date, 
                COALESCE(SUM(dm.views), 0) as first_week_views
            FROM videos v
            LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
            WHERE v.video_id IN ({placeholders})
            AND dm.days_since_published BETWEEN 0 AND 6
            AND dm.traffic_source = ?
            GROUP BY v.video_id, v.title, v.published_date
        '''
        
        params = video_ids + [traffic_source]
        cursor.execute(query, params)
        
        results = {}
        for row in cursor.fetchall():
            video_id, title, published_date, first_week_views = row
            results[video_id] = {
                'title': title,
                'published_date': published_date,
                'first_week_views': int(first_week_views) if first_week_views else 0
            }
        
        conn.close()
        return results

    def get_first_week_daily_breakdown(self, video_ids: List[str], traffic_source: str = TrafficSources.BROWSE_FEATURES) -> Dict[str, Dict]:
        """Get day-by-day breakdown for first 7 days of each video"""
        if not video_ids:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        
        if traffic_source.lower() == 'all':
            # Sum across all traffic sources
            query = f'''
                SELECT 
                    v.video_id,
                    v.title, 
                    v.published_date,
                    dm.days_since_published,
                    COALESCE(SUM(dm.views), 0) as views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                WHERE v.video_id IN ({placeholders})
                AND dm.days_since_published BETWEEN 0 AND 6
                GROUP BY v.video_id, v.title, v.published_date, dm.days_since_published
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids
        else:
            # Single traffic source
            query = f'''
                SELECT 
                    v.video_id,
                    v.title, 
                    v.published_date,
                    dm.days_since_published,
                    COALESCE(dm.views, 0) as views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                WHERE v.video_id IN ({placeholders})
                AND dm.days_since_published BETWEEN 0 AND 6
                AND dm.traffic_source = ?
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids + [traffic_source]
        
        cursor.execute(query, params)
        
        results = {}
        for row in cursor.fetchall():
            video_id, title, published_date, days_since, views = row
            if video_id not in results:
                results[video_id] = {
                    'title': title,
                    'published_date': published_date,
                    'daily_views': {}
                }
            results[video_id]['daily_views'][days_since] = int(views) if views else 0
        
        # Fill in missing days with 0 views
        for video_data in results.values():
            for day in range(7):
                if day not in video_data['daily_views']:
                    video_data['daily_views'][day] = 0
        
        conn.close()
        return results
    
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
    
    def get_missing_date_ranges(self, video_id: str, start_date: date, end_date: date) -> List[tuple]:
        """Find date ranges where we're missing data for a video"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all dates we have data for
        cursor.execute('''
            SELECT DISTINCT date 
            FROM daily_metrics 
            WHERE video_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
        ''', (video_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        
        existing_dates = {datetime.strptime(row[0], '%Y-%m-%d').date() for row in cursor.fetchall()}
        conn.close()
        
        # Find missing date ranges
        missing_ranges = []
        current_date = start_date
        range_start = None
        
        while current_date <= end_date:
            if current_date not in existing_dates:
                if range_start is None:
                    range_start = current_date
            else:
                if range_start is not None:
                    missing_ranges.append((range_start, current_date - timedelta(days=1)))
                    range_start = None
            current_date += timedelta(days=1)
        
        # Handle case where missing range extends to end
        if range_start is not None:
            missing_ranges.append((range_start, end_date))
        
        return missing_ranges
