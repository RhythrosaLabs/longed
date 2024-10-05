import streamlit as st
import replicate
import moviepy.editor as mpy
import os
import requests

# Function to generate images with Stable Diffusion
def generate_images(api_key, prompt, style, num_images, dimensions):
    model = replicate.Client(api_token=api_key).models.get("stability-ai/stable-diffusion")
    images = []
    
    for i in range(num_images):
        # Call Stable Diffusion API to generate images
        output = model.predict(
            prompt=f"{prompt}, {style}",
            width=dimensions[0],
            height=dimensions[1]
        )
        images.append(output[0])  # Add generated image URL to the list
    return images

# Function to download and save the images locally
def save_images(image_urls, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    saved_images = []
    
    for i, url in enumerate(image_urls):
        image_path = f"{output_dir}/image_{i}.png"
        # Download the image
        img_data = requests.get(url).content
        with open(image_path, 'wb') as handler:
            handler.write(img_data)
        saved_images.append(image_path)
    
    return saved_images

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

# API key input
api_key = st.text_input("Enter your Replicate API key:", type="password")

# User inputs
prompt = st.text_input("Enter a prompt for image generation:")
style = st.selectbox("Choose a style:", ["comic book", "3d render", "cyberpunk", "realistic", "oil painting"])
num_images = st.slider("Number of images:", min_value=2, max_value=20, value=5)
dimensions = st.slider("Dimensions (width x height):", min_value=128, max_value=1024, value=(512, 512))
speed = st.slider("How fast should images change in the video (seconds):", min_value=0.5, max_value=5.0, value=1.0)

# Check if the API key and prompt are provided
if st.button("Generate Video") and api_key and prompt:
    # Generate images
    image_urls = generate_images(api_key, prompt, style, num_images, dimensions)
    
    # Save images locally
    saved_images = save_images(image_urls, "generated_images")
    
    # Create video
    video_file = "output_video.mp4"
    create_video(saved_images, speed, video_file)
    
    # Display video in the app
    st.video(video_file)
    
    # Provide download link
    with open(video_file, "rb") as file:
        st.download_button("Download Video", file, file_name="generated_video.mp4")
else:
    if not api_key:
        st.warning("Please enter your Replicate API key.")
    if not prompt:
        st.warning("Please enter a prompt for image generation.")
