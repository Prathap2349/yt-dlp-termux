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


def success(text):
    print(colorize(f"✅ {text}", C.GREEN, C.BOLD))


def error(text):
    print(colorize(f"❌ {text}", C.RED, C.BOLD))


def warn(text):
    print(colorize(f"⚠️  {text}", C.YELLOW, C.BOLD))


def info(text):
    print(colorize(f"ℹ️  {text}", C.CYAN))


# ---------------------------------------------------------
# Boxes / banners / breadcrumbs
# ---------------------------------------------------------

def clear():
    os.system('clear' if os.name == 'posix' else 'cls')


def box(title, width=37):
    line = "═" * (width - 2)
    print(colorize(f"╔{line}╗", C.CYAN))
    pad = (width - 2 - len(title)) // 2
    spaces_right = width - 2 - len(title) - pad
    print(colorize(f"║{' ' * pad}{title}{' ' * spaces_right}║", C.CYAN, C.BOLD))
    print(colorize(f"╚{line}╝", C.CYAN))
    print()


def banner():
    box("Universal Downloader")


def breadcrumb(step, total, label):
    bar = colorize(f"Step {step}/{total}", C.MAGENTA, C.BOLD)
    print(f"{bar} — {colorize(label, C.WHITE, C.BOLD)}")
    print(colorize("─" * 37, C.DIM))


def section(title):
    print()
    print(colorize(f"▸ {title}", C.BLUE, C.BOLD))


# ---------------------------------------------------------
# Spinner
# ---------------------------------------------------------

class Spinner:
    """Simple console spinner shown while a blocking task runs."""

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
# Global state (set once at startup)
# ---------------------------------------------------------

FFMPEG_AVAILABLE = False  # set in __main__ block


# ---------------------------------------------------------
# Core checks
# ---------------------------------------------------------

def check_ytdlp():
    """Verify yt-dlp is installed before showing the menu."""
    if shutil.which("yt-dlp") is None:
        error("yt-dlp is not installed or not on PATH.")
        print("Install it with:  pip install yt-dlp")
        sys.exit(1)


def check_ffmpeg():
    """Check that ffmpeg is available.
    Returns True if available, False otherwise.
    Warning is shown once and can be dismissed permanently via settings."""
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
# Settings (remember default download folder)
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
# Format listing
# ---------------------------------------------------------

def show_formats(url):
    """List all available formats for the given URL using yt-dlp -F."""
    with Spinner("Fetching available formats..."):
        try:
            result = subprocess.run(
                ["yt-dlp", "--no-playlist", "-F", url],
                capture_output=True, text=True, timeout=60
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
# Platform detection
# ---------------------------------------------------------

def detect_platform(url):
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"
    elif "instagram.com" in u:
        return "Instagram"
    elif "reddit.com" in u:
        return "Reddit"
    elif "twitter.com" in u or "x.com" in u:
        return "Twitter/X"
    elif "facebook.com" in u or "fb.watch" in u:
        return "Facebook"
    else:
        return "Unknown (yt-dlp will try anyway)"


# ---------------------------------------------------------
# Download folder
# ---------------------------------------------------------

def get_download_folder(skip_save_prompt=False):
    settings = load_settings()
    default = settings.get("default_folder")

    section("Choose download folder")
    print("1. Downloads")
    print("2. Music")
    print("3. Movies")
    print("4. Custom Folder")
    if default:
        print(f"5. Use saved default ({colorize(default, C.DIM)})")

    choice = input(colorize("> ", C.CYAN)).strip()

    if default and choice == "5":
        return default

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

    if choice in folders:
        path = folders[choice]
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
    else:
        warn("Invalid choice, defaulting to Downloads.")
        path = folders["1"]

    # Ensure path exists (handles missing Android paths on desktop)
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
    """Fetch basic video info using yt-dlp --print (no download)."""
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

    lines = result.stdout.strip().split("\n")
    title    = lines[0] if len(lines) > 0 else "Unknown"
    duration = lines[1] if len(lines) > 1 else "Unknown"
    uploader = lines[2] if len(lines) > 2 else "Unknown"

    print(f"{colorize('Title:', C.BOLD)}    {title}")
    print(f"{colorize('Duration:', C.BOLD)} {duration}")
    print(f"{colorize('Uploader:', C.BOLD)} {uploader}")
    return {"title": title, "duration": duration, "uploader": uploader}


# ---------------------------------------------------------
# Download type / quality / audio options
# ---------------------------------------------------------

def choose_download_type():
    section("Choose download type")
    print("1. 🎬 Video")
    print("2. 🎵 Audio (MP3)")
    print("3. 🔍 Show available formats")
    choice = input(colorize("> ", C.CYAN)).strip()
    while choice not in ("1", "2", "3"):
        choice = input("Please enter 1, 2 or 3\n> ").strip()
    if choice == "1":
        return "video"
    elif choice == "2":
        return "audio"
    else:
        return "formats"


def choose_quality():
    section("Choose video quality")
    print("1. 360p")
    print("2. 720p")
    print("3. 1080p")
    print("4. Best available")
    choice = input(colorize("> ", C.CYAN)).strip()
    qualities = {
        "1": "360",
        "2": "720",
        "3": "1080",
        "4": "best",
    }
    return qualities.get(choice, "best")


def choose_audio_options():
    """Always return MP3 format with user-chosen bitrate.
    Returns (audio_format, audio_bitrate) — format is always 'mp3'."""
    section("Audio quality (bitrate)")
    print("1. 128 kbps  (smaller file)")
    print("2. 192 kbps  (balanced)")
    print("3. 320 kbps  (best quality)")
    choice = input(colorize("> ", C.CYAN)).strip()
    bitrates = {
        "1": "128",
        "2": "192",
        "3": "320",
    }
    audio_bitrate = bitrates.get(choice, "192")
    return "mp3", audio_bitrate


# ---------------------------------------------------------
# Confirm summary
# ---------------------------------------------------------

def confirm_summary(url, platform, dtype, quality, folder,
                    audio_format=None, audio_bitrate=None):
    section("Confirm download")
    print(f"  {colorize('Platform:', C.BOLD)} {platform}")
    print(f"  {colorize('Type:', C.BOLD)}     {dtype}")
    if dtype == "video":
        label = "Best available" if quality == "best" else f"{quality}p"
        print(f"  {colorize('Quality:', C.BOLD)}  {label}")
    if dtype == "audio":
        fmt = audio_format.upper() if audio_format else "MP3"
        print(f"  {colorize('Format:', C.BOLD)}   {fmt}")
        if audio_bitrate:
            print(f"  {colorize('Bitrate:', C.BOLD)}  {audio_bitrate} kbps")
    print(f"  {colorize('Folder:', C.BOLD)}   {folder}")
    print(f"  {colorize('URL:', C.BOLD)}      {url}")
    print()
    choice = input("Proceed with download? (y/n)\n> ").strip().lower()
    return choice == "y"


# ---------------------------------------------------------
# Progress bar via yt-dlp --newline output
# ---------------------------------------------------------

def run_with_progress(cmd):
    """Run a yt-dlp command and render a live progress bar with speed/ETA."""
    print()
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )

    progress_re = re.compile(
        r"^\[download\]\s+(\d{1,3}(?:\.\d+)?)%"
        r"(?:\s+of\s+~?\s*([\d.]+\s*\w+))?"
        r"(?:\s+at\s+([\d.]+\s*\w+/s|Unknown speed))?"
        r"(?:\s+ETA\s+([\d:]+|Unknown))?"
    )
    ffmpeg_re = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

    last_line_was_progress = False
    converting_shown = False
    recent_lines = []

    for line in process.stdout:
        line = line.rstrip()
        match = progress_re.match(line)
        if match:
            percent = float(match.group(1))
            size    = match.group(2) or ""
            speed   = match.group(3) or ""
            eta     = match.group(4) or ""

            filled      = int(percent // 5)   # 20-block bar
            bar         = "█" * filled + "░" * (20 - filled)
            bar_colored = colorize(bar, C.GREEN)

            extras = []
            if size:  extras.append(f"of {size}")
            if speed: extras.append(f"@ {speed}")
            if eta:   extras.append(f"ETA {eta}")
            extra_str = "  " + " ".join(extras) if extras else ""

            sys.stdout.write(f"\r{bar_colored} {percent:5.1f}%{extra_str}   ")
            sys.stdout.flush()
            last_line_was_progress = True

        elif ffmpeg_re.search(line):
            if last_line_was_progress:
                print()
                last_line_was_progress = False
            if not converting_shown:
                sys.stdout.write(colorize("Converting to MP3... ", C.YELLOW))
                sys.stdout.flush()
                converting_shown = True
            else:
                sys.stdout.write(".")
                sys.stdout.flush()

        else:
            if last_line_was_progress:
                print()
                last_line_was_progress = False
            if converting_shown:
                print()
                converting_shown = False
            if line:
                print(line)
                recent_lines.append(line)
                if len(recent_lines) > 5:
                    recent_lines.pop(0)

    process.wait()
    if last_line_was_progress or converting_shown:
        print()

    return process.returncode, recent_lines


# ---------------------------------------------------------
# Build yt-dlp command
# ---------------------------------------------------------

def build_command(url, dtype, quality, folder, audio_format="mp3", audio_bitrate="192"):
    """Build the yt-dlp argument list.

    audio_format  : always 'mp3' (kept as param for future flexibility)
    audio_bitrate : '128' | '192' | '320' — always a string, never None
    """
    output_template = os.path.join(folder, "%(title)s.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--newline", "--continue",
           "-o", output_template]

    if dtype == "audio":
        if FFMPEG_AVAILABLE:
            # Extract best audio stream and convert to MP3 at chosen bitrate
            cmd += [
                "-f", "bestaudio",
                "-x",
                "--audio-format", audio_format,
                "--audio-quality", f"{audio_bitrate}K",
            ]
        else:
            # No ffmpeg — grab the best native audio stream without conversion
            warn("ffmpeg not found; downloading native audio stream (no MP3 conversion).")
            cmd += ["-f", "bestaudio"]

    else:  # video
        if FFMPEG_AVAILABLE:
            if quality == "best":
                cmd += ["-f", "bestvideo+bestaudio/best"]
            else:
                cmd += ["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"]
        else:
            # No ffmpeg — can't merge streams; use a single pre-merged format
            if quality == "best":
                cmd += ["-f", "best"]
            else:
                cmd += ["-f", f"best[height<={quality}]/best"]

    cmd.append(url)
    return cmd


# ---------------------------------------------------------
# Non-retryable error detection
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
# ---------------------------------------------------------

def download_one(url, dtype, quality, folder, retries=2,
                 audio_format="mp3", audio_bitrate="192"):
    """Run the download, retrying transient failures.
    Permanent errors (unavailable, copyright, etc.) are not retried."""
    cmd = build_command(url, dtype, quality, folder, audio_format, audio_bitrate)

    attempt = 1
    last_error_lines = []
    while True:
        if attempt > 1:
            warn(f"Retry attempt {attempt} (resuming if possible)...")
        returncode, recent_lines = run_with_progress(cmd)
        if returncode == 0:
            return True, []
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

    platform = detect_platform(url)
    info(f"Detected: {platform}")

    fetch_video_info(url)

    # Defaults (used when shared_options provides audio keys)
    audio_format  = "mp3"
    audio_bitrate = "192"

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
            return None   # explicit None so batch summary isn't misled

        quality = "best"
        if dtype == "video":
            quality = choose_quality()
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
            for line in error_lines:
                print(colorize(f"  {line}", C.DIM))
        if dtype == "audio" and not FFMPEG_AVAILABLE:
            warn("ffmpeg is missing — MP3 conversion is not possible without it.")

    return ok


# ---------------------------------------------------------
# Main flow
# ---------------------------------------------------------

def get_urls():
    """Prompt for one or more URLs. Returns a list."""
    section("Paste video URL")
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
    breadcrumb(1, 3, "Enter URL(s)")

    urls = get_urls()
    if not urls:
        warn("No URL entered. Exiting.")
        return

    valid_urls = []
    for u in urls:
        if is_valid_url(u):
            valid_urls.append(u)
        else:
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

        quality = "best"
        audio_format  = "mp3"
        audio_bitrate = "192"

        if dtype == "video":
            quality = choose_quality()
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
        if failed:
            error(f"{failed} failed")
        if skipped:
            info(f"{skipped} skipped (formats view)")

    breadcrumb(3, 3, "Done")


# ---------------------------------------------------------
# History
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
            print(
                f"{colorize(str(i) + '.', C.BOLD)} "
                f"[{entry['date']}] {entry['platform']} — "
                f"{entry['type']} ({entry['quality']}) → {entry['folder']}"
            )
            print(f"   {colorize(entry['url'], C.DIM)}")

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
    success(f"Deleted: {removed['url']}")


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
    FFMPEG_AVAILABLE = check_ffmpeg()   # ← module-level, used by build_command
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
