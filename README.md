# Text-to-Speech Server with Custom Voice

A web-based TTS server supporting both **local Piper voices** (ONNX models, free/offline) and **OpenAI TTS** (cloud API). Run on your computer and access from your phone or any device on your network.

## Features

- **Custom Local Voices**: Use your own ONNX voice models (Piper TTS)
- **OpenAI Cloud Voices**: 6 high-quality voices (alloy, echo, fable, onyx, nova, shimmer)
- **Works Offline**: Local voices don't need internet or API keys
- **Mobile-Friendly**: Responsive web interface works on phone
- **Speed Control**: Adjust playback speed from 0.5x to 2.0x
- **Download Audio**: Save generated speech as WAV/MP3 files

## Quick Start

### 1. Install Dependencies

```bash
cd tools/whisper-tts
pip install -r requirements.txt
```

### 2. Add Your Custom Voice (Optional)

Place your ONNX voice files in the `voices` folder:

```
tools/whisper-tts/
├── voices/
│   ├── cortana.onnx        # Your voice model
│   └── cortana.onnx.json   # Voice config (optional)
├── tts_server.py
└── ...
```

The server will automatically detect any `.onnx` files in this folder.

### 3. Run the Server

```bash
python tts_server.py
```

Output:
```
==================================================
  TTS Server with Custom Voice
==================================================

  Local:   http://localhost:5000
  Network: http://192.168.1.100:5000

  Access from your phone using the Network URL
  (Make sure your phone is on the same WiFi)

  Local voices found:
    - cortana

==================================================
```

### 4. Access from Your Phone

1. Make sure your phone is on the same WiFi network
2. Open the **Network URL** in your phone's browser
3. Paste text, select voice, tap "Speak"

## Using Local Piper Voices

### Where to Get Voice Models

Download Piper voice models from:
- [Piper Voices Repository](https://github.com/rhasspy/piper/blob/master/VOICES.md)
- [Hugging Face Piper Models](https://huggingface.co/rhasspy/piper-voices)

Each voice needs two files:
- `voicename.onnx` - The neural network model
- `voicename.onnx.json` - Configuration file

### Custom/Trained Voices

If you have custom-trained Piper voices (like your `cortana.onnx`), just drop them in the `voices` folder and restart the server.

### Benefits of Local Voices

- **Free**: No API costs
- **Offline**: Works without internet
- **Fast**: No network latency
- **Private**: Audio never leaves your computer

## Using OpenAI Voices (Optional)

To enable cloud voices, set your API key:

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "your-api-key-here"
```

**macOS/Linux:**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### OpenAI Voice Options

| Voice | Description |
|-------|-------------|
| **Alloy** | Neutral and balanced |
| **Echo** | Warm and clear |
| **Fable** | Expressive and dynamic |
| **Onyx** | Deep and authoritative |
| **Nova** | Friendly and upbeat |
| **Shimmer** | Soft and gentle |

## Configuration

### Custom Port

```bash
PORT=8080 python tts_server.py
```

### Speed Control

Use the slider in the web UI to adjust speed from 0.5x (slow) to 2.0x (fast).

## Troubleshooting

### "Piper TTS not installed"
```bash
pip install piper-tts
```

### Voice model not found
- Make sure `.onnx` files are in the `voices/` folder
- Check file names match exactly (case-sensitive)
- Restart the server after adding new voices

### Can't access from phone
1. Check both devices are on the same WiFi
2. Try disabling firewall temporarily
3. Use the Network URL (not localhost)

### Audio doesn't autoplay
Some browsers block autoplay. Tap the play button on the audio player.

### Piper runs slowly
First run may be slow while the model loads. Subsequent requests are faster.

## API Costs (OpenAI only)

Local Piper voices are **free**. OpenAI TTS costs apply only when using cloud voices:
- tts-1: $0.015 / 1K characters
- tts-1-hd: $0.030 / 1K characters

## Project Structure

```
tools/whisper-tts/
├── tts_server.py       # Main server
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── voices/            # Put your .onnx files here
    ├── cortana.onnx
    └── cortana.onnx.json
```

## License

MIT - Use freely for personal projects.
