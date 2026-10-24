"""YouTube Control - Maya / Jarvis ke liye.
Bolke control: "youtube open kar", "chrome me youtube open kar",
"youtube pe koi gana chala de", "youtube pe <song name> chala de".

Koi extra install nahi chahiye - sirf stdlib.
Gana DIRECT play hota hai (pehle video ka watch URL khulta hai, autoplay).
"""

import json
import os
import random
import re
import urllib.parse
import urllib.request
import webbrowser

# Koi bhi gana bolo toh inme se random bajega
RANDOM_SONGS = [
    "Arijit Singh Tum Hi Ho",
    "Arijit Singh Kesariya",
    "Shreya Ghoshal Teri Meri",
    "AP Dhillon Brown Munde",
    "Arijit Singh Apna Time Aayega Gully Boy",
    "Kishore Kumar Mere Sapno Ki Rani",
    "Lata Mangeshkar Lag Jaa Gale",
    "Sonu Nigam Kal Ho Naa Ho",
    "AR Rahman Chaiyya Chaiyya",
    "Neha Kakkar Dilbar",
]

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

# Shuru ke filler shabd (aage se hatate jao jab tak filler mile)
LEAD_FILLERS = {
    "youtube", "yutub", "utube", "youtu", "chrome",
    "mere", "mera", "meri", "me", "mein", "men", "pe", "pay", "par",
    "ko", "koi", "ek",
    "maya", "janu", "sona", "baby", "darling", "yaar", "bhai", "bro",
    "please", "plz", "jara", "zara", "achha", "accha", "acha", "sa",
    "gana", "gaana", "song", "songs", "music", "video", "geet",
    "play", "baja", "bajao", "chala", "chal", "chalao", "laga", "lagao",
    "suna", "sunao", "suno", "ye", "yeh", "yo",
}

# Aakhir ke filler shabd (peeche se hatate jao jab tak filler mile)
# NOTE: "tum/hi/ho" isme NAHI hai taaki "tum hi ho" na toote.
TRAIL_FILLERS = {
    "de", "do", "dijiye", "diyo",
    "chala", "chal", "chalana", "chalao", "chalaye", "chalen", "chale", "chalna", "chalnaa",
    "baja", "bajao", "bajaye", "bajaao",
    "laga", "lagao", "lagaye",
    "suna", "sunao", "sunaye", "suno",
    "play", "karo", "kar", "karke",
    "gana", "gaana", "gane", "gaane", "song", "songs", "music", "video", "videos", "geet",
    "chahiye", "thik", "theek", "ok", "okay",
    "na", "o", "please", "plz", "jara", "zara", "ek", "baar",
    "youtube", "yutub", "utube", "youtu", "on",
}


def find_chrome():
    """Chrome installed hai toh uska path do, warna None."""
    for p in CHROME_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def _open_url(url, prefer_chrome=False):
    """URL kholo. Chrome manga ho aur mila ho toh Chrome me, warna default me."""
    print(f"[YouTube] khol raha hoon: {url}")
    try:
        if prefer_chrome:
            c = find_chrome()
            if c:
                try:
                    webbrowser.get(f'"{c}" %s').open(url)
                    return True
                except Exception as e:
                    print(f"[YouTube] chrome me nahi khula ({e!r}), default me try")
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"[YouTube] open fail: {e!r}")
        return False


def open_youtube(prefer_chrome=False):
    """Sirf youtube.com kholo."""
    ok = _open_url("https://www.youtube.com", prefer_chrome)
    return "YouTube khol diya janu!" if ok else "YouTube kholne me dikkat aayi janu!"


def _scrape_video_id(query):
    """YouTube search page se pehla video ID nikalo. Na mile toh None."""
    try:
        url = ("https://www.youtube.com/results?search_query="
               + urllib.parse.quote_plus(query))
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0 Safari/537.36"),
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            # Consent wall bypass - warna video list nahi milti
            "Cookie": "CONSENT=YES+cb.20210328-17-p0.en+FX+175;",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="ignore")
        for pat in (r'"videoId":"([0-9A-Za-z_-]{11})"',
                    r'watch\?v=([0-9A-Za-z_-]{11})',
                    r'/shorts/([0-9A-Za-z_-]{11})'):
            ids = list(dict.fromkeys(re.findall(pat, html)))
            if ids:
                return ids[0]
        print("[YouTube] scrape: page mila par video ID nahi mila")
        return None
    except Exception as e:
        print(f"[YouTube] scrape fail: {e!r}")
        return None


def _api_video_id(query):
    """Backup: public search API se video ID (koi key nahi chahiye)."""
    try:
        url = ("https://yt.lemnoslife.com/noKey/search?q="
               + urllib.parse.quote_plus(query) + "&type=video")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        for item in data.get("items", []):
            vid = (item.get("id", {}).get("videoId")
                   if isinstance(item.get("id"), dict) else item.get("id"))
            if vid and re.fullmatch(r"[0-9A-Za-z_-]{11}", str(vid)):
                return vid
        print("[YouTube] api: jawab mila par video ID nahi")
        return None
    except Exception as e:
        print(f"[YouTube] api fail: {e!r}")
        return None


def search_first_video(query):
    """Pehla video ID: pehle YouTube scrape, fail ho toh backup API."""
    print(f"[YouTube] search kar raha hoon: '{query}'")
    vid = _scrape_video_id(query)
    if vid:
        print(f"[YouTube] video mila: {vid}")
        return vid
    print("[YouTube] backup API try kar raha hoon...")
    vid = _api_video_id(query)
    if vid:
        print(f"[YouTube] video mila: {vid}")
    return vid


def play_on_youtube(query, prefer_chrome=False):
    """Gana DIRECT bajao - pehle video ka watch URL kholo (autoplay)."""
    q = (query or "").strip()
    if not q:
        return play_random_song(prefer_chrome=prefer_chrome)
    vid = search_first_video(q)
    if vid:
        url = f"https://www.youtube.com/watch?v={vid}&autoplay=1"
    else:
        print("[YouTube] direct video nahi mila, search page khol raha hoon")
        url = ("https://www.youtube.com/results?search_query="
               + urllib.parse.quote_plus(q))
    ok = _open_url(url, prefer_chrome)
    if ok:
        return f"Youtube pe '{q}' chala diya janu!"
    return "Gana chalane me dikkat aayi janu!"


def play_random_song(prefer_chrome=False):
    """List me se koi ek random gana bajao."""
    song = random.choice(RANDOM_SONGS)
    return play_on_youtube(song, prefer_chrome=prefer_chrome)


def _clean_query(t):
    """Aage-peeche ke filler shabd hatao, beech ka (gaane ka naam) rakho.

    "tum hi ho" jaise naam nahi tootenge kyunki beech ke shabd hath nahi lagate.
    """
    toks = t.split()
    i = 0
    while i < len(toks) and toks[i] in LEAD_FILLERS:
        i += 1
    j = len(toks)
    while j > i and toks[j - 1] in TRAIL_FILLERS:
        j -= 1
    return " ".join(toks[i:j]).strip(" -:,'\"")


def handle_youtube_command(text):
    """User ki baat me YouTube command ho toh action lo.

    Returns: (handled: bool, reply: str)
    """
    if not text:
        return False, ""
    t = text.lower().strip()

    has_yt = any(k in t for k in ("youtube", "yutub", "utube", "youtu"))
    chrome_manga = "chrome" in t
    gana_manga = any(k in t for k in ("gana", "gaana", "song", "music",
                                      "baja", "chala", "play", "laga",
                                      "sunao", "suna"))
    open_manga = any(k in t for k in ("open", "khol", "kholo", "chalu", "start"))

    # 1) YouTube open (gana nahi manga)
    if has_yt and open_manga and not gana_manga:
        return True, open_youtube(prefer_chrome=chrome_manga)

    # 2) Gana chalana - "youtube" word ho YA sirf "gana chala/baja" bola ho
    if gana_manga and (has_yt or any(k in t for k in ("chala", "baja", "play", "laga", "sunao", "suna"))):
        q = _clean_query(t)
        if not q or q in ("koi", "sa", "bhi", "koisa", "koi sa",
                          "achha", "accha", "ek", "kuch",
                          "achha sa", "accha sa", "koi achha sa", "koi accha sa"):
            return True, play_random_song(prefer_chrome=chrome_manga)
        return True, play_on_youtube(q, prefer_chrome=chrome_manga)

    # 3) Sirf "youtube" bola -> open samjho
    if has_yt and (open_manga or chrome_manga or len(t.split()) <= 3):
        return True, open_youtube(prefer_chrome=chrome_manga)

    return False, ""


# Direct test: python youtube_control.py "youtube pe kesariya chala de"
if __name__ == "__main__":
    import sys

    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "youtube pe kesariya chala de"
    print("saaf query:", repr(_clean_query(cmd.lower().strip())))
    ok, msg = handle_youtube_command(cmd)
    print(f"handled={ok} -> {msg}")
