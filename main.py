import streamlit as st
import requests
import base64
from PIL import Image
import io
from moviepy.editor import ImageClip, concatenate_videoclips, vfx
import os
import numpy as np
import time

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

def get_last_frame_image(video_path):
    if not os.path.exists(video_path):
        st.error(f"Video file not found: {video_path}")
        return None
    try:
        video_clip = ImageClip(video_path)
        if video_clip is None:
            st.error(f"Failed to load video clip: {video_path}")
            return None
        last_frame = video_clip.get_frame(video_clip.duration - 0.001)
        last_frame_image = Image.fromarray(np.uint8(last_frame)).convert('RGB')
        video_clip.close()
        return last_frame_image
    except Exception as e:
        st.error(f"Error extracting last frame from {video_path}: {str(e)}")
        return None

def concatenate_videos(images, fps, output_path="concatenated_snapshot_video.mp4"):
    try:
        clips = [ImageClip(np.array(img)).set_duration(1 / fps) for img in images]
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(output_path, fps=fps, codec="libx264")
        return output_path
    except Exception as e:
        st.error(f"Error concatenating videos: {str(e)}")
        return None

def snapshot_mode_v2(api_key, prompt, num_segments, cfg_scale, motion_bucket_id, seed, fps, generate_video):
    st.write("Generating initial image for Snapshot Mode v2...")

    # Step 1: Generate the first image from the prompt.
    initial_image = generate_image_from_text(api_key, prompt)
    if initial_image is None:
        return None, None

    st.session_state.generated_images.append(initial_image)
    current_image = initial_image
    current_seed = seed  # Start with the provided seed

    for i in range(num_segments):
        st.write(f"Generating frame {i+1}/{num_segments}...")

        # Step 2: Use current image as the guide for the next variant
        generation_id = start_video_generation(api_key, current_image, cfg_scale, motion_bucket_id, current_seed)

        if generation_id:
            video_content = poll_for_video(api_key, generation_id)
            if video_content:
                video_path = f"video_segment_{i+1}.mp4"
                with open(video_path, "wb") as f:
                    f.write(video_content)
                st.write(f"Saved video segment to {video_path}")

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
        
        # Slightly adjust seed for the next image
        current_seed += 1

    # Step 3: If 'Generate video' is checked, concatenate images into a video
    if generate_video:
        st.write("Concatenating images into final video...")
        final_video_path = concatenate_videos(st.session_state.generated_images, fps)
        if final_video_path:
            st.session_state.final_video = final_video_path
            st.success(f"Final video created: {final_video_path}")
        else:
            st.error("Failed to create final video.")

    return st.session_state.generated_images, st.session_state.final_video

# Main app function
def main():
    st.set_page_config(page_title="Stable Diffusion Snapshot Mode", layout="wide")

    # Sidebar for API key input
    st.sidebar.title("API Key")
    api_key = st.sidebar.text_input("Enter your Stability AI API Key", type="password")

    # Main content
    st.title("Snapshot Mode v2")

    prompt = st.text_area("Enter a text prompt for image generation", height=100)
    num_segments = st.slider("Number of segments", 1, 60, 10)
    fps = st.slider("Frames per second", 1, 60, 24)
    generate_video = st.checkbox("Generate video from images", value=True)
    cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8)
    motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
    seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)

    if st.button("Generate Content"):
        if not api_key:
            st.error("Please enter the API key in the sidebar.")
            return

        if not prompt:
            st.error("Please enter a text prompt.")
            return

        # Clear previous results
        st.session_state.generated_images = []
        st.session_state.generated_videos = []
        st.session_state.final_video = None

        try:
            images, final_video = snapshot_mode_v2(api_key, prompt, num_segments, cfg_scale, motion_bucket_id, seed, fps, generate_video)

            if images:
                st.success(f"Generated {len(images)} images.")
            if final_video:
                st.video(final_video)
                with open(final_video, "rb") as f:
                    st.download_button("Download Final Video", f, file_name="snapshot_video.mp4")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
