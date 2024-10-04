import os
import sys
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from moviepy.editor import (
    ImageClip, 
    concatenate_videoclips, 
    AudioFileClip, 
    CompositeVideoClip, 
    TextClip, 
    CompositeAudioClip
)
from moviepy.video.fx.all import fadein, fadeout
from PIL import Image
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Configuration Defaults
DEFAULT_SNAPSHOT_DIR = 'snapshots'
DEFAULT_OUTPUT_DIR = 'output'
DEFAULT_ASSETS_DIR = 'assets'
DEFAULT_FRAME_RATE = 24
DEFAULT_TRANSITION_DURATION = 1  # seconds
DEFAULT_VIDEO_DURATION = 2  # seconds per image
DEFAULT_VIDEO_CODEC = 'libx264'
DEFAULT_VIDEO_FORMAT = 'mp4'
DEFAULT_OUTPUT_VIDEO = os.path.join(DEFAULT_OUTPUT_DIR, 'output_video.mp4')
DEFAULT_AUDIO_FILE = os.path.join(DEFAULT_ASSETS_DIR, 'background_music.mp3')
DEFAULT_FONT = os.path.join(DEFAULT_ASSETS_DIR, 'custom_font.ttf')  # Ensure this exists or use default

# Supported Image Formats
IMAGE_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')

# Create necessary directories if they don't exist
for directory in [DEFAULT_SNAPSHOT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_ASSETS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

class VideoGeneratorHandler(FileSystemEventHandler):
    """Handles new image files and updates the video."""

    def __init__(self, generator):
        super().__init__()
        self.generator = generator

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(IMAGE_FORMATS):
            print(f"New image detected: {event.src_path}")
            self.generator.update_video()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(IMAGE_FORMATS):
            print(f"Image modified: {event.src_path}")
            self.generator.update_video()

class VideoGenerator:
    """Main class to handle video generation and watching directory."""

    def __init__(self, snapshot_dir, output_dir, assets_dir, output_video, frame_rate,
                 transition_duration, video_duration, video_codec, video_format,
                 audio_file, font_path, enable_transitions, enable_audio, enable_text,
                 text_content, text_position, text_fontsize, text_color):
        self.snapshot_dir = snapshot_dir
        self.output_dir = output_dir
        self.assets_dir = assets_dir
        self.output_video = output_video
        self.frame_rate = frame_rate
        self.transition_duration = transition_duration
        self.video_duration = video_duration
        self.video_codec = video_codec
        self.video_format = video_format
        self.audio_file = audio_file
        self.font_path = font_path
        self.enable_transitions = enable_transitions
        self.enable_audio = enable_audio
        self.enable_text = enable_text
        self.text_content = text_content
        self.text_position = text_position
        self.text_fontsize = text_fontsize
        self.text_color = text_color

        self.observer = None

    def get_sorted_image_paths(self):
        """Retrieve and sort image paths from the snapshot directory."""
        images = [img for img in os.listdir(self.snapshot_dir) if img.lower().endswith(IMAGE_FORMATS)]
        images.sort()  # Sort images by name; modify if necessary
        image_paths = [os.path.join(self.snapshot_dir, img) for img in images]
        return image_paths

    def create_video(self, image_paths):
        """Create a video from image paths with optional transitions and text overlays."""
        if not image_paths:
            print("No images found to create a video.")
            return

        clips = []
        for img_path in image_paths:
            try:
                img = Image.open(img_path)
                width, height = img.size
                img.close()
                # Create ImageClip
                clip = ImageClip(img_path).set_duration(self.video_duration)
                # Add text overlay if enabled
                if self.enable_text and self.text_content:
                    txt_clip = TextClip(
                        self.text_content,
                        fontsize=self.text_fontsize,
                        color=self.text_color,
                        font=self.font_path if self.font_path else 'Arial'
                    ).set_position(self.text_position).set_duration(self.video_duration)
                    clip = CompositeVideoClip([clip, txt_clip])
                # Add fade in and fade out transitions
                if self.enable_transitions:
                    clip = clip.fx(fadein, self.transition_duration).fx(fadeout, self.transition_duration)
                clips.append(clip)
            except Exception as e:
                print(f"Error processing image {img_path}: {e}")
                continue

        # Concatenate clips
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Add background audio if enabled
        if self.enable_audio and os.path.exists(self.audio_file):
            try:
                audio_clip = AudioFileClip(self.audio_file).subclip(0, final_clip.duration)
                final_audio = CompositeAudioClip([audio_clip])
                final_clip = final_clip.set_audio(final_audio)
            except Exception as e:
                print(f"Error adding audio: {e}")

        # Write the video file
        try:
            final_clip.write_videofile(
                self.output_video,
                fps=self.frame_rate,
                codec=self.video_codec,
                audio_codec='aac' if self.enable_audio else None,
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
            print(f"Video successfully saved at {self.output_video}")
        except Exception as e:
            print(f"Error writing video file: {e}")
        finally:
            final_clip.close()

    def update_video(self):
        """Fetch images and create/update the video."""
        image_paths = self.get_sorted_image_paths()
        self.create_video(image_paths)

    def start_watching(self):
        """Start watching the snapshot directory for changes."""
        event_handler = VideoGeneratorHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, path=self.snapshot_dir, recursive=False)
        self.observer.start()
        print(f"Started watching directory: {self.snapshot_dir}")

    def stop_watching(self):
        """Stop watching the snapshot directory."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print(f"Stopped watching directory: {self.snapshot_dir}")

class VideoGeneratorGUI:
    """GUI for the Video Generator application."""

    def __init__(self, root):
        self.root = root
        self.root.title("🔥 Super Bad Ass Video Generator and Editor 🔥")
        self.root.geometry("800x600")
        self.video_generator = None
        self.observer_thread = None

        # Initialize variables with defaults
        self.snapshot_dir = tk.StringVar(value=DEFAULT_SNAPSHOT_DIR)
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.assets_dir = tk.StringVar(value=DEFAULT_ASSETS_DIR)
        self.output_video = tk.StringVar(value=DEFAULT_OUTPUT_VIDEO)
        self.frame_rate = tk.IntVar(value=DEFAULT_FRAME_RATE)
        self.transition_duration = tk.DoubleVar(value=DEFAULT_TRANSITION_DURATION)
        self.video_duration = tk.DoubleVar(value=DEFAULT_VIDEO_DURATION)
        self.video_codec = tk.StringVar(value=DEFAULT_VIDEO_CODEC)
        self.video_format = tk.StringVar(value=DEFAULT_VIDEO_FORMAT)
        self.audio_file = tk.StringVar(value=DEFAULT_AUDIO_FILE)
        self.font_path = tk.StringVar(value=DEFAULT_FONT)
        self.enable_transitions = tk.BooleanVar(value=True)
        self.enable_audio = tk.BooleanVar(value=True)
        self.enable_text = tk.BooleanVar(value=False)
        self.text_content = tk.StringVar(value="Sample Text")
        self.text_position = tk.StringVar(value="bottom")
        self.text_fontsize = tk.IntVar(value=24)
        self.text_color = tk.StringVar(value="white")

        self.create_widgets()

    def create_widgets(self):
        """Create and place GUI widgets."""
        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill='both')

        # Settings Tab
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text='Settings')

        # Snapshot Directory
        ttk.Label(settings_frame, text="📸 Snapshots Directory:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.snapshot_dir, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_snapshot_dir).grid(row=0, column=2, padx=5, pady=5)

        # Output Directory
        ttk.Label(settings_frame, text="📂 Output Directory:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.output_dir, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_output_dir).grid(row=1, column=2, padx=5, pady=5)

        # Assets Directory
        ttk.Label(settings_frame, text="🎨 Assets Directory:").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.assets_dir, width=50).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_assets_dir).grid(row=2, column=2, padx=5, pady=5)

        # Output Video File
        ttk.Label(settings_frame, text="🎥 Output Video File:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.output_video, width=50).grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_output_video).grid(row=3, column=2, padx=5, pady=5)

        # Frame Rate
        ttk.Label(settings_frame, text="⏱️ Frame Rate (fps):").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        ttk.Spinbox(settings_frame, from_=1, to=60, textvariable=self.frame_rate, width=5).grid(row=4, column=1, sticky='w', padx=5, pady=5)

        # Transition Duration
        ttk.Label(settings_frame, text="🔄 Transition Duration (s):").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        ttk.Spinbox(settings_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.transition_duration, width=5).grid(row=5, column=1, sticky='w', padx=5, pady=5)

        # Video Duration per Image
        ttk.Label(settings_frame, text="⏳ Duration per Image (s):").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        ttk.Spinbox(settings_frame, from_=1, to=10, increment=0.5, textvariable=self.video_duration, width=5).grid(row=6, column=1, sticky='w', padx=5, pady=5)

        # Video Codec
        ttk.Label(settings_frame, text="🖥️ Video Codec:").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        ttk.Combobox(settings_frame, textvariable=self.video_codec, values=['libx264', 'mpeg4', 'libvpx'], width=10).grid(row=7, column=1, sticky='w', padx=5, pady=5)

        # Video Format
        ttk.Label(settings_frame, text="📄 Video Format:").grid(row=8, column=0, sticky='e', padx=5, pady=5)
        ttk.Combobox(settings_frame, textvariable=self.video_format, values=['mp4', 'avi', 'webm'], width=10).grid(row=8, column=1, sticky='w', padx=5, pady=5)

        # Background Audio File
        ttk.Label(settings_frame, text="🎵 Background Audio File:").grid(row=9, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.audio_file, width=50).grid(row=9, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_audio_file).grid(row=9, column=2, padx=5, pady=5)

        # Font File
        ttk.Label(settings_frame, text="🅰️ Font File (optional):").grid(row=10, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.font_path, width=50).grid(row=10, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_font_file).grid(row=10, column=2, padx=5, pady=5)

        # Enable Transitions
        ttk.Checkbutton(settings_frame, text="🔁 Enable Transitions", variable=self.enable_transitions).grid(row=11, column=1, sticky='w', padx=5, pady=5)

        # Enable Audio
        ttk.Checkbutton(settings_frame, text="🔊 Enable Background Audio", variable=self.enable_audio).grid(row=12, column=1, sticky='w', padx=5, pady=5)

        # Enable Text Overlay
        ttk.Checkbutton(settings_frame, text="✏️ Enable Text Overlay", variable=self.enable_text, command=self.toggle_text_options).grid(row=13, column=1, sticky='w', padx=5, pady=5)

        # Text Content
        self.text_content_entry = ttk.Entry(settings_frame, textvariable=self.text_content, width=50)
        self.text_content_entry.grid(row=14, column=1, padx=5, pady=5)
        ttk.Label(settings_frame, text="📝 Text Content:").grid(row=14, column=0, sticky='e', padx=5, pady=5)

        # Text Position
        ttk.Label(settings_frame, text="📍 Text Position:").grid(row=15, column=0, sticky='e', padx=5, pady=5)
        ttk.Combobox(settings_frame, textvariable=self.text_position, values=['top', 'center', 'bottom', 'left', 'right'], width=10).grid(row=15, column=1, sticky='w', padx=5, pady=5)

        # Text Font Size
        ttk.Label(settings_frame, text="🔤 Text Font Size:").grid(row=16, column=0, sticky='e', padx=5, pady=5)
        ttk.Spinbox(settings_frame, from_=10, to=100, textvariable=self.text_fontsize, width=5).grid(row=16, column=1, sticky='w', padx=5, pady=5)

        # Text Color
        ttk.Label(settings_frame, text="🎨 Text Color:").grid(row=17, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.text_color, width=10).grid(row=17, column=1, sticky='w', padx=5, pady=5)

        # Start and Stop Buttons
        ttk.Button(settings_frame, text="🚀 Start Generating Video", command=self.start_video_generation).grid(row=18, column=1, sticky='e', padx=5, pady=20)
        ttk.Button(settings_frame, text="🛑 Stop", command=self.stop_video_generation).grid(row=18, column=2, sticky='w', padx=5, pady=20)

        # Disable text options initially
        self.toggle_text_options()

    def toggle_text_options(self):
        """Enable or disable text overlay options based on the checkbox."""
        state = 'normal' if self.enable_text.get() else 'disabled'
        self.text_content_entry.configure(state=state)

    def browse_snapshot_dir(self):
        """Browse and select the snapshots directory."""
        directory = filedialog.askdirectory()
        if directory:
            self.snapshot_dir.set(directory)

    def browse_output_dir(self):
        """Browse and select the output directory."""
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)

    def browse_assets_dir(self):
        """Browse and select the assets directory."""
        directory = filedialog.askdirectory()
        if directory:
            self.assets_dir.set(directory)

    def browse_output_video(self):
        """Browse and select the output video file."""
        filetypes = [('MP4', '*.mp4'), ('AVI', '*.avi'), ('WebM', '*.webm')]
        file = filedialog.asksaveasfilename(defaultextension='.mp4', filetypes=filetypes)
        if file:
            self.output_video.set(file)

    def browse_audio_file(self):
        """Browse and select the background audio file."""
        filetypes = [('Audio Files', '*.mp3 *.wav *.aac *.m4a')]
        file = filedialog.askopenfilename(filetypes=filetypes)
        if file:
            self.audio_file.set(file)

    def browse_font_file(self):
        """Browse and select the font file."""
        filetypes = [('Font Files', '*.ttf *.otf')]
        file = filedialog.askopenfilename(filetypes=filetypes)
        if file:
            self.font_path.set(file)

    def start_video_generation(self):
        """Initialize the VideoGenerator and start watching the snapshot directory."""
        # Validate directories
        if not os.path.exists(self.snapshot_dir.get()):
            messagebox.showerror("Error", f"Snapshot directory does not exist: {self.snapshot_dir.get()}")
            return
        if not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())
        if not os.path.exists(self.assets_dir.get()):
            os.makedirs(self.assets_dir.get())

        # Update output video path based on format
        output_video = self.output_video.get()
        if not output_video.endswith(self.video_format.get()):
            output_video += f".{self.video_format.get()}"

        # Initialize VideoGenerator
        self.video_generator = VideoGenerator(
            snapshot_dir=self.snapshot_dir.get(),
            output_dir=self.output_dir.get(),
            assets_dir=self.assets_dir.get(),
            output_video=output_video,
            frame_rate=self.frame_rate.get(),
            transition_duration=self.transition_duration.get(),
            video_duration=self.video_duration.get(),
            video_codec=self.video_codec.get(),
            video_format=self.video_format.get(),
            audio_file=self.audio_file.get(),
            font_path=self.font_path.get(),
            enable_transitions=self.enable_transitions.get(),
            enable_audio=self.enable_audio.get(),
            enable_text=self.enable_text.get(),
            text_content=self.text_content.get(),
            text_position=self.text_position.get(),
            text_fontsize=self.text_fontsize.get(),
            text_color=self.text_color.get()
        )

        # Initial Video Creation
        self.video_generator.update_video()

        # Start watching in a separate thread to keep GUI responsive
        self.observer_thread = threading.Thread(target=self.video_generator.start_watching, daemon=True)
        self.observer_thread.start()

        messagebox.showinfo("Started", "🚀 Video generation started and directory is being watched.")

    def stop_video_generation(self):
        """Stop watching the snapshot directory."""
        if self.video_generator:
            self.video_generator.stop_watching()
            messagebox.showinfo("Stopped", "🛑 Video generation stopped.")

def main():
    root = tk.Tk()
    app = VideoGeneratorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
