#!/usr/bin/env python3
"""
YouTube Analytics Tool - Main Entry Point

A user-friendly YouTube analytics tool with on-demand data fetching,
modular reports, and automatic database management.
"""

import click
from datetime import datetime, timedelta, date
from rich.console import Console
from rich.panel import Panel
from rich import box

from youtube_analytics.data import AnalyticsDatabase, DataFetcher
from youtube_analytics.data.fetcher2 import DataFetcher2
from youtube_analytics.reports import SearchTrafficReport, FirstNDaysReport, TrafficBreakdownReport, First90DaysTrafficReport, First180DaysSearchReport, ShortsDetectionReport, SpikeDetectionReport, VideoRankingReport, EvergreenVideosReport
from youtube_analytics.config import TrafficSources, DEFAULT_MAX_RESULTS

console = Console()


def show_welcome():
    """Display welcome message"""
    console.print(Panel.fit(
        "[bold magenta]🎬 YouTube Analytics Tool[/bold magenta]\n"
        "[dim]Modular analytics with on-demand data fetching[/dim]",
        border_style="magenta"
    ))


@click.command()
@click.option("--start", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (YYYY-MM-DD)")
@click.option("--max", "max_results", default=DEFAULT_MAX_RESULTS, help="Maximum number of results")
@click.option("--days", default=28, help="Number of recent days (default mode)")

@click.option("--search", is_flag=True, help="Show only search traffic report")  
@click.option("--first-n-days", is_flag=True, help="Show first N days performance comparison")
@click.option("--n-days", default=7, help="Number of days for first-n-days analysis (default: 7)")
@click.option("--start-day", default=0, help="Starting day offset for first-n-days analysis (default: 0)")
@click.option("--first-90-days-traffic", is_flag=True, help="Show first 90 days traffic performance")
@click.option("--traffic-source-90", default='YouTube search', help="Traffic source for 90-day analysis")
@click.option("--first-180-days-traffic", is_flag=True, help="Show first 180 days traffic performance")
@click.option("--traffic-source-180", default='YouTube search', help="Traffic source for 180-day analysis")
@click.option("--shorts", is_flag=True, help="Show Shorts detection report")
@click.option("--spike-detection", is_flag=True, help="Show traffic spike detection report")
@click.option("--video-ranking", is_flag=True, help="Show video performance ranking report")
@click.option("--video-id", help="Target video ID for ranking analysis (defaults to most recent)")
@click.option("--evergreen", is_flag=True, help="Show evergreen videos report (current performance of older videos)")
@click.option("--evergreen-days", default=30, help="Days of recent traffic to analyze for evergreen report (default: 30)")
@click.option("--evergreen-min-age", default=60, help="Minimum age in days for videos to be considered evergreen (default: 60)")
@click.option("--evergreen-type", default="long", help="Content type filter for evergreen report: short, long, or all (default: long)")
@click.option("--traffic-source", default=TrafficSources.BROWSE_FEATURES, 
              help=f"Traffic source for first-n-days and spike detection analysis ({', '.join(TrafficSources.first_week_options())})")
@click.option("--traffic-breakdown", help="Show traffic breakdown for specific video and date (format: VIDEO_ID,YYYY-MM-DD)")
@click.option("--sync", help="Sync video data (provide video ID or 'recent' for recent videos)")
@click.option("--complete-history", is_flag=True, help="When syncing, fetch complete history from publish date to today")
@click.option("--video-complete-history", help="Get complete history for specific video ID using Fetcher2")
@click.option("--backfill-oldest-complete-history", is_flag=True, help="Backfill complete history for oldest videos using Fetcher2")
@click.option("--refresh", is_flag=True, help="Force refresh data when using --video-complete-history")
@click.option("--max-backfill", default=10, help="Maximum number of oldest videos to backfill when using --backfill-oldest-complete-history")
@click.option("--update-video-listings", is_flag=True, help="Update complete video catalog for channel (metadata only, no analytics)")
@click.option("--backfill-content-types", is_flag=True, help="Backfill content type (Short/Long) for videos missing this info")
@click.option("--all", "show_all", is_flag=True, help="Show all reports (default)")
def main(start, end, max_results, days, search, first_n_days, n_days, start_day, first_90_days_traffic, traffic_source_90, first_180_days_traffic, traffic_source_180, shorts, spike_detection, video_ranking, video_id, evergreen, evergreen_days, evergreen_min_age, evergreen_type, traffic_source, traffic_breakdown, sync, complete_history, video_complete_history, backfill_oldest_complete_history, refresh, max_backfill, update_video_listings, backfill_content_types, show_all):
    """🎬 YouTube Analytics Tool
    
    Automatically fetches missing data on-demand and provides modular reports.
    
    Default: Shows comprehensive analytics from last 28 days
    Custom range: Use --start and --end dates
    Report selection: Use --search or --first-n-days for specific reports
    
    Examples:
      python main.py                           # All reports, last 28 days
      python main.py --first-n-days --n-days 30 --traffic-source organic --max 15  # Top 15 organic videos
      python main.py --start 2024-01-01 --end 2024-01-31  # Custom date range
      python main.py --sync recent             # Sync recent videos
      python main.py --backfill-content-types # Update Short/Long format for videos
      python main.py --first-n-days --n-days 7 --traffic-source "YouTube search"  # First week search performance
      python main.py --first-n-days --n-days 30 --traffic-source organic  # First 30 days organic performance
      python main.py --shorts                  # Show which videos are Shorts
    """
    
    show_welcome()
    
    # Initialize database and fetcher
    db = AnalyticsDatabase()
    fetcher = DataFetcher(db)
    
    # Handle traffic breakdown
    if traffic_breakdown:
        try:
            video_id, date_str = traffic_breakdown.split(',')
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            report = TrafficBreakdownReport(db, fetcher)
            if report.run_traffic_breakdown(video_id, target_date):
                return
            else:
                console.print("[red]❌ Failed to generate traffic breakdown[/red]")
                return
        except ValueError:
            console.print("[red]Error: Traffic breakdown format should be VIDEO_ID,YYYY-MM-DD[/red]")
            console.print("[dim]Example: --traffic-breakdown AUCt28gVR6Y,2025-06-19[/dim]")
            return
    
    # Handle video complete history with Fetcher2
    if video_complete_history:
        console.print(f"[blue]Getting complete history for video {video_complete_history} using Fetcher2...[/blue]")
        fetcher2 = DataFetcher2(db)
        if fetcher2.get_video_complete_history(video_complete_history, refresh=refresh):
            console.print(f"[green]✅ Successfully fetched complete history for video {video_complete_history}[/green]")
        else:
            console.print(f"[red]❌ Failed to fetch complete history for video {video_complete_history}[/red]")
        return
    
    # Handle backfill oldest complete history with Fetcher2
    if backfill_oldest_complete_history:
        console.print(f"[blue]Backfilling complete history for up to {max_backfill} oldest videos...[/blue]")
        fetcher2 = DataFetcher2(db)
        successful_count = fetcher2.backfill_oldest_videos_complete_history(max_backfill)
        if successful_count > 0:
            console.print(f"[green]✅ Successfully backfilled {successful_count} videos[/green]")
        else:
            console.print(f"[yellow]⚠️  No videos were backfilled[/yellow]")
        return
    
    # Handle update video listings with Fetcher2
    if update_video_listings:
        console.print("[blue]Updating complete video catalog for channel...[/blue]")
        fetcher2 = DataFetcher2(db)
        result = fetcher2.ensure_all_channel_videos()
        if result["total"] > 0:
            console.print(f"[green]✅ Video catalog updated: {result['total']} total, {result['added']} added, {result['updated']} updated[/green]")
        else:
            console.print(f"[yellow]⚠️  No videos found or processed[/yellow]")
        return
    
    # Handle sync operations
    if sync:
        if sync.lower() == 'recent':
            if complete_history:
                console.print(f"[blue]Backfilling complete history for {max_results} recent videos...[/blue]")
                successful_videos = fetcher.backfill_recent_videos_complete_history(max_results)
                console.print(f"[green]✅ Successfully backfilled {len(successful_videos)} videos with complete history[/green]")
            else:
                console.print("[blue]Syncing recent videos...[/blue]")
                successful_videos = fetcher.sync_recent_videos(max_results * 2, days)
                console.print(f"[green]✅ Successfully synced {len(successful_videos)} videos[/green]")
        else:
            # Sync specific video
            if complete_history:
                console.print(f"[blue]Backfilling complete history for video {sync}...[/blue]")
                if fetcher.refresh_video_complete_history(sync):
                    console.print(f"[green]✅ Successfully backfilled video {sync} with complete history[/green]")
                else:
                    console.print(f"[red]❌ Failed to backfill video {sync}[/red]")
            else:
                console.print(f"[blue]Syncing video {sync}...[/blue]")
                end_date = date.today()
                start_date = end_date - timedelta(days=60)
                
                if fetcher.ensure_video_data(sync, start_date, end_date):
                    console.print(f"[green]✅ Successfully synced video {sync}[/green]")
                else:
                    console.print(f"[red]❌ Failed to sync video {sync}[/red]")
        return
    
    # Handle content type backfill
    if backfill_content_types:
        console.print(f"[blue]Backfilling content types for up to {max_results} videos...[/blue]")
        if fetcher.backfill_video_content_types(max_results):
            console.print("[green]✅ Content type backfill completed[/green]")
        else:
            console.print("[red]❌ Content type backfill failed[/red]")
        return
    
    # Determine date range
    if start and end:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    else:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
    
    # Determine which reports to show
    if not any([search, first_n_days, first_90_days_traffic, first_180_days_traffic, shorts, spike_detection, video_ranking, evergreen]):
        show_all = True  # Default to all reports if none specified
    
    success_count = 0
    
    # Run selected reports
    if show_all or search:
        report = SearchTrafficReport(db, fetcher)
        if report.run_report(start_date, end_date, max_results):
            success_count += 1
    
    if first_n_days:
        # First N days report uses comprehensive backfill data
        recent_end = date.today() 
        recent_start = recent_end - timedelta(days=365)  # Not used since we use backfill
        
        report = FirstNDaysReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results, traffic_source=traffic_source, days=n_days, start_day=start_day):
            success_count += 1
    
    if first_90_days_traffic:
        # 90-day traffic report analyzes recent videos
        recent_end = date.today()
        recent_start = recent_end - timedelta(days=180)  # Look back further for recent videos
        
        report = First90DaysTrafficReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results, traffic_source=traffic_source_90):
            success_count += 1
    
    if first_180_days_traffic:
        # 180-day traffic report analyzes recent videos
        recent_end = date.today()
        recent_start = recent_end - timedelta(days=365)  # Look back further for recent videos
        
        report = First180DaysSearchReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results, traffic_source=traffic_source_180):
            success_count += 1
    
    if shorts:
        # Shorts detection report
        report = ShortsDetectionReport(db, fetcher)
        if report.run_report(start_date, end_date, max_results):
            success_count += 1
    
    if spike_detection:
        # Spike detection report uses database-only analysis
        recent_end = date.today() 
        recent_start = recent_end - timedelta(days=365)  # Not used since we use database only
        
        report = SpikeDetectionReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results, traffic_source=traffic_source):
            success_count += 1
    
    if video_ranking:
        # Video ranking report uses database-only analysis  
        recent_end = date.today()
        recent_start = recent_end - timedelta(days=365)  # Not used since we use database only
        
        report = VideoRankingReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results, video_id=video_id):
            success_count += 1
    
    if evergreen:
        # Evergreen videos report shows current performance of older videos
        report = EvergreenVideosReport(days_back=evergreen_days, min_age_days=evergreen_min_age, content_type=evergreen_type, db=db, fetcher=fetcher)
        if report.run_report(max_results=max_results):
            success_count += 1
    
    # Show completion message
    if success_count > 0:
        console.print(Panel(
            f"[bold green]✅ {success_count} report(s) completed successfully![/bold green]",
            style="green", box=box.ROUNDED
        ))
    else:
        console.print(Panel(
            "[bold yellow]⚠️  No reports were generated[/bold yellow]",
            style="yellow", box=box.ROUNDED
        ))


if __name__ == "__main__":
    main()
