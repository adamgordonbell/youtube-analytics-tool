"""Configuration and constants for YouTube Analytics Tool"""

from pathlib import Path

# Database configuration
DEFAULT_DB_PATH = "youtube_analytics.db"

# API configuration
YOUTUBE_DATA_TOKENS_FILE = "youtube_data_tokens.json"
YOUTUBE_ANALYTICS_TOKENS_FILE = "tokens.json"
CLIENT_SECRETS_FILE = "client_secrets.json"

# Default settings
DEFAULT_DAYS_BACK = 30
MAX_VIDEOS_PER_REQUEST = 50
DEFAULT_MAX_RESULTS = 10

# Branded keywords for highlighting in reports
BRANDED_KEYWORDS = [
    "pulumi",
    "pulumi tutorial",
]

# Traffic sources (using YouTube Studio category names)
class TrafficSources:
    YOUTUBE_SEARCH = "YouTube search"
    BROWSE_FEATURES = "Browse features"
    CHANNEL_PAGES = "Channel pages" 
    ADVERTISING = "Advertising"
    EXTERNAL = "External"
    SUGGESTED_VIDEOS = "Suggested videos"
    DIRECT_OR_UNKNOWN = "Direct or unknown"
    OTHER_YOUTUBE_FEATURES = "Other YouTube features"
    PLAYLISTS = "Playlists"
    NOTIFICATIONS = "Notifications"
    END_SCREENS = "End screens"
    SHORTS = "Shorts"
    
    @classmethod
    def all(cls):
        return [cls.YOUTUBE_SEARCH, cls.BROWSE_FEATURES, cls.CHANNEL_PAGES, cls.ADVERTISING, 
                cls.EXTERNAL, cls.SUGGESTED_VIDEOS, cls.DIRECT_OR_UNKNOWN, cls.OTHER_YOUTUBE_FEATURES,
                cls.PLAYLISTS, cls.NOTIFICATIONS, cls.END_SCREENS, cls.SHORTS]
    
    @classmethod
    def common(cls):
        """Most commonly used traffic sources"""
        return [cls.YOUTUBE_SEARCH, cls.BROWSE_FEATURES, cls.CHANNEL_PAGES, cls.ADVERTISING, cls.EXTERNAL]
    
    @classmethod
    def first_week_options(cls):
        """Options for first week report including all"""
        return ["all"] + cls.common()
