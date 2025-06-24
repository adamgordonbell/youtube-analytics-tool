# YouTube Analytics System Documentation

A comprehensive YouTube analytics tool with SQLite database storage for advanced video performance analysis.

## 📁 System Architecture

### Core Files

| File | Purpose | Description |
|------|---------|-------------|
| `youtube_stats.py` | Main CLI Tool | Real-time analytics reports and database operations |
| `youtube_analytics_db.py` | Database System | SQLite storage and historical analysis engine |
| `client_secrets.json` | OAuth Config | YouTube Analytics API credentials |
| `tokens.json` | Auth Tokens | YouTube Analytics API access tokens |
| `youtube_data_tokens.json` | Data API Tokens | YouTube Data API v3 access tokens |
| `youtube_analytics.db` | SQLite Database | Historical video performance data |
| `YOUTUBE_API_SETUP.md` | Setup Guide | API configuration instructions |

## 🎬 Main Tool: youtube_stats.py

### Real-Time Analytics Reports

The main CLI tool provides three core real-time reports:

#### 🌱 Organic Views Report (`--organic`)
- Shows videos ranked by **true organic performance** (excluding advertising)
- Reveals actual audience engagement vs paid promotion
- Example: "Pulumi in Three Minutes" shows 1,361 organic vs 71,785 total views (98.1% ads)

#### 🔍 Search Traffic Report (`--search`) 
- Shows videos ranked by **YouTube search discovery**
- Identifies which content gets found organically
- Example: Same video gets 761 search views out of total organic traffic

#### 🔑 Search Keywords Report (`--keywords`)
- Shows actual **search terms** people use to find your content
- Limited to 25 keywords max due to API constraints
- Example: "pulumi" (562 views), "pulumi tutorial" (87 views), "pulumi vs terraform" (51 views)

### Database Operations

#### Sync Commands
```bash
# Sync specific video with 60 days of historical data
python youtube_stats.py --sync VIDEO_ID

# Sync recent videos (in development)
python youtube_stats.py --sync recent
```

#### Analysis Commands
```bash
# Compare first week performance across recent videos
python youtube_stats.py --first-week --traffic-source YT_SEARCH
python youtube_stats.py --first-week --traffic-source SUBSCRIBER
python youtube_stats.py --first-week --traffic-source ADVERTISING
```

### Usage Examples

```bash
# Default: All three real-time reports
python youtube_stats.py

# Specific reports
python youtube_stats.py --organic
python youtube_stats.py --search  
python youtube_stats.py --keywords --max 25

# Custom date range
python youtube_stats.py --start 2025-01-01 --end 2025-06-24

# Database operations
python youtube_stats.py --sync Q8tw6YTD3ac
python youtube_stats.py --first-week --traffic-source YT_SEARCH
```

## 🗃️ Database System: youtube_analytics_db.py

### SQLite Schema

#### Videos Table
```sql
CREATE TABLE videos (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    published_date DATE NOT NULL,
    channel_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Daily Metrics Table
```sql
CREATE TABLE daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    date DATE NOT NULL,
    days_since_published INTEGER NOT NULL,
    traffic_source TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos (video_id),
    UNIQUE(video_id, date, traffic_source)
);
```

### Key Classes

#### YouTubeAnalyticsDB
Main database interface with methods:
- `sync_video(video_id, days_back=60)` - Download and store video analytics
- `analyze_first_week_performance(video_ids, traffic_source)` - Compare early performance
- `get_recent_videos(limit=10)` - Get most recently published videos

#### Data Models
- `VideoInfo` - Video metadata (ID, title, published date, channel)
- `DailyMetric` - Daily view data (video, date, days since published, traffic source, views)

### Database Features

#### Historical Storage
- **Daily traffic source breakdown** for each video
- **Days since published** calculation for trend analysis
- **Automatic deduplication** with UNIQUE constraints
- **Performance indexes** on common query patterns

#### Analysis Capabilities
- **First week performance** comparison across videos
- **Traffic source analysis** (search vs subscriber vs advertising)
- **Publication timing** impact on performance
- **Extensible for custom queries** and reporting

## 🔧 API Integration

### YouTube Analytics API v2
**Purpose**: Historical performance data and traffic source breakdown
**Scope**: `https://www.googleapis.com/auth/yt-analytics.readonly`
**Token File**: `tokens.json`

**Key Endpoints Used**:
- Daily traffic source breakdown: `dimensions=day,insightTrafficSourceType`
- Video performance: `dimensions=video,insightTrafficSourceType` 
- Search keywords: `dimensions=insightTrafficSourceDetail`

### YouTube Data API v3
**Purpose**: Video metadata (titles, published dates, descriptions)
**Scope**: `https://www.googleapis.com/auth/youtube.readonly`
**Token File**: `youtube_data_tokens.json`

**Key Endpoints Used**:
- Video details: `videos().list(part='snippet', id=video_id)`

## 📊 Traffic Source Types

The system tracks these YouTube traffic sources:

| Source | Description | Use Case |
|--------|-------------|----------|
| `ADVERTISING` | Paid promotion views | Measure paid vs organic performance |
| `YT_SEARCH` | YouTube search results | Organic discovery through search |
| `SUBSCRIBER` | Subscriber feeds/notifications | Existing audience engagement |
| `EXT_URL` | External website referrals | Social media, blog posts, etc. |
| `RELATED_VIDEO` | YouTube's related video suggestions | Algorithmic recommendations |
| `YT_CHANNEL` | Channel page visits | Direct channel engagement |
| `NO_LINK_OTHER` | Direct traffic/other sources | Bookmarks, direct URLs |
| `PLAYLIST` | Playlist plays | Playlist optimization success |
| `NOTIFICATION` | YouTube notifications | Notification engagement |
| `YT_OTHER_PAGE` | Other YouTube pages | Browse features, trending |

## 🎯 Analysis Use Cases

### Content Strategy
1. **Organic Performance**: Compare true audience engagement across videos
2. **Search Optimization**: Identify top-performing keywords and optimize content
3. **Advertising ROI**: Measure organic vs paid view ratios

### Publishing Strategy  
1. **First Week Analysis**: Compare early performance patterns across videos
2. **Traffic Source Trends**: Understand how different content types get discovered
3. **Timing Impact**: Analyze publication timing effects on performance

### Example Insights
- **"Pulumi in Three Minutes"**: 98.1% advertising, shows heavy promotion impact
- **Search Terms**: "pulumi" dominates (562 views), tutorial content in demand
- **First Week Patterns**: Can compare how new videos perform in critical first 7 days

## 🚀 Setup and Configuration

### Prerequisites
1. **Python Environment**: Virtual environment with dependencies
2. **Google Cloud Project**: With YouTube APIs enabled
3. **OAuth Credentials**: Downloaded as `client_secrets.json`
4. **API Tokens**: Generated through OAuth flow

### Installation
```bash
# Install dependencies
pip install click rich google-api-python-client google-auth-oauthlib analytix

# Initialize database
python -c "from youtube_analytics_db import YouTubeAnalyticsDB; YouTubeAnalyticsDB()"

# Test basic functionality
python youtube_stats.py --organic
```

### First-Time Setup
1. Follow `YOUTUBE_API_SETUP.md` for API configuration
2. Run OAuth flow to generate token files
3. Sync initial video data: `python youtube_stats.py --sync VIDEO_ID`
4. Start analysis: `python youtube_stats.py --first-week`

## 🔍 Advanced Usage

### Database Queries
Direct SQLite access for custom analysis:
```python
from youtube_analytics_db import YouTubeAnalyticsDB
import sqlite3

db = YouTubeAnalyticsDB()
conn = sqlite3.connect(db.db_path)

# Custom query: Weekly performance trends
cursor.execute('''
    SELECT 
        v.title,
        dm.days_since_published / 7 as week_number,
        dm.traffic_source,
        SUM(dm.views) as weekly_views
    FROM daily_metrics dm
    JOIN videos v ON dm.video_id = v.video_id
    WHERE dm.days_since_published <= 28
    GROUP BY v.video_id, week_number, dm.traffic_source
    ORDER BY v.published_date DESC, week_number, weekly_views DESC
''')
```

### Performance Monitoring
```bash
# Daily sync routine (could be automated)
python youtube_stats.py --sync recent

# Weekly analysis
python youtube_stats.py --first-week --traffic-source YT_SEARCH
python youtube_stats.py --first-week --traffic-source SUBSCRIBER

# Monthly keyword review
python youtube_stats.py --keywords --max 25
```

## 🛠️ Troubleshooting

### Common Issues

#### Token Expiration
- **Symptom**: OAuth errors, "invalid_client" messages
- **Solution**: Re-run OAuth flow, check `client_secrets.json`

#### API Limits
- **Symptom**: 400 errors, "query not supported" messages  
- **Solution**: Reduce `--max` parameters, check API quotas

#### Database Issues
- **Symptom**: SQLite errors, missing data
- **Solution**: Delete `youtube_analytics.db` and re-sync videos

#### Missing Data
- **Symptom**: Empty analysis results
- **Solution**: Ensure videos are synced first with `--sync VIDEO_ID`

### Debug Commands
```bash
# Check database contents
python -c "
from youtube_analytics_db import YouTubeAnalyticsDB
import sqlite3
db = YouTubeAnalyticsDB()
conn = sqlite3.connect(db.db_path)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM videos')
print(f'Videos: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM daily_metrics') 
print(f'Daily metrics: {cursor.fetchone()[0]}')
"

# Test API connectivity
python youtube_stats.py --keywords --max 5
```

## 📈 Future Enhancements

### Planned Features
1. **Automated Sync**: Scheduled background syncing of recent videos
2. **Trend Analysis**: Weekly/monthly performance trend reports
3. **Comparative Analytics**: Cross-channel or competitor analysis
4. **Export Features**: CSV/JSON export for external analysis
5. **Web Dashboard**: Browser-based analytics interface

### Extension Points
- **Custom Traffic Sources**: Add new traffic source categorizations
- **Advanced Metrics**: Watch time, engagement rate, subscriber conversion
- **Alerting**: Performance threshold notifications
- **Integration**: Connect to other analytics platforms

## 📝 Technical Notes

### Performance Considerations
- **API Rate Limits**: YouTube Analytics has daily quotas
- **Database Size**: Each video generates ~30-60 daily metric records
- **Sync Duration**: Full video sync takes 10-30 seconds per video

### Data Accuracy
- **Real-time Lag**: YouTube data has 24-48 hour delay
- **Aggregation Differences**: API vs Studio may show slight variations
- **Traffic Source Evolution**: YouTube periodically updates traffic categorization

### Security
- **Token Storage**: Keep `tokens.json` and `client_secrets.json` secure
- **Database Access**: SQLite file contains sensitive analytics data
- **API Keys**: Never commit OAuth credentials to version control

---

*This system provides professional-grade YouTube analytics with the flexibility to analyze performance patterns that YouTube Studio doesn't easily reveal.*
