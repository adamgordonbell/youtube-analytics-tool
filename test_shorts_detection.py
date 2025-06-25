#!/usr/bin/env python3
"""
Test the simple, reliable Shorts detection function
"""

from youtube_analytics.utils import is_video_short, get_video_type_label, get_video_type_emoji, format_duration

def test_shorts_detection():
    """Test the Shorts detection function with various durations"""
    
    test_cases = [
        # (duration_seconds, expected_result, description)
        (30, True, "30 second video"),
        (45, True, "45 second video"),
        (60, True, "60 second video (boundary case)"),
        (61, False, "61 second video"),
        (90, False, "1.5 minute video"),
        (180, False, "3 minute video"),
        (1800, False, "30 minute video"),
        (0, True, "0 second video (edge case)"),
        (1, True, "1 second video"),
        (59, True, "59 second video"),
    ]
    
    print("🧪 Testing Shorts Detection Function")
    print("=" * 60)
    print(f"{'Duration':<12} {'Expected':<10} {'Actual':<10} {'Label':<8} {'Emoji':<5} {'Result'}")
    print("-" * 60)
    
    all_passed = True
    
    for duration, expected, description in test_cases:
        actual = is_video_short(duration)
        label = get_video_type_label(duration)
        emoji = get_video_type_emoji(duration)
        duration_str = format_duration(duration)
        
        passed = "✅" if actual == expected else "❌"
        if actual != expected:
            all_passed = False
        
        print(f"{duration_str:<12} {'Short' if expected else 'Video':<10} "
              f"{'Short' if actual else 'Video':<10} {label:<8} {emoji:<5} {passed}")
    
    print("-" * 60)
    if all_passed:
        print("🎉 All tests passed! Shorts detection function works correctly.")
    else:
        print("❌ Some tests failed!")
    
    print(f"\n📋 Detection Rule: Videos ≤60 seconds = Shorts")
    print(f"📋 This matches YouTube's official definition for Shorts")
    
    return all_passed

if __name__ == "__main__":
    test_shorts_detection()
