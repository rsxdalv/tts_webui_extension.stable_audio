# Extension adapter for Stable Audio

License - the source code within this repository is licensed under the MIT license.

This extension provides a text-to-audio model for generating high-quality music and sound effects.

## Features

- Generate music and audio from text descriptions
- Control the length and timing of generated audio
- Adjust generation parameters for different results
- Support for inpainting to modify existing audio
- Preview generation steps
- Save and manage generated outputs

## Usage

### Model Setup
1. Download a model using the "Model Download" tab or manually place it in the `data/models/stable-audio` folder
2. Select the model from the dropdown and click "Load model"
3. Choose whether to use half precision (faster but may cause issues with init audio or inpainting)

### Generation
1. Enter a text prompt describing the audio you want to generate
2. Optionally enter a negative prompt to specify what you don't want
3. Adjust parameters like length, steps, and CFG scale
4. Click "Generate" to create audio

### Advanced Options
- **Sampler Parameters**: Control the sampling process with different algorithms and settings
- **Init Audio**: Start generation from an existing audio file
- **Inpainting**: Modify specific sections of existing audio

## Recommended Models

- **voices**: RoyalCities/Vocal_Textures_Main
- **piano**: RoyalCities/RC_Infinite_Pianos
- **original**: stabilityai/stable-audio-open-1.0

This extension uses the [Stable Audio Tools](https://github.com/Stability-AI/stable-audio-tools) from Stability AI.
