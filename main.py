import streamlit as st
from diffusers import StableDiffusionPipeline
import torch
import moviepy.editor as mpy
import os
from PIL import Image
import numpy as np
import nest_asyncio
import aiohttp

nest_asyncio.apply()

# Function to generate images using Stable Diffusion
def generate_images(prompt, style, num_images, dimensions):
    # Load the Stable Diffusion pipeline
    pipe = StableDiffusionPipeline.from_pretrained("CompVis/stable-diffusion-v1-4", torch_dtype=torch.float16)
    pipe.to("cuda")  # Use GPU if available
    
    images = []
    
    for i in range(num_images):
        # Generate an image
        image = pipe(f"{prompt}, {style}", height=dimensions[1], width=dimensions[0]).images[0]
        
        # Save the image to a local file
        image_path = f"generated_image_{i}.png"
        image.save(image_path)
        images.append(image_path)
    
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

if st.button("Generate Video") and prompt:
    # Generate images
    saved_images = generate_images(prompt, style, num_images, dimensions)
    
    # Create video
    video_file = "output_video.mp4"
    create_video(saved_images, speed, video_file)
    
    # Display video in the app
    st.video(video_file)
    
    # Provide download link
    with open(video_file, "rb") as file:
        st.download_button("Download Video", file, file_name="generated_video.mp4")
else:
    if not prompt:
        st.warning("Please enter a prompt for image generation.")
