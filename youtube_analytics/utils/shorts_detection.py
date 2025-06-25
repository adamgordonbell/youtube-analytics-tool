"""
Simple, reliable Shorts detection based on video duration
"""

def is_video_short(duration_seconds: int) -> bool:
    """
    Determine if a video is a YouTube Short based on duration.
    
    YouTube Shorts must be 60 seconds or less by platform definition.
    This is the most reliable detection method available.
    
    Args:
        duration_seconds: Video duration in seconds
        
    Returns:
        True if video is a Short (≤60 seconds), False if regular video
    """
    return duration_seconds <= 60


def get_video_type_label(duration_seconds: int) -> str:
    """
    Get a human-readable label for video type.
    
    Args:
        duration_seconds: Video duration in seconds
        
    Returns:
        "Short" or "Video" label
    """
    return "Short" if is_video_short(duration_seconds) else "Video"


def get_video_type_emoji(duration_seconds: int) -> str:
    """
    Get an emoji representation for video type.
    
    Args:
        duration_seconds: Video duration in seconds
        
    Returns:
        Emoji string representing video type
    """
    return "🎬" if is_video_short(duration_seconds) else "📺"


def format_duration(duration_seconds: int) -> str:
    """
    Format duration for display.
    
    Args:
        duration_seconds: Duration in seconds
        
    Returns:
        Formatted duration string (e.g., "1:23", "45s")
    """
    if duration_seconds < 60:
        return f"{duration_seconds}s"
    
    minutes = duration_seconds // 60
    seconds = duration_seconds % 60
    
    if minutes < 60:
        return f"{minutes}:{seconds:02d}"
    
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"
