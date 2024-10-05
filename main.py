import streamlit as st
import replicate
import moviepy.editor as mpy
import os
import cv2

# Set up Replicate's Stable Diffusion model
REPLICATE_API_TOKEN = "your_replicate_api_token"

# Function to generate images with Stable Diffusion
def generate_images(prompt, style, num_images, dimensions):
    model = replicate.models.get("stability-ai/stable-diffusion")
    images = []
    
    for i in range(num_images):
        # Call Stable Diffusion API to generate images
        output = model.predict(
            prompt=f"{prompt}, {style}",
            width=dimensions[0],
            height=dimensions[1]
        )
        images.append(output)
    return images

# Function to create a video from images
def create_video(images, speed, output_file):
    frame_rate = 1 / speed  # Controls how fast images change
    
    # Create video clip from images
    clips = [mpy.ImageClip(img).set_duration(frame_rate) for img in images]
    video = mpy.concatenate_videoclips(clips, method="compose")
    
    # Save video
    video.write_videofile(output_file, fps=24)

# Streamlit app interface
st.title("Stable Diffusion Video Generator")

# User inputs
prompt = st.text_input("Enter a prompt for image generation:")
style = st.selectbox("Choose a style:", ["comic book", "3d render", "cyberpunk", "realistic", "oil painting"])
num_images = st.slider("Number of images:", min_value=2, max_value=20, value=5)
dimensions = st.slider("Dimensions (width x height):", min_value=128, max_value=1024, value=(512, 512))
speed = st.slider("How fast should images change in the video (seconds):", min_value=0.5, max_value=5.0, value=1.0)

if st.button("Generate Video"):
    # Generate images
    images = generate_images(prompt, style, num_images, dimensions)
    
    # Create video
    video_file = "output_video.mp4"
    create_video(images, speed, video_file)
    
    # Display video in the app
    st.video(video_file)
    
    # Provide download link
    with open(video_file, "rb") as file:
        st.download_button("Download Video", file, file_name="generated_video.mp4")

