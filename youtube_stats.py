#!/usr/bin/env python
import click
from analytix import Client
from datetime import datetime, timedelta
import json
import os
from googleapiclient.discovery import build
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box
from youtube_analytics_db import YouTubeAnalyticsDB

# Initialize Rich console
console = Console()

# Configuration for branded keywords to highlight in reports
BRANDED_KEYWORDS = [
    "pulumi",
    "pulumi tutorial",
]

def get_youtube_data_client():
    """Create a separate YouTube Data API client with expanded OAuth scope"""
    from google_auth_oauthlib.flow import InstalledAppFlow
    import json
    import os
    
    # Check if we have YouTube Data API tokens
    if os.path.exists("youtube_data_tokens.json"):
        from google.oauth2.credentials import Credentials
        
        with open("youtube_data_tokens.json", "r") as f:
            token_data = json.load(f)
        
        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.readonly"]
        )
        
        # Check if token is valid
        if creds.valid:
            return build('youtube', 'v3', credentials=creds)
        elif creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Save refreshed token
            token_data["access_token"] = creds.token
            with open("youtube_data_tokens.json", "w") as f:
                json.dump(token_data, f)
            return build('youtube', 'v3', credentials=creds)
    
    # Need to authorize
    scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", scopes)
    creds = flow.run_local_server(port=8080)
    
    # Save tokens for next time
    with open("client_secrets.json", "r") as f:
        secrets = json.load(f)
    
    token_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": secrets["installed"]["client_id"],
        "client_secret": secrets["installed"]["client_secret"]
    }
    with open("youtube_data_tokens.json", "w") as f:
        json.dump(token_data, f)
    
    return build('youtube', 'v3', credentials=creds)

def get_video_info(video_ids):
    """Get video titles and publish dates from YouTube Data API"""
    try:
        youtube = get_youtube_data_client()
        
        # Get video details in batches of 50 (API limit)
        video_info = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            response = youtube.videos().list(
                part='snippet',
                id=','.join(batch)
            ).execute()
            
            for item in response['items']:
                title = item['snippet']['title']
                # Truncate title to 25 characters
                if len(title) > 25:
                    title = title[:22] + "..."
                
                # Format publish date (e.g., "Jun 24" or "6/24")
                from datetime import datetime
                pub_date = datetime.fromisoformat(item['snippet']['publishedAt'].replace('Z', '+00:00'))
                date_str = pub_date.strftime("%b %d")  # e.g., "Jun 24"
                
                video_info[item['id']] = {
                    'title': title,
                    'date': date_str
                }
        
        return video_info
    except Exception as e:
        print(f"Warning: Could not fetch video info: {e}")
        return {vid: {'title': "Title unavailable", 'date': "Unknown"} for vid in video_ids}

def get_client():
    """Initialize and return authenticated client"""
    return Client("client_secrets.json")

def get_youtube_analytics_client():
    """Get YouTube Analytics API v2 client using same OAuth tokens"""
    try:
        # Use the same OAuth tokens from analytix
        from google.oauth2.credentials import Credentials
        import json
        
        # Read client secrets
        with open("client_secrets.json", "r") as f:
            secrets = json.load(f)
        
        # Read tokens
        with open("tokens.json", "r") as f:
            token_data = json.load(f)
        
        # Create credentials
        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            client_id=secrets["installed"]["client_id"],
            client_secret=secrets["installed"]["client_secret"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/yt-analytics.readonly"]
        )
        
        return build('youtubeAnalytics', 'v2', credentials=creds)
        
    except Exception as e:
        print(f"Error creating YouTube Analytics client: {e}")
        return None

def get_organic_views_per_video(client, start_date, end_date, max_videos=30):
    """Get precise organic views per video using YouTube Analytics API v2"""
    try:
        # First get top videos by total views
        total_report = client.fetch_report(
            dimensions=("video",),
            metrics=("views",),
            start_date=start_date,
            end_date=end_date,
            sort_options=("-views",),
            max_results=max_videos,
        )
        total_df = total_report.to_pandas()
        if total_df.empty:
            return {}
        
        # Get YouTube Analytics API client
        yt_analytics = get_youtube_analytics_client()
        if not yt_analytics:
            print("Falling back to ratio-based approximation...")
            return get_organic_views_with_ratio_fallback(client, start_date, end_date, max_videos)
        
        organic_views = {}
        
    
        for _, row in total_df.iterrows():
            video_id = row['video']
            total_views = int(row['views'])
            
            try:
                # Get per-video traffic source breakdown
                resp = yt_analytics.reports().query(
                    ids=f"channel==MINE",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics="views",
                    dimensions="video,insightTrafficSourceType",
                    filters=f"video=={video_id}",
                    sort="-views"
                ).execute()
                
                # Calculate organic views (exclude ADVERTISING)
                organic_count = 0
                ad_count = 0
                
                if 'rows' in resp:
                    for traffic_row in resp['rows']:
                        _, source_type, views = traffic_row
                        views = int(views)
                        
                        if source_type == 'ADVERTISING':
                            ad_count += views
                        else:
                            organic_count += views
                
                organic_views[video_id] = organic_count
                ad_percentage = (ad_count / total_views * 100) if total_views > 0 else 0

                
            except Exception as e:
                console.print(f"[red]  Error getting traffic for {video_id}: {e}[/red]")
                # Fallback to total views if per-video fails
                organic_views[video_id] = total_views
        
        return organic_views
        
    except Exception as e:
        print(f"Warning: Could not get per-video organic views: {e}")
        return {}

def get_organic_views_with_ratio_fallback(client, start_date, end_date, max_videos=30):
    """Fallback method using channel-wide ratio"""
    try:
        # Get total views by video
        total_report = client.fetch_report(
            dimensions=("video",),
            metrics=("views",),
            start_date=start_date,
            end_date=end_date,
            sort_options=("-views",),
            max_results=max_videos,
        )
        total_df = total_report.to_pandas()
        if total_df.empty:
            return {}
        
        # Get overall traffic source breakdown
        traffic_report = client.fetch_report(
            dimensions=("insightTrafficSourceType",),
            metrics=("views",),
            start_date=start_date,
            end_date=end_date,
        )
        traffic_df = traffic_report.to_pandas()
        
        # Calculate advertising ratio
        total_channel_views = traffic_df['views'].sum()
        ad_views = traffic_df[traffic_df['insightTrafficSourceType'] == 'ADVERTISING']['views'].sum()
        ad_ratio = ad_views / total_channel_views if total_channel_views > 0 else 0
        
        print(f"Using channel-wide ratio: {ad_ratio:.1%} advertising")
        print("Note: This is an approximation. Individual videos may vary significantly.")
        
        # Apply ratio to each video (this is an approximation)
        organic_views = {}
        for _, row in total_df.iterrows():
            video_id = row['video']
            total_views = int(row['views'])
            estimated_ad_views = int(total_views * ad_ratio)
            organic_views[video_id] = max(0, total_views - estimated_ad_views)
        
        return organic_views
        
    except Exception as e:
        print(f"Warning: Could not calculate organic views: {e}")
        return {}

def get_search_traffic_views(client, start_date, end_date, max_videos=30):
    """Get YouTube search traffic views per video"""
    try:
        # Get top videos by total views first
        total_report = client.fetch_report(
            dimensions=("video",),
            metrics=("views",),
            start_date=start_date,
            end_date=end_date,
            sort_options=("-views",),
            max_results=max_videos,
        )
        total_df = total_report.to_pandas()
        if total_df.empty:
            return {}
        
        # Get YouTube Analytics API client
        yt_analytics = get_youtube_analytics_client()
        if not yt_analytics:
            console.print("[red]Cannot get search traffic data without YouTube Analytics API[/red]")
            return {}
        
        search_views = {}
        
    
        for _, row in total_df.iterrows():
            video_id = row['video']
            
            try:
                # Get traffic source breakdown for this video
                resp = yt_analytics.reports().query(
                    ids=f"channel==MINE",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics="views",
                    dimensions="video,insightTrafficSourceType",
                    filters=f"video=={video_id}",
                    sort="-views"
                ).execute()
                
                # Find YT_SEARCH views
                search_count = 0
                if 'rows' in resp:
                    for traffic_row in resp['rows']:
                        _, source_type, views = traffic_row
                        if source_type == 'YT_SEARCH':
                            search_count = int(views)
                            break
                
                if search_count > 0:
                    search_views[video_id] = search_count
    
                
            except Exception as e:
                console.print(f"[red]  Error getting search traffic for {video_id}: {e}[/red]")
        
        return search_views
        
    except Exception as e:
        console.print(f"[red]Warning: Could not get search traffic views: {e}[/red]")
        return {}

def get_organic_views(client, start_date, end_date, max_videos=30):
    """Get organic (non-advertising) views for videos"""
    # Try the precise per-video method first, fallback to ratio-based
    return get_organic_views_per_video(client, start_date, end_date, max_videos)

def debug_traffic_sources(client, start_date, end_date):
    """Debug function to see what traffic sources exist"""
    print("=== DEBUGGING TRAFFIC SOURCES ===")
    
    # First, let's see what traffic sources exist overall
    try:
        traffic_report = client.fetch_report(
            dimensions=("insightTrafficSourceType",),
            metrics=("views",),
            start_date=start_date,
            end_date=end_date,
            sort_options=("-views",),
            max_results=20,
        )
        traffic_df = traffic_report.to_pandas()
        
        if not traffic_df.empty:
            print("Available traffic sources:")
            for _, row in traffic_df.iterrows():
                source = row['insightTrafficSourceType']
                views = int(row['views'])
                print(f"  {source}: {views:,} views")
        else:
            print("No traffic source data found")
            
    except Exception as e:
        print(f"Error getting traffic sources: {e}")
    
    # Now let's try to get advertising views specifically
    try:
        print("\nTesting advertising filter...")
        ad_report = client.fetch_report(
            dimensions=("insightTrafficSourceType",),
            metrics=("views",),
            filters={"insightTrafficSourceType": "ADVERTISING"},
            start_date=start_date,
            end_date=end_date,
        )
        ad_df = ad_report.to_pandas()
        
        if not ad_df.empty:
            total_ad_views = int(ad_df['views'].sum())
            print(f"Total advertising views: {total_ad_views:,}")
        else:
            print("No advertising views found")
            
    except Exception as e:
        print(f"Error getting advertising views: {e}")

def get_search_keywords(client, start_date, end_date, max_results=20):
    """Get top search keywords that led to views
    
    Note: As of 2025, the YouTube Analytics API no longer supports detailed
    search keyword retrieval via insightTrafficSourceDetail dimension.
    """
    try:
        yt_analytics = get_youtube_analytics_client()
        if not yt_analytics:
            console.print("[red]Cannot get search keywords without YouTube Analytics API[/red]")
            return {}
        
        console.print("[dim]Getting top search keywords...[/dim]")
        
        # Get search keywords across all videos
        resp = yt_analytics.reports().query(
            ids=f"channel==MINE",
            startDate=start_date.strftime("%Y-%m-%d"),
            endDate=end_date.strftime("%Y-%m-%d"),
            metrics="views",
            dimensions="insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SEARCH",
            sort="-views"
        ).execute()
        
        keywords = {}
        if 'rows' in resp:
            for row in resp['rows']:
                keyword, views = row
                if keyword and keyword != '(not provided)' and keyword.strip():
                    keywords[keyword] = int(views)
                    console.print(f"[dim]  '{keyword}': {views:,} views[/dim]")
        
        return keywords
        
    except Exception as e:
        console.print(f"[yellow]⚠️  Search keywords not available via API[/yellow]")
        console.print("[dim]YouTube Analytics API no longer supports search keyword details[/dim]")
        console.print("[dim]Use YouTube Studio Analytics for search term data[/dim]")
        return {}

def get_video_keywords(client, video_id, start_date, end_date):
    """Get search keywords for a specific video"""
    try:
        yt_analytics = get_youtube_analytics_client()
        if not yt_analytics:
            console.print("[red]Cannot get video keywords without YouTube Analytics API[/red]")
            return {}
        
        console.print(f"[dim]Getting search keywords for video {video_id}...[/dim]")
        
        # Try different approaches since the API has limitations
        approaches = [
            # Approach 1: Try to get keywords for specific video (may not work)
            {
                "dimensions": "insightTrafficSourceDetail",
                "filters": f"video=={video_id};insightTrafficSourceType==YT_SEARCH"
            },
            # Approach 2: Get all keywords and note that we can't filter by video
            {
                "dimensions": "insightTrafficSourceDetail", 
                "filters": "insightTrafficSourceType==YT_SEARCH"
            }
        ]
        
        for i, approach in enumerate(approaches):
            try:
                resp = yt_analytics.reports().query(
                    ids=f"channel==MINE",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics="views",
                    dimensions=approach["dimensions"],
                    filters=approach["filters"],
                    sort="-views"
                ).execute()
                
                keywords = {}
                if 'rows' in resp:
                    for row in resp['rows']:
                        keyword, views = row
                        if keyword and keyword != '(not provided)' and keyword.strip():
                            keywords[keyword] = int(views)
                            console.print(f"[dim]  '{keyword}': {views:,} views[/dim]")
                
                if i == 0 and keywords:
                    console.print("[green]✓ Got video-specific keywords[/green]")
                    return keywords
                elif i == 1:
                    console.print("[yellow]⚠ API limitation: Showing channel-wide keywords (cannot filter by specific video)[/yellow]")
                    return keywords
                    
            except Exception as e:
                console.print(f"[dim]Approach {i+1} failed: {e}[/dim]")
                continue
        
        return {}
        
    except Exception as e:
        console.print(f"[yellow]⚠️  Video-specific keywords not available via API[/yellow]")
        console.print("[dim]YouTube Analytics API no longer supports per-video search keyword details[/dim]")
        console.print("[dim]Use YouTube Studio Analytics for detailed search term data[/dim]")
        return {}

def show_search_keywords_report(client, start_date, end_date, max_results):
    """Show top search keywords that led to views"""
    
    # Header
    title = f"🔑 TOP {max_results} SEARCH KEYWORDS"
    subtitle = f"{start_date} to {end_date}"
    console.print(Panel(f"[bold yellow]{title}[/bold yellow]\n[dim]{subtitle}[/dim]", 
                       box=box.ROUNDED, style="yellow"))
    
    # Get keywords with progress indicator
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
                  console=console) as progress:
        task = progress.add_task("🔑 Getting top search keywords...", total=None)
        keywords = get_search_keywords(client, start_date, end_date, max_results * 2)
        progress.update(task, completed=100)
    
    if not keywords:
        console.print("[dim]No search keywords found for the specified date range[/dim]")
        return
    
    # Sort by views
    sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:max_results]
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Views", justify="right", style="yellow")
    table.add_column("Search Keyword", style="white")
    
    for i, (keyword, views) in enumerate(sorted_keywords, 1):
        table.add_row(
            f"{i:2d}.",
            f"{views:,}",
            f"'{keyword}'"
        )
    
    console.print(table)
    console.print()

def show_latest_video_keywords_report(client, start_date, end_date, max_results=10):
    """Show search keywords for the latest video"""
    
    # Header
    title = f"🎯 SEARCH KEYWORDS FOR LATEST VIDEO"
    subtitle = f"{start_date} to {end_date}"
    console.print(Panel(f"[bold purple]{title}[/bold purple]\n[dim]{subtitle}[/dim]", 
                       box=box.ROUNDED, style="purple"))
    
    # Get latest video (highest views in the period)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
                  console=console) as progress:
        task = progress.add_task("🎯 Finding latest video and keywords...", total=None)
        
        # Get top video by views
        total_report = client.fetch_report(
            dimensions=("video",),
            metrics=("views",),
            start_date=start_date,
            end_date=end_date,
            sort_options=("-views",),
            max_results=1,
        )
        total_df = total_report.to_pandas()
        
        if total_df.empty:
            console.print("[dim]No videos found for the specified date range[/dim]")
            return
        
        latest_video_id = total_df.iloc[0]['video']
        progress.update(task, completed=100)
    
    # Get video info
    video_info = get_video_info([latest_video_id])
    info = video_info.get(latest_video_id, {'title': "Title unavailable", 'date': "Unknown"})
    
    # Show video details
    console.print(f"[bold white]Video:[/bold white] {info['title']} [dim]({info['date']})[/dim]")
    console.print(f"[bold white]Link:[/bold white] [blue underline]https://youtube.com/watch?v={latest_video_id}[/blue underline]")
    console.print()
    
    # Get keywords for this video
    keywords = get_video_keywords(client, latest_video_id, start_date, end_date)
    
    if not keywords:
        console.print("[yellow]⚠️  Video-specific keywords not available via API[/yellow]")
        console.print("[dim]YouTube Analytics API no longer supports per-video search keyword details[/dim]")
        console.print("[dim]Use YouTube Studio Analytics for detailed search term data[/dim]")
        return
    
    # Sort by views and limit results
    sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:max_results]
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Views", justify="right", style="purple")
    table.add_column("Search Keyword", style="white")
    table.add_column("Type", style="cyan", width=8)
    
    branded_keywords_lower = [kw.lower() for kw in BRANDED_KEYWORDS]
    
    for i, (keyword, views) in enumerate(sorted_keywords, 1):
        keyword_type = "🏷️ Branded" if keyword.lower() in branded_keywords_lower else "🔍 Organic"
        table.add_row(
            f"{i:2d}.",
            f"{views:,}",
            f"'{keyword}'",
            keyword_type
        )
    
    console.print(table)
    console.print()

def get_search_keywords(client, start_date, end_date, max_results=20):
    """Get top search keywords that led to views"""
    try:
        yt_analytics = get_youtube_analytics_client()
        if not yt_analytics:
            console.print("[red]Cannot get search keywords without YouTube Analytics API[/red]")
            return {}
        
        # YouTube Analytics API has limits on maxResults for keywords (usually 20-25)
        # Try with requested amount first, fallback to smaller amounts
        limits_to_try = [min(max_results, 25), 20, 10]
        
        for limit in limits_to_try:
            try:
                resp = yt_analytics.reports().query(
                    ids=f"channel==MINE",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics="views",
                    dimensions="insightTrafficSourceDetail",
                    filters="insightTrafficSourceType==YT_SEARCH",
                    sort="-views",
                    maxResults=limit
                ).execute()
                
                keywords = {}
                if 'rows' in resp:
                    for row in resp['rows']:
                        keyword, views = row
                        if keyword and keyword != '(not provided)' and keyword.strip():
                            keywords[keyword] = int(views)
                
                if limit < max_results and keywords:
                    console.print(f"[yellow]Note: Limited to {limit} keywords (API limit)[/yellow]")
                
                return keywords
                
            except Exception as inner_e:
                if limit == limits_to_try[-1]:  # Last attempt
                    raise inner_e
                continue
        
        return {}
        
    except Exception as e:
        console.print(f"[yellow]⚠️  Search keywords not available: {e}[/yellow]")
        return {}

def get_video_views(client, start_date, end_date, max_videos=30):
    """Get basic video views for recent videos"""
    try:
        # Use the same approach as the other functions
        total_df = client.retrieve(
            dimensions=["video"],
            metrics=["views"],
            start_date=start_date,
            end_date=end_date,
            max_results=max_videos
        )
        
        if total_df.empty:
            return {}
        
        video_views = {}
        for _, row in total_df.iterrows():
            video_views[row['video']] = int(row['views'])
        
        return video_views
    except Exception as e:
        console.print(f"[red]Error getting video views: {e}[/red]")
        return {}

def show_search_keywords_report(client, start_date, end_date, max_results):
    """Show top search keywords that led to views"""
    
    # Header
    title = f"🔑 TOP {max_results} SEARCH KEYWORDS"
    subtitle = f"{start_date} to {end_date}"
    console.print(Panel(f"[bold blue]{title}[/bold blue]\n[dim]{subtitle}[/dim]", 
                       box=box.ROUNDED, style="blue"))
    
    # Get keywords with progress indicator
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
                  console=console) as progress:
        task = progress.add_task("🔑 Getting top search keywords...", total=None)
        keywords = get_search_keywords(client, start_date, end_date, max_results)
        progress.update(task, completed=100)
    
    if not keywords:
        console.print("[dim]No search keywords found for the specified date range[/dim]")
        console.print()
        return
    
    # Sort by views and limit results
    sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:max_results]
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Views", justify="right", style="purple")
    table.add_column("Search Keyword", style="white")
    
    for i, (keyword, views) in enumerate(sorted_keywords, 1):
        table.add_row(
            f"{i:2d}.",
            f"{views:,}",
            f"'{keyword}'"
        )
    
    console.print(table)
    console.print()

def show_search_traffic_report(client, start_date, end_date, max_results):
    """Show top videos by YouTube search traffic"""
    
    # Header
    title = f"🔍 TOP {max_results} VIDEOS BY YOUTUBE SEARCH TRAFFIC"
    subtitle = f"{start_date} to {end_date}"
    console.print(Panel(f"[bold blue]{title}[/bold blue]\n[dim]{subtitle}[/dim]", 
                       box=box.ROUNDED, style="blue"))
    
    # Get search traffic views with progress indicator
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
                  console=console) as progress:
        task = progress.add_task("🔍 Getting YouTube search traffic...", total=None)
        search_views = get_search_traffic_views(client, start_date, end_date, max_results * 3)
        progress.update(task, completed=100)
    
    # Create list of videos with search views and sort
    video_data = []
    for video_id, search_count in search_views.items():
        if search_count > 0:
            video_data.append((video_id, search_count))
    
    # Sort by search views and take top results
    video_data.sort(key=lambda x: x[1], reverse=True)
    top_videos = video_data[:max_results]
    
    if not top_videos:
        console.print("[dim]No videos found with search traffic in the specified date range[/dim]")
        return
    
    # Get video info (titles and dates)
    top_video_ids = [vid for vid, _ in top_videos]
    video_info = get_video_info(top_video_ids)
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Search Views", justify="right", style="blue")
    table.add_column("Title", style="white")
    table.add_column("Date", style="cyan", width=8)
    table.add_column("Link", style="blue underline", width=30)
    
    for i, (video_id, search_count) in enumerate(top_videos, 1):
        views = f"{search_count:,}"
        info = video_info.get(video_id, {'title': "Title unavailable", 'date': "Unknown"})
        title = info['title']
        date = info['date']
        link = f"youtube.com/watch?v={video_id}"
        
        table.add_row(
            f"{i:2d}.",
            views,
            title,
            date,
            link
        )
    
    console.print(table)
    console.print()

def show_organic_views_report(client, start_date, end_date, max_results):
    """Show top videos by organic views (excluding advertising)"""
    
    # Header
    title = f"🌱 TOP {max_results} VIDEOS BY ORGANIC VIEWS"
    subtitle = f"{start_date} to {end_date}"
    console.print(Panel(f"[bold green]{title}[/bold green]\n[dim]{subtitle}[/dim]", 
                       box=box.ROUNDED, style="green"))
    
    # Get organic views with progress indicator
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), 
                  console=console) as progress:
        task = progress.add_task("📊 Calculating organic views (excluding advertising)...", total=None)
        organic_views = get_organic_views(client, start_date, end_date, max_results * 3)
        progress.update(task, completed=100)
    
    # Create list of videos with organic views and sort
    video_data = []
    for video_id, organic_count in organic_views.items():
        if organic_count > 0:  # Only include videos with organic views
            video_data.append((video_id, organic_count))
    
    # Sort by organic views and take top results
    video_data.sort(key=lambda x: x[1], reverse=True)
    top_videos = video_data[:max_results]
    
    if not top_videos:
        console.print("[dim]No videos found with organic views in the specified date range[/dim]")
        return
    
    # Get video info (titles and dates)
    top_video_ids = [vid for vid, _ in top_videos]
    video_info = get_video_info(top_video_ids)
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Organic Views", justify="right", style="green")
    table.add_column("Title", style="white")
    table.add_column("Date", style="cyan", width=8)
    table.add_column("Link", style="blue underline", width=30)
    
    for i, (video_id, organic_count) in enumerate(top_videos, 1):
        views = f"{organic_count:,}"
        info = video_info.get(video_id, {'title': "Title unavailable", 'date': "Unknown"})
        title = info['title']
        date = info['date']
        link = f"youtube.com/watch?v={video_id}"
        
        table.add_row(
            f"{i:2d}.",
            views,
            title,
            date,
            link
        )
    
    console.print(table)
    console.print()

def recent_top_videos(days=28, max_results=10):
    """Get top videos from the last N days with multiple report types"""
    client = get_client()
    
    # Calculate date range
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Show organic views report
    show_organic_views_report(client, start_date, end_date, max_results)
    
    # Show search traffic report
    show_search_traffic_report(client, start_date, end_date, max_results)
    
    # Show search keywords report
    show_search_keywords_report(client, start_date, end_date, max_results)

@click.command()
@click.option("--start", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (YYYY-MM-DD)")
@click.option("--max", default=10, help="Maximum number of results")
@click.option("--days", default=28, help="Number of recent days (default mode)")
@click.option("--organic", is_flag=True, help="Show only organic views report")
@click.option("--search", is_flag=True, help="Show only search traffic report")  
@click.option("--keywords", is_flag=True, help="Show only search keywords report")
@click.option("--sync", help="Sync video data to database (provide video ID or 'recent' for recent videos)")
@click.option("--first-week", is_flag=True, help="Compare first week performance across recent videos")
@click.option("--traffic-source", default="BROWSE", help="Traffic source for analysis (BROWSE, YT_SEARCH, ADVERTISING, etc.)")
@click.option("--all", "show_all", is_flag=True, help="Show all reports (default)")
def main(start, end, max, days, organic, search, keywords, sync, first_week, traffic_source, show_all):
    """🎬 YouTube Analytics Stats Tool
    
    Default: Shows comprehensive analytics from last 28 days
    Custom range: Use --start and --end dates
    Report selection: Use --organic, --search, or --keywords for specific reports
    
    Database features:
    --sync recent             Sync recent videos to database
    --sync VIDEO_ID          Sync specific video
    --first-week             Compare first week performance
    """
    
    # Welcome message
    console.print(Panel.fit(
        "[bold magenta]🎬 YouTube Analytics Stats Tool[/bold magenta]\n"
        "[dim]Organic views • Search traffic • Keywords analysis[/dim]",
        border_style="magenta"
    ))
    
    # Handle database operations first
    if sync:
        db = YouTubeAnalyticsDB()
        
        if sync.lower() == 'recent':
            console.print("[blue]Syncing recent videos to database...[/blue]")
            
            # Get recent videos from current API
            client = get_client()
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            video_views = get_video_views(client, start_date, end_date, 10)
            
            for video_id in video_views.keys():
                db.sync_video(video_id, days_back=60)
                
            console.print("[green]✅ Sync complete![/green]")
        else:
            # Sync specific video
            db = YouTubeAnalyticsDB()
            if db.sync_video(sync, days_back=60):
                console.print(f"[green]✅ Synced video {sync}![/green]")
            else:
                console.print(f"[red]❌ Failed to sync video {sync}[/red]")
        return
    
    if first_week:
        db = YouTubeAnalyticsDB()
        recent_videos = db.get_recent_videos(5)
        
        if not recent_videos:
            console.print("[yellow]No videos in database. Run --sync recent first.[/yellow]")
            return
        
        console.print(Panel(f"[bold blue]📊 FIRST WEEK {traffic_source} PERFORMANCE COMPARISON[/bold blue]\n"
                           f"[dim]Comparing first 7 days for {len(recent_videos)} recent videos[/dim]", 
                           box=box.ROUNDED, style="blue"))
        
        analysis = db.analyze_first_week_performance(recent_videos, traffic_source)
        
        # Create comparison table
        table = Table(show_header=True, header_style="bold magenta", box=box.MINIMAL_DOUBLE_HEAD)
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Title", style="white", width=40)
        table.add_column("Published", style="cyan", width=12)
        table.add_column(f"First Week {traffic_source}", justify="right", style="green")
        
        # Sort by first week views
        sorted_videos = sorted(analysis.items(), 
                             key=lambda x: x[1]['first_week_views'], 
                             reverse=True)
        
        for i, (video_id, data) in enumerate(sorted_videos, 1):
            published = datetime.strptime(data['published_date'], '%Y-%m-%d').strftime('%b %d')
            table.add_row(
                f"{i}.",
                data['title'][:37] + "..." if len(data['title']) > 40 else data['title'],
                published,
                f"{data['first_week_views']:,}"
            )
        
        console.print(table)
        console.print()
        return
    
    # Regular reporting mode
    client = get_client()
    
    if start and end:
        # Custom date range mode
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    else:
        # Default mode: recent days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
    
    # Determine which reports to show
    if not any([organic, search, keywords]):
        show_all = True  # Default to all reports if none specified
    
    # Show selected reports
    if show_all or organic:
        show_organic_views_report(client, start_date, end_date, max)
    
    if show_all or search:
        show_search_traffic_report(client, start_date, end_date, max)
    
    if show_all or keywords:
        show_search_keywords_report(client, start_date, end_date, max)
    
    # Success message
    console.print(Panel(
        "[bold green]✅ Reports complete![/bold green]",
        style="green", box=box.ROUNDED
    ))

if __name__ == "__main__":
    main()
