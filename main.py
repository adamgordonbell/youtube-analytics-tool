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
from youtube_analytics.reports import OrganicViewsReport, SearchTrafficReport, FirstWeekReport, TrafficBreakdownReport, First90DaysSearchReport, ShortsDetectionReport
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
@click.option("--organic", is_flag=True, help="Show only organic views report")
@click.option("--search", is_flag=True, help="Show only search traffic report")  
@click.option("--first-week", is_flag=True, help="Show first week performance comparison")
@click.option("--first-90-days-search", is_flag=True, help="Show first 90 days search performance")
@click.option("--shorts", is_flag=True, help="Show Shorts detection report")
@click.option("--traffic-source", default=TrafficSources.BROWSE_FEATURES, 
              help=f"Traffic source for first-week analysis ({', '.join(TrafficSources.first_week_options())})")
@click.option("--traffic-breakdown", help="Show traffic breakdown for specific video and date (format: VIDEO_ID,YYYY-MM-DD)")
@click.option("--sync", help="Sync video data (provide video ID or 'recent' for recent videos)")
@click.option("--complete-history", is_flag=True, help="When syncing, fetch complete history from publish date to today")
@click.option("--backfill-content-types", is_flag=True, help="Backfill content type (Short/Long) for videos missing this info")
@click.option("--all", "show_all", is_flag=True, help="Show all reports (default)")
def main(start, end, max_results, days, organic, search, first_week, first_90_days_search, shorts, traffic_source, traffic_breakdown, sync, complete_history, backfill_content_types, show_all):
    """🎬 YouTube Analytics Tool
    
    Automatically fetches missing data on-demand and provides modular reports.
    
    Default: Shows comprehensive analytics from last 28 days
    Custom range: Use --start and --end dates
    Report selection: Use --organic, --search, or --first-week for specific reports
    
    Examples:
      python main.py                           # All reports, last 28 days
      python main.py --organic --max 15       # Top 15 organic videos
      python main.py --start 2024-01-01 --end 2024-01-31  # Custom date range
      python main.py --sync recent             # Sync recent videos
      python main.py --backfill-content-types # Update Short/Long format for videos
      python main.py --first-week --traffic-source YT_SEARCH  # First week search performance
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
                if fetcher.backfill_video_complete_history(sync):
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
    if not any([organic, search, first_week, first_90_days_search, shorts]):
        show_all = True  # Default to all reports if none specified
    
    success_count = 0
    
    # Run selected reports
    if show_all or organic:
        report = OrganicViewsReport(db, fetcher)
        if report.run_report(start_date, end_date, max_results):
            success_count += 1
    
    if show_all or search:
        report = SearchTrafficReport(db, fetcher)
        if report.run_report(start_date, end_date, max_results):
            success_count += 1
    
    if first_week:
        # First week report needs recent videos (not filtered by date range)
        recent_end = date.today()
        recent_start = recent_end - timedelta(days=90)  # Look back further for recent videos
        
        report = FirstWeekReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results, traffic_source=traffic_source):
            success_count += 1
    
    if first_90_days_search:
        # 90-day search report analyzes recent videos
        recent_end = date.today()
        recent_start = recent_end - timedelta(days=180)  # Look back further for recent videos
        
        report = First90DaysSearchReport(db, fetcher)
        if report.run_report(recent_start, recent_end, max_results):
            success_count += 1
    
    if shorts:
        # Shorts detection report
        report = ShortsDetectionReport(db, fetcher)
        if report.run_report(start_date, end_date, max_results):
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
