import streamlit as st
from moviepy.editor import concatenate_videoclips, VideoFileClip
from diffusers import StableDiffusionImg2ImgPipeline
import torch
import os
import time

# Function to generate a video from an image using Stable Diffusion
def generate_video_from_image(pipe, prompt, duration=5):
    # Generate images from the prompt
    video_frames = []
    
    for i in range(duration * 30):  # Assume 30 frames per second
        image = pipe(prompt).images[0]
        frame_path = f"frame_{i}.png"
        image.save(frame_path)
        video_frames.append(frame_path)
    
    # Create a video from the frames using MoviePy
    video_path = f"generated_video_{duration}.mp4"
    video_clips = [VideoFileClip(frame).set_duration(1/30) for frame in video_frames]
    final_clip = concatenate_videoclips(video_clips)
    final_clip.write_videofile(video_path)
    
    return video_path

# Function to concatenate videos
def concatenate_videos(video_paths):
    clips = [VideoFileClip(path) for path in video_paths]
    final_video = concatenate_videoclips(clips)
    return final_video

# Streamlit App UI
def main():
    st.title("Longform AI Video Creator")
    
    # API Key Input
    api_key = st.text_input("Enter your Stability AI API Key", type="password")
    
    if not api_key:
        st.warning("Please enter your API key.")
        st.stop()

    # Slider for total video duration
    total_duration = st.slider("Select total video duration (5 seconds increments)", 5, 300, 5, step=5)
    
    # Prompt for Stable Diffusion
    prompt = st.text_input("Enter a prompt for the video")
    
    # Progress bar
    progress_bar = st.progress(0)
    
    if st.button("Generate Video"):
        st.write("Starting video generation... this might take a while.")
        
        # Initialize Stable Diffusion pipeline
        pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
            "CompVis/stable-diffusion-v1-4",
            torch_dtype=torch.float16,
            use_auth_token=api_key
        ).to("cuda")
        
        video_clips = []
        initial_prompt = prompt
        
        for i in range(0, total_duration, 5):
            # Generate a 5-second video
            st.write(f"Generating 5-second video {i//5 + 1} of {total_duration//5}...")
            video_path = generate_video_from_image(pipe, initial_prompt, 5)
            video_clips.append(video_path)
            
            # Update progress bar
            progress_bar.progress((i + 5) / total_duration)
        
        # Concatenate all videos
        st.write("Combining videos...")
        final_video = concatenate_videos(video_clips)
        final_video_path = "final_video.mp4"
        final_video.write_videofile(final_video_path)

        # Provide download link
        with open(final_video_path, "rb") as f:
            st.download_button("Download Video", f, file_name="longform_video.mp4")
        
        st.success("Video generation complete!")
        progress_bar.progress(1)

if __name__ == "__main__":
    main()

