import streamlit as st
import requests
import base64
from PIL import Image
import io
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip, vfx
import os
import sys
import numpy as np
import time
import traceback

# Redirect stderr to stdout to avoid issues with logging in some environments
sys.stderr = sys.stdout

# Initialize session state for persistent storage
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []
if 'generated_videos' not in st.session_state:
    st.session_state.generated_videos = []
if 'final_video' not in st.session_state:
    st.session_state.final_video = None

# ... [Previous functions remain the same: resize_image, generate_image_from_text, start_video_generation, poll_for_video, validate_video_clip, get_last_frame_image] ...

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
        
        if crossfade_duration > 0:
            st.write(f"Applying crossfade of {crossfade_duration} seconds")
            # Apply crossfade transition
            final_clips = []
            for i, clip in enumerate(valid_clips):
                if i == 0:
                    final_clips.append(clip)
                else:
                    # Create a crossfade transition
                    fade_out = valid_clips[i-1].fx(vfx.fadeout, duration=crossfade_duration)
                    fade_in = clip.fx(vfx.fadein, duration=crossfade_duration)
                    transition = CompositeVideoClip([fade_out, fade_in])
                    transition = transition.set_duration(crossfade_duration)
                    
                    # Add the transition and the full clip
                    final_clips.append(transition)
                    final_clips.append(clip)
            
            final_video = concatenate_videoclips(final_clips)
        else:
            final_video = concatenate_videoclips(valid_clips)
        
        st.write(f"Concatenation successful. Final video duration: {final_video.duration} seconds")
        return final_video, valid_clips
    except Exception as e:
        st.error(f"Error concatenating videos: {str(e)}")
        for clip in valid_clips:
            clip.close()
        return None, None

def main():
    st.title("Stable Diffusion Longform Video Creator")

    api_key = st.text_input("Enter your Stability AI API Key", type="password")
    mode = st.radio("Select Mode", ("Text-to-Video", "Image-to-Video"))

    if mode == "Text-to-Video":
        prompt = st.text_input("Enter a text prompt for video generation")
    else:
        image_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])

    cfg_scale = st.slider("CFG Scale (Stick to original image)", 0.0, 10.0, 1.8)
    motion_bucket_id = st.slider("Motion Bucket ID (Less motion to more motion)", 1, 255, 127)
    seed = st.number_input("Seed (0 for random)", min_value=0, max_value=4294967294, value=0)
    num_segments = st.slider("Number of video segments to generate", 1, 60, 5)
    crossfade_duration = st.slider("Crossfade Duration (seconds)", 0.0, 2.0, 0.0, 0.01)

    if st.button("Generate Longform Video"):
        if not api_key:
            st.error("Please enter the API key.")
            return

        if mode == "Text-to-Video" and not prompt:
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
            if mode == "Text-to-Video":
                st.write("Generating image from text prompt...")
                image = generate_image_from_text(api_key, prompt)
                if image is None:
                    return
            else:
                image = Image.open(image_file)

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
                        st.write(f"File exists: {os.path.exists(video_path)}")
                        st.write(f"File size: {os.path.getsize(video_path)} bytes")
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
                    except Exception as e:
                        st.error(f"Error writing final video: {str(e)}")
                        st.write("Traceback:", traceback.format_exc())
                    finally:
                        # Close all clips
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

        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            st.write("Error details:", str(e))
            st.write("Traceback:", traceback.format_exc())

    # Display results in tabs
    if st.session_state.generated_images or st.session_state.generated_videos or st.session_state.final_video:
        tab1, tab2 = st.tabs(["Generated Images", "Generated Videos"])
        
        with tab1:
            st.subheader("Generated Images")
            cols = st.columns(len(st.session_state.generated_images))
            for i, img in enumerate(st.session_state.generated_images):
                with cols[i]:
                    st.image(img, caption=f"Image {i+1}", use_column_width=True)
        
        with tab2:
            st.subheader("Generated Videos")
            for i, video_path in enumerate(st.session_state.generated_videos):
                if os.path.exists(video_path):
                    st.video(video_path)
                    st.write(f"Video Segment {i+1}")
            
            if st.session_state.final_video and os.path.exists(st.session_state.final_video):
                st.subheader("Final Longform Video")
                st.video(st.session_state.final_video)
                with open(st.session_state.final_video, "rb") as f:
                    st.download_button("Download Longform Video", f, file_name="longform_video.mp4")

if __name__ == "__main__":
    main()
