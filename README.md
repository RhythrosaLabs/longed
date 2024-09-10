# Stable Diffusion Longform Video Creator

This Streamlit app allows users to generate longform videos by concatenating video segments created from text prompts or images. Using Stability AI's API, the app can generate images based on text or convert uploaded images into video clips. It then concatenates these clips to produce a cohesive longform video. **Note:** This process can get expensive due to the pricing of Stable Diffusion's API.

## Features
- **Text-to-Video**: Generate a video starting from a text prompt.
- **Image-to-Video**: Generate a video starting from an uploaded image.
- **Multiple Segments**: Specify the number of video segments to generate and stitch them together.
- **Custom Settings**: Adjust CFG scale, motion intensity, crossfade duration, and seed for unique results.
- **Concatenation with Crossfade**: Stitch videos with optional crossfade between segments.
- **Downloadable Output**: After video generation, users can download the final longform video.

## Usage
1. **Enter API Key**: Provide your Stability AI API key in the sidebar.
2. **Select Mode**: Choose either `Text-to-Video` or `Image-to-Video` mode in the Generator tab.
3. **Configure Settings**: Adjust the settings to fine-tune the video generation process.
4. **Generate Video**: Click the "Generate Longform Video" button and wait for the video segments to be generated.
5. **View Results**: Generated images and videos will be displayed in their respective tabs. Once a full video is generated, it will be available for download.

## API Pricing Warning
Please be aware that using the Stability AI API for generating images and videos can incur significant costs, depending on the number of segments and complexity of requests. The app utilizes Stability AI's paid services, so users should monitor API usage and expenses carefully. We plan to integrate a more cost-effective solution in the future to alleviate these concerns.

## Future Updates
- **Alternative APIs**: We intend to switch out Stability AI for a more cost-effective solution.
- **More Flexibility**: Additional modes and customization options for generating longform videos.
- **Optimizations**: Improvements to the video generation and concatenation process for better performance.
