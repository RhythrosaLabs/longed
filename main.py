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

# ============================
# Helper Functions
# ============================

def remove_background_replicate(api_key, image_path):
    """
    Remove background from an image using Replicate's remove-bg model.
    """
    os.environ["REPLICATE_API_TOKEN"] = api_key
    try:
        model = replicate.models.get("joshshorer/remove-bg")
        version = model.versions.get("97543df48a5c1044935bfeb501a7a832cd5e7a54")
        output_url = version.predict(image=open(image_path, "rb"))
        return output_url
    except Exception as e:
        st.error(f"Error removing background: {e}")
        return None

def apply_filter_replicate(api_key, image_path, filter_type):
    """
    Apply a filter to an image using Replicate's style transfer models.
    """
    os.environ["REPLICATE_API_TOKEN"] = api_key
    try:
        if filter_type == "Artistic":
            model = replicate.models.get("jamesroutley/cyberpunk")
            version = model.versions.get("a93eab4d32c12a154d3c7d9e0e126b54fa7efc3e")
        elif filter_type == "Vintage":
            # Example model; replace with an actual vintage filter model from Replicate
            model = replicate.models.get("basujindal/vintage")
            version = model.versions.get("1f2d3e4g5h6i7j8k9l0m")
        else:
            st.error("Unsupported filter type.")
            return None
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
    uploaded_images = st.sidebar.file_uploader("Upload Images", type=["png", "jpg", "jpeg", "bmp", "tiff"], accept_multiple_files=True)
    uploaded_videos = st.sidebar.file_uploader("Upload Videos", type=["mp4", "avi", "mov", "mkv"], accept_multiple_files=True)

    # ============================
    # Configuration Options
    # ============================
    st.sidebar.header("⚙️ Configuration")

    # Mode Selection
    mode = st.sidebar.selectbox("🎨 Select Mode", ["Add Text Overlay", "Remove Background", "Apply Filter", "Concatenate Videos", "Advanced Editing"])

    # Add Text Overlay Configuration
    if mode == "Add Text Overlay":
        st.sidebar.subheader("✏️ Text Overlay Settings")
        text = st.sidebar.text_input("📝 Text to Add", "Your Text Here")
        position = st.sidebar.selectbox("📍 Position", ["top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right"])
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
        concat_order = st.sidebar.text_input("📋 Video Order (comma-separated indices, e.g., 1,2,3)")

    # Advanced Editing Configuration
    elif mode == "Advanced Editing":
        st.sidebar.subheader("🛠️ Advanced Editing Settings")
        # Placeholder for additional advanced settings
        st.sidebar.info("Advanced editing features coming soon!")

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
                for video_file in uploaded_videos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                        tmp_video.write(video_file.read())
                        tmp_video_path = tmp_video.name
                    try:
                        video = VideoFileClip(tmp_video_path)
                        video = add_text_overlay(video, text, position, fontsize, color, font)
                        output_path = os.path.join(output_dir, f"text_overlay_{os.path.basename(tmp_video_path)}")
                        video.write_videofile(output_path, codec="libx264", audio_codec="aac")
                        video.close()
                        st.success(f"Text overlay added and video saved to `{output_path}`")
                    except Exception as e:
                        st.error(f"Error processing video {video_file.name}: {e}")

        elif mode == "Remove Background":
            if not uploaded_images:
                st.error("Please upload at least one image to remove backgrounds.")
            else:
                for image_file in uploaded_images:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file.name)[1]) as tmp_image:
                        tmp_image.write(image_file.read())
                        tmp_image_path = tmp_image.name
                    output = remove_background_replicate(replicate_api_key, tmp_image_path)
                    if output:
                        # Download the output image from the URL
                        try:
                            import requests
                            response = requests.get(output)
                            if response.status_code == 200:
                                output_path = os.path.join(output_dir, f"no_bg_{os.path.splitext(image_file.name)[0]}.{output_format}")
                                with open(output_path, "wb") as f:
                                    f.write(response.content)
                                st.success(f"Background removed and image saved to `{output_path}`")
                            else:
                                st.error(f"Failed to download processed image for `{image_file.name}`")
                        except Exception as e:
                            st.error(f"Error downloading processed image for `{image_file.name}`: {e}")

        elif mode == "Apply Filter":
            if not uploaded_images:
                st.error("Please upload at least one image to apply filters.")
            else:
                for idx, image_file in enumerate(uploaded_images):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file.name)[1]) as tmp_image:
                        tmp_image.write(image_file.read())
                        tmp_image_path = tmp_image.name
                    output = apply_filter_replicate(replicate_api_key, tmp_image_path, filter_type)
                    if output:
                        # Download the output image from the URL
                        try:
                            import requests
                            response = requests.get(output)
                            if response.status_code == 200:
                                output_path = os.path.join(output_dir, f"filtered_{filter_type.lower()}_{idx}.{output_format}")
                                with open(output_path, "wb") as f:
                                    f.write(response.content)
                                st.success(f"Filter applied and image saved to `{output_path}`")
                            else:
                                st.error(f"Failed to download processed image for `{image_file.name}`")
                        except Exception as e:
                            st.error(f"Error downloading processed image for `{image_file.name}`: {e}")

        elif mode == "Concatenate Videos":
            if not uploaded_videos:
                st.error("Please upload at least two videos to concatenate.")
            else:
                video_paths = []
                for video_file in uploaded_videos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                        tmp_video.write(video_file.read())
                        tmp_video_path = tmp_video.name
                        video_paths.append(tmp_video_path)
                if concat_order:
                    try:
                        order = [int(i.strip())-1 for i in concat_order.split(",")]
                        if any(i < 0 or i >= len(video_paths) for i in order):
                            raise ValueError("Index out of range.")
                        ordered_videos = [video_paths[i] for i in order]
                    except Exception as e:
                        st.error(f"Invalid concatenation order: {e}")
                        ordered_videos = video_paths
                else:
                    ordered_videos = video_paths
                output_path = os.path.join(output_dir, "concatenated_video.mp4")
                concatenate_videos(ordered_videos, output_path)

        elif mode == "Advanced Editing":
            st.info("Advanced editing features are under development.")

    # ============================
    # Display Output Videos and Images
    # ============================
    st.header("📹 Output Videos and Images")

    output_dir = "output"
    if os.path.exists(output_dir):
        output_files = os.listdir(output_dir)
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
            st.info("No output files found. Process some files first!")
    else:
        st.info("No output directory found. Process some files first!")

    # ============================
    # Footer
    # ============================
    st.markdown("---")
    st.markdown("""
    **Bad Ass Video Generator & Editor** - Powered by [Replicate](https://replicate.com/).
    """)

if __name__ == "__main__":
    main()
