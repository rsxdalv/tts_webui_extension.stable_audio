import setuptools

setuptools.setup(
    name="extension_stable_audio",
    packages=setuptools.find_namespace_packages(),
    version="0.0.2",
    author="rsxdalv",
    description="Stable Audio is a text-to-audio model for generating high-quality music and sound effects",
    url="https://github.com/rsxdalv/extension_stable_audio",
    project_urls={},
    scripts=[],
    install_requires=[
        "stable-audio-tools @ https://github.com/rsxdalv/stable-audio-tools/releases/download/v0.0.21/stable_audio_tools-0.0.21-py3-none-any.whl",
        "descript-audiotools @ https://github.com/rsxdalv/audiotools/releases/download/v0.7.4/descript_audiotools-0.7.4-py2.py3-none-any.whl",
        "protobuf==4.25.3",
        "setuptools<70.0.0",
        "sentencepiece==0.2.0",
        "aeiou",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
