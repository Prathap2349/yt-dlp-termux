# yt-dlp-termux

> A polished, menu-driven video & audio downloader for Android (Termux), macOS, and Linux — powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

![Platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux%20%7C%20macOS-blue)
![Python](https://img.shields.io/badge/python-3.7%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## Preview

```
╔═══════════════════════════════════╗
║       Universal Downloader        ║
╚═══════════════════════════════════╝

Step 1/3 — Enter URL(s)
─────────────────────────────────────

▸ Paste video URL
> https://youtube.com/watch?v=...

▸ Choose download type
1. 🎬 Video
2. 🎵 Audio (MP3)
3. 🔍 Show available formats
```

---

## Features

- **Video downloads** — 360p, 720p, 1080p, or best available
- **Audio downloads** — always MP3, choose 128 / 192 / 320 kbps
- **Batch mode** — paste multiple URLs and download them all at once
- **Live progress bar** — shows speed, ETA, and file size while downloading
- **Smart retry** — retries failed downloads, skips permanent errors (private, geo-blocked, copyright)
- **Download history** — view, delete, or clear past downloads
- **Saved default folder** — remembers your preferred save location
- **Cross-platform** — works on Android (Termux), macOS, and Linux
- **ffmpeg-aware** — gracefully handles missing ffmpeg with clear warnings

---

## Supported Sites

Any site supported by yt-dlp — including YouTube, Instagram, Twitter/X, Reddit, Facebook, and [1000+ more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python 3.7+ | Run the script |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Download engine |
| ffmpeg *(recommended)* | MP3 conversion, merging video+audio streams |

---

## Installation

### Android (Termux)

```bash
# 1. Install dependencies
pkg update && pkg upgrade
pkg install python ffmpeg

# 2. Install yt-dlp
pip install yt-dlp

# 3. Grant storage permission
termux-setup-storage

# 4. Clone the repo
git clone https://github.com/Prathap2349/yt-dlp-termux.git
cd yt-dlp-termux

# 5. Make executable and add shortcut
chmod +x downloader
cp downloader ~
echo 'export PATH="$HOME:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### macOS

```bash
# Install dependencies
brew install python ffmpeg
pip install yt-dlp

# Clone and set up
git clone https://github.com/Prathap2349/yt-dlp-termux.git
cd yt-dlp-termux
chmod +x downloader
cp downloader /usr/local/bin/downloader
```

### Linux

```bash
# Install dependencies
sudo apt install python3 ffmpeg
pip install yt-dlp

# Clone and set up
git clone https://github.com/Prathap2349/yt-dlp-termux.git
cd yt-dlp-termux
chmod +x downloader
sudo cp downloader /usr/local/bin/downloader
```

---

## Usage

**Termux shortcut (after setup):**
```bash
downloader
```

**Or run directly:**
```bash
python downloader.py
```

### Download a video
1. Paste the URL when prompted
2. Choose **Video**
3. Pick quality (360p / 720p / 1080p / best)
4. Choose save folder
5. Confirm and download

### Download audio as MP3
1. Paste the URL when prompted
2. Choose **Audio (MP3)**
3. Pick bitrate (128 / 192 / 320 kbps)
4. Choose save folder
5. Confirm and download

### Batch download
1. Paste the first URL
2. When asked *"Add another URL?"* — type `y`
3. Paste remaining URLs one per line
4. Press Enter on an empty line when done
5. Set shared options once — all URLs download automatically

---

## Save Locations

| Platform | Downloads | Music | Movies |
|---|---|---|---|
| Android (Termux) | `/storage/emulated/0/Download` | `/storage/emulated/0/Music` | `/storage/emulated/0/Movies` |
| macOS / Linux | `~/Downloads` | `~/Music` | `~/Movies` |

You can also choose a **custom folder** or save a **default folder** that gets remembered across sessions.

---

## Files

```
yt-dlp-termux/
├── downloader        # Main script (no .py extension for shortcut use)
├── settings.json     # Auto-created — saves default folder preference
├── history.json      # Auto-created — download history log
└── README.md
```

> `settings.json` and `history.json` are excluded from git via `.gitignore`.

---

## Updating yt-dlp

Sites update frequently and can break downloads. Keep yt-dlp fresh:

```bash
pip install -U yt-dlp
```

---

## Troubleshooting

**`command not found: downloader`**
```bash
chmod +x ~/downloader
export PATH="$HOME:$PATH"
```

**`ffmpeg not found` warning**
```bash
pkg install ffmpeg        # Termux
brew install ffmpeg       # macOS
sudo apt install ffmpeg   # Linux
```

**`termux-setup-storage` not working**
Go to Android Settings → Apps → Termux → Permissions → Storage → Allow All.

**Download fails immediately**
The video may be private, geo-restricted, or age-restricted. The script will tell you and won't waste retries on permanent errors.

---

## License

MIT — free to use, modify, and distribute.

---

*Built with ❤️ for Termux users who want a clean download experience without touching a browser.*
