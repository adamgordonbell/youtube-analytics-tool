# YouTube Analytics Tool

A CLI tool for analyzing YouTube channel performance with automatic data fetching and rich reporting.

## Features

- **Organic Views Analysis**: Exclude advertising traffic to see true organic performance
- **Search Traffic Breakdown**: Analyze how viewers find your content via YouTube search
- **First Week Performance**: Compare early performance patterns across videos
- **Automatic Data Fetching**: Tool fetches missing data on-demand
- **Rich Terminal UI**: Beautiful, colored output with progress indicators

## Quick Start

1. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Set up YouTube API credentials** (if not already done):
   - Follow the setup guide in `YOUTUBE_ANALYTICS_GUIDE.md`
   - Place your `client_secrets.json` file in the project directory

3. **Run your first report**:
   ```bash
   python main.py --organic
   ```

## Usage

### Using Helper Functions (Recommended)
```bash
# Load helper functions
source util/functions

# Run reports using simple commands
,organic              # Top organic videos
,search               # YouTube search traffic
,all                  # All reports
,first-week "Browse features" # First week performance by traffic source
,sync recent          # Sync recent videos
,sync VIDEO_ID        # Sync specific video
```

### Direct Commands
```bash
# All reports for last 28 days
python main.py

# Specific reports
python main.py --organic
python main.py --search
python main.py --first-week

# Custom options
python main.py --organic --max 15
python main.py --start 2024-01-01 --end 2024-01-31
python main.py --first-week --traffic-source "YouTube search"

# Data management
python main.py --sync recent
python main.py --sync VIDEO_ID
```

## Traffic Sources

The tool analyzes these YouTube traffic sources:
- **ADVERTISING**: Paid YouTube ads
- **YT_SEARCH**: YouTube search results
- **SUBSCRIBER**: Subscriber feeds and notifications
- **EXT_URL**: External websites and social media
- **RELATED_VIDEO**: YouTube's suggested videos
- **YT_CHANNEL**: Your channel page visits
- **PLAYLIST**: Playlist placements
- **NOTIFICATION**: YouTube notifications
- **NO_LINK_OTHER**: Direct traffic
- **YT_OTHER_PAGE**: Other YouTube pages

## Key Insights

This tool helps answer questions like:
- What percentage of my views come from advertising vs. organic sources?
- Which videos perform best organically in their first week?
- What search terms are driving traffic to my content?
- How does subscriber engagement compare across videos?

## Documentation

See `YOUTUBE_ANALYTICS_GUIDE.md` for complete setup instructions, API configuration, and advanced usage examples.

## Requirements

- Python 3.7+
- YouTube Analytics API access
- YouTube Data API v3 access
- Channel ownership or management permissions

## License

MIT License
