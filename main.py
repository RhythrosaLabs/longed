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
from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation

# ============================
# Helper Functions
# ============================

def remove_background_replicate(api_key, image_path):
    """
    Remove background from an image using Replicate's removebg model.
    """
    os.environ["REPLICATE_API_TOKEN"] = api_key
    model = replicate.models.get("joshshorer/remove-bg")
    version = model.versions.get("97543df48a5c1044935bfeb501a7a832cd5e7a54")
    output = version.predict(image=open(image_path, "rb"))
    return output

def apply_filter_replicate(api_key, image_path, filter_type):
    """
    Apply a filter to an image using Replicate's style transfer models.
    """
    os.environ["REPLICATE_API_TOKEN"] = api_key
    if filter_type == "Artistic":
        model = replicate.models.get("jamesroutley/cyberpunk")
        version = model.versions.get("a93eab4d32c12a154d3c7d9e0e126b54fa7efc3e")
    elif filter_type == "Vintage":
        model = replicate.models.get("rinarppar/nostalgic")
        version = model.versions.get("c3f63d2d4d2b4a9d1e2f1e0a8c1b3a2d4e5f6g7h")
    else:
        st.error("Unsupported filter type.")
        return None
    output = version.predict(image=open(image_path, "rb"))
    return output

def add_text_overlay(video_clip, text, position, fontsize, color, font):
    """
    Add text overlay to a video clip.
    """
    txt_clip = TextClip(text, fontsize=fontsize, color=color, font=font)
    txt_clip = txt_clip.set_position(position).set_duration(video_clip.duration)
    video = CompositeVideoClip([video_clip, txt_clip])
    return video

def concatenate_videos(video_paths, output_path):
    """
    Concatenate multiple video files into one.
    """
    clips = [VideoFileClip(video) for video in video_paths]
    final_clip = concatenate_videoclips(clips)
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    final_clip.close()

# ============================
# Streamlit Application
# ============================

def main():
    st.set_page_config(page_title="🔥 Bad Ass Video Generator & Editor 🔥", layout="wide")
    st.title("🔥 **Bad Ass Video Generator & Editor** 🔥")

    st.markdown("""
    Welcome to the **Bad Ass Video Generator & Editor**! This powerful tool allows you to create and edit videos with multiple features such as adding text overlays, removing backgrounds, applying filters, and more. Connect with Replicate and StabilityAI to harness advanced AI capabilities.
    """)

    # ============================
    # API Key Inputs
    # ============================
    st.sidebar.header("🔑 API Keys")
    replicate_api_key = st.sidebar.text_input("Replicate API Key", type="password")
    stability_api_key = st.sidebar.text_input("StabilityAI API Key", type="password")

    if not replicate_api_key or not stability_api_key:
        st.sidebar.warning("Please enter both Replicate and StabilityAI API keys to proceed.")
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
        font = st.sidebar.text_input("🅰️ Font", "Arial")

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
        if mode == "Add Text Overlay":
            if not uploaded_videos:
                st.error("Please upload at least one video to add text overlays.")
            else:
                for video_file in uploaded_videos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                        tmp_video.write(video_file.read())
                        tmp_video_path = tmp_video.name
                    video = VideoFileClip(tmp_video_path)
                    video = add_text_overlay(video, text, position, fontsize, color, font)
                    output_path = os.path.join("output", f"text_overlay_{os.path.basename(tmp_video_path)}")
                    video.write_videofile(output_path, codec="libx264", audio_codec="aac")
                    video.close()
                    st.success(f"Text overlay added and video saved to `{output_path}`")

        elif mode == "Remove Background":
            if not uploaded_images:
                st.error("Please upload at least one image to remove backgrounds.")
            else:
                for image_file in uploaded_images:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file.name)[1]) as tmp_image:
                        tmp_image.write(image_file.read())
                        tmp_image_path = tmp_image.name
                    output = remove_background_replicate(replicate_api_key, tmp_image_path)
                    output_path = os.path.join("output", f"no_bg_{os.path.basename(tmp_image_path)}.{output_format}")
                    Image.open(output).save(output_path)
                    st.success(f"Background removed and image saved to `{output_path}`")

        elif mode == "Apply Filter":
            if not uploaded_images:
                st.error("Please upload at least one image to apply filters.")
            else:
                for idx, image_file in enumerate(uploaded_images):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file.name)[1]) as tmp_image:
                        tmp_image.write(image_file.read())
                        tmp_image_path = tmp_image.name
                    output = apply_filter_replicate(replicate_api_key, tmp_image_path, filter_type)
                    output_path = os.path.join("output", f"filtered_{filter_type.lower()}_{idx}.{output_format}")
                    Image.open(output).save(output_path)
                    st.success(f"Filter applied and image saved to `{output_path}`")

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
                        order = [int(i)-1 for i in concat_order.split(",")]
                        ordered_videos = [video_paths[i] for i in order]
                    except:
                        st.error("Invalid concatenation order. Please provide comma-separated numeric indices.")
                        ordered_videos = video_paths
                else:
                    ordered_videos = video_paths
                output_path = os.path.join("output", "concatenated_video.mp4")
                concatenate_videos(ordered_videos, output_path)
                st.success(f"Videos concatenated and saved to `{output_path}`")

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
    **Bad Ass Video Generator & Editor** - Powered by [Replicate](https://replicate.com/) and [StabilityAI](https://stability.ai/).
    """)

if __name__ == "__main__":
    main()
