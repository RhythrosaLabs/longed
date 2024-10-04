import os
import streamlit as st
import tempfile
from PIL import Image
from moviepy.editor import (
    ImageClip,
    concatenate_videoclips,
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    AudioFileClip,
)
import replicate
import requests
import numpy as np

# ============================
# Helper Functions
# ============================

def remove_background_replicate(api_key, image_path):
    """
    Remove background from an image using Replicate's background removal model.
    """
    try:
        # Set Replicate API Token
        os.environ["REPLICATE_API_TOKEN"] = api_key

        # Choose a background removal model. Example: remove-bg from joshshorer
        model = replicate.models.get("joshshorer/remove-bg")
        version = model.versions.get("97543df48a5c1044935bfeb501a7a832cd5e7a54")  # Replace with latest version ID

        # Predict and get the output URL
        output_url = version.predict(image=open(image_path, "rb"))

        return output_url
    except Exception as e:
        st.error(f"Error removing background: {e}")
        return None

def apply_filter_replicate(api_key, image_path, filter_type):
    """
    Apply a filter to an image using Replicate's style transfer models.
    """
    try:
        # Set Replicate API Token
        os.environ["REPLICATE_API_TOKEN"] = api_key

        if filter_type == "Artistic":
            # Example model: jamesroutley/cyberpunk
            model = replicate.models.get("jamesroutley/cyberpunk")
            version = model.versions.get("a93eab4d32c12a154d3c7d9e0e126b54fa7efc3e")  # Replace with latest version ID
        elif filter_type == "Vintage":
            # Example model: stability-ai/stable-diffusion-v1-5
            model = replicate.models.get("stability-ai/stable-diffusion")
            version = model.versions.get("a1b2c3d4e5f6g7h8i9j0")  # Replace with actual version ID
        else:
            st.error("Unsupported filter type.")
            return None

        # Predict and get the output URL
        output_url = version.predict(image=open(image_path, "rb"))

        return output_url
    except Exception as e:
        st.error(f"Error applying filter: {e}")
        return None

def add_text_overlay(video_clip, text, position, fontsize, color, font):
    """
    Add text overlay to a video clip.
    """
    try:
        txt_clip = TextClip(text, fontsize=fontsize, color=color, font=font)
        txt_clip = txt_clip.set_position(position).set_duration(video_clip.duration)
        video = CompositeVideoClip([video_clip, txt_clip])
        return video
    except Exception as e:
        st.error(f"Error adding text overlay: {e}")
        return video_clip

def concatenate_videos(video_paths, output_path):
    """
    Concatenate multiple video files into one.
    """
    try:
        clips = [VideoFileClip(video) for video in video_paths]
        final_clip = concatenate_videoclips(clips)
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        final_clip.close()
        st.success(f"Videos concatenated and saved to `{output_path}`")
    except Exception as e:
        st.error(f"Error concatenating videos: {e}")

def download_image(url, save_path):
    """
    Download an image from a URL and save it locally.
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            st.error(f"Failed to download image. Status code: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error downloading image: {e}")
        return False

# ============================
# Streamlit Application
# ============================

def main():
    st.set_page_config(page_title="🔥 Bad Ass Video Generator & Editor 🔥", layout="wide")
    st.title("🔥 **Bad Ass Video Generator & Editor** 🔥")

    st.markdown("""
    Welcome to the **Bad Ass Video Generator & Editor**! This powerful tool allows you to create and edit videos with multiple features such as adding text overlays, removing backgrounds, applying filters, and concatenating videos. Connect with Replicate's advanced AI models to harness cutting-edge capabilities.
    """)

    # ============================
    # API Key Inputs
    # ============================
    st.sidebar.header("🔑 API Keys")
    replicate_api_key = st.sidebar.text_input("Replicate API Key", type="password")

    if not replicate_api_key:
        st.sidebar.warning("Please enter your Replicate API key to proceed.")
        st.stop()

    # ============================
    # File Uploads
    # ============================
    st.sidebar.header("📂 Upload Files")
    uploaded_images = st.sidebar.file_uploader(
        "Upload Images for Processing (Background Removal / Apply Filters)",
        type=["png", "jpg", "jpeg", "bmp", "tiff"],
        accept_multiple_files=True,
    )
    uploaded_videos = st.sidebar.file_uploader(
        "Upload Videos for Processing (Add Text Overlay / Concatenate)",
        type=["mp4", "avi", "mov", "mkv"],
        accept_multiple_files=True,
    )

    # ============================
    # Configuration Options
    # ============================
    st.sidebar.header("⚙️ Configuration")

    # Mode Selection
    mode = st.sidebar.selectbox(
        "🎨 Select Mode",
        ["Add Text Overlay", "Remove Background", "Apply Filter", "Concatenate Videos"],
    )

    # Add Text Overlay Configuration
    if mode == "Add Text Overlay":
        st.sidebar.subheader("✏️ Text Overlay Settings")
        text = st.sidebar.text_input("📝 Text to Add", "Your Text Here")
        position = st.sidebar.selectbox(
            "📍 Position",
            ["top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right"],
        )
        fontsize = st.sidebar.slider("🔤 Font Size", 10, 100, 30)
        color = st.sidebar.color_picker("🎨 Text Color", "#FFFFFF")
        font = st.sidebar.text_input("🅰️ Font", "Arial")  # Ensure the font is available on the system

    # Remove Background Configuration
    elif mode == "Remove Background":
        st.sidebar.subheader("🖼️ Background Removal Settings")
        bg_color = st.sidebar.color_picker("🎨 Background Color", "#000000")
        output_format = st.sidebar.selectbox("📄 Output Format", ["png", "jpg"])

    # Apply Filter Configuration
    elif mode == "Apply Filter":
        st.sidebar.subheader("🎨 Filter Settings")
        filter_type = st.sidebar.selectbox("✨ Select Filter", ["Artistic", "Vintage"])
        strength = st.sidebar.slider("💪 Filter Strength", 1, 10, 5)

    # Concatenate Videos Configuration
    elif mode == "Concatenate Videos":
        st.sidebar.subheader("📽️ Concatenation Settings")
        concat_order = st.sidebar.text_input("📋 Video Order (comma-separated indices, e.g., 1,2,3)", "1,2,3")

    # ============================
    # Processing Button
    # ============================
    if st.sidebar.button("🚀 Process"):
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if mode == "Add Text Overlay":
            if not uploaded_videos:
                st.error("Please upload at least one video to add text overlays.")
            else:
                processed_video_paths = []
                for idx, video_file in enumerate(uploaded_videos):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                        tmp_video.write(video_file.read())
                        tmp_video_path = tmp_video.name
                    try:
                        video = VideoFileClip(tmp_video_path)
                        video = add_text_overlay(video, text, position, fontsize, color, font)
                        output_path = os.path.join(output_dir, f"text_overlay_{idx+1}.mp4")
                        video.write_videofile(output_path, codec="libx264", audio_codec="aac")
                        video.close()
                        processed_video_paths.append(output_path)
                        st.success(f"Text overlay added and video saved to `{output_path}`")
                    except Exception as e:
                        st.error(f"Error processing video {video_file.name}: {e}")

        elif mode == "Remove Background":
            if not uploaded_images:
                st.error("Please upload at least one image to remove backgrounds.")
            else:
                for idx, image_file in enumerate(uploaded_images):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file.name)[1]) as tmp_image:
                        tmp_image.write(image_file.read())
                        tmp_image_path = tmp_image.name
                    output_url = remove_background_replicate(replicate_api_key, tmp_image_path)
                    if output_url:
                        # Download the processed image from the output URL
                        success = download_image(output_url, os.path.join(output_dir, f"no_bg_{idx+1}.{output_format}"))
                        if success:
                            st.success(f"Background removed and image saved to `output/no_bg_{idx+1}.{output_format}`")

        elif mode == "Apply Filter":
            if not uploaded_images:
                st.error("Please upload at least one image to apply filters.")
            else:
                for idx, image_file in enumerate(uploaded_images):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file.name)[1]) as tmp_image:
                        tmp_image.write(image_file.read())
                        tmp_image_path = tmp_image.name
                    output_url = apply_filter_replicate(replicate_api_key, tmp_image_path, filter_type)
                    if output_url:
                        # Download the processed image from the output URL
                        success = download_image(output_url, os.path.join(output_dir, f"{filter_type.lower()}_{idx+1}.{output_format}"))
                        if success:
                            st.success(f"Filter applied and image saved to `output/{filter_type.lower()}_{idx+1}.{output_format}`")

        elif mode == "Concatenate Videos":
            if not uploaded_videos or len(uploaded_videos) < 2:
                st.error("Please upload at least two videos to concatenate.")
            else:
                video_paths = []
                for idx, video_file in enumerate(uploaded_videos):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                        tmp_video.write(video_file.read())
                        tmp_video_path = tmp_video.name
                        video_paths.append(tmp_video_path)
                # Process concatenation order
                try:
                    order = [int(i.strip()) - 1 for i in concat_order.split(",")]
                    if any(i < 0 or i >= len(video_paths) for i in order):
                        raise ValueError("Index out of range.")
                    ordered_videos = [video_paths[i] for i in order]
                except Exception as e:
                    st.error(f"Invalid concatenation order: {e}")
                    ordered_videos = video_paths  # Default to original order

                output_path = os.path.join(output_dir, "concatenated_video.mp4")
                concatenate_videos(ordered_videos, output_path)

    # ============================
    # Display Output Videos and Images
    # ============================
    st.header("📹 Output Videos and Images")

    output_dir = "output"
    if os.path.exists(output_dir):
        output_files = sorted(os.listdir(output_dir))
        if output_files:
            for file in output_files:
                file_path = os.path.join(output_dir, file)
                if file.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                    st.subheader(f"🎥 {file}")
                    video_bytes = open(file_path, "rb").read()
                    st.video(video_bytes)
                elif file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                    st.subheader(f"🖼️ {file}")
                    st.image(file_path, use_column_width=True)
        else:
            st.info("No output files found. Please process some files first!")
    else:
        st.info("No output directory found. Please process some files first!")

    # ============================
    # Footer
    # ============================
    st.markdown("---")
    st.markdown("""
    **Bad Ass Video Generator & Editor** - Powered by [Replicate](https://replicate.com/).
    """)

if __name__ == "__main__":
    main()
