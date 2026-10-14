#!/bin/bash

# Generate All-Time Traffic Source Reports (Top 30)
# Creates CSV files for each major traffic source covering full channel history

echo "🎬 Generating All-Time Traffic Source Reports..."

# Create output directory
mkdir -p alltime_reports
cd alltime_reports

# Activate virtual environment
source ../venv/bin/activate

echo "📊 Generating Organic Traffic Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "organic" --max 30 --csv organic_alltime.csv

echo "🔍 Generating YouTube Search Report..."  
python ../main.py --first-n-days --n-days 2000 --traffic-source "YouTube search" --max 30 --csv search_alltime.csv

echo "🌐 Generating External Traffic Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "External" --max 30 --csv external_alltime.csv

echo "📱 Generating Browse Features Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "Browse features" --max 30 --csv browse_alltime.csv

echo "💡 Generating Suggested Videos Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "Suggested videos" --max 30 --csv suggested_alltime.csv

echo "📺 Generating Channel Pages Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "Channel pages" --max 30 --csv channel_alltime.csv

echo "🔗 Generating Direct/Unknown Traffic Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "Direct or unknown" --max 30 --csv direct_alltime.csv

echo "📋 Generating Playlists Report..."
python ../main.py --first-n-days --n-days 2000 --traffic-source "Playlists" --max 30 --csv playlists_alltime.csv

cd ..

echo "✅ All reports generated in alltime_reports/ folder:"
ls -la alltime_reports/*.csv

echo ""
echo "📊 Report Summary:"
echo "- organic_alltime.csv     - All non-advertising traffic"
echo "- search_alltime.csv      - YouTube search results"  
echo "- external_alltime.csv    - External websites, social media"
echo "- browse_alltime.csv      - YouTube browse features, subscriber feeds"
echo "- suggested_alltime.csv   - YouTube's algorithmic recommendations"
echo "- channel_alltime.csv     - Direct channel page visits"
echo "- direct_alltime.csv      - Bookmarks, direct URLs"
echo "- playlists_alltime.csv   - Playlist plays"
