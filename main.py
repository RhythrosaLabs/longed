import os
import threading
import tempfile
import time
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
import streamlit as st

# ============================
# Configuration Defaults
# ============================

DEFAULT_SNAPSHOT_DIR = 'snapshots'
DEFAULT_OUTPUT_DIR = 'output'
DEFAULT_ASSETS_DIR = 'assets'
DEFAULT_FRAME_RATE = 24.0
DEFAULT_TRANSITION_DURATION = 1.0  # seconds
DEFAULT_VIDEO_DURATION = 2.0  # seconds per image
DEFAULT_VIDEO_CODEC = 'libx264'
DEFAULT_VIDEO_FORMAT = 'mp4'
DEFAULT_OUTPUT_VIDEO = os.path.join(DEFAULT_OUTPUT_DIR, 'output_video.mp4')
DEFAULT_AUDIO_FILE = os.path.join(DEFAULT_ASSETS_DIR, 'background_music.mp3')
DEFAULT_FONT = 'Arial'  # Default system font

# Supported Image Formats
IMAGE_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')

# Ensure necessary directories exist
for directory in [DEFAULT_SNAPSHOT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_ASSETS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# ============================
# Video Generator Class
# ============================

class VideoGenerator:
    """Handles video creation from images with optional transitions, text overlays, and background music."""
    
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
        self.font_path = font_path if font_path else DEFAULT_FONT
        self.enable_transitions = enable_transitions
        self.enable_audio = enable_audio
        self.enable_text = enable_text
        self.text_content = text_content
        self.text_position = text_position
        self.text_fontsize = text_fontsize
        self.text_color = text_color

    def get_sorted_image_paths(self):
        """Retrieve and sort image paths from the snapshot directory."""
        try:
            images = [img for img in os.listdir(self.snapshot_dir) if img.lower().endswith(IMAGE_FORMATS)]
            images.sort()  # Sort images by name; modify if necessary
            image_paths = [os.path.join(self.snapshot_dir, img) for img in images]
            return image_paths
        except Exception as e:
            st.error(f"Error accessing snapshot directory: {e}")
            return []

    def create_video(self, image_paths, progress_callback=None):
        """Create a video from image paths with optional transitions and text overlays."""
        if not image_paths:
            if progress_callback:
                progress_callback(0)
            st.warning("No images found to create a video.")
            return

        clips = []
        total_images = len(image_paths)

        for idx, img_path in enumerate(image_paths):
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
                        font=self.font_path
                    ).set_position(self.text_position).set_duration(self.video_duration)
                    clip = CompositeVideoClip([clip, txt_clip])
                
                # Add fade in and fade out transitions
                if self.enable_transitions:
                    clip = clip.fx(fadein, self.transition_duration).fx(fadeout, self.transition_duration)
                
                clips.append(clip)
                
                # Update progress
                if progress_callback:
                    progress = (idx + 1) / total_images
                    progress_callback(progress)
                    
            except Exception as e:
                st.error(f"Error processing image {img_path}: {e}")
                continue

        # Concatenate clips
        try:
            final_clip = concatenate_videoclips(clips, method="compose")
        except Exception as e:
            st.error(f"Error concatenating video clips: {e}")
            return
        
        # Add background audio if enabled
        if self.enable_audio and os.path.exists(self.audio_file):
            try:
                audio_clip = AudioFileClip(self.audio_file).subclip(0, final_clip.duration)
                final_audio = CompositeAudioClip([audio_clip])
                final_clip = final_clip.set_audio(final_audio)
            except Exception as e:
                st.error(f"Error adding audio: {e}")
        
        # Write the video file
        try:
            final_clip.write_videofile(
                self.output_video,
                fps=self.frame_rate,
                codec=self.video_codec,
                audio_codec='aac' if self.enable_audio else None,
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            st.success(f"Video successfully saved at `{self.output_video}`")
        except Exception as e:
            st.error(f"Error writing video file: {e}")
        finally:
            final_clip.close()

# ============================
# Watchdog Handler Class
# ============================

class VideoGeneratorHandler(FileSystemEventHandler):
    """Handles new image files and updates the video."""
    
    def __init__(self, generator, progress_callback=None):
        super().__init__()
        self.generator = generator
        self.progress_callback = progress_callback
        self.lock = threading.Lock()
        self.update_triggered = False

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(IMAGE_FORMATS):
            with self.lock:
                if not self.update_triggered:
                    self.update_triggered = True
                    threading.Thread(target=self.update_video).start()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(IMAGE_FORMATS):
            with self.lock:
                if not self.update_triggered:
                    self.update_triggered = True
                    threading.Thread(target=self.update_video).start()

    def update_video(self):
        self.generator.create_video(self.generator.get_sorted_image_paths(), self.progress_callback)
        with self.lock:
            self.update_triggered = False

# ============================
# Streamlit App
# ============================

def main():
    st.set_page_config(page_title="🔥 Super Bad Ass Video Generator and Editor 🔥", layout="wide")
    st.title("🔥 **Super Bad Ass Video Generator and Editor** 🔥")
    
    # Initialize session state
    if 'observer' not in st.session_state:
        st.session_state.observer = None
    if 'handler' not in st.session_state:
        st.session_state.handler = None
    if 'generator' not in st.session_state:
        st.session_state.generator = None
    if 'running' not in st.session_state:
        st.session_state.running = False

    # Sidebar for configuration
    st.sidebar.header("⚙️ Configuration")
    
    # Snapshot Directory
    snapshot_dir = st.sidebar.text_input("📸 Snapshots Directory", DEFAULT_SNAPSHOT_DIR)
    
    # Output Directory
    output_dir = st.sidebar.text_input("📂 Output Directory", DEFAULT_OUTPUT_DIR)
    
    # Assets Directory
    assets_dir = st.sidebar.text_input("🎨 Assets Directory", DEFAULT_ASSETS_DIR)
    
    # Output Video File
    video_filename = st.sidebar.text_input("🎥 Output Video Filename", "output_video.mp4")
    video_format = st.sidebar.selectbox("📄 Video Format", ['mp4', 'avi', 'webm'], index=0)
    output_video = os.path.join(output_dir, video_filename)
    if not output_video.endswith(f".{video_format}"):
        output_video += f".{video_format}"
    
    # Frame Rate
    frame_rate = st.sidebar.slider("⏱️ Frame Rate (fps)", 1.0, 60.0, DEFAULT_FRAME_RATE, 0.1)
    
    # Transition Duration
    transition_duration = st.sidebar.slider(
        "🔄 Transition Duration (s)", 
        0.1, 
        5.0, 
        DEFAULT_TRANSITION_DURATION, 
        0.1,
        key='transition_duration_slider'
    )
    
    # Video Duration per Image
    video_duration = st.sidebar.slider(
        "⏳ Duration per Image (s)", 
        1.0, 
        10.0, 
        DEFAULT_VIDEO_DURATION, 
        0.5,
        key='video_duration_slider'
    )
    
    # Video Codec
    video_codec = st.sidebar.selectbox("🖥️ Video Codec", ['libx264', 'mpeg4', 'libvpx'], index=0)
    
    # Background Audio File
    audio_file = st.sidebar.file_uploader("🎵 Upload Background Audio File", type=['mp3', 'wav', 'aac', 'm4a'])
    if audio_file:
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.name)[1])
        temp_audio.write(audio_file.read())
        temp_audio.close()
        audio_file_path = temp_audio.name
    else:
        audio_file_path = DEFAULT_AUDIO_FILE  # Default path
    
    # Font File
    font_file = st.sidebar.file_uploader("🅰️ Upload Font File (optional)", type=['ttf', 'otf'])
    if font_file:
        temp_font = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(font_file.name)[1])
        temp_font.write(font_file.read())
        temp_font.close()
        font_path = temp_font.name
    else:
        font_path = None  # Use default system font
    
    # Enable Transitions
    enable_transitions = st.sidebar.checkbox("🔁 Enable Transitions", value=True)
    
    # Enable Audio
    enable_audio = st.sidebar.checkbox("🔊 Enable Background Audio", value=True)
    
    # Enable Text Overlay
    enable_text = st.sidebar.checkbox("✏️ Enable Text Overlay", value=False)
    
    # Text Overlay Options
    if enable_text:
        text_content = st.sidebar.text_input("📝 Text Content", "Sample Text")
        text_position = st.sidebar.selectbox("📍 Text Position", ['top', 'center', 'bottom', 'left', 'right'], index=1)
        text_fontsize = st.sidebar.slider("🔤 Text Font Size", 10, 100, 24, step=1)
        text_color = st.sidebar.color_picker("🎨 Text Color", "#FFFFFF")
    else:
        text_content = ""
        text_position = "bottom"
        text_fontsize = 24
        text_color = "#FFFFFF"
    
    # Progress Bar
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # Function to update progress
    def update_progress(progress):
        progress_bar.progress(progress)
        progress_text.text(f"Processing... {int(progress * 100)}%")
    
    # Start Video Generation and Monitoring
    if st.sidebar.button("🚀 Start Video Generation and Monitoring"):
        if st.session_state.running:
            st.warning("Video generation and monitoring is already running.")
        else:
            # Validate directories
            if not os.path.exists(snapshot_dir):
                st.error(f"Snapshot directory does not exist: `{snapshot_dir}`")
            elif not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                    st.warning(f"Output directory created: `{output_dir}`")
                except Exception as e:
                    st.error(f"Error creating output directory: {e}")
            elif not os.path.exists(assets_dir):
                try:
                    os.makedirs(assets_dir)
                    st.warning(f"Assets directory created: `{assets_dir}`")
                except Exception as e:
                    st.error(f"Error creating assets directory: {e}")
            else:
                # Initialize VideoGenerator
                generator = VideoGenerator(
                    snapshot_dir=snapshot_dir,
                    output_dir=output_dir,
                    assets_dir=assets_dir,
                    output_video=output_video,
                    frame_rate=frame_rate,
                    transition_duration=transition_duration,
                    video_duration=video_duration,
                    video_codec=video_codec,
                    video_format=video_format,
                    audio_file=audio_file_path,
                    font_path=font_path,
                    enable_transitions=enable_transitions,
                    enable_audio=enable_audio,
                    enable_text=enable_text,
                    text_content=text_content,
                    text_position=text_position,
                    text_fontsize=text_fontsize,
                    text_color=text_color
                )
                
                # Initial Video Creation
                with st.spinner("Generating initial video..."):
                    generator.create_video(generator.get_sorted_image_paths(), update_progress)
                
                # Set up Watchdog Handler and Observer
                handler = VideoGeneratorHandler(generator, progress_callback=update_progress)
                observer = Observer()
                observer.schedule(handler, path=snapshot_dir, recursive=False)
                observer.start()
                
                # Save to session state
                st.session_state.observer = observer
                st.session_state.handler = handler
                st.session_state.generator = generator
                st.session_state.running = True
                
                st.success("🛰️ Started monitoring snapshots directory for new images.")
    
    # Stop Video Generation and Monitoring
    if st.sidebar.button("🛑 Stop Monitoring"):
        if st.session_state.running:
            try:
                st.session_state.observer.stop()
                st.session_state.observer.join()
                st.session_state.running = False
                st.success("🛑 Stopped monitoring snapshots directory.")
            except Exception as e:
                st.error(f"Error stopping observer: {e}")
        else:
            st.warning("Video generation and monitoring is not running.")
    
    # Display Output Video
    if os.path.exists(output_video):
        st.subheader("📹 Generated Video:")
        video_file = open(output_video, "rb")
        video_bytes = video_file.read()
        st.video(video_bytes)
    
    # Display Instructions
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📌 **Instructions:**")
    st.sidebar.markdown("""
    1. **Snapshots Directory:** Ensure that your images are saved in the specified `snapshots` directory. Supported formats are PNG, JPG, JPEG, BMP, and TIFF.
    2. **Assets Directory:** Place your background music (`.mp3`, `.wav`, etc.) and custom fonts (`.ttf`, `.otf`) in the `assets` directory or upload them via the sidebar.
    3. **Configure Settings:** Use the sidebar to adjust frame rate, transition duration, video duration per image, video codec, format, and enable/disable features like transitions, audio, and text overlays.
    4. **Start Monitoring:** Click on "🚀 Start Video Generation and Monitoring" to generate the initial video and begin watching for new images. The video will update automatically as new images are added to the `snapshots` directory.
    5. **Stop Monitoring:** Click on "🛑 Stop Monitoring" to halt the directory watching process.
    6. **View Video:** The generated video will be displayed within the app. You can also download it directly from the `output` directory.
    """)
    
    # Cleanup Temporary Files on Exit
    def cleanup():
        if 'handler' in st.session_state and st.session_state.handler:
            st.session_state.handler.update_triggered = False
        if audio_file:
            os.unlink(audio_file_path)
        if font_file:
            os.unlink(font_path)
    
    import atexit
    atexit.register(cleanup)

if __name__ == "__main__":
    main()
