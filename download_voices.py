#!/usr/bin/env python3
"""
Download Piper TTS voice models from Hugging Face.
Run: python download_voices.py
"""

import os
import urllib.request
from pathlib import Path

VOICES_DIR = Path(__file__).parent / "voices"

# Available voice models to download
VOICE_MODELS = {
    "en_US-libritts_r-medium": {
        "description": "Multi-speaker (904 voices) - Best for story narration",
        "files": [
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/libritts_r/medium/en_US-libritts_r-medium.onnx",
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/libritts_r/medium/en_US-libritts_r-medium.onnx.json"
        ]
    },
    "en_US-lessac-medium": {
        "description": "Clear male narrator voice",
        "files": [
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
        ]
    },
    "en_GB-alan-medium": {
        "description": "British male voice - good for narration",
        "files": [
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json"
        ]
    },
    "en_US-amy-medium": {
        "description": "American female voice",
        "files": [
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
        ]
    }
}

def download_file(url, dest_path):
    """Download a file with progress indicator."""
    print(f"  Downloading: {dest_path.name}")
    try:
        urllib.request.urlretrieve(url, dest_path)
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"    Done ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False

def main():
    # Create voices directory
    VOICES_DIR.mkdir(exist_ok=True)

    print("\n" + "="*50)
    print("  Piper TTS Voice Downloader")
    print("="*50)
    print(f"\nVoices will be saved to: {VOICES_DIR}\n")

    # Show available voices
    print("Available voices:\n")
    for i, (name, info) in enumerate(VOICE_MODELS.items(), 1):
        print(f"  {i}. {name}")
        print(f"     {info['description']}\n")

    # Ask user which to download
    print("Options:")
    print("  a - Download ALL voices")
    print("  1 - Download voice #1 (libritts_r - recommended for stories)")
    print("  q - Quit\n")

    choice = input("Enter choice: ").strip().lower()

    if choice == 'q':
        print("Cancelled.")
        return

    if choice == 'a':
        to_download = list(VOICE_MODELS.keys())
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(VOICE_MODELS):
            to_download = [list(VOICE_MODELS.keys())[idx]]
        else:
            print("Invalid choice.")
            return
    else:
        print("Invalid choice.")
        return

    # Download selected voices
    print("\nDownloading...\n")

    for voice_name in to_download:
        print(f"\n{voice_name}:")
        info = VOICE_MODELS[voice_name]

        for url in info['files']:
            filename = url.split('/')[-1]
            dest_path = VOICES_DIR / filename

            if dest_path.exists():
                print(f"  Skipping (exists): {filename}")
            else:
                download_file(url, dest_path)

    print("\n" + "="*50)
    print("  Download complete!")
    print("="*50)
    print("\nYou can now start the TTS server:")
    print("  python tts_server.py\n")

    # Tip for multi-speaker model
    if "en_US-libritts_r-medium" in to_download:
        print("Tip: libritts_r has 904 speakers!")
        print("Try different Speaker IDs (0-903) in Advanced Settings")
        print("to find voices you like.\n")

if __name__ == '__main__':
    main()
