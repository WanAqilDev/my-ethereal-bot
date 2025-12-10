import yt_dlp
import json

# Options from music_cog.py
YDL_OPTIONS = {
    'format': 'bestaudio',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'force_ipv4': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web']
        }
    }
}

import time

def test_speed(search_term):
    print(f"Testing speed for: {search_term}")
    
    # Test android_creator WITHOUT force_ipv4
    opts = YDL_OPTIONS.copy()
    opts['force_ipv4'] = False
    opts['extractor_args'] = {'youtube': {'player_client': ['android_creator']}}
    opts['format'] = 'bestaudio'
    
    print("\n--- Testing android_creator (IPv6 allowed) ---")
    start_time = time.time()
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{search_term}", download=True)['entries'][0]
            duration = time.time() - start_time
            print(f"\n[SUCCESS] Downloaded in {duration:.2f} seconds")
        except Exception as e:
            print(f"\n[FAIL] {e}")

if __name__ == "__main__":
    test_speed("never gonna give you up")
