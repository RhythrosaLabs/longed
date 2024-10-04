import streamlit as st
import requests
import base64
from PIL import Image, ImageEnhance
import io
from moviepy.editor import (
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    vfx,
    AudioFileClip,
)
import os
import sys
import numpy as np
import time
import traceback
import zipfile
import logging
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiohttp
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redirect stderr to stdout to capture all logs in Streamlit
sys.stderr = sys.stdout

# Initialize session state for persistent storage
for key in ['generated_images', 'generated_videos', 'final_video', 'audio_file']:
    if key not in st.session_state:
        st.session_state[key] = [] if key != 'final_video' else None
        if key == 'audio_file':
            st.session_state[key] = None

# Caching decorator for resizing images
@st.cache_data(show_spinner=False)
def cached_resize_image(image_bytes: bytes, size: tuple) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes))
    return image.resize(size)

# Caching decorator for validating video clips
@st.cache_resource
def cached_validate_video_clip(video_path: str) -> bool:
    if not os.path.exists(video_path):
        return False
    try:
        with VideoFileClip(video_path) as clip:
            return clip.duration > 0
    except:
        return False

def resize_image(image: Image.Image) -> Image.Image:
    """
    Resize the image to one of the supported dimensions or default to 768x768.
    """
    supported_sizes = [(1024, 576), (576, 1024), (768, 768)]
    if image.size in supported_sizes:
        return image
    else:
        st.warning("Resizing image to 768x768 (default)")
        return image.resize((768, 768))

async def generate_image_from_text(session: aiohttp.ClientSession, api_key: str, prompt: str) -> Image.Image:
    """
    Asynchronously generate an image from a text prompt using Stability AI's API.
    """
    url = "https://api.stability.ai/v1beta/generation/stable-diffusion-v1-6/text-to-image"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "text_prompts": [{"text": prompt}],
        "cfg_scale": 7,
        "height": 768,
        "width": 768,
        "samples": 1,
        "steps": 30,
    }
    try:
        async with session.post(url, headers=headers, json=data) as response:
            response.raise_for_status()
            resp_json = await response.json()
            image_data = resp_json['artifacts'][0]['base64']
            image = Image.open(io.BytesIO(base64.b64decode(image_data)))
            return image
    except Exception as e:
        st.error(f"Error generating image: {str(e)}")
        logger.error(f"Error generating image: {str(e)}")
        return None

async def start_video_generation(session: aiohttp.ClientSession, api_key: str, image: Image.Image, cfg_scale: float = 1.8,
                                motion_bucket_id: int = 127, seed: int = 0) -> str:
    """
    Asynchronously initiate video generation based on an image using Stability AI's API.
    Returns the generation ID if successful.
    """
    url = "https://api.stability.ai/v2beta/image-to-video"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    data = {
        "seed": str(seed),
        "cfg_scale": str(cfg_scale),
        "motion_bucket_id": str(motion_bucket_id)
    }
    # aiohttp does not support multipart/form-data in the same way as requests
    # We'll use aiohttp's FormData
    try:
        form = aiohttp.FormData()
        form.add_field('image', img_bytes, filename='image.png', content_type='image/png')
        form.add_field('seed', str(seed))
        form.add_field('cfg_scale', str(cfg_scale))
        form.add_field('motion_bucket_id', str(motion_bucket_id))

        async with session.post(url, headers=headers, data=form) as response:
            response.raise_for_status()
            resp_json = await response.json()
            generation_id = resp_json.get('id')
            if generation_id:
                return generation_id
            else:
                st.error("No generation ID returned from the API.")
                logger.error("No generation ID returned from the API.")
                return None
    except Exception as e:
        st.error(f"Error starting video generation: {str(e)}")
        logger.error(f"Error starting video generation: {str(e)}")
        return None

async def poll_for_video(session: aiohttp.ClientSession, api_key: str, generation_id: str, timeout: int = 600, interval: int = 10) -> bytes:
    """
    Asynchronously poll the API for the generated video until it's ready or timeout is reached.
    Returns the video content in bytes if successful.
    """
    url = f"https://api.stability.ai/v2beta/image-to-video/result/{generation_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "video/*"
    }
    attempts = timeout // interval
    for attempt in range(1, attempts + 1):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 202:
                    st.info(f"Video generation in progress... (Attempt {attempt}/{attempts})")
                    await asyncio.sleep(interval)
                elif response.status == 200:
                    st.success("Video generation completed.")
                    return await response.read()
                else:
                    response.raise_for_status()
        except Exception as e:
            st.error(f"Error polling for video: {str(e)}")
            logger.error(f"Error polling for video: {str(e)}")
            return None
    st.error("Video generation timed out. Please try again.")
    logger.error("Video generation timed out.")
    return None

def get_last_frame_image(video_path: str) -> Image.Image:
    """
    Extract the last frame of a video as an image.
    """
    if not os.path.exists(video_path):
        st.error(f"Video file not found: {video_path}")
        logger.error(f"Video file not found: {video_path}")
        return None
    try:
        with VideoFileClip(video_path) as video_clip:
            if video_clip.duration <= 0:
                st.error(f"Invalid video duration for {video_path}")
                logger.error(f"Invalid video duration for {video_path}")
                return None
            last_frame = video_clip.get_frame(video_clip.duration - 0.001)
            last_frame_image = Image.fromarray(np.uint8(last_frame)).convert('RGB')
            return last_frame_image
    except Exception as e:
        st.error(f"Error extracting last frame from {video_path}: {str(e)}")
        logger.error(f"Error extracting last frame from {video_path}: {str(e)}")
        return None

def concatenate_videos(video_clips: list, crossfade_duration: float = 0.0) -> (VideoFileClip, list):
    """
    Concatenate multiple video clips into a single video with optional crossfade transitions.
    Returns the final video clip and a list of valid clips.
    """
    valid_clips = []
    for clip_path in video_clips:
        st.write(f"Attempting to load clip: {clip_path}")
        if cached_validate_video_clip(clip_path):
            try:
                clip = VideoFileClip(clip_path)
                valid_clips.append(clip)
                st.write(f"Successfully loaded clip: {clip_path}, Duration: {clip.duration} seconds")
            except Exception as e:
                st.warning(f"Error loading clip {clip_path}: {str(e)}")
                logger.warning(f"Error loading clip {clip_path}: {str(e)}")
        else:
            st.warning(f"Validation failed for clip: {clip_path}")
            logger.warning(f"Validation failed for clip: {clip_path}")

    if not valid_clips:
        st.error("No valid video segments found. Unable to concatenate.")
        logger.error("No valid video segments found. Unable to concatenate.")
        return None, None

    try:
        st.write(f"Attempting to concatenate {len(valid_clips)} valid clips")
        if crossfade_duration > 0:
            # Apply crossfade transitions
            clips_with_transitions = []
            for i, clip in enumerate(valid_clips):
                if i != 0:
                    clip = clip.crossfadein(crossfade_duration)
                clips_with_transitions.append(clip)
            final_video = concatenate_videoclips(clips_with_transitions, method="compose")
        else:
            final_video = concatenate_videoclips(valid_clips, method="compose")
        st.write(f"Concatenation successful. Final video duration: {final_video.duration} seconds")
        return final_video, valid_clips
    except Exception as e:
        st.error(f"Error concatenating videos: {str(e)}")
        logger.error(f"Error concatenating videos: {str(e)}")
        for clip in valid_clips:
            clip.close()
        return None, None

async def generate_multiple_images_concurrently(session: aiohttp.ClientSession, api_key: str, prompt: str, num_images: int) -> list:
    """
    Generate multiple images from a text prompt concurrently.
    """
    tasks = []
    for i in range(num_images):
        tasks.append(generate_image_from_text(session, api_key, prompt))
    images = await asyncio.gather(*tasks)
    # Filter out any None images due to errors
    images = [img for img in images if img is not None]
    return images

def add_audio_to_video(video_path: str, audio_path: str, output_path: str) -> str:
    """
    Add background audio to a video.
    """
    try:
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path).subclip(0, video_clip.duration)
        video_with_audio = video_clip.set_audio(audio_clip)
        video_with_audio.write_videofile(output_path, codec="libx264", audio_codec="aac")
        video_clip.close()
        audio_clip.close()
        return output_path
    except Exception as e:
        st.error(f"Error adding audio to video: {str(e)}")
        logger.error(f"Error adding audio to video: {str(e)}")
        return None

def create_zip_file(images: list, videos: list, output_path: str = "generated_content.zip") -> str:
    """
    Create a ZIP file containing all generated images and videos.
    """
    if not images and not videos:
        st.error("No images or videos to create a zip file.")
        logger.error("No images or videos to create a zip file.")
        return None

    try:
        with zipfile.ZipFile(output_path, 'w') as zipf:
            for i, img in enumerate(images):
                img_path = f"image_{i+1}.png"
                img.save(img_path)
                zipf.write(img_path)
                os.remove(img_path)

            for video in videos:
                if os.path.exists(video):
                    zipf.write(video)
                else:
                    st.warning(f"Video file not found: {video}")
                    logger.warning(f"Video file not found: {video}")

        return output_path
    except Exception as e:
        st.error(f"Error creating zip file: {str(e)}")
        logger.error(f"Error creating zip file: {str(e)}")
        return None

def display_images_in_grid(images: list, columns: int = 3):
    """
    Display images in a grid layout with captions.
    """
    for i in range(0, len(images), columns):
        cols = st.columns(columns)
        for j in range(columns):
            if i + j < len(images):
                with cols[j]:
                    st.image(images[i + j], use_column_width=True, caption=f"Image {i + j + 1}")
                    st.markdown(f"<p style='text-align: center;'>Image {i + j + 1}</p>", unsafe_allow_html=True)

def display_video_with_download(video_path: str, index: int = None):
    """
    Display video and provide a download button.
    """
    if os.path.exists(video_path):
        st.video(video_path)
        if index is not None:
            st.write(f"Video Segment {index + 1}")
            with open(video_path, "rb") as f:
                st.download_button(
                    label=f"Download Video Segment {index + 1}",
                    data=f,
                    file_name=f"video_segment_{index + 1}.mp4",
                    mime="video/mp4"
                )
        else:
            st.write("Final Longform Video")
            with open(video_path, "rb") as f:
                st.download_button(
                    label="Download Longform Video",
                    data=f,
                    file_name="longform_video.mp4",
                    mime="video/mp4"
                )
    else:
        st.error(f"Video file not found: {video_path}")
        logger.error(f"Video file not found: {video_path}")

def main():
    """
    Main function to run the Streamlit app.
    """
    st.set_page_config(page_title="Stable Diffusion Longform Video Creator", layout="wide")

    # Sidebar Information
    st.sidebar.title("About")
    st.sidebar.info(
        "This app uses Stability AI's API to create longform videos from text prompts or images. "
        "It offers three modes: Text-to-Video, Image-to-Video, and Snapshot Mode."
    )

    st.sidebar.title("How to Use")
    st.sidebar.markdown(
        """
        1. Enter your Stability AI API Key
        2. Navigate to the Generator tab
        3. Choose a mode: Text-to-Video, Image-to-Video, or Snapshot Mode
        4. Enter required inputs and adjust settings
        5. Click 'Generate Content'
        6. Wait for the process to complete
        7. View results in the Images and Videos tabs
        """
    )

    st.sidebar.title("API Key")
    api_key = st.sidebar.text_input("Enter your Stability AI API Key", type="password")

    # Main Content
    st.title("Stable Diffusion Longform Video Creator")

    tab1, tab2, tab3 = st.tabs(["Generator", "Images", "Videos"])

    with tab1:
        mode = st.radio("Select Mode", ("Text-to-Video", "Image-to-Video", "Snapshot Mode"))

        if mode in ["Text-to-Video", "Snapshot Mode"]:
            prompt = st.text_area("Enter a text prompt for video generation", height=100)
        elif mode == "Image-to-Video":
            image_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])

        with st.expander("Settings", expanded=False):
            if mode == "Snapshot Mode":
                num_images = st.slider("Number of images to generate", 10, 300, 60)
                fps = st.slider("Frames per second", 1, 60, 24)
                use_video = st.checkbox("Generate video from images", value=False)
                if use_video:
                    num_segments = st.slider("Number of video segments", 1, 10, 5)
                    cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8, 0.1)
                    motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
                    seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)
                    crossfade_duration = st.slider("Crossfade Duration (seconds)", 0.0, 2.0, 0.0, 0.1)
                    resolution = st.selectbox("Select Video Resolution", ["720p", "1080p", "4K"], index=0)
            else:
                cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8, 0.1)
                motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
                seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)
                num_segments = st.slider("Number of video segments to generate", 1, 60, 5)
                crossfade_duration = st.slider("Crossfade Duration (seconds)", 0.0, 2.0, 0.0, 0.1)
                resolution = st.selectbox("Select Video Resolution", ["720p", "1080p", "4K"], index=1)

            # New Feature: Audio Upload
            st.markdown("---")
            st.subheader("Audio Settings")
            audio_file = st.file_uploader("Upload background music (MP3 or WAV)", type=["mp3", "wav"], key="audio_upload")
            if audio_file:
                st.session_state.audio_file = audio_file

        if st.button("Generate Content"):
            if not api_key:
                st.error("Please enter the API key in the sidebar.")
                return

            if mode in ["Text-to-Video", "Snapshot Mode"] and not prompt:
                st.error("Please enter a text prompt.")
                return

            if mode == "Image-to-Video" and not image_file:
                st.error("Please upload an image.")
                return

            # Clear previous results
            st.session_state.generated_images = []
            st.session_state.generated_videos = []
            st.session_state.final_video = None

            # Set video resolution
            resolution_map = {
                "720p": (1280, 720),
                "1080p": (1920, 1080),
                "4K": (3840, 2160)
            }
            selected_resolution = resolution_map.get(resolution, (1920, 1080))

            try:
                with TemporaryDirectory() as temp_dir:
                    # Initialize aiohttp session
                    async def process():
                        async with aiohttp.ClientSession() as session:
                            if mode == "Snapshot Mode":
                                # Generate multiple images concurrently
                                with st.spinner("Generating images for Snapshot Mode..."):
                                    images = await generate_multiple_images_concurrently(session, api_key, prompt, num_images)

                                if images:
                                    st.success(f"Successfully generated {len(images)} images.")
                                    st.session_state.generated_images = images

                                    if use_video:
                                        st.write("Generating video segments from images...")
                                        video_clips = []
                                        tasks = []
                                        current_image = images[0]

                                        # Generate video segments sequentially to update current_image
                                        for i in range(num_segments):
                                            st.write(f"Generating video segment {i+1}/{num_segments}...")
                                            generation_id = await start_video_generation(session, api_key, current_image, cfg_scale, motion_bucket_id, seed)

                                            if generation_id:
                                                video_content = await poll_for_video(session, api_key, generation_id)
                                                if video_content:
                                                    video_path = os.path.join(temp_dir, f"video_segment_{i+1}.mp4")
                                                    with open(video_path, "wb") as f:
                                                        f.write(video_content)
                                                    st.write(f"Saved video segment {i+1}")
                                                    video_clips.append(video_path)
                                                    st.session_state.generated_videos.append(video_path)

                                                    last_frame_image = get_last_frame_image(video_path)
                                                    if last_frame_image:
                                                        current_image = last_frame_image
                                                        st.session_state.generated_images.append(current_image)
                                                    else:
                                                        st.warning(f"Could not extract last frame from segment {i+1}. Using previous image.")
                                                else:
                                                    st.error(f"Failed to retrieve video content for segment {i+1}.")
                                            else:
                                                st.error(f"Failed to start video generation for segment {i+1}.")

                                        if video_clips:
                                            st.write("Concatenating video segments into one longform video...")
                                            final_video, valid_clips = concatenate_videos(video_clips, crossfade_duration=crossfade_duration)

                                            if final_video:
                                                # Adjust video resolution
                                                final_video = final_video.resize(newsize=selected_resolution)

                                                # Add audio if uploaded
                                                if st.session_state.audio_file:
                                                    audio_path = os.path.join(temp_dir, "background_audio.mp3")
                                                    with open(audio_path, "wb") as f:
                                                        f.write(st.session_state.audio_file.getbuffer())
                                                    final_video_path = os.path.join(temp_dir, "snapshot_longform_video_with_audio.mp4")
                                                    final_video = add_audio_to_video(final_video_path, audio_path, final_video_path)
                                                else:
                                                    final_video_path = os.path.join(temp_dir, "snapshot_longform_video.mp4")
                                                    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac")

                                                st.session_state.final_video = final_video_path
                                                st.success(f"Snapshot Mode video created: {final_video_path}")
                                            else:
                                                st.error("Failed to create the final video.")
                                        else:
                                            st.error("No video segments were successfully generated.")
                                else:
                                    st.error("Failed to generate images for Snapshot Mode.")

                            elif mode == "Text-to-Video":
                                st.write("Generating image from text prompt...")
                                image = await generate_image_from_text(session, api_key, prompt)
                                if image is None:
                                    return
                                image = resize_image(image)
                                image = image.resize(selected_resolution)
                                st.session_state.generated_images.append(image)

                                video_clips = []
                                current_image = image

                                # Generate video segments sequentially to update current_image
                                for i in range(num_segments):
                                    st.write(f"Generating video segment {i+1}/{num_segments}...")
                                    generation_id = await start_video_generation(session, api_key, current_image, cfg_scale, motion_bucket_id, seed)

                                    if generation_id:
                                        video_content = await poll_for_video(session, api_key, generation_id)

                                        if video_content:
                                            video_path = os.path.join(temp_dir, f"video_segment_{i+1}.mp4")
                                            with open(video_path, "wb") as f:
                                                f.write(video_content)
                                            st.write(f"Saved video segment {i+1}")
                                            video_clips.append(video_path)
                                            st.session_state.generated_videos.append(video_path)

                                            last_frame_image = get_last_frame_image(video_path)
                                            if last_frame_image:
                                                current_image = last_frame_image
                                                current_image = current_image.resize(selected_resolution)
                                                st.session_state.generated_images.append(current_image)
                                            else:
                                                st.warning(f"Could not extract last frame from segment {i+1}. Using previous image.")
                                        else:
                                            st.error(f"Failed to retrieve video content for segment {i+1}.")
                                    else:
                                        st.error(f"Failed to start video generation for segment {i+1}.")

                                if video_clips:
                                    st.write("Concatenating video segments into one longform video...")
                                    final_video, valid_clips = concatenate_videos(video_clips, crossfade_duration=crossfade_duration)

                                    if final_video:
                                        # Adjust video resolution
                                        final_video = final_video.resize(newsize=selected_resolution)

                                        # Add audio if uploaded
                                        if st.session_state.audio_file:
                                            audio_path = os.path.join(temp_dir, "background_audio.mp3")
                                            with open(audio_path, "wb") as f:
                                                f.write(st.session_state.audio_file.getbuffer())
                                            final_video_path = os.path.join(temp_dir, "longform_video_with_audio.mp4")
                                            final_video = add_audio_to_video(final_video_path, audio_path, final_video_path)
                                        else:
                                            final_video_path = os.path.join(temp_dir, "longform_video.mp4")
                                            final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac")

                                        st.session_state.final_video = final_video_path
                                        st.success(f"Longform video created: {final_video_path}")
                                    else:
                                        st.error("Failed to create the final video.")
                            elif mode == "Image-to-Video":
                                image = Image.open(image_file)
                                image = resize_image(image)
                                image = image.resize(selected_resolution)
                                st.session_state.generated_images.append(image)

                                st.write("Generating video from uploaded image...")
                                generation_id = await start_video_generation(session, api_key, image, cfg_scale, motion_bucket_id, seed)

                                if generation_id:
                                    video_content = await poll_for_video(session, api_key, generation_id)
                                    if video_content:
                                        video_path = os.path.join(temp_dir, "image_to_video.mp4")
                                        with open(video_path, "wb") as f:
                                            f.write(video_content)
                                        st.write(f"Saved video to {video_path}")
                                        st.session_state.generated_videos.append(video_path)

                                        # Adjust video resolution
                                        with VideoFileClip(video_path) as clip:
                                            clip_resized = clip.resize(newsize=selected_resolution)
                                            clip_resized.write_videofile(video_path, codec="libx264", audio_codec="aac")

                                        # Add audio if uploaded
                                        if st.session_state.audio_file:
                                            audio_path = os.path.join(temp_dir, "background_audio.mp3")
                                            with open(audio_path, "wb") as f:
                                                f.write(st.session_state.audio_file.getbuffer())
                                            final_video_path = os.path.join(temp_dir, "image_to_video_with_audio.mp4")
                                            final_video = add_audio_to_video(video_path, audio_path, final_video_path)
                                            st.session_state.final_video = final_video_path
                                        else:
                                            st.session_state.final_video = video_path

                                        st.success(f"Image-to-Video created: {video_path}")
                                    else:
                                        st.error("Failed to retrieve video content.")
                                else:
                                    st.error("Failed to start video generation.")

                    asyncio.create_task(process())

            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
                logger.error(f"An unexpected error occurred: {str(e)}")
                st.write("Traceback:", traceback.format_exc())

    with tab2:
        st.subheader("Generated Images")
        if st.session_state.generated_images:
            display_images_in_grid(st.session_state.generated_images)
        else:
            st.write("No images generated yet. Use the Generator tab to create images.")

    with tab3:
        st.subheader("Generated Videos")
        if st.session_state.generated_videos:
            for i, video_path in enumerate(st.session_state.generated_videos):
                display_video_with_download(video_path, index=i)
            
            if st.session_state.final_video and os.path.exists(st.session_state.final_video):
                st.subheader("Final Longform Video")
                display_video_with_download(st.session_state.final_video)
        else:
            st.write("No videos generated yet. Use the Generator tab to create videos.")

    # Add download all button
    if st.session_state.generated_images or st.session_state.generated_videos:
        with TemporaryDirectory() as temp_dir:
            zip_path = create_zip_file(st.session_state.generated_images, st.session_state.generated_videos)
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="Download All Content (ZIP)",
                        data=f,
                        file_name="generated_content.zip",
                        mime="application/zip"
                    )
                os.remove(zip_path)
            else:
                st.error("Failed to create ZIP file.")

if __name__ == "__main__":
    main()
