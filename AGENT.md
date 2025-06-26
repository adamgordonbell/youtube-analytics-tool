# YouTube Analytics Tool - Agent Context

## Usage
- Activate venv: `source venv/bin/activate`
- Load functions: `source util/functions` then use shortcuts like `,ranking`, `,7-day-browse`, `,spikes`
- Main CLI: `python main.py --video-ranking` or `python main.py --first-n-days --n-days 7`

## Architecture
- **Database**: SQLite at `youtube_analytics.db` stores video info + daily metrics
- **APIs**: YouTube Analytics API (quotas sensitive) + YouTube Data API v3
- **Reports**: Modular system in `youtube_analytics/reports/` with quota-aware fallbacks
- **Data Flow**: Fetcher → Database → Reports (auto-backfills missing historical data)
