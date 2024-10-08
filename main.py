import streamlit as st
import requests
import base64
from PIL import Image
import io
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip, vfx
import os
import sys
import numpy as np
import time
import traceback
import zipfile

# Redirect stderr to stdout to avoid issues with logging in some environments
sys.stderr = sys.stdout

# Initialize session state for persistent storage
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []
if 'generated_videos' not in st.session_state:
    st.session_state.generated_videos = []
if 'final_video' not in st.session_state:
    st.session_state.final_video = None

def resize_image(image):
    width, height = image.size
    if (width, height) in [(1024, 576), (576, 1024), (768, 768)]:
        return image
    else:
        st.warning("Resizing image to 768x768 (default)")
        return image.resize((768, 768))

def generate_image_from_text(api_key, prompt):
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
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        image_data = response.json()['artifacts'][0]['base64']
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        return image
    except requests.exceptions.RequestException as e:
        st.error(f"Error generating image: {str(e)}")
        return None

def start_video_generation(api_key, image, cfg_scale=1.8, motion_bucket_id=127, seed=0):
    url = "https://api.stability.ai/v2beta/image-to-video"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    files = {
        "image": ("image.png", img_byte_arr, "image/png")
    }
    data = {
        "seed": str(seed),
        "cfg_scale": str(cfg_scale),
        "motion_bucket_id": str(motion_bucket_id)
    }
    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json().get('id')
    except requests.exceptions.RequestException as e:
        st.error(f"Error starting video generation: {str(e)}")
        return None

def poll_for_video(api_key, generation_id):
    url = f"https://api.stability.ai/v2beta/image-to-video/result/{generation_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "video/*"
    }
    max_attempts = 60
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 202:
                st.write(f"Video generation in progress... Polling attempt {attempt + 1}/{max_attempts}")
                time.sleep(10)
            elif response.status_code == 200:
                return response.content
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            st.error(f"Error polling for video: {str(e)}")
            return None
    st.error("Video generation timed out. Please try again.")
    return None

def validate_video_clip(video_path):
    if not os.path.exists(video_path):
        st.error(f"Video file not found: {video_path}")
        return False
    try:
        clip = VideoFileClip(video_path)
        if clip is None:
            st.error(f"Failed to load video clip: {video_path}")
            return False
        duration = clip.duration
        clip.close()
        st.write(f"Validated video clip: {video_path}, Duration: {duration} seconds")
        return duration > 0
    except Exception as e:
        st.error(f"Invalid video segment: {video_path}, Error: {str(e)}")
        return False

def get_last_frame_image(video_path):
    if not os.path.exists(video_path):
        st.error(f"Video file not found: {video_path}")
        return None
    try:
        video_clip = VideoFileClip(video_path)
        if video_clip is None:
            st.error(f"Failed to load video clip: {video_path}")
            return None
        if video_clip.duration <= 0:
            st.error(f"Invalid video duration for {video_path}")
            video_clip.close()
            return None
        last_frame = video_clip.get_frame(video_clip.duration - 0.001)
        last_frame_image = Image.fromarray(np.uint8(last_frame)).convert('RGB')
        video_clip.close()
        return last_frame_image
    except Exception as e:
        st.error(f"Error extracting last frame from {video_path}: {str(e)}")
        return None

def concatenate_videos(video_clips, crossfade_duration=0):
    valid_clips = []
    for clip_path in video_clips:
        st.write(f"Attempting to load clip: {clip_path}")
        if validate_video_clip(clip_path):
            try:
                clip = VideoFileClip(clip_path)
                if clip is not None and clip.duration > 0:
                    valid_clips.append(clip)
                    st.write(f"Successfully loaded clip: {clip_path}, Duration: {clip.duration} seconds")
                else:
                    st.warning(f"Skipping invalid clip: {clip_path}")
            except Exception as e:
                st.warning(f"Error loading clip {clip_path}: {str(e)}")
        else:
            st.warning(f"Validation failed for clip: {clip_path}")

    if not valid_clips:
        st.error("No valid video segments found. Unable to concatenate.")
        return None, None

    try:
        st.write(f"Attempting to concatenate {len(valid_clips)} valid clips")
        
        # Trim the last frame from all clips except the last one
        trimmed_clips = []
        for i, clip in enumerate(valid_clips):
            if i < len(valid_clips) - 1:
                # Subtract a small duration (e.g., 1/30 second) to remove approximately one frame
                trimmed_clip = clip.subclip(0, clip.duration - 1/30)
                trimmed_clips.append(trimmed_clip)
            else:
                trimmed_clips.append(clip)
        
        if crossfade_duration > 0:
            st.write(f"Applying crossfade of {crossfade_duration} seconds")
            # Apply crossfade transition
            final_clips = []
            for i, clip in enumerate(trimmed_clips):
                if i == 0:
                    final_clips.append(clip)
                else:
                    # Create a crossfade transition
                    fade_out = trimmed_clips[i-1].fx(vfx.fadeout, duration=crossfade_duration)
                    fade_in = clip.fx(vfx.fadein, duration=crossfade_duration)
                    transition = CompositeVideoClip([fade_out, fade_in])
                    transition = transition.set_duration(crossfade_duration)
                    
                    # Add the transition and the full clip
                    final_clips.append(transition)
                    final_clips.append(clip)
            
            final_video = concatenate_videoclips(final_clips)
        else:
            final_video = concatenate_videoclips(trimmed_clips)
        
        st.write(f"Concatenation successful. Final video duration: {final_video.duration} seconds")
        return final_video, valid_clips
    except Exception as e:
        st.error(f"Error concatenating videos: {str(e)}")
        for clip in valid_clips:
            clip.close()
        return None, None

def generate_multiple_images(api_key, prompt, num_images):
    images = []
    for i in range(num_images):
        st.write(f"Generating image {i+1}/{num_images}...")
        image = generate_image_from_text(api_key, prompt)
        if image:
            images.append(image)
        else:
            st.error(f"Failed to generate image {i+1}")
    return images

def create_video_from_images(images, fps, output_path):
    clips = [ImageClip(np.array(img)).set_duration(1/fps) for img in images]
    video = concatenate_videoclips(clips, method="compose")
    video.write_videofile(output_path, fps=fps, codec="libx264")
    return output_path

def display_images_in_grid(images, columns=3):
    """Display images in a grid layout with captions."""
    for i in range(0, len(images), columns):
        cols = st.columns(columns)
        for j in range(columns):
            if i + j < len(images):
                with cols[j]:
                    st.image(images[i + j], use_column_width=True, caption=f"Image {i + j + 1}")
                    st.markdown(f"<p style='text-align: center;'>Image {i + j + 1}</p>", unsafe_allow_html=True)

def create_zip_file(images, videos, output_path="generated_content.zip"):
    if not images and not videos:
        st.error("No images or videos to create a zip file.")
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
        
        return output_path
    except Exception as e:
        st.error(f"Error creating zip file: {str(e)}")
        return None


def snapshot_mode_v2(api_key, prompt, num_segments, cfg_scale, motion_bucket_id, seed):
    st.write("Generating initial image for Snapshot Mode v2...")
    initial_image = generate_image_from_text(api_key, prompt)
    if initial_image is None:
        return None, None

    st.session_state.generated_images.append(initial_image)
    
    video_clips = []
    current_image = initial_image

    for i in range(num_segments):
        st.write(f"Generating video segment {i+1}/{num_segments}...")
        generation_id = start_video_generation(api_key, current_image, cfg_scale, motion_bucket_id, seed)

        if generation_id:
            video_content = poll_for_video(api_key, generation_id)

            if video_content:
                video_path = f"video_segment_{i+1}.mp4"
                with open(video_path, "wb") as f:
                    f.write(video_content)
                st.write(f"Saved video segment to {video_path}")
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

    return video_clips, initial_image

def main():
    st.set_page_config(page_title="Stable Diffusion Longform Video Creator", layout="wide")

    # Sidebar
    st.sidebar.title("About")
    st.sidebar.info(
        "This app uses Stability AI's API to create longform videos from text prompts or images. "
        "It offers three modes: Text-to-Video, Image-to-Video, and Snapshot Mode."
    )
    
    st.sidebar.title("How to Use")
    st.sidebar.markdown(
        """
        1. Enter your Stability AI API Key
        2. Go to the Generator tab
        3. Choose a mode: Text-to-Video, Image-to-Video, or Snapshot Mode
        4. Enter required inputs and adjust settings
        5. Click 'Generate Content'
        6. Wait for the process to complete
        7. View results in the Images and Videos tabs
        """
    )
    
    st.sidebar.title("API Key")
    api_key = st.sidebar.text_input("Enter your Stability AI API Key", type="password")

    # Main content
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
                    cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8)
                    motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
                    seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)
                    crossfade_duration = st.slider("Crossfade Duration (seconds)", 0.0, 2.0, 0.0, 0.01)
            else:
                cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8)
                motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
                seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)
                num_segments = st.slider("Number of video segments to generate", 1, 60, 5)
                crossfade_duration = st.slider("Crossfade Duration (seconds)", 0.0, 2.0, 0.0, 0.01)

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

            try:
                if mode == "Snapshot Mode":
                    st.write("Generating images for Snapshot Mode...")
                    images = generate_multiple_images(api_key, prompt, num_images)
                    st.session_state.generated_images = images
                    
                    if images:
                        if use_video:
                            st.write("Creating video from generated images...")
                            video_clips = []
                            for i, image in enumerate(images):
                                st.write(f"Generating video segment {i+1}/{num_segments}...")
                                generation_id = start_video_generation(api_key, image, cfg_scale, motion_bucket_id, seed)
                                if generation_id:
                                    video_content = poll_for_video(api_key, generation_id)
                                    if video_content:
                                        video_path = f"video_segment_{i+1}.mp4"
                                        with open(video_path, "wb") as f:
                                            f.write(video_content)
                                        st.write(f"Saved video segment to {video_path}")
                                        video_clips.append(video_path)
                                        st.session_state.generated_videos.append(video_path)
                                    else:
                                        st.error(f"Failed to retrieve video content for segment {i+1}.")
                                else:
                                    st.error(f"Failed to start video generation for segment {i+1}.")
                                
                                if len(video_clips) >= num_segments:
                                    break

                            if video_clips:
                                st.write("Concatenating video segments into one longform video...")
                                final_video, valid_clips = concatenate_videos(video_clips, crossfade_duration=crossfade_duration)
                                if final_video:
                                    try:
                                        final_video_path = "snapshot_longform_video.mp4"
                                        final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac")
                                        st.session_state.final_video = final_video_path
                                        st.success(f"Snapshot Mode video created: {final_video_path}")
                                    except Exception as e:
                                        st.error(f"Error writing final video: {str(e)}")
                                        st.write("Traceback:", traceback.format_exc())
                                    finally:
                                        if final_video:
                                            final_video.close()
                                        if valid_clips:
                                            for clip in valid_clips:
                                                clip.close()
                                else:
                                    st.error("Failed to create the final video.")
                                
                                # Clean up individual video segments
                                for video_file in video_clips:
                                    if os.path.exists(video_file):
                                        os.remove(video_file)
                                        st.write(f"Removed temporary file: {video_file}")
                                    else:
                                        st.warning(f"Could not find file to remove: {video_file}")
                            else:
                                st.error("No video segments were successfully generated.")
                        else:
                            st.success(f"Generated {len(images)} images for Snapshot Mode.")
                    else:
                        st.error("Failed to generate images for Snapshot Mode.")

                elif mode == "Text-to-Video":
                    st.write("Generating image from text prompt...")
                    image = generate_image_from_text(api_key, prompt)
                    if image is None:
                        return
                    image = resize_image(image)
                    st.session_state.generated_images.append(image)
                    
                    video_clips = []
                    current_image = image

                    for i in range(num_segments):
                        st.write(f"Generating video segment {i+1}/{num_segments}...")
                        generation_id = start_video_generation(api_key, current_image, cfg_scale, motion_bucket_id, seed)

                        if generation_id:
                            video_content = poll_for_video(api_key, generation_id)

                            if video_content:
                                video_path = f"video_segment_{i+1}.mp4"
                                with open(video_path, "wb") as f:
                                    f.write(video_content)
                                st.write(f"Saved video segment to {video_path}")
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
                            try:
                                final_video_path = "longform_video.mp4"
                                final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac")
                                st.session_state.final_video = final_video_path
                                st.success(f"Longform video created: {final_video_path}")
                            except Exception as e:
                                st.error(f"Error writing final video: {str(e)}")
                                st.write("Traceback:", traceback.format_exc())
                            finally:
                                if final_video:
                                    final_video.close()
                                if valid_clips:
                                    for clip in valid_clips:
                                        clip.close()
                        else:
                            st.error("Failed to create the final video.")
                        
                        # Clean up individual video segments
                        for video_file in video_clips:
                            if os.path.exists(video_file):
                                os.remove(video_file)
                                st.write(f"Removed temporary file: {video_file}")
                            else:
                                st.warning(f"Could not find file to remove: {video_file}")
                    else:
                        st.error("No video segments were successfully generated.")

                elif mode == "Image-to-Video":
                    image = Image.open(image_file)
                    image = resize_image(image)
                    st.session_state.generated_images.append(image)

                    st.write("Generating video from uploaded image...")
                    generation_id = start_video_generation(api_key, image, cfg_scale, motion_bucket_id, seed)

                    if generation_id:
                        video_content = poll_for_video(api_key, generation_id)

                        if video_content:
                            video_path = "image_to_video.mp4"
                            with open(video_path, "wb") as f:
                                f.write(video_content)
                            st.write(f"Saved video to {video_path}")
                            st.session_state.generated_videos.append(video_path)
                            st.session_state.final_video = video_path
                            st.success(f"Image-to-Video created: {video_path}")
                        else:
                            st.error("Failed to retrieve video content.")
                    else:
                        st.error("Failed to start video generation.")

            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
                st.write("Error details:", str(e))
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
                if os.path.exists(video_path):
                    st.video(video_path)
                    st.write(f"Video Segment {i+1}")
                    with open(video_path, "rb") as f:
                        st.download_button(f"Download Video Segment {i+1}", f, file_name=f"video_segment_{i+1}.mp4")
                else:
                    st.error(f"Video file not found: {video_path}")
            
            if st.session_state.final_video and os.path.exists(st.session_state.final_video):
                st.subheader("Final Longform Video")
                st.video(st.session_state.final_video)
                with open(st.session_state.final_video, "rb") as f:
                    st.download_button("Download Longform Video", f, file_name="longform_video.mp4")
        else:
            st.write("No videos generated yet. Use the Generator tab to create videos.")

    # Add download all button
    if st.session_state.generated_images or st.session_state.generated_videos:
        zip_path = create_zip_file(st.session_state.generated_images, st.session_state.generated_videos)
        with open(zip_path, "rb") as f:
            st.download_button("Download All Content (ZIP)", f, file_name="generated_content.zip")
        os.remove(zip_path)

if __name__ == "__main__":
    main()
