#!/usr/bin/env python3
"""
Universal Downloader - A friendly menu wrapper around yt-dlp
Run with: python downloader.py
"""

import os
import re
import sys
import time
import json
import shutil
import threading
import subprocess
import unicodedata
from datetime import datetime

# ---------------------------------------------------------
# Colors / styling
# ---------------------------------------------------------

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"


def supports_color():
    return sys.stdout.isatty()


def colorize(text, *styles):
    if not supports_color():
        return text
    return "".join(styles) + text + C.RESET


def success(msg):  print(colorize(f"✅ {msg}", C.GREEN, C.BOLD))
def error(msg):    print(colorize(f"❌ {msg}", C.RED, C.BOLD))
def warn(msg):     print(colorize(f"⚠️  {msg}", C.YELLOW, C.BOLD))
def info(msg):     print(colorize(f"ℹ️  {msg}", C.CYAN))


# ---------------------------------------------------------
# BUG FIX #9 — box() used len() which counts bytes, not
# display-width.  Emoji and some Unicode chars are "wide"
# (2 columns).  Use wcwidth-style calculation so the box
# borders don't misalign.
# ---------------------------------------------------------

def display_width(text):
    """Return the terminal column-width of a string."""
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("W", "F") else 1
    return w


def box(title, width=40):
    line = "═" * (width - 2)
    print(colorize(f"╔{line}╗", C.CYAN))
    dw   = display_width(title)
    pad  = (width - 2 - dw) // 2
    rpad = width - 2 - dw - pad
    print(colorize(f"║{' ' * pad}{title}{' ' * rpad}║", C.CYAN, C.BOLD))
    print(colorize(f"╚{line}╝", C.CYAN))
    print()


def banner():
    box("Universal Downloader")


def breadcrumb(step, total, label):
    bar = colorize(f"Step {step}/{total}", C.MAGENTA, C.BOLD)
    print(f"{bar} — {colorize(label, C.WHITE, C.BOLD)}")
    print(colorize("─" * 40, C.DIM))


def section(title):
    print()
    print(colorize(f"▸ {title}", C.BLUE, C.BOLD))


def clear():
    os.system('clear' if os.name == 'posix' else 'cls')


# ---------------------------------------------------------
# Spinner
# ---------------------------------------------------------

class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Working..."):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = None

    def _spin(self):
        i = 0
        while not self._stop_event.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r{colorize(frame, C.CYAN)} {self.message}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)
        sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        if supports_color():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            print(self.message)
        return self

    def __exit__(self, *exc):
        if self._thread:
            self._stop_event.set()
            self._thread.join()


# ---------------------------------------------------------
# BUG FIX #10 — FFMPEG_AVAILABLE was set only inside the
# __main__ block, causing a NameError if any function is
# called before that (e.g. when imported or tested).
# Default it to False here at module level.
# ---------------------------------------------------------

FFMPEG_AVAILABLE = False   # overwritten at startup by check_ffmpeg()


# ---------------------------------------------------------
# Core checks
# ---------------------------------------------------------

def check_ytdlp():
    if shutil.which("yt-dlp") is None:
        error("yt-dlp is not installed or not on PATH.")
        print("Install it with:  pip install yt-dlp")
        sys.exit(1)


def check_ffmpeg():
    if shutil.which("ffmpeg") is not None:
        return True

    settings = load_settings()
    if not settings.get("ffmpeg_warning_dismissed"):
        warn("ffmpeg is not installed. Audio conversion and merging")
        warn("separate video/audio streams will fail.")
        print("Install it with:  pkg install ffmpeg   (Termux)")
        print("              or: apt install ffmpeg   (Linux)")
        choice = input("\nDon't show this warning again? (y/n)\n> ").strip().lower()
        if choice == "y":
            settings["ffmpeg_warning_dismissed"] = True
            save_settings(settings)
        print()
    return False


URL_RE = re.compile(r"^https?://[^\s]+\.[^\s]{2,}")

def is_valid_url(url):
    return bool(URL_RE.match(url.strip()))


# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        error(f"Could not save settings: {e}")


# ---------------------------------------------------------
# Welcome tips screen (shows once on first run)
# ---------------------------------------------------------

TIPS = [
    ("Batch mode",      "Enter multiple URLs — the app asks after the first one."),
    ("Re-download",     "Use 'View history' from the main menu to re-queue past URLs."),
    ("MP4 vs Video",    "MP4 forces the .mp4 container; Video picks the best format."),
    ("No ffmpeg?",      "Install it with: pkg install ffmpeg   (Termux)"),
    ("Auto-qualities",  "Qualities shown are real — fetched live from the video."),
    ("Custom folder",   "Choose option 4 in the folder menu to use any path."),
]


def show_welcome_tips():
    """Print a framed tips panel on first run, then never again."""
    settings = load_settings()
    if settings.get("welcome_seen"):
        return

    width = 44
    line  = "─" * (width - 2)
    print(colorize(f"┌{line}┐", C.CYAN))

    title = "  Welcome! Quick tips to get started"
    rpad  = width - 2 - len(title)
    print(colorize(f"│{title}{' ' * rpad}│", C.CYAN, C.BOLD))
    print(colorize(f"├{line}┤", C.CYAN))

    for label, tip in TIPS:
        label_str = colorize(f"  {label:<14}", C.BOLD)
        # build the raw line (no ANSI) to measure padding
        raw = f"  {label:<14}  {tip}"
        rpad = max(0, width - 2 - len(raw))
        inner = f"{label_str}  {tip}{' ' * rpad}"
        print(colorize("│", C.CYAN) + inner + colorize("│", C.CYAN))

    print(colorize(f"└{line}┘", C.CYAN))
    print()

    settings["welcome_seen"] = True
    save_settings(settings)


# ---------------------------------------------------------
# Clipboard auto-paste
# ---------------------------------------------------------

def get_clipboard():
    """
    Try to read the system clipboard.
    Supports Termux (termux-clipboard-get), Linux X11 (xclip / xsel),
    Wayland (wl-paste), and macOS (pbpaste).
    Returns a stripped string or '' on failure — never raises.
    """
    commands = [
        ["termux-clipboard-get"],
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
        ["wl-paste", "--no-newline"],
        ["pbpaste"],
    ]
    for cmd in commands:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                errors="replace", timeout=3
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            continue
    return ""


def prompt_clipboard_url():
    """
    If the clipboard holds a valid URL, offer to use it.
    Returns the URL string if accepted, '' otherwise.
    """
    clip = get_clipboard()
    if not clip or not is_valid_url(clip):
        return ""

    short = clip if len(clip) <= 60 else clip[:57] + "..."
    print(colorize(f"  Clipboard: {short}", C.DIM))
    choice = input(colorize("  Use this URL? (y/n)\n  > ", C.CYAN)).strip().lower()
    print()
    if choice == "y":
        return clip
    return ""


# ---------------------------------------------------------
# Format listing
# ---------------------------------------------------------

def show_formats(url):
    with Spinner("Fetching available formats..."):
        try:
            result = subprocess.run(
                ["yt-dlp", "--no-playlist", "-F", url],
                capture_output=True, text=True, timeout=90
            )
        except subprocess.TimeoutExpired:
            warn("Timed out fetching formats.")
            return

    if result.returncode != 0:
        error("Could not fetch formats.")
        print(result.stderr.strip()[:300])
        return
    print(result.stdout)


# ---------------------------------------------------------
# Auto-detect available video qualities
#
# BUG FIX #1 — timeout raised to 120 s; added one retry
#              on timeout so slow networks don't instantly
#              fall back to the fixed menu.
#
# BUG FIX #2 — yt-dlp -J can emit WARNING/ERROR lines
#              before the JSON object.  We now scan stdout
#              for the first line that starts with '{' so
#              stray log lines don't crash json.loads.
# ---------------------------------------------------------

def fetch_available_qualities(url):
    """
    Returns a sorted list of unique integer heights available for the URL,
    e.g. [144, 360, 720, 1080].  Returns [] on any failure.
    """
    for attempt in range(1, 3):          # up to 2 tries (fix #1)
        with Spinner(f"Detecting available qualities… (attempt {attempt}/2)"):
            try:
                result = subprocess.run(
                    ["yt-dlp", "--no-playlist", "-J", "--skip-download", url],
                    capture_output=True, text=True, timeout=120   # fix #1
                )
            except subprocess.TimeoutExpired:
                if attempt == 2:
                    warn("Timed out detecting qualities.")
                    return []
                continue   # retry

        if result.returncode != 0:
            warn("Could not detect qualities.")
            return []

        # BUG FIX #2 — find the first JSON line, skip log noise
        json_text = None
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("{"):
                json_text = stripped
                break

        if not json_text:
            warn("Could not locate JSON in yt-dlp output.")
            return []

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            warn("Could not parse format info.")
            return []

        heights = set()
        for fmt in data.get("formats", []):
            h = fmt.get("height")
            if h and isinstance(h, int) and h > 0 and fmt.get("vcodec", "none") != "none":
                heights.add(h)

        return sorted(heights)

    return []


def choose_quality_auto(url):
    """
    Present only the heights that actually exist for this URL.
    Falls back to a fixed menu when detection fails.

    BUG FIX #3 — the fallback fixed-menu now validates input
                 in a loop instead of silently returning 'best'.
    """
    heights = fetch_available_qualities(url)

    section("Choose video quality")

    if not heights:
        warn("Could not detect qualities — showing standard options.")
        options = {"1": "360", "2": "720", "3": "1080", "4": "best"}
        print("1. 360p")
        print("2. 720p")
        print("3. 1080p")
        print("4. Best available")
        while True:                                   # fix #3 — loop until valid
            choice = input(colorize("> ", C.CYAN)).strip()
            if choice in options:
                return options[choice]
            warn("Please enter 1, 2, 3 or 4.")
        # unreachable, but satisfies linters
        return "best"

    options = {}
    print(colorize("Available qualities for this video:", C.DIM))
    for i, h in enumerate(heights, 1):
        options[str(i)] = str(h)
        print(f"{i}. {h}p")

    best_num = len(heights) + 1
    options[str(best_num)] = "best"
    print(f"{best_num}. Best available")

    while True:
        choice = input(colorize("> ", C.CYAN)).strip()
        if choice in options:
            selected = options[choice]
            label = "Best available" if selected == "best" else f"{selected}p"
            info(f"Selected: {label}")
            return selected
        warn(f"Please enter a number between 1 and {best_num}.")


# ---------------------------------------------------------
# Platform detection
# ---------------------------------------------------------

def detect_platform(url):
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:   return "YouTube"
    if "instagram.com" in u:                      return "Instagram"
    if "reddit.com" in u:                         return "Reddit"
    if "twitter.com" in u or "x.com" in u:        return "Twitter/X"
    if "facebook.com" in u or "fb.watch" in u:    return "Facebook"
    if "tiktok.com" in u:                          return "TikTok"
    return "Unknown (yt-dlp will try anyway)"


# ---------------------------------------------------------
# Download folder
#
# BUG FIX #7 — when no default is saved, pressing "5" fell
#              through to warn("Invalid choice") instead of
#              asking again.  Now handled explicitly.
# ---------------------------------------------------------

def get_download_folder(skip_save_prompt=False):
    settings = load_settings()
    default  = settings.get("default_folder")

    home = os.path.expanduser("~")
    candidate_roots = [
        "/storage/emulated/0",
        "/sdcard",
        os.path.join(home, "storage", "shared"),
    ]
    storage = next((p for p in candidate_roots if os.path.isdir(p)), None)

    if storage:
        folders = {
            "1": os.path.join(storage, "Download"),
            "2": os.path.join(storage, "Music"),
            "3": os.path.join(storage, "Movies"),
        }
    else:
        folders = {
            "1": os.path.join(home, "Downloads"),
            "2": os.path.join(home, "Music"),
            "3": os.path.join(home, "Movies"),
        }

    while True:
        section("Choose download folder")
        print("1. Downloads")
        print("2. Music")
        print("3. Movies")
        print("4. Custom Folder")
        if default:
            print(f"5. Use saved default ({colorize(default, C.DIM)})")

        choice = input(colorize("> ", C.CYAN)).strip()

        # fix #7 — only honour "5" when a default actually exists
        if choice == "5" and default:
            return default

        if choice in folders:
            path = folders[choice]
            break
        elif choice == "4":
            path = input("Enter full folder path: ").strip()
            if not path:
                warn("No path entered, defaulting to Downloads.")
                path = folders["1"]
            elif not os.path.isdir(path):
                create = input(f"'{path}' doesn't exist. Create it? (y/n)\n> ").strip().lower()
                if create != "y":
                    warn("Cancelled, defaulting to Downloads.")
                    path = folders["1"]
                else:
                    try:
                        os.makedirs(path, exist_ok=True)
                    except Exception as e:
                        error(f"Could not create folder: {e}")
                        path = folders["1"]
            break
        else:
            warn("Invalid choice — please try again.")

    if not os.path.isdir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            path = os.path.join(home, "Downloads")
            os.makedirs(path, exist_ok=True)
            warn(f"Could not access chosen folder. Using {path} instead.")

    if path != default and not skip_save_prompt:
        save_choice = input("Save this as your default folder? (y/n)\n> ").strip().lower()
        if save_choice == "y":
            settings["default_folder"] = path
            save_settings(settings)

    return path


# ---------------------------------------------------------
# Video info
# ---------------------------------------------------------

def fetch_video_info(url):
    with Spinner("Fetching video info..."):
        try:
            result = subprocess.run(
                ["yt-dlp", "--no-playlist", "--skip-download", "--print",
                 "%(title)s\n%(duration_string)s\n%(uploader)s", url],
                capture_output=True, text=True, timeout=60
            )
        except FileNotFoundError:
            error("yt-dlp not found. Install it with: pip install yt-dlp")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            warn("Timed out fetching info (continuing anyway).")
            return None

    if result.returncode != 0:
        warn("Could not fetch video info (continuing anyway).")
        print(result.stderr.strip()[:300])
        return None

    lines    = result.stdout.strip().split("\n")
    title    = lines[0] if len(lines) > 0 else "Unknown"
    duration = lines[1] if len(lines) > 1 else "Unknown"
    uploader = lines[2] if len(lines) > 2 else "Unknown"

    print(f"{colorize('Title:', C.BOLD)}    {title}")
    print(f"{colorize('Duration:', C.BOLD)} {duration}")
    print(f"{colorize('Uploader:', C.BOLD)} {uploader}")
    return {"title": title, "duration": duration, "uploader": uploader}


# ---------------------------------------------------------
# Download type / audio options
# ---------------------------------------------------------

def choose_download_type():
    section("Choose download type")
    print("1. 🎬 Video        (auto-detect qualities)")
    print("2. 🎵 Audio        (MP3)")
    print("3. 📦 MP4          (force MP4 container)")
    print("4. 🔍 Show formats (inspect all streams)")
    choice = input(colorize("> ", C.CYAN)).strip()
    while choice not in ("1", "2", "3", "4"):
        choice = input("Please enter 1, 2, 3 or 4\n> ").strip()
    return {"1": "video", "2": "audio", "3": "mp4", "4": "formats"}[choice]


def choose_audio_options():
    section("Audio quality (bitrate)")
    print("1. 128 kbps  (smaller file)")
    print("2. 192 kbps  (balanced)")
    print("3. 320 kbps  (best quality)")
    choice = input(colorize("> ", C.CYAN)).strip()
    bitrate = {"1": "128", "2": "192", "3": "320"}.get(choice, "192")
    return "mp3", bitrate


# ---------------------------------------------------------
# Confirm summary
# ---------------------------------------------------------

def confirm_summary(url, platform, dtype, quality, folder,
                    audio_format=None, audio_bitrate=None):
    section("Confirm download")
    type_label = {
        "video":   "🎬 Video",
        "audio":   "🎵 Audio (MP3)",
        "mp4":     "📦 MP4",
        "formats": "🔍 Show formats",
    }.get(dtype, dtype)

    print(f"  {colorize('Platform:', C.BOLD)} {platform}")
    print(f"  {colorize('Type:', C.BOLD)}     {type_label}")

    if dtype in ("video", "mp4"):
        label = "Best available" if quality == "best" else f"{quality}p"
        print(f"  {colorize('Quality:', C.BOLD)}  {label}")
    if dtype == "audio":
        fmt = (audio_format or "mp3").upper()
        print(f"  {colorize('Format:', C.BOLD)}   {fmt}")
        if audio_bitrate:
            print(f"  {colorize('Bitrate:', C.BOLD)}  {audio_bitrate} kbps")

    print(f"  {colorize('Folder:', C.BOLD)}   {folder}")
    print(f"  {colorize('URL:', C.BOLD)}      {url}")
    print()
    return input("Proceed with download? (y/n)\n> ").strip().lower() == "y"


# ---------------------------------------------------------
# Progress bar
#
# BUG FIX #6 — file lines can contain non-UTF-8 bytes when
#              the video title has special characters.
#              errors="replace" prevents a UnicodeDecodeError
#              from crashing the whole download mid-way.
# ---------------------------------------------------------

def _print_download_header(video_info, dtype):
    """
    Print a styled banner above the progress bar showing what is downloading.
    Called once at the start of run_with_progress().

    Layout example:
    ╔══════════════════════════════════════════╗
    ║  🎬  Lo-fi hip hop radio — beats to r…  ║
    ║      3:42 · ChilledCow · Video / 1080p  ║
    ╚══════════════════════════════════════════╝
    """
    if not video_info:
        return

    title    = video_info.get("title",    "Unknown")
    duration = video_info.get("duration", "")
    uploader = video_info.get("uploader", "")

    type_icon = {"video": "🎬", "audio": "🎵", "mp4": "📦"}.get(dtype, "⬇")

    # Truncate title to fit nicely
    max_title = 42
    display_title = title if len(title) <= max_title else title[:max_title - 1] + "…"

    # Build the subtitle line from available metadata
    meta_parts = [p for p in [duration, uploader] if p and p != "Unknown"]
    subtitle = "  ·  ".join(meta_parts)
    max_sub = 44
    if len(subtitle) > max_sub:
        subtitle = subtitle[:max_sub - 1] + "…"

    # Box width — wide enough for the longest line
    inner_w = max(len(display_title) + 6, len(subtitle) + 4, 44)
    border   = "═" * (inner_w + 2)

    print()
    print(colorize(f"╔{border}╗", C.CYAN))

    # Title row with icon
    title_line = f"  {type_icon}  {display_title}"
    rpad = inner_w - len(title_line)
    print(colorize("║", C.CYAN) +
          colorize(f"{title_line}{' ' * rpad}  ", C.WHITE, C.BOLD) +
          colorize("║", C.CYAN))

    # Subtitle row (metadata)
    if subtitle:
        sub_line = f"      {subtitle}"
        rpad2 = inner_w - len(sub_line)
        print(colorize("║", C.CYAN) +
              colorize(f"{sub_line}{' ' * rpad2}  ", C.DIM) +
              colorize("║", C.CYAN))

    print(colorize(f"╚{border}╝", C.CYAN))
    print()


def run_with_progress(cmd, video_info=None, dtype="video"):
    """
    Run a yt-dlp command and render a live progress bar.

    video_info : dict from fetch_video_info() — title, duration, uploader
    dtype      : 'video' | 'audio' | 'mp4'  — used for the header icon
                 and to label dual-stream phases (Video stream / Audio stream).
    """
    _print_download_header(video_info, dtype)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        errors="replace",
        bufsize=1
    )

    progress_re = re.compile(
        r"^\[download\]\s+(\d{1,3}(?:\.\d+)?)%"
        r"(?:\s+of\s+~?\s*([\d.]+\s*\w+))?"
        r"(?:\s+at\s+([\d.]+\s*\w+/s|Unknown speed))?"
        r"(?:\s+ETA\s+([\d:]+|Unknown))?"
    )
    ffmpeg_re    = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
    # Detect yt-dlp announcing it is switching to the audio stream
    audio_re     = re.compile(r"\[download\] Destination:.*?\.(m4a|opus|webm|ogg)", re.I)
    video_re     = re.compile(r"\[download\] Destination:.*?\.(mp4|mkv|webm|mov)", re.I)

    last_line_was_progress = False
    converting_shown       = False
    stream_phase           = None   # None | "video" | "audio"
    recent_lines           = []

    for line in process.stdout:
        line  = line.rstrip()
        match = progress_re.match(line)

        # ── Detect stream phase switches ────────────────────────────────
        if audio_re.search(line):
            if last_line_was_progress:
                print()
                last_line_was_progress = False
            stream_phase = "audio"
            print(colorize("  ▸ Audio stream", C.MAGENTA, C.BOLD))
            continue
        if video_re.search(line):
            if last_line_was_progress:
                print()
                last_line_was_progress = False
            stream_phase = "video"
            print(colorize("  ▸ Video stream", C.CYAN, C.BOLD))
            continue

        # ── Progress bar ────────────────────────────────────────────────
        if match:
            percent = float(match.group(1))
            size    = match.group(2) or ""
            speed   = match.group(3) or ""
            eta     = match.group(4) or ""

            filled      = int(percent // 5)
            # Green for video/single stream, magenta for audio stream
            bar_color   = C.MAGENTA if stream_phase == "audio" else C.GREEN
            bar         = "█" * filled + "░" * (20 - filled)
            bar_colored = colorize(bar, bar_color)

            extras    = []
            if size:  extras.append(colorize(f"of {size}", C.DIM))
            if speed: extras.append(colorize(f"@ {speed}", C.CYAN))
            if eta:   extras.append(colorize(f"ETA {eta}", C.YELLOW))
            extra_str = "  " + " ".join(extras) if extras else ""

            pct_colored = colorize(f"{percent:5.1f}%", C.WHITE, C.BOLD)
            sys.stdout.write(f"\r{bar_colored} {pct_colored}{extra_str}   ")
            sys.stdout.flush()
            last_line_was_progress = True

        # ── ffmpeg conversion ────────────────────────────────────────────
        elif ffmpeg_re.search(line):
            if last_line_was_progress:
                print()
                last_line_was_progress = False
            if not converting_shown:
                sys.stdout.write(colorize("  ▸ Converting… ", C.YELLOW, C.BOLD))
                sys.stdout.flush()
                converting_shown = True
            else:
                sys.stdout.write(colorize(".", C.YELLOW))
                sys.stdout.flush()

        # ── All other output ─────────────────────────────────────────────
        else:
            if last_line_was_progress:
                print()
                last_line_was_progress = False
            if converting_shown:
                print()
                converting_shown = False
            if line:
                print(colorize(f"  {line}", C.DIM))
                recent_lines.append(line)
                if len(recent_lines) > 5:
                    recent_lines.pop(0)

    process.wait()
    if last_line_was_progress or converting_shown:
        print()

    return process.returncode, recent_lines


# ---------------------------------------------------------
# Build yt-dlp command
#
# BUG FIX #4 — the no-ffmpeg warning for audio was inside
#              build_command(), which is called on every
#              retry.  Moved the warn() to download_one()
#              so it only fires once before the first attempt.
# ---------------------------------------------------------

def build_command(url, dtype, quality, folder, audio_format="mp3", audio_bitrate="192"):
    output_template = os.path.join(folder, "%(title)s.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--newline", "--continue",
           "-o", output_template]

    if dtype == "audio":
        if FFMPEG_AVAILABLE:
            cmd += [
                "-f", "bestaudio",
                "-x",
                "--audio-format", audio_format,
                "--audio-quality", f"{audio_bitrate}K",
            ]
        else:
            cmd += ["-f", "bestaudio"]   # warn moved to download_one (fix #4)

    elif dtype == "mp4":
        if FFMPEG_AVAILABLE:
            if quality == "best":
                cmd += [
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                    "--merge-output-format", "mp4",
                ]
            else:
                cmd += [
                    "-f", (
                        f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]"
                        f"/bestvideo[height<={quality}]+bestaudio"
                        f"/best[height<={quality}]"
                    ),
                    "--merge-output-format", "mp4",
                ]
        else:
            if quality == "best":
                cmd += ["-f", "best[ext=mp4]/best"]
            else:
                cmd += ["-f", f"best[height<={quality}][ext=mp4]/best[height<={quality}]/best"]

    else:  # video
        if FFMPEG_AVAILABLE:
            if quality == "best":
                cmd += ["-f", "bestvideo+bestaudio/best"]
            else:
                cmd += ["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"]
        else:
            if quality == "best":
                cmd += ["-f", "best"]
            else:
                cmd += ["-f", f"best[height<={quality}]/best"]

    cmd.append(url)
    return cmd


# ---------------------------------------------------------
# Non-retryable error patterns
# ---------------------------------------------------------

NON_RETRYABLE_PATTERNS = [
    "video unavailable",
    "private video",
    "this video is unavailable",
    "account has been suspended",
    "content unavailable",
    "removed by the user",
    "copyright",
    "does not exist",
    "unsupported url",
    "no video formats found",
    "geo-restricted",
    "sign in to confirm your age",
]

def is_non_retryable(lines):
    text = " ".join(lines).lower()
    return any(p in text for p in NON_RETRYABLE_PATTERNS)


# ---------------------------------------------------------
# Download with retries
#
# BUG FIX #4 (continued) — warn about missing ffmpeg once,
#            here, before the first attempt, not inside
#            build_command on every call.
#
# BUG FIX #5 — last_error_lines stayed [] when the process
#            crashed before printing anything.  We now
#            capture stderr separately as a fallback so
#            the error block always has something to show.
# ---------------------------------------------------------

def download_one(url, dtype, quality, folder, retries=2,
                 audio_format="mp3", audio_bitrate="192",
                 video_info=None):

    # fix #4 — single warning before any attempt
    if dtype == "audio" and not FFMPEG_AVAILABLE:
        warn("ffmpeg not found; downloading native audio stream (no MP3 conversion).")
    if dtype == "mp4" and not FFMPEG_AVAILABLE:
        warn("ffmpeg not found; MP4 stream merging unavailable — using best pre-muxed format.")

    cmd = build_command(url, dtype, quality, folder, audio_format, audio_bitrate)

    attempt          = 1
    last_error_lines = []

    while True:
        if attempt > 1:
            warn(f"Retry attempt {attempt} (resuming if possible)...")

        returncode, recent_lines = run_with_progress(cmd, video_info=video_info, dtype=dtype)

        if returncode == 0:
            return True, []

        # fix #5 — if recent_lines is empty, re-run quickly just to get stderr
        if not recent_lines:
            probe = subprocess.run(cmd, capture_output=True, text=True,
                                   errors="replace", timeout=30)
            fallback = (probe.stderr or probe.stdout or "").strip().splitlines()[-5:]
            recent_lines = fallback or ["(no output captured)"]

        last_error_lines = recent_lines

        if is_non_retryable(recent_lines):
            break
        if attempt > retries:
            break
        attempt += 1

    return False, last_error_lines


# ---------------------------------------------------------
# Single-URL flow
# ---------------------------------------------------------

def process_url(url, batch_index=None, batch_total=None, shared_options=None):
    if batch_index is not None:
        print()
        print(colorize(f"━━━ URL {batch_index}/{batch_total} ━━━", C.MAGENTA, C.BOLD))

    platform      = detect_platform(url)
    audio_format  = "mp3"
    audio_bitrate = "192"

    info(f"Detected: {platform}")
    video_info = fetch_video_info(url)

    if shared_options:
        dtype         = shared_options["dtype"]
        quality       = shared_options["quality"]
        folder        = shared_options["folder"]
        audio_format  = shared_options.get("audio_format", "mp3")
        audio_bitrate = shared_options.get("audio_bitrate", "192")
    else:
        dtype = choose_download_type()

        if dtype == "formats":
            show_formats(url)
            return None

        quality = "best"

        if dtype in ("video", "mp4"):
            quality = choose_quality_auto(url)
        elif dtype == "audio":
            audio_format, audio_bitrate = choose_audio_options()

        folder = get_download_folder()

        if not confirm_summary(url, platform, dtype, quality, folder,
                               audio_format, audio_bitrate):
            warn("Skipped.")
            return False

    print()
    info("Downloading...")
    ok, error_lines = download_one(url, dtype, quality, folder,
                                   audio_format=audio_format,
                                   audio_bitrate=audio_bitrate)

    if ok:
        success(f"Download complete! Saved to: {folder}")
        save_history(url, platform, dtype, quality, folder)
    else:
        error("Download failed after retries.")
        if error_lines:
            print(colorize("Last output:", C.DIM))
            for ln in error_lines:
                print(colorize(f"  {ln}", C.DIM))

    return ok


# ---------------------------------------------------------
# Main flow
# ---------------------------------------------------------

def get_urls():
    section("Paste video URL")

    # Auto-paste from clipboard if it holds a valid URL
    clip_url = prompt_clipboard_url()
    if clip_url:
        return [clip_url]

    first = input(colorize("> ", C.CYAN)).strip()
    if not first:
        return []

    urls = [first]
    more = input("\nAdd another URL for batch mode? (y/n)\n> ").strip().lower()
    if more == "y":
        print(colorize(
            "Paste additional URLs, one per line. "
            "Press Enter on an empty line when done.", C.DIM
        ))
        while True:
            line = input(colorize("> ", C.CYAN)).strip()
            if not line:
                break
            urls.append(line)

    return urls


def main():
    clear()
    banner()
    show_welcome_tips()           # only shows on first run
    breadcrumb(1, 3, "Enter URL(s)")

    urls = get_urls()
    if not urls:
        warn("No URL entered. Exiting.")
        return

    valid_urls = [u for u in urls if is_valid_url(u)]
    for u in urls:
        if not is_valid_url(u):
            warn(f"Skipping invalid URL: {u}")

    if not valid_urls:
        error("No valid URLs to process.")
        return

    breadcrumb(2, 3, "Video Info & Options")

    if len(valid_urls) == 1:
        process_url(valid_urls[0])
    else:
        info(f"Batch mode: {len(valid_urls)} URLs queued.")
        section("Choose settings for all URLs in this batch")
        dtype = choose_download_type()

        if dtype == "formats":
            for u in valid_urls:
                show_formats(u)
            breadcrumb(3, 3, "Done")
            return

        quality       = "best"
        audio_format  = "mp3"
        audio_bitrate = "192"

        if dtype in ("video", "mp4"):
            info("Detecting qualities from first URL as reference for batch...")
            quality = choose_quality_auto(valid_urls[0])
        elif dtype == "audio":
            audio_format, audio_bitrate = choose_audio_options()

        folder = get_download_folder(skip_save_prompt=True)

        shared_options = {
            "dtype":         dtype,
            "quality":       quality,
            "folder":        folder,
            "audio_format":  audio_format,
            "audio_bitrate": audio_bitrate,
        }

        if not confirm_summary(
            f"({len(valid_urls)} URLs)", "Batch", dtype, quality, folder,
            audio_format, audio_bitrate
        ):
            warn("Batch cancelled.")
            return

        results = []
        for i, u in enumerate(valid_urls, 1):
            ok = process_url(u, batch_index=i, batch_total=len(valid_urls),
                             shared_options=shared_options)
            results.append(ok)

        succeeded = sum(1 for r in results if r is True)
        failed    = sum(1 for r in results if r is False)
        skipped   = sum(1 for r in results if r is None)

        print()
        section("Batch summary")
        success(f"{succeeded} succeeded")
        if failed:  error(f"{failed} failed")
        if skipped: info(f"{skipped} skipped (formats view)")

    breadcrumb(3, 3, "Done")


# ---------------------------------------------------------
# History
#
# BUG FIX #8 — old history entries may be missing the
#              'quality' key, causing a KeyError when
#              view_history() renders them.  Use .get()
#              with a safe default for every optional field.
# ---------------------------------------------------------

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(url, platform, dtype, quality, folder):
    history = load_history()
    history.append({
        "url":      url,
        "platform": platform,
        "type":     dtype,
        "quality":  quality,
        "folder":   folder,
        "date":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    write_history(history)


def view_history():
    while True:
        history = load_history()
        if not history:
            print("\nNo download history yet.")
            return

        section("Download History")
        for i, entry in enumerate(history, 1):
            # fix #8 — safe .get() for every field
            date     = entry.get("date",     "unknown date")
            platform = entry.get("platform", "?")
            dtype    = entry.get("type",     "?")
            quality  = entry.get("quality",  "?")
            folder   = entry.get("folder",   "?")
            url      = entry.get("url",      "")
            print(
                f"{colorize(str(i) + '.', C.BOLD)} "
                f"[{date}] {platform} — {dtype} ({quality}) → {folder}"
            )
            print(f"   {colorize(url, C.DIM)}")

        print("\n1. Delete an entry")
        print("2. Clear all history")
        print("3. Back")
        choice = input(colorize("> ", C.CYAN)).strip()

        if choice == "1":
            delete_entry(history)
        elif choice == "2":
            clear_history()
        else:
            return


def delete_entry(history):
    num = input(f"\nEnter entry number to delete (1-{len(history)}): ").strip()
    if not num.isdigit() or not (1 <= int(num) <= len(history)):
        error("Invalid number.")
        return
    removed = history.pop(int(num) - 1)
    write_history(history)
    success(f"Deleted: {removed.get('url', '(unknown)')}")


def clear_history():
    confirm = input("\nAre you sure you want to clear ALL history? (y/n)\n> ").strip().lower()
    if confirm == "y":
        write_history([])
        success("History cleared.")
    else:
        info("Cancelled.")


def write_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        error(f"Could not save history: {e}")


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    check_ytdlp()
    FFMPEG_AVAILABLE = check_ffmpeg()
    try:
        while True:
            main()
            print()
            section("What next?")
            print("1. Download another")
            print("2. View history")
            print("3. Exit")
            choice = input(colorize("> ", C.CYAN)).strip()

            if choice == "2":
                view_history()
                input("\nPress Enter to continue...")
                clear()
            elif choice == "3":
                print("Goodbye!")
                break
            else:
                clear()
    except KeyboardInterrupt:
        print("\n\nCancelled by user. Goodbye!")
