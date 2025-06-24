# YouTube Analytics Tool

A comprehensive CLI tool for analyzing YouTube channel performance with a focus on organic views, search traffic, and keyword analysis.

## Features

- **Organic Views Analysis**: Exclude advertising traffic to see true organic performance
- **Search Traffic Breakdown**: Analyze how viewers find your content via YouTube search
- **Keyword Analysis**: Discover which search terms drive traffic to your channel
- **Historical Data**: Store and analyze performance trends over time
- **First Week Performance**: Compare early performance patterns across videos
- **Rich Terminal UI**: Beautiful, colored output with progress indicators

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up YouTube API credentials**:
   - Follow the setup guide in `YOUTUBE_ANALYTICS_GUIDE.md`
   - Place your `client_secrets.json` file in the project directory

3. **Run your first report**:
   ```bash
   python youtube_stats.py --organic
   ```

## Usage Examples

### Real-time Reports
```bash
# Organic views (excluding advertising)
python youtube_stats.py --organic

# YouTube search traffic only
python youtube_stats.py --search

# Top search keywords for your channel
python youtube_stats.py --keywords

# All reports at once
python youtube_stats.py --all
```

### Historical Analysis
```bash
# Store historical data for a video
python youtube_stats.py --sync Q8tw6YTD3ac

# Analyze first week performance by traffic source
python youtube_stats.py --first-week --traffic-source SUBSCRIBER
python youtube_stats.py --first-week --traffic-source YT_SEARCH
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
