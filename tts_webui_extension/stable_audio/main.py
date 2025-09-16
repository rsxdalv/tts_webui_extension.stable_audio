import os
import json
from gradio_iconbutton import IconButton
import numpy as np
import torch
import gradio as gr

from huggingface_hub import hf_hub_download

from tts_webui.utils.open_folder import open_folder
from tts_webui.utils.get_path_from_root import get_path_from_root
from tts_webui.utils.torch_clear_memory import torch_clear_memory
from tts_webui.utils.prompt_to_title import prompt_to_title
from tts_webui.utils.OpenFolderButton import OpenFolderButton

LOCAL_DIR_BASE = os.path.join("data", "models", "stable-audio")
LOCAL_DIR_BASE_ABSOLUTE = get_path_from_root(*LOCAL_DIR_BASE.split(os.path.sep))
OUTPUT_DIR = os.path.join("outputs-rvc", "Stable Audio")


def generate_cond(
    prompt,
    negative_prompt=None,
    seconds_start=0,
    seconds_total=30,
    cfg_scale=6.0,
    steps=250,
    preview_every=None,
    seed=-1,
    sampler_type="dpmpp-3m-sde",
    sigma_min=0.03,
    sigma_max=1000,
    cfg_rescale=0.0,
    use_init=False,
    init_audio=None,
    init_noise_level=1.0,
    mask_cropfrom=None,
    mask_pastefrom=None,
    mask_pasteto=None,
    mask_maskstart=None,
    mask_maskend=None,
    mask_softnessL=None,
    mask_softnessR=None,
    mask_marination=None,
    batch_size=1,
):
    import gc
    import torchaudio
    from einops import rearrange
    from torchaudio import transforms as T
    from aeiou.viz import audio_spectrogram_image

    from stable_audio_tools.interface.gradio import model
    from stable_audio_tools.inference.generation import generate_diffusion_cond

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    print(f"Prompt: {prompt}")

    global preview_images
    preview_images = []
    if preview_every == 0:
        preview_every = None

    # Return fake stereo audio
    conditioning = [
        {
            "prompt": prompt,
            "seconds_start": seconds_start,
            "seconds_total": seconds_total,
        }
    ] * batch_size

    if negative_prompt:
        negative_conditioning = [
            {
                "prompt": negative_prompt,
                "seconds_start": seconds_start,
                "seconds_total": seconds_total,
            }
        ] * batch_size
    else:
        negative_conditioning = None

    # Get the device from the model
    device = next(model.parameters()).device

    seed = int(seed)

    if not use_init:
        init_audio = None

    input_sample_size = sample_size

    if init_audio is not None:
        in_sr, init_audio = init_audio
        # Turn into torch tensor, converting from int16 to float32
        init_audio = torch.from_numpy(init_audio).float().div(32767)

        if init_audio.dim() == 1:
            init_audio = init_audio.unsqueeze(0)  # [1, n]
        elif init_audio.dim() == 2:
            init_audio = init_audio.transpose(0, 1)  # [n, 2] -> [2, n]

        if in_sr != sample_rate:
            resample_tf = T.Resample(in_sr, sample_rate).to(init_audio.device)
            init_audio = resample_tf(init_audio)

        audio_length = init_audio.shape[-1]

        if audio_length > sample_size:
            input_sample_size = (
                audio_length
                + (model.min_input_length - (audio_length % model.min_input_length))  # type: ignore
                % model.min_input_length  # type: ignore
            )

        init_audio = (sample_rate, init_audio)

    def progress_callback(callback_info):
        global preview_images
        denoised = callback_info["denoised"]
        current_step = callback_info["i"]
        sigma = callback_info["sigma"]

        if (current_step - 1) % preview_every == 0:
            if model.pretransform is not None:
                denoised = model.pretransform.decode(denoised)
            denoised = rearrange(denoised, "b d n -> d (b n)")
            denoised = denoised.clamp(-1, 1).mul(32767).to(torch.int16).cpu()
            audio_spectrogram = audio_spectrogram_image(
                denoised, sample_rate=sample_rate
            )
            preview_images.append(
                (audio_spectrogram, f"Step {current_step} sigma={sigma:.3f})")
            )

    # Do the audio generation
    audio = generate_diffusion_cond(
        model,
        conditioning=conditioning,  # type: ignore
        negative_conditioning=negative_conditioning,  # type: ignore
        steps=steps,
        cfg_scale=cfg_scale,  # type: ignore
        batch_size=batch_size,
        sample_size=input_sample_size,  # type: ignore
        sample_rate=sample_rate,
        seed=seed,
        device=device,  # type: ignore
        sampler_type=sampler_type,
        sigma_min=sigma_min,
        sigma_max=sigma_max,
        init_audio=init_audio,
        init_noise_level=init_noise_level,
        # mask_args=mask_args,
        callback=progress_callback if preview_every is not None else None,
        scale_phi=cfg_rescale,
    )

    # Convert to WAV file
    audio = rearrange(audio, "b d n -> d (b n)")
    audio = (
        audio.to(torch.float32)
        .div(torch.max(torch.abs(audio)))
        .clamp(-1, 1)
        .mul(32767)
        .to(torch.int16)
        .cpu()
    )
    torchaudio.save("output.wav", audio, sample_rate)

    # Let's look at a nice spectrogram too
    audio_spectrogram = audio_spectrogram_image(audio, sample_rate=sample_rate)

    return ("output.wav", [audio_spectrogram, *preview_images])


def generate_cond_lazy(
    prompt,
    negative_prompt=None,
    seconds_start=0,
    seconds_total=30,
    cfg_scale=6.0,
    steps=250,
    preview_every=None,
    seed=-1,
    sampler_type="dpmpp-3m-sde",
    sigma_min=0.03,
    sigma_max=1000,
    cfg_rescale=0.0,
    use_init=False,
    init_audio=None,
    init_noise_level=1.0,
    mask_cropfrom=None,
    mask_pastefrom=None,
    mask_pasteto=None,
    mask_maskstart=None,
    mask_maskend=None,
    mask_softnessL=None,
    mask_softnessR=None,
    mask_marination=None,
    batch_size=1,
):
    from stable_audio_tools.interface.gradio import model

    if model is None:
        gr.Error("Model not loaded")
        raise Exception("Model not loaded")

    return generate_cond(
        prompt=prompt,
        negative_prompt=negative_prompt,
        seconds_start=seconds_start,
        seconds_total=seconds_total,
        cfg_scale=cfg_scale,
        steps=steps,
        preview_every=preview_every,
        seed=seed,
        sampler_type=sampler_type,
        sigma_min=sigma_min,
        sigma_max=sigma_max,
        cfg_rescale=cfg_rescale,
        use_init=use_init,
        init_audio=init_audio,
        init_noise_level=init_noise_level,
        mask_cropfrom=mask_cropfrom,
        mask_pastefrom=mask_pastefrom,
        mask_pasteto=mask_pasteto,
        mask_maskstart=mask_maskstart,
        mask_maskend=mask_maskend,
        mask_softnessL=mask_softnessL,
        mask_softnessR=mask_softnessR,
        mask_marination=mask_marination,
        batch_size=batch_size,
    )


def get_local_dir(name):
    return os.path.join(LOCAL_DIR_BASE, name.replace("/", "__"))


def get_config_path(name):
    return os.path.join(get_local_dir(name), "model_config.json")


def get_ckpt_path(name):
    # check if model.safetensors exists, if not, check if model.ckpt exists
    safetensor_path = os.path.join(get_local_dir(name), "model.safetensors")
    if os.path.exists(safetensor_path):
        return safetensor_path
    else:
        chkpt_path = os.path.join(get_local_dir(name), "model.ckpt")
        if os.path.exists(chkpt_path):
            return chkpt_path
        else:
            raise Exception(
                f"Neither model.safetensors nor model.ckpt exists for {name}"
            )


def download_pretrained_model(name: str, token: str):
    local_dir = get_local_dir(name)

    model_config_path = hf_hub_download(
        name,
        filename="model_config.json",
        repo_type="model",
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        token=token,
    )

    # Try to download the model.safetensors file first, if it doesn't exist, download the model.ckpt file
    try:
        print(f"Downloading {name} model.safetensors")
        ckpt_path = hf_hub_download(
            name,
            filename="model.safetensors",
            repo_type="model",
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            token=token,
        )
    except Exception as e:
        print(f"Downloading {name} model.ckpt")
        ckpt_path = hf_hub_download(
            name,
            filename="model.ckpt",
            repo_type="model",
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            token=token,
        )

    return model_config_path, ckpt_path


def get_model_list():
    try:
        return [
            x
            for x in os.listdir(LOCAL_DIR_BASE)
            if os.path.isdir(os.path.join(LOCAL_DIR_BASE, x))
        ]
    except FileNotFoundError as e:
        print(e)
        return []


def load_model_config(model_name):
    path = get_config_path(model_name)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(e)
        message = (
            f"Model config not found at {path}. Please ensure model_config.json exists."
        )
        gr.Error(message)
        raise Exception(message)


def unload_model():
    from stable_audio_tools.interface.gradio import model, model_type

    del model, model_type
    torch.cuda.empty_cache()


def stable_audio_ui():
    default_model_config_path = os.path.join(LOCAL_DIR_BASE, "diffusion_cond.json")
    with open(default_model_config_path) as f:
        model_config = json.load(f)

    pretransform_ckpt_path = None
    pretrained_name = None

    def load_model_helper(model_name, model_half):
        if model_name == None:
            return model_name

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        from stable_audio_tools.interface.gradio import load_model

        _, model_config_new = load_model(
            model_config=load_model_config(model_name),
            model_ckpt_path=get_ckpt_path(model_name),
            pretrained_name=None,
            pretransform_ckpt_path=pretransform_ckpt_path,
            model_half=model_half,
            device=device,  # type: ignore
        )

        model_type = model_config_new["model_type"]  # type: ignore

        if model_type != "diffusion_cond":
            gr.Error("Only diffusion_cond models are supported")
            raise Exception("Only diffusion_cond models are supported")

        # if model_type == "diffusion_cond":
        #     ui = create_txt2audio_ui(model_config)
        # elif model_type == "diffusion_uncond":
        #     ui = create_diffusion_uncond_ui(model_config)
        # elif model_type == "autoencoder" or model_type == "diffusion_autoencoder":
        #     ui = create_autoencoder_ui(model_config)
        # elif model_type == "diffusion_prior":
        #     ui = create_diffusion_prior_ui(model_config)
        # elif model_type == "lm":
        #     ui = create_lm_ui(model_config)

        return model_name

    def model_select_ui():
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    model_select = gr.Dropdown(
                        choices=get_model_list(),  # type: ignore
                        label="Model",
                        value=pretrained_name,
                    )

                    OpenFolderButton(
                        LOCAL_DIR_BASE, api_name="stable_audio_open_models"
                    )
                    IconButton("refresh").click(
                        fn=lambda: gr.Dropdown(choices=get_model_list()),
                        outputs=[model_select],
                        api_name="stable_audio_refresh_models",
                    )
                with gr.Row():
                    load_model_button = gr.Button(value="Load model")
                    gr.Button("Unload model (not 100%)").click(
                        fn=unload_model,
                        api_name="stable_audio_unload_model",
                    )

            with gr.Column():
                gr.Markdown(
                    """
                    Stable Audio requires a manual download of a model.
                    Please download a model using the download tab or manually place it in the `data/models/stable-audio` folder.

                    Note: Due to a [bug](https://github.com/Stability-AI/stable-audio-tools/issues/80) when using half precision
                    the model will fail to generate with "init audio" or during "inpainting".
                    """
                )
                half_checkbox = gr.Checkbox(
                    label="Use half precision when loading the model",
                    value=True,
                )

            load_model_button.click(
                fn=load_model_helper,
                inputs=[model_select, half_checkbox],
                outputs=[model_select],
            )

            

    model_select_ui()

    with gr.Tabs():
        with gr.Tab("Generation"):
            create_sampling_ui(model_config)
            open_dir_btn = gr.Button("Open outputs folder")
            open_dir_btn.click(
                lambda: open_folder(OUTPUT_DIR),
                api_name="stable_audio_open_output_dir",
            )
        with gr.Tab("Inpainting", visible=False):
            create_sampling_ui(model_config, inpainting=True)
            open_dir_btn = gr.Button("Open outputs folder")
            open_dir_btn.click(lambda: open_folder(OUTPUT_DIR))
        with gr.Tab("Model Download"):
            model_download_ui()


def model_download_ui():
    gr.Markdown(
        """
Models can be found on the [HuggingFace model hub](https://huggingface.co/models?search=stable-audio-open-1.0).

Recommended models:

- voices: RoyalCities/Vocal_Textures_Main
- piano: RoyalCities/RC_Infinite_Pianos
- original: stabilityai/stable-audio-open-1.0
        """
    )
    pretrained_name_text = gr.Textbox(
        label="HuggingFace repo name, e.g. stabilityai/stable-audio-open-1.0",
        value="",
    )
    token_text = gr.Textbox(
        label="HuggingFace Token (Optional, but needed for some non-public models)",
        placeholder="hf_nFjKuKLJF...",
        value="",
    )
    download_btn = gr.Button("Download")
    download_btn.click(
        download_pretrained_model,
        inputs=[pretrained_name_text, token_text],
        outputs=[pretrained_name_text],
        api_name="model_download",
    )

    gr.Markdown(
        "Models can also be downloaded manually and placed within the directory in a folder, for example `data/models/stable-audio/my_model`"
    )

    open_dir_btn = gr.Button("Open local models dir")
    open_dir_btn.click(
        lambda: open_folder(LOCAL_DIR_BASE_ABSOLUTE),
        api_name="model_open_dir",
    )


import scipy.io.wavfile as wavfile
from tts_webui.utils.date import get_date_string


def save_result(audio, *generation_args):
    date = get_date_string()

    generation_args = {
        "date": date,
        "prompt": generation_args[0],
        "negative_prompt": generation_args[1],
        "seconds_start_slider": generation_args[2],
        "seconds_total_slider": generation_args[3],
        "cfg_scale_slider": generation_args[4],
        "steps_slider": generation_args[5],
        "preview_every_slider": generation_args[6],
        "seed_textbox": generation_args[7],
        "sampler_type_dropdown": generation_args[8],
        "sigma_min_slider": generation_args[9],
        "sigma_max_slider": generation_args[10],
        "cfg_rescale_slider": generation_args[11],
        "init_audio_checkbox": generation_args[12],
        "init_audio_input": generation_args[13],
        "init_noise_level_slider": generation_args[14],
    }
    print(generation_args)
    prompt = generation_args["prompt"]

    name = f"{date}_{prompt_to_title(prompt)}"

    base_dir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(base_dir, exist_ok=True)

    sr, data = audio

    wavfile.write(os.path.join(base_dir, f"{name}.wav"), sr, data)

    with open(os.path.join(base_dir, f"{name}.json"), "w") as outfile:
        json.dump(
            generation_args,
            outfile,
            indent=2,
            default=lambda o: "<not serializable>",
        )


def create_uncond_sampling_ui():
    generate_button = gr.Button("Generate", variant="primary", scale=1)

    with gr.Row(equal_height=False):
        with gr.Column():
            with gr.Row():
                # Steps slider
                steps_slider = gr.Slider(
                    minimum=1, maximum=500, step=1, value=100, label="Steps"
                )

            with gr.Accordion("Sampler params", open=False):
                # Seed
                seed_textbox = gr.Textbox(
                    label="Seed (set to -1 for random seed)", value="-1"
                )

                # Sampler params
                with gr.Row():
                    sampler_type_dropdown = gr.Dropdown(
                        [
                            "dpmpp-2m-sde",
                            "dpmpp-3m-sde",
                            "k-heun",
                            "k-lms",
                            "k-dpmpp-2s-ancestral",
                            "k-dpm-2",
                            "k-dpm-fast",
                        ],
                        label="Sampler type",
                        value="dpmpp-3m-sde",
                    )
                    sigma_min_slider = gr.Slider(
                        minimum=0.0,
                        maximum=2.0,
                        step=0.01,
                        value=0.03,
                        label="Sigma min",
                    )
                    sigma_max_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1000.0,
                        step=0.1,
                        value=500,
                        label="Sigma max",
                    )

            with gr.Accordion("Init audio", open=False):
                init_audio_checkbox = gr.Checkbox(label="Use init audio")
                init_audio_input = gr.Audio(label="Init audio")
                init_noise_level_slider = gr.Slider(
                    minimum=0.0,
                    maximum=100.0,
                    step=0.01,
                    value=0.1,
                    label="Init noise level",
                )

        with gr.Column():
            audio_output = gr.Audio(label="Output audio", interactive=False)
            audio_spectrogram_output = gr.Gallery(
                label="Output spectrogram", show_label=False
            )
            send_to_init_button = gr.Button("Send to init audio", scale=1)
            send_to_init_button.click(
                fn=lambda audio: audio,
                inputs=[audio_output],
                outputs=[init_audio_input],
            )

    from stable_audio_tools.interface.gradio import generate_uncond

    generate_button.click(
        fn=generate_uncond,
        inputs=[
            steps_slider,
            seed_textbox,
            sampler_type_dropdown,
            sigma_min_slider,
            sigma_max_slider,
            init_audio_checkbox,
            init_audio_input,
            init_noise_level_slider,
        ],
        outputs=[audio_output, audio_spectrogram_output],
        api_name="generate",
    )


sample_rate = 32000
sample_size = 1920000


def create_sampling_ui(model_config, inpainting=False):
    with gr.Row():
        with gr.Column(scale=6):
            text = gr.Textbox(show_label=False, placeholder="Prompt")
            negative_prompt = gr.Textbox(
                show_label=False, placeholder="Negative prompt"
            )
        generate_button = gr.Button("Generate", variant="primary", scale=1)

    model_conditioning_config = model_config["model"].get("conditioning", None)

    has_seconds_start = False
    has_seconds_total = False

    if model_conditioning_config is not None:
        for conditioning_config in model_conditioning_config["configs"]:
            if conditioning_config["id"] == "seconds_start":
                has_seconds_start = True
            if conditioning_config["id"] == "seconds_total":
                has_seconds_total = True

    with gr.Row(equal_height=False):
        with gr.Column():
            with gr.Row(visible=has_seconds_start or has_seconds_total):
                # Timing controls
                seconds_start_slider = gr.Slider(
                    minimum=0,
                    maximum=512,
                    step=1,
                    value=0,
                    label="Seconds start",
                    visible=has_seconds_start,
                )
                seconds_total_slider = gr.Slider(
                    minimum=0,
                    maximum=512,
                    step=1,
                    value=sample_size // sample_rate,
                    label="Seconds total",
                    visible=has_seconds_total,
                )

            with gr.Row():
                # Steps slider
                steps_slider = gr.Slider(
                    minimum=1, maximum=500, step=1, value=100, label="Steps"
                )

                # Preview Every slider
                preview_every_slider = gr.Slider(
                    minimum=0, maximum=100, step=1, value=0, label="Preview Every"
                )

                # CFG scale
                cfg_scale_slider = gr.Slider(
                    minimum=0.0, maximum=25.0, step=0.1, value=7.0, label="CFG scale"
                )

            with gr.Accordion("Sampler params", open=False):
                # Seed
                seed_textbox = gr.Textbox(label="Seed", value="-1")

                CUSTOM_randomize_seed_checkbox = gr.Checkbox(
                    label="Randomize seed", value=True
                )

                # Sampler params
                with gr.Row():
                    sampler_type_dropdown = gr.Dropdown(
                        [
                            "dpmpp-2m-sde",
                            "dpmpp-3m-sde",
                            "k-heun",
                            "k-lms",
                            "k-dpmpp-2s-ancestral",
                            "k-dpm-2",
                            "k-dpm-fast",
                        ],
                        label="Sampler type",
                        value="dpmpp-3m-sde",
                    )
                    sigma_min_slider = gr.Slider(
                        minimum=0.0,
                        maximum=2.0,
                        step=0.01,
                        value=0.03,
                        label="Sigma min",
                    )
                    sigma_max_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1000.0,
                        step=0.1,
                        value=500,
                        label="Sigma max",
                    )
                    cfg_rescale_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1,
                        step=0.01,
                        value=0.0,
                        label="CFG rescale amount",
                    )

            if inpainting:
                # Inpainting Tab
                with gr.Accordion("Inpainting", open=False):
                    sigma_max_slider.maximum = 1000

                    init_audio_checkbox = gr.Checkbox(label="Do inpainting")
                    init_audio_input = gr.Audio(label="Init audio")
                    init_noise_level_slider = gr.Slider(
                        minimum=0.1,
                        maximum=100.0,
                        step=0.1,
                        value=80,
                        label="Init audio noise level",
                        visible=False,
                    )  # hide this

                    mask_cropfrom_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=0,
                        label="Crop From %",
                    )
                    mask_pastefrom_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=0,
                        label="Paste From %",
                    )
                    mask_pasteto_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=100,
                        label="Paste To %",
                    )

                    mask_maskstart_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=50,
                        label="Mask Start %",
                    )
                    mask_maskend_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=100,
                        label="Mask End %",
                    )
                    mask_softnessL_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=0,
                        label="Softmask Left Crossfade Length %",
                    )
                    mask_softnessR_slider = gr.Slider(
                        minimum=0.0,
                        maximum=100.0,
                        step=0.1,
                        value=0,
                        label="Softmask Right Crossfade Length %",
                    )
                    mask_marination_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1,
                        step=0.0001,
                        value=0,
                        label="Marination level",
                        visible=False,
                    )  # still working on the usefulness of this

                    inputs = [
                        text,
                        negative_prompt,
                        seconds_start_slider,
                        seconds_total_slider,
                        cfg_scale_slider,
                        steps_slider,
                        preview_every_slider,
                        seed_textbox,
                        sampler_type_dropdown,
                        sigma_min_slider,
                        sigma_max_slider,
                        cfg_rescale_slider,
                        init_audio_checkbox,
                        init_audio_input,
                        init_noise_level_slider,
                        mask_cropfrom_slider,
                        mask_pastefrom_slider,
                        mask_pasteto_slider,
                        mask_maskstart_slider,
                        mask_maskend_slider,
                        mask_softnessL_slider,
                        mask_softnessR_slider,
                        mask_marination_slider,
                    ]
            else:
                # Default generation tab
                with gr.Accordion("Init audio", open=False):
                    init_audio_checkbox = gr.Checkbox(label="Use init audio")
                    init_audio_input = gr.Audio(label="Init audio")
                    init_noise_level_slider = gr.Slider(
                        minimum=0.1,
                        maximum=100.0,
                        step=0.01,
                        value=0.1,
                        label="Init noise level",
                    )

                    inputs = [
                        text,
                        negative_prompt,
                        seconds_start_slider,
                        seconds_total_slider,
                        cfg_scale_slider,
                        steps_slider,
                        preview_every_slider,
                        seed_textbox,
                        sampler_type_dropdown,
                        sigma_min_slider,
                        sigma_max_slider,
                        cfg_rescale_slider,
                        init_audio_checkbox,
                        init_audio_input,
                        init_noise_level_slider,
                    ]

        with gr.Column():
            audio_output = gr.Audio(label="Output audio", interactive=False)
            audio_spectrogram_output = gr.Gallery(
                label="Output spectrogram", show_label=False
            )
            send_to_init_button = gr.Button("Send to init audio", scale=1)
            send_to_init_button.click(
                fn=lambda audio: audio,
                inputs=[audio_output],
                outputs=[init_audio_input],
            )

    def randomize_seed(seed, randomize_seed):
        if randomize_seed:
            return np.random.randint(0, 2**32 - 1, dtype=np.uint32)
        else:
            return int(seed)

    generate_button.click(
        fn=randomize_seed,
        inputs=[seed_textbox, CUSTOM_randomize_seed_checkbox],
        outputs=[seed_textbox],
    ).then(
        fn=generate_cond_lazy,
        inputs=inputs,
        outputs=[audio_output, audio_spectrogram_output],
        api_name="stable_audio_inpaint" if inpainting else "stable_audio_generate",
    ).then(
        fn=save_result,
        inputs=[
            audio_output,
            *inputs,
        ],
        api_name="stable_audio_save_inpaint" if inpainting else "stable_audio_save",
    ).then(
        fn=torch_clear_memory,
    )


# FEATURE - crop the audio to the actual length specified
# def crop_audio(audio, seconds_start_slider, seconds_total_slider):
#     sr, data = audio
#     seconds_start = seconds_start_slider.value
#     seconds_total = seconds_total_slider.value
#     data = data[int(seconds_start * sr) : int(seconds_total * sr)]
#     return sr, data


def ui():
    stable_audio_ui()


def extension__tts_generation_webui():
    ui()

    return {
        "package_name": "extension_stable_audio",
        "name": "Stable Audio",
        "requirements": "git+https://github.com/rsxdalv/extension_stable_audio@main",
        "description": "Stable Audio is a text-to-audio model for generating high-quality music and sound effects",
        "extension_type": "interface",
        "extension_class": "audio-music-generation",
        "author": "Stability AI",
        "extension_author": "rsxdalv",
        "license": "MIT",
        "website": "https://github.com/Stability-AI/stable-audio-tools",
        "extension_website": "https://github.com/rsxdalv/extension_stable_audio",
        "extension_platform_version": "0.0.1",
    }


if __name__ == "__main__":
    if "demo" in locals():
        locals()["demo"].close()
    with gr.Blocks() as demo:
        with gr.Tab("Stable Audio"):
            ui()

    demo.launch(
        server_port=7771,
    )
