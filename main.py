import streamlit as st
import requests
import time
from PIL import Image
import io

# Function to resize image to supported dimensions
def resize_image(image):
    width, height = image.size
    if (width, height) == (1024, 576) or (width, height) == (576, 1024) or (width, height) == (768, 768):
        return image  # Return if image already has valid dimensions
    else:
        st.warning("Resizing image to 768x768 (default)")
        return image.resize((768, 768))  # Default resize

# Function to start video generation
def start_video_generation(api_key, image, cfg_scale=1.8, motion_bucket_id=127, seed=0):
    url = "https://api.stability.ai/v2beta/image-to-video"
    headers = {
        "authorization": f"Bearer {api_key}"
    }
    
    # Convert PIL image to bytes for the request
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    files = {
        "image": ("image.png", img_byte_arr, "image/png")
    }
    
    data = {
        "seed": seed,
        "cfg_scale": cfg_scale,
        "motion_bucket_id": motion_bucket_id
    }
    
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        return response.json().get('id')
    else:
        st.error(f"Error: {response.status_code} - {response.text}")
        return None

# Function to poll for video generation result
def poll_for_video(api_key, generation_id):
    url = f"https://api.stability.ai/v2beta/image-to-video/result/{generation_id}"
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "video/*"
    }
    
    while True:
        response = requests.get(url, headers=headers)
        if response.status_code == 202:
            st.write("Video generation in progress... Polling again in 10 seconds.")
            time.sleep(10)
        elif response.status_code == 200:
            return response.content
        else:
            st.error(f"Error: {response.status_code} - {response.text}")
            return None

# Streamlit UI
def main():
    st.title("Stable Diffusion Video Creator")

    # User inputs API key and parameters
    api_key = st.text_input("Enter your Stability AI API Key", type="password")
    image_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8)
    motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
    seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)

    if st.button("Generate Video"):
        if not api_key or not image_file:
            st.error("Please enter the API key and upload an image.")
        else:
            # Open the uploaded image using PIL
            image = Image.open(image_file)
            
            # Resize the image to supported dimensions if necessary
            resized_image = resize_image(image)

            # Start the video generation process
            st.write("Starting video generation...")
            generation_id = start_video_generation(api_key, resized_image, cfg_scale, motion_bucket_id, seed)
            
            if generation_id:
                st.write(f"Generation started with ID: {generation_id}")
                # Poll for the video result
                video_content = poll_for_video(api_key, generation_id)
                
                if video_content:
                    # Save the video
                    video_path = "generated_video.mp4"
                    with open(video_path, "wb") as f:
                        f.write(video_content)
                    
                    # Provide download link
                    st.video(video_path)
                    with open(video_path, "rb") as f:
                        st.download_button("Download Video", f, file_name="generated_video.mp4")

if __name__ == "__main__":
    main()
