import os
import re
import json
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.ttk import Progressbar
from io import BytesIO

import requests
from PIL import Image, ImageTk
import yt_dlp

# --------------- Helpers ---------------

class YTDLogger:
    def __init__(self, callback=None):
        self.cb = callback
    def _emit(self, msg):
        try:
            print(str(msg))
        finally:
            if self.cb:
                try:
                    self.cb(str(msg))
                except Exception:
                    pass
    def debug(self, msg):
        self._emit(msg)
    def info(self, msg):
        self._emit(msg)
    def warning(self, msg):
        self._emit(msg)
    def error(self, msg):
        self._emit(msg)


def human_readable_size(num: int | float | None) -> str:
    if not num or num <= 0:
        return "-"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def sanitize_filename(name: str) -> str:
    # Basic sanitization for Windows filenames
    return re.sub(r"[\\/:*?\"<>|]", "_", name).strip()


def fetch_video_info(url):
    """Fetch video or playlist title and thumbnail quickly using yt-dlp."""
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,     # fast metadata
            "playlist_items": "1",  # only need first item for preview
            "socket_timeout": 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("_type") == "playlist":
                title = info.get("title") or "Playlist"
                thumb = info.get("thumbnail", "")
                return title or "Unknown Title", thumb
            return info.get("title", "Unknown Title"), info.get("thumbnail", "")
    except Exception:
        return "Unknown Title", ""


def update_thumbnail(thumbnail_url):
    """Deprecated: replaced by fetch_thumbnail_image + show_thumbnail."""
    try:
        img = fetch_thumbnail_image(thumbnail_url)
        show_thumbnail(img)
    except Exception as e:
        print(f"Thumbnail Error: {e}")
        thumbnail_label.config(image="", text="Thumbnail Not Available", width=20, height=2)
        thumbnail_label.image = None


def fetch_thumbnail_image(thumbnail_url):
    """Download thumbnail image and return PIL Image. No UI updates here."""
    try:
        if not thumbnail_url:
            return None
        response = requests.get(thumbnail_url, stream=True, timeout=15)
        response.raise_for_status()
        image_data = Image.open(BytesIO(response.content))
        return image_data
    except Exception as e:
        print(f"Thumbnail fetch error: {e}")
        return None


def show_thumbnail(image_obj):
    """Render a PIL Image into the UI. Must be called from the Tk main thread."""
    try:
        if image_obj is None:
            raise ValueError("no image")
        img = image_obj.copy()
        max_width, max_height = 640, 360
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        thumbnail_img = ImageTk.PhotoImage(img)
        thumbnail_label.config(image=thumbnail_img, text="")
        thumbnail_label.image = thumbnail_img
    except Exception as e:
        print(f"Thumbnail render error: {e}")
        thumbnail_label.config(image="", text="Thumbnail Not Available", width=20, height=2)
        thumbnail_label.image = None


def build_format_string(selection: str) -> str:
    mapping = {
        "Best Available (Auto)": 'bestvideo+bestaudio/best',
        "Best MP4": 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        "2160p (4K)": 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
        "1440p (2K)": 'bestvideo[height<=1440]+bestaudio/best[height<=1440]/best',
        "1080p": 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        "720p": 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        "Audio (M4A)": 'bestaudio[ext=m4a]/bestaudio/best',
        "Audio (MP3)": 'bestaudio/best',
    }
    return mapping.get(selection, mapping["Best MP4"])


def maybe_playlist_url(url: str, want_playlist: bool) -> str:
    """If user wants playlist and URL contains list=, convert to playlist URL to ensure full download."""
    if want_playlist and "list=" in url:
        m = re.search(r"[?&]list=([^&]+)", url)
        if m:
            return f"https://www.youtube.com/playlist?list={m.group(1)}"
    return url


# --------------- Download Logic ---------------

def download_youtube_video(url: str, output_path: str, selection: str, options: dict,
                           progress_var: tk.IntVar, title_var: tk.StringVar, progress_text_var: tk.StringVar):
    try:
        # Preview info
        preview_url = maybe_playlist_url(url, options.get("playlist", False))
        title, thumbnail_url = fetch_video_info(preview_url)
        # Update title safely on UI thread
        root.after(0, lambda: title_var.set(title))
        # Download thumbnail in background, then render on UI thread
        def _thumb_worker():
            img = fetch_thumbnail_image(thumbnail_url)
            root.after(0, lambda: show_thumbnail(img))
        threading.Thread(target=_thumb_worker, daemon=True).start()

        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)

        want_playlist = options.get("playlist", False)
        want_subs = options.get("subtitles", False)
        embed_thumb = options.get("embed_thumbnail", False)
        add_metadata = options.get("add_metadata", False)

        fmt = build_format_string(selection)
        need_ffmpeg = True  # Merging and most post-processing require ffmpeg
        ffmpeg_ok = check_ffmpeg()

        postprocessors = []
        merge_output_format = None

        if selection == "Audio (MP3)":
            if not ffmpeg_ok:
                messagebox.showerror("FFmpeg required", "Converting to MP3 requires FFmpeg in PATH.")
                return
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            })
            merge_output_format = None
        elif selection == "Audio (M4A)":
            # Prefer direct m4a download; no conversion needed
            merge_output_format = None
        else:
            # For video+audio, ask yt-dlp to merge to mp4 when possible
            merge_output_format = 'mp4'

        if add_metadata:
            postprocessors.append({'key': 'FFmpegMetadata'})
        if embed_thumb:
            if not ffmpeg_ok:
                messagebox.showwarning("FFmpeg recommended", "Embedding thumbnails requires FFmpeg.")
            else:
                postprocessors.append({'key': 'EmbedThumbnail'})

        # Progress hook updating UI
        def update_progress_ui(pct: int, text: str):
            def _apply():
                progress_var.set(max(0, min(100, pct)))
                progress_text_var.set(text)
            root.after(0, _apply)

        def progress_hook(d):
            status = d.get('status')
            if status == 'downloading':
                downloaded = d.get('downloaded_bytes') or 0
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                pct = int(downloaded / total * 100) if total else 0
                spd = d.get('speed') or 0
                eta = d.get('eta')
                text = f"{pct}% | {human_readable_size(downloaded)} of {human_readable_size(total)} @ {human_readable_size(spd)}/s"
                if eta is not None:
                    text += f" | ETA {eta}s"
                update_progress_ui(pct, text)
            elif status == 'finished':
                update_progress_ui(100, 'Merging/Finishing...')

        # UI logger used by yt-dlp
        def ui_log(msg: str):
            print(str(msg))
            try:
                root.after(0, lambda m=str(msg): progress_text_var.set(m))
            except Exception:
                pass

        # ydl options
        outtmpl = os.path.join(output_path, '%(title)s.%(ext)s')
        if want_playlist:
            # Organize playlist downloads into a folder and prefix index for order
            outtmpl = os.path.join(output_path, '%(playlist_title)s', '%(playlist_index)03d - %(title)s.%(ext)s')

        ydl_opts: dict = {
            'format': fmt,
            'outtmpl': outtmpl,
            'progress_hooks': [progress_hook],
            # 'noplaylist' behavior: when a single video URL contains a playlist param,
            # yt-dlp downloads just the video unless we explicitly enable playlist.
            'ignoreerrors': want_playlist,  # continue on playlist errors
            'quiet': False,
            'no_warnings': False,
            'retries': 5,
            'restrictfilenames': True,
            'socket_timeout': 20,
            'logger': YTDLogger(callback=ui_log),
        }

        if want_playlist:
            ydl_opts['yesplaylist'] = True
        else:
            ydl_opts['noplaylist'] = True

        if want_subs:
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitlesformat': 'srt',
                'subtitleslangs': ['en', 'en.*', 'hi', 'hi.*']  # tweak as needed
            })

        if postprocessors:
            ydl_opts['postprocessors'] = postprocessors
        if merge_output_format:
            ydl_opts['merge_output_format'] = merge_output_format

        # Disable UI while working
        def disable_ui(disabled=True):
            state = tk.DISABLED if disabled else tk.NORMAL
            download_button.config(state=state)
            reset_button.config(state=state)
            preview_button.config(state=state)
            browse_button.config(state=state)
            quality_combo.config(state='disabled' if disabled else 'readonly')
            for cb in (playlist_chk, subs_chk, embed_thumb_chk, metadata_chk):
                cb.config(state=state)

        disable_ui(True)
        update_progress_ui(0, 'Starting...')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            target_url = maybe_playlist_url(url, want_playlist)
            ui_log(f"Starting download: playlist={want_playlist}, quality={selection}")
            ui_log(f"URL: {target_url}")
            ydl.download([target_url])

        update_progress_ui(100, 'Done')
        messagebox.showinfo("Success", "Download complete!")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        def enable():
            disable_ui(False)
        root.after(0, enable)


# --------------- UI Actions ---------------

def start_download():
    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Error", "Please enter a YouTube URL.")
        return

    output_path = output_path_var.get().strip()
    if not output_path:
        messagebox.showwarning("Folder Required", "Please choose a download folder.")
        return

    # Persist last folder
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump({"last_output": output_path}, f)
    except Exception:
        pass

    progress_var.set(0)
    progress_text_var.set("")

    # Kick off download in a worker thread
    opts = {
        "playlist": playlist_var.get(),
        "subtitles": subtitles_var.get(),
        "embed_thumbnail": embed_thumb_var.get(),
        "add_metadata": metadata_var.get(),
    }
    threading.Thread(
        target=download_youtube_video,
        args=(url, output_path, quality_var.get(), opts, progress_var, title_var, progress_text_var),
        daemon=True,
    ).start()


def do_preview():
    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Error", "Please enter a YouTube URL to preview.")
        return
    title_var.set("Fetching video info...")
    thumbnail_label.config(image="", text="Loading...", width=20, height=2)

    def _work():
        preview_url = maybe_playlist_url(url, playlist_var.get())
        title, thumb_url = fetch_video_info(preview_url)
        img = fetch_thumbnail_image(thumb_url)
        def _apply():
            title_var.set(title)
            show_thumbnail(img)
        root.after(0, _apply)

    threading.Thread(target=_work, daemon=True).start()


def reset_gui():
    url_entry.delete(0, tk.END)
    progress_var.set(0)
    progress_text_var.set("")
    title_var.set("No Video Selected")
    thumbnail_label.config(image="", text="No Thumbnail", width=20, height=2)
    thumbnail_label.image = None


def paste_from_clipboard():
    try:
        data = root.clipboard_get()
        url_entry.delete(0, tk.END)
        url_entry.insert(0, data)
    except Exception:
        pass


def browse_output_folder():
    initial = output_path_var.get() or os.path.join(os.path.expanduser("~"), "Downloads")
    folder = filedialog.askdirectory(title="Select Download Folder", initialdir=initial)
    if folder:
        output_path_var.set(folder)


# --------------- UI Setup ---------------
root = tk.Tk()
root.title("YouTube Downloader (yt-dlp)")
root.geometry("980x640")
root.minsize(820, 560)

# Theme
try:
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TButton', padding=6)
    style.configure('TLabel', padding=2)
except Exception:
    pass

# Persistent settings
settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
last_output_folder = ""
try:
    if os.path.exists(settings_path):
        with open(settings_path, 'r', encoding='utf-8') as f:
            last_output_folder = json.load(f).get("last_output", "")
except Exception:
    last_output_folder = ""

# Default output folder
if not last_output_folder:
    last_output_folder = os.path.join(os.path.expanduser("~"), "Downloads")

# Top-level layout frames
main_container = ttk.Frame(root, padding=10)
main_container.pack(fill=tk.BOTH, expand=True)

left_frame = ttk.Frame(main_container)
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

right_frame = ttk.Frame(main_container)
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# URL input
url_label = ttk.Label(left_frame, text="YouTube URL:")
url_label.pack(anchor=tk.W)

url_row = ttk.Frame(left_frame)
url_row.pack(fill=tk.X, pady=4)

url_entry = ttk.Entry(url_row)
url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

paste_button = ttk.Button(url_row, text="Paste", command=paste_from_clipboard)
paste_button.pack(side=tk.LEFT, padx=4)

preview_button = ttk.Button(url_row, text="Preview", command=do_preview)
preview_button.pack(side=tk.LEFT)

# Output folder chooser
output_lbl = ttk.Label(left_frame, text="Output Folder:")
output_lbl.pack(anchor=tk.W, pady=(10, 0))

output_row = ttk.Frame(left_frame)
output_row.pack(fill=tk.X, pady=4)

output_path_var = tk.StringVar(value=last_output_folder)
output_entry = ttk.Entry(output_row, textvariable=output_path_var)
output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

browse_button = ttk.Button(output_row, text="Browse", command=browse_output_folder)
browse_button.pack(side=tk.LEFT, padx=4)

# Quality & options
quality_lbl = ttk.Label(left_frame, text="Quality:")
quality_lbl.pack(anchor=tk.W, pady=(10, 0))

quality_var = tk.StringVar(value="Best MP4")
quality_combo = ttk.Combobox(left_frame, state='readonly', textvariable=quality_var,
                             values=[
                                 "Best Available (Auto)",
                                 "Best MP4",
                                 "2160p (4K)",
                                 "1440p (2K)",
                                 "1080p",
                                 "720p",
                                 "Audio (M4A)",
                                 "Audio (MP3)",
                             ])
quality_combo.pack(fill=tk.X, pady=4)

# Option checkboxes
playlist_var = tk.BooleanVar(value=False)
subtitles_var = tk.BooleanVar(value=False)
embed_thumb_var = tk.BooleanVar(value=False)
metadata_var = tk.BooleanVar(value=True)

options_frame = ttk.LabelFrame(left_frame, text="Options")
options_frame.pack(fill=tk.X, pady=8)

playlist_chk = ttk.Checkbutton(options_frame, text="Download entire playlist", variable=playlist_var)
playlist_chk.pack(anchor=tk.W, pady=2)

subs_chk = ttk.Checkbutton(options_frame, text="Subtitles (EN/HI, auto if available)", variable=subtitles_var)
subs_chk.pack(anchor=tk.W, pady=2)

embed_thumb_chk = ttk.Checkbutton(options_frame, text="Embed thumbnail (requires FFmpeg)", variable=embed_thumb_var)
embed_thumb_chk.pack(anchor=tk.W, pady=2)

metadata_chk = ttk.Checkbutton(options_frame, text="Write metadata tags", variable=metadata_var)
metadata_chk.pack(anchor=tk.W, pady=2)

# Buttons
buttons_row = ttk.Frame(left_frame)
buttons_row.pack(fill=tk.X, pady=10)

download_button = ttk.Button(buttons_row, text="Download", command=start_download)
download_button.pack(side=tk.LEFT)

reset_button = ttk.Button(buttons_row, text="Reset", command=reset_gui)
reset_button.pack(side=tk.LEFT, padx=6)

# Right panel: preview + progress
thumbnail_label = tk.Label(right_frame, text="No Thumbnail", width=60, height=18, relief="ridge", bg="#f3f3f3")
thumbnail_label.pack(pady=5, fill=tk.BOTH, expand=True)

title_var = tk.StringVar(value="No Video Selected")
title_label = ttk.Label(right_frame, textvariable=title_var, font=("Segoe UI", 12, "bold"), wraplength=420)
title_label.pack(pady=4)

progress_var = tk.IntVar(value=0)
progress_bar = Progressbar(right_frame, orient="horizontal", length=400, mode="determinate", variable=progress_var)
progress_bar.pack(pady=(10, 0), fill=tk.X)

progress_text_var = tk.StringVar(value="")
progress_text = ttk.Label(right_frame, textvariable=progress_text_var)
progress_text.pack(anchor=tk.W, pady=(4, 0))

# Footer hint about ffmpeg
ffmpeg_note = ttk.Label(root, text=(
    "Tip: Install FFmpeg and add it to PATH for best results (merging, MP3, embedding thumbnails)."
), foreground="#555")
ffmpeg_note.pack(pady=(0, 6))

root.mainloop()
