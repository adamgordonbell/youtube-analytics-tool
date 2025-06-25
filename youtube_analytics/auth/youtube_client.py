"""YouTube API client management"""

import json
import os
from typing import Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from analytix import Client

from ..config import CLIENT_SECRETS_FILE, YOUTUBE_DATA_TOKENS_FILE, YOUTUBE_ANALYTICS_TOKENS_FILE


class YouTubeClientManager:
    """Manages YouTube API clients with authentication"""
    
    def __init__(self):
        self._data_client = None
        self._analytics_client = None
        self._analytix_client = None
    
    def get_data_client(self):
        """Get YouTube Data API v3 client"""
        if self._data_client is not None:
            return self._data_client
        
        if os.path.exists(YOUTUBE_DATA_TOKENS_FILE):
            with open(YOUTUBE_DATA_TOKENS_FILE, "r") as f:
                token_data = json.load(f)
            
            creds = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                client_id=token_data["client_id"],
                client_secret=token_data["client_secret"],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/youtube.readonly"]
            )
            
            if creds.valid:
                self._data_client = build('youtube', 'v3', credentials=creds)
                return self._data_client
            elif creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_data["access_token"] = creds.token
                with open(YOUTUBE_DATA_TOKENS_FILE, "w") as f:
                    json.dump(token_data, f)
                self._data_client = build('youtube', 'v3', credentials=creds)
                return self._data_client
        
        # Need to authorize
        scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes)
        creds = flow.run_local_server(port=8080)
        
        # Save tokens for next time
        with open(CLIENT_SECRETS_FILE, "r") as f:
            secrets = json.load(f)
        
        token_data = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "client_id": secrets["installed"]["client_id"],
            "client_secret": secrets["installed"]["client_secret"]
        }
        with open(YOUTUBE_DATA_TOKENS_FILE, "w") as f:
            json.dump(token_data, f)
        
        self._data_client = build('youtube', 'v3', credentials=creds)
        return self._data_client
    
    def get_analytics_client(self):
        """Get YouTube Analytics API v2 client"""
        if self._analytics_client is not None:
            return self._analytics_client
        
        try:
            with open(CLIENT_SECRETS_FILE, "r") as f:
                secrets = json.load(f)
            
            with open(YOUTUBE_ANALYTICS_TOKENS_FILE, "r") as f:
                token_data = json.load(f)
            
            creds = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                client_id=secrets["installed"]["client_id"],
                client_secret=secrets["installed"]["client_secret"],
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/yt-analytics.readonly"]
            )
            
            self._analytics_client = build('youtubeAnalytics', 'v2', credentials=creds)
            return self._analytics_client
            
        except Exception as e:
            print(f"Error creating YouTube Analytics client: {e}")
            return None
    
    def get_analytix_client(self) -> Optional[Client]:
        """Get Analytix client for easier data retrieval"""
        if self._analytix_client is not None:
            return self._analytix_client
        
        try:
            self._analytix_client = Client(CLIENT_SECRETS_FILE)
            return self._analytix_client
        except Exception as e:
            print(f"Error creating Analytix client: {e}")
            return None
