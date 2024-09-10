# Stable Diffusion Longform Video Creator

This Streamlit app allows users to generate longform videos by concatenating video segments created from text prompts or images. Using Stability AI's API, the app can generate images based on text or convert uploaded images into video clips. It then concatenates these clips to produce a cohesive longform video. **Note:** This process can get expensive due to the pricing of Stable Diffusion's API.

## Features

- **Text-to-Image**: Generate images based on text prompts using Stability AI's API.
- **Image-to-Video**: Convert an image into a video with optional motion effects using Stability AI's API.
- **Snapshot Mode**: Generate multiple images from a prompt and create video segments from them, forming a longform video.
- **Crossfade Video**: Option to apply crossfade transitions between video segments.

## How to Use

1. **Enter your API Key**: In the sidebar, input your Stability AI API key.
2. **Choose a Generation Mode**: 
   - Text-to-Video
   - Image-to-Video
   - Snapshot Mode
3. **Configure Settings**: Depending on the mode selected, configure parameters like the number of video segments, FPS, CFG scale, and more.
4. **Generate Content**: Hit the "Generate Content" button to create images and videos.
5. **View Generated Results**: Use the tabs to view generated images and videos.
6. **Download**: You can download individual video segments or a ZIP file containing all generated content.

- **Alternative APIs**: We intend to switch out Stability AI for a more cost-effective solution.
- **More Flexibility**: Additional modes and customization options for generating longform videos.
- **Optimizations**: Improvements to the video generation and concatenation process for better performance.
