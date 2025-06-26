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
        
        # Add duration column if it doesn't exist (migration)
        try:
            cursor.execute('ALTER TABLE videos ADD COLUMN duration_seconds INTEGER')
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Add is_short_format column if it doesn't exist (migration)
        try:
            cursor.execute('ALTER TABLE videos ADD COLUMN is_short_format BOOLEAN')
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
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
            (video_id, title, published_date, channel_id, duration_seconds, is_short_format, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (video.video_id, video.title, video.published_date, video.channel_id, video.duration_seconds, video.is_short_format))
        
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
    
    def clear_video_metrics(self, video_id: str):
        """Clear all daily metrics for a video (for clean backfill)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM daily_metrics WHERE video_id = ?', (video_id,))
        conn.commit()
        conn.close()
    
    def get_video_info(self, video_id: str) -> Optional[VideoInfo]:
        """Get video information from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT video_id, title, published_date, channel_id, duration_seconds, is_short_format FROM videos WHERE video_id = ?', 
                      (video_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            video_id, title, published_date_str, channel_id, duration_seconds, is_short_format = result
            published_date = datetime.strptime(published_date_str, '%Y-%m-%d').date()
            return VideoInfo(video_id, title, published_date, channel_id, duration_seconds, is_short_format)
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
                v.duration_seconds,
                COALESCE(SUM(dm.views), 0) as total_views,
                COALESCE(SUM(CASE WHEN dm.traffic_source != 'Advertising' THEN dm.views ELSE 0 END), 0) as organic_views,
                COALESCE(SUM(CASE WHEN dm.traffic_source = 'YouTube search' THEN dm.views ELSE 0 END), 0) as search_views
            FROM videos v
            LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id 
                AND dm.date BETWEEN ? AND ?
            WHERE v.video_id IN ({placeholders})
            GROUP BY v.video_id, v.title, v.published_date, v.channel_id, v.duration_seconds
        '''
        
        params = [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')] + video_ids
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            video_id, title, published_date_str, channel_id, duration_seconds, total_views, organic_views, search_views = row
            published_date = datetime.strptime(published_date_str, '%Y-%m-%d').date()
            
            video_info = VideoInfo(video_id, title, published_date, channel_id, duration_seconds)
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


    def get_first_n_days_total(self, video_ids: List[str], days: int = 7, traffic_source: str = TrafficSources.BROWSE_FEATURES, start_day: int = 0) -> Dict[str, Dict]:
        """Get total views for a range of days after publication (no daily breakdown)"""
        if not video_ids:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        end_day = start_day + days - 1
        
        if traffic_source.lower() == 'all':
            # Sum across all traffic sources
            query = f'''
                SELECT 
                    v.video_id,
                    v.title, 
                    v.published_date,
                    COALESCE(SUM(dm.views), 0) as total_views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                    AND dm.days_since_published BETWEEN ? AND ?
                WHERE v.video_id IN ({placeholders})
                GROUP BY v.video_id, v.title, v.published_date
                ORDER BY total_views DESC
            '''
            params = [start_day, end_day] + video_ids
        elif traffic_source.lower() == 'organic':
            # Exclude advertising traffic
            query = f'''
                SELECT 
                    v.video_id,
                    v.title, 
                    v.published_date,
                    COALESCE(SUM(dm.views), 0) as total_views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                    AND dm.days_since_published BETWEEN ? AND ?
                    AND dm.traffic_source != 'Advertising'
                WHERE v.video_id IN ({placeholders})
                GROUP BY v.video_id, v.title, v.published_date
                ORDER BY total_views DESC
            '''
            params = [start_day, end_day] + video_ids
        else:
            # Single traffic source
            query = f'''
                SELECT 
                    v.video_id,
                    v.title, 
                    v.published_date,
                    COALESCE(SUM(dm.views), 0) as total_views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                    AND dm.days_since_published BETWEEN ? AND ?
                    AND dm.traffic_source = ?
                WHERE v.video_id IN ({placeholders})
                GROUP BY v.video_id, v.title, v.published_date
                ORDER BY total_views DESC
            '''
            params = [start_day, end_day, traffic_source] + video_ids
        
        cursor.execute(query, params)
        
        results = {}
        for row in cursor.fetchall():
            video_id, title, published_date, total_views = row
            results[video_id] = {
                'title': title,
                'published_date': published_date,
                'total_views': int(total_views) if total_views else 0
            }
        
        conn.close()
        return results
    
    def get_all_video_ids(self) -> List[str]:
        """Get all video IDs from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT video_id FROM videos ORDER BY published_date DESC')
        video_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return video_ids
    
    def has_daily_metrics_in_range(self, video_id: str, start_date: date, end_date: date) -> bool:
        """Check if we have any daily metrics data for a video in the given date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert dates to days since published
        video_info = self.get_video_info(video_id)
        if not video_info:
            conn.close()
            return False
        
        start_days = (start_date - video_info.published_date).days
        end_days = (end_date - video_info.published_date).days
        
        cursor.execute('''
            SELECT COUNT(*) FROM daily_metrics 
            WHERE video_id = ? 
            AND days_since_published BETWEEN ? AND ?
        ''', (video_id, start_days, end_days))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def get_daily_views_for_spike_analysis(self, video_ids: List[str], traffic_source: str = "organic") -> Dict[str, Dict]:
        """Get daily views data for spike detection analysis"""
        if not video_ids:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        
        if traffic_source.lower() == 'organic':
            # Exclude advertising traffic, start from day 7 (skip initial momentum)
            query = f'''
                SELECT 
                    v.video_id,
                    v.title,
                    v.published_date,
                    dm.days_since_published,
                    dm.date,
                    COALESCE(SUM(dm.views), 0) as daily_views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                WHERE v.video_id IN ({placeholders})
                AND dm.days_since_published >= 7
                AND dm.traffic_source != 'Advertising'
                GROUP BY v.video_id, v.title, v.published_date, dm.days_since_published, dm.date
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids
        else:
            # Single traffic source, start from day 7
            query = f'''
                SELECT 
                    v.video_id,
                    v.title,
                    v.published_date,
                    dm.days_since_published,
                    dm.date,
                    COALESCE(dm.views, 0) as daily_views
                FROM videos v
                LEFT JOIN daily_metrics dm ON v.video_id = dm.video_id
                WHERE v.video_id IN ({placeholders})
                AND dm.days_since_published >= 7
                AND dm.traffic_source = ?
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids + [traffic_source]
        
        cursor.execute(query, params)
        
        results = {}
        for row in cursor.fetchall():
            video_id, title, published_date, days_since, date_str, daily_views = row
            if video_id not in results:
                results[video_id] = {
                    'title': title,
                    'published_date': published_date,
                    'daily_data': []
                }
            results[video_id]['daily_data'].append({
                'days_since_published': days_since,
                'date': date_str,
                'views': int(daily_views) if daily_views else 0
            })
        
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
    
    def get_first_90_days_traffic(self, video_ids: List[str], traffic_source: str = 'YouTube search') -> Dict[str, Dict]:
        """Get traffic views for first 90 days of each video, broken down by weeks"""
        if not video_ids:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        
        # Handle 'all' traffic sources vs 'organic' vs specific traffic source
        if traffic_source.lower() == 'all':
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
                AND dm.days_since_published BETWEEN 0 AND 89
                GROUP BY v.video_id, v.title, v.published_date, dm.days_since_published
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids
        elif traffic_source.lower() == 'organic':
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
                AND dm.days_since_published BETWEEN 0 AND 89
                AND dm.traffic_source != 'Advertising'
                GROUP BY v.video_id, v.title, v.published_date, dm.days_since_published
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids
        else:
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
                AND dm.days_since_published BETWEEN 0 AND 89
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
                    'total_traffic_views': 0,
                    'week_breakdowns': {}  # week_number -> views
                }
            
            # Calculate which week this day falls into (0-12 for 90 days)
            week_number = days_since // 7
            if week_number not in results[video_id]['week_breakdowns']:
                results[video_id]['week_breakdowns'][week_number] = 0
            
            results[video_id]['week_breakdowns'][week_number] += int(views) if views else 0
            results[video_id]['total_traffic_views'] += int(views) if views else 0
        
        conn.close()
        return results
    
    def get_first_180_days_traffic(self, video_ids: List[str], traffic_source: str = 'YouTube search') -> Dict[str, Dict]:
        """Get traffic views for first 180 days of each video, broken down by months"""
        if not video_ids:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(video_ids))
        
        # Handle 'all' traffic sources vs 'organic' vs specific traffic source
        if traffic_source.lower() == 'all':
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
                AND dm.days_since_published BETWEEN 0 AND 179
                GROUP BY v.video_id, v.title, v.published_date, dm.days_since_published
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids
        elif traffic_source.lower() == 'organic':
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
                AND dm.days_since_published BETWEEN 0 AND 179
                AND dm.traffic_source != 'Advertising'
                GROUP BY v.video_id, v.title, v.published_date, dm.days_since_published
                ORDER BY v.video_id, dm.days_since_published
            '''
            params = video_ids
        else:
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
                AND dm.days_since_published BETWEEN 0 AND 179
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
                    'total_traffic_views': 0,
                    'month_breakdowns': {}  # month_number -> views
                }
            
            # Calculate which month this day falls into (0-5 for 180 days)
            month_number = days_since // 30  # Approximate 30 days per month
            if month_number not in results[video_id]['month_breakdowns']:
                results[video_id]['month_breakdowns'][month_number] = 0
            
            results[video_id]['month_breakdowns'][month_number] += int(views) if views else 0
            results[video_id]['total_traffic_views'] += int(views) if views else 0
        
        conn.close()
        return results
