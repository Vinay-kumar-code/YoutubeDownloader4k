import yt_dlp
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar
from PIL import Image, ImageTk
import requests
from io import BytesIO

def fetch_video_info(url):
    """Fetch video title and thumbnail URL."""
    try:
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title", "Unknown Title"), info.get("thumbnail", "")
    except:
        return "Unknown Title", ""

def update_thumbnail(thumbnail_url):
    """Download and display the video thumbnail in GUI properly."""
    try:
        if not thumbnail_url:
            raise ValueError("Invalid URL")

        response = requests.get(thumbnail_url, stream=True)
        response.raise_for_status()
        image_data = Image.open(BytesIO(response.content))

        
        max_width, max_height = 640, 360  # HD resolution
        image_data.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        
        thumbnail_img = ImageTk.PhotoImage(image_data)

      
        thumbnail_label.config(image=thumbnail_img, text="")
        thumbnail_label.image = thumbnail_img  # Keep reference to prevent garbage collection
        root.update_idletasks()

    except Exception as e:
        print(f"Thumbnail Error: {e}")
        thumbnail_label.config(image="", text="Thumbnail Not Available", width=20, height=2)

def download_youtube_video(url, output_path, progress_var, title_var):
    try:
        title, thumbnail_url = fetch_video_info(url)
        title_var.set(title)
        update_thumbnail(thumbnail_url)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        def progress_hook(d):
            """Update progress bar dynamically"""
            if d['status'] == 'downloading':
                downloaded_bytes = d.get('downloaded_bytes', 0)
                total_bytes = d.get('total_bytes_estimate', d.get('total_bytes', 1))
                if total_bytes > 0:
                    progress = int(downloaded_bytes / total_bytes * 100)
                    progress_var.set(progress)
                    root.update_idletasks()

            elif d['status'] == 'finished':
                progress_var.set(100)
                root.update_idletasks()

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        messagebox.showinfo("Success", "Download complete!")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

def start_download():
    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Input Error", "Please enter a YouTube video URL.")
        return

    output_path = filedialog.askdirectory(title="Select Download Folder")
    if not output_path:
        return

    progress_var.set(0)
    title_var.set("Fetching video info...")
    thumbnail_label.config(image="", text="Loading...", width=20, height=2)

    threading.Thread(target=download_youtube_video, args=(url, output_path, progress_var, title_var), daemon=True).start()

def reset_gui():
    """Resets all input fields, progress bar, and UI elements."""
    url_entry.delete(0, tk.END)
    progress_var.set(0)
    title_var.set("No Video Selected")
    thumbnail_label.config(image="", text="No Thumbnail", width=20, height=2)


root = tk.Tk()
root.title("YouTube Downloader")

url_label = tk.Label(root, text="YouTube Video URL:")
url_label.pack(pady=5)

url_entry = tk.Entry(root, width=50)
url_entry.pack(pady=5)

title_var = tk.StringVar(value="No Video Selected")
title_label = tk.Label(root, textvariable=title_var, font=("Arial", 12, "bold"))
title_label.pack(pady=5)

thumbnail_label = tk.Label(root, text="No Thumbnail", width=200, height=20, relief="ridge")
thumbnail_label.pack(pady=5)

progress_var = tk.IntVar()
progress_bar = Progressbar(root, orient="horizontal", length=400, mode="determinate", variable=progress_var)
progress_bar.pack(pady=10)

download_button = tk.Button(root, text="Download", command=start_download)
download_button.pack(pady=5)

reset_button = tk.Button(root, text="Reset", command=reset_gui)
reset_button.pack(pady=5)

root.geometry("700x600")
root.mainloop()
