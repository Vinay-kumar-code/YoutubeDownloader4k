# YouTubeDownloader4k

A fast, modern YouTube downloader with a clean Tkinter GUI powered by yt-dlp. Download single videos or full playlists, pick quality (up to 4K), preview titles and thumbnails, and track real-time progress with speed and ETA.

## 🚀 Features

- Single videos and full playlists (organized into a playlist folder with numbered items)
- Quality presets: Best Auto, Best MP4, 2160p (4K), 1440p (2K), 1080p, 720p
- Audio-only: M4A direct or MP3 (via FFmpeg)
- Preview: Paste/Preview buttons, video title, and HD thumbnail
- Progress details: percentage, size, speed, and ETA
- Output folder picker with last-location memory
- Subtitles: EN/HI (auto if available)
- Optional: embed thumbnail and write metadata tags
- Responsive UI (multithreaded)

## 📦 Requirements

- Python 3.10+
- Dependencies (installed via requirements.txt):
  - yt-dlp, Pillow, requests
- Optional but recommended: FFmpeg on PATH (required for MP3, merging separate video/audio, and embedding thumbnails)

## ⚙️ Setup

Windows PowerShell (recommended):

```powershell
# From the project folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\main.py
```

FFmpeg (optional):
- winget: `winget install Gyan.FFmpeg`
- Chocolatey: `choco install ffmpeg`

## 🧭 Usage

1) Paste a YouTube URL and click Preview to see the title and thumbnail.
2) Choose an output folder.
3) Select quality and options (playlist, subtitles, embed thumbnail, metadata).
4) Click Download.

Tips:
- For playlists, check “Download entire playlist.” The app normalizes list URLs and saves items under a playlist folder with numeric order.
- MP3 conversion and thumbnail embedding require FFmpeg.

## 📝 Notes & Troubleshooting

- Age-restricted/private/unavailable content may require authentication or won’t download.
- If a playlist does not start, ensure the URL contains `list=` and is publicly accessible.
- Network timeouts or throttling can occur; try again later or with a different network.
- The app stores only a local `settings.json` for your last chosen folder.

## 🛠 Built With

- Python, Tkinter
- yt-dlp
- Pillow (thumbnails)
- Requests (thumbnail fetch)

## 📜 License

Licensed under the GNU License. Use and modify as needed.

## 🤝 Contributing

Issues and PRs are welcome. Fork and submit a pull request.

## ⭐ Support

If you find this useful, please star the repo.

---

**Made with 💙 by [Vinay-Kumar]**

