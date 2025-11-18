#!/usr/bin/env python3
"""
Text-to-Speech Web Server with Custom Voice Support
Supports both local Piper TTS (ONNX models) and OpenAI TTS API.

Run on your computer and access from any device on your network.
"""

import os
import io
import socket
import subprocess
import tempfile
import json
from pathlib import Path
from flask import Flask, render_template_string, request, send_file, jsonify

app = Flask(__name__)

# Directory for local voice models
VOICES_DIR = Path(__file__).parent / "voices"

# Available voices from OpenAI TTS
OPENAI_VOICES = {
    "openai:alloy": "OpenAI - Neutral and balanced",
    "openai:echo": "OpenAI - Warm and clear",
    "openai:fable": "OpenAI - Expressive and dynamic",
    "openai:onyx": "OpenAI - Deep and authoritative",
    "openai:nova": "OpenAI - Friendly and upbeat",
    "openai:shimmer": "OpenAI - Soft and gentle"
}

def get_local_voices():
    """Scan for local Piper ONNX voice models."""
    voices = {}
    if not VOICES_DIR.exists():
        return voices

    for onnx_file in VOICES_DIR.glob("*.onnx"):
        if onnx_file.name.endswith(".onnx.json"):
            continue

        voice_name = onnx_file.stem
        json_file = onnx_file.with_suffix(".onnx.json")

        # Get description from JSON if available
        description = "Local voice"
        if json_file.exists():
            try:
                with open(json_file) as f:
                    config = json.load(f)
                    if "language" in config:
                        lang = config["language"].get("name_english", "")
                        if lang:
                            description = f"Local - {lang}"
                    if "dataset" in config:
                        description = f"Local - {config['dataset']}"
            except Exception:
                pass

        voices[f"local:{voice_name}"] = description

    return voices

def get_all_voices():
    """Get all available voices (local + OpenAI)."""
    voices = get_local_voices()

    # Add OpenAI voices
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        voices.update(OPENAI_VOICES)

    # If no voices available, still show OpenAI options with note
    if not voices:
        voices = {k: v + " (needs API key)" for k, v in OPENAI_VOICES.items()}

    return voices

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS - Custom Voice</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }
        h1 {
            text-align: center;
            color: #00d4ff;
            margin-bottom: 30px;
        }
        .container {
            background: #16213e;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #00d4ff;
        }
        textarea {
            width: 100%;
            height: 150px;
            padding: 15px;
            border: 2px solid #0f3460;
            border-radius: 8px;
            font-size: 16px;
            resize: vertical;
            background: #0f3460;
            color: #eee;
            margin-bottom: 20px;
        }
        textarea:focus {
            outline: none;
            border-color: #00d4ff;
        }
        .controls {
            display: grid;
            grid-template-columns: 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }
        select {
            width: 100%;
            padding: 12px;
            border: 2px solid #0f3460;
            border-radius: 8px;
            font-size: 14px;
            background: #0f3460;
            color: #eee;
            cursor: pointer;
        }
        select:focus {
            outline: none;
            border-color: #00d4ff;
        }
        optgroup {
            font-weight: bold;
            color: #00d4ff;
        }
        button {
            width: 100%;
            padding: 15px;
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover {
            background: #00a8cc;
            transform: translateY(-2px);
        }
        button:disabled {
            background: #555;
            cursor: not-allowed;
            transform: none;
        }
        #status {
            text-align: center;
            margin-top: 15px;
            padding: 10px;
            border-radius: 8px;
            display: none;
        }
        #status.loading {
            display: block;
            background: #0f3460;
            color: #00d4ff;
        }
        #status.error {
            display: block;
            background: #e94560;
            color: white;
        }
        #status.success {
            display: block;
            background: #0f3460;
            color: #4ade80;
        }
        #audioContainer {
            margin-top: 20px;
            text-align: center;
            display: none;
        }
        audio {
            width: 100%;
            margin-bottom: 15px;
        }
        .download-btn {
            background: #4ade80;
            padding: 10px 20px;
            font-size: 14px;
            display: inline-block;
            text-decoration: none;
            color: #1a1a2e;
            border-radius: 8px;
            font-weight: bold;
        }
        .download-btn:hover {
            background: #22c55e;
        }
        .info {
            background: #0f3460;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            line-height: 1.6;
        }
        .info strong {
            color: #00d4ff;
        }
        .local-badge {
            background: #4ade80;
            color: #1a1a2e;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            margin-left: 5px;
        }
        .speed-control {
            margin-top: 10px;
        }
        .speed-control input {
            width: 100%;
        }
        .speed-label {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #888;
        }
    </style>
</head>
<body>
    <h1>Text to Speech</h1>

    <div class="container">
        <div class="info">
            <strong>How to use:</strong> Paste your text below, select a voice, then click "Speak".
            {% if has_local %}
            <br><br><strong>Local voices</strong> work offline and are free!
            {% endif %}
        </div>

        <form id="ttsForm">
            <label for="text">Text to speak:</label>
            <textarea id="text" name="text" placeholder="Paste or type your text here..." required></textarea>

            <div class="controls">
                <div>
                    <label for="voice">Voice:</label>
                    <select id="voice" name="voice">
                        {% if local_voices %}
                        <optgroup label="Local Voices (Offline)">
                            {% for voice_id, desc in local_voices.items() %}
                            <option value="{{ voice_id }}" {% if loop.first %}selected{% endif %}>
                                {{ voice_id.split(':')[1].replace('_', ' ').title() }} - {{ desc }}
                            </option>
                            {% endfor %}
                        </optgroup>
                        {% endif %}
                        {% if openai_voices %}
                        <optgroup label="OpenAI Voices (Cloud)">
                            {% for voice_id, desc in openai_voices.items() %}
                            <option value="{{ voice_id }}" {% if not local_voices and loop.first %}selected{% endif %}>
                                {{ voice_id.split(':')[1].title() }} - {{ desc }}
                            </option>
                            {% endfor %}
                        </optgroup>
                        {% endif %}
                    </select>
                </div>

                <div class="speed-control">
                    <label for="speed">Speed: <span id="speedValue">1.0x</span></label>
                    <input type="range" id="speed" name="speed" min="0.5" max="2.0" step="0.1" value="1.0">
                    <div class="speed-label">
                        <span>0.5x</span>
                        <span>2.0x</span>
                    </div>
                </div>
            </div>

            <button type="submit" id="speakBtn">Speak</button>
        </form>

        <div id="status"></div>

        <div id="audioContainer">
            <audio id="audioPlayer" controls></audio>
            <br>
            <a id="downloadLink" class="download-btn" download="speech.wav">Download Audio</a>
        </div>
    </div>

    <script>
        const form = document.getElementById('ttsForm');
        const status = document.getElementById('status');
        const audioContainer = document.getElementById('audioContainer');
        const audioPlayer = document.getElementById('audioPlayer');
        const downloadLink = document.getElementById('downloadLink');
        const speakBtn = document.getElementById('speakBtn');
        const speedSlider = document.getElementById('speed');
        const speedValue = document.getElementById('speedValue');

        speedSlider.addEventListener('input', () => {
            speedValue.textContent = speedSlider.value + 'x';
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const text = document.getElementById('text').value.trim();
            const voice = document.getElementById('voice').value;
            const speed = parseFloat(document.getElementById('speed').value);

            if (!text) {
                showStatus('Please enter some text', 'error');
                return;
            }

            speakBtn.disabled = true;
            speakBtn.textContent = 'Generating...';
            showStatus('Generating speech... This may take a moment.', 'loading');
            audioContainer.style.display = 'none';

            try {
                const response = await fetch('/speak', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text, voice, speed })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to generate speech');
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const ext = voice.startsWith('local:') ? 'wav' : 'mp3';

                audioPlayer.src = url;
                downloadLink.href = url;
                downloadLink.download = `speech_${voice.split(':')[1]}_${Date.now()}.${ext}`;

                audioContainer.style.display = 'block';
                showStatus('Speech generated successfully!', 'success');

                // Auto-play
                audioPlayer.play().catch(() => {
                    // Autoplay might be blocked, that's okay
                });

            } catch (error) {
                showStatus(error.message, 'error');
            } finally {
                speakBtn.disabled = false;
                speakBtn.textContent = 'Speak';
            }
        });

        function showStatus(message, type) {
            status.textContent = message;
            status.className = type;
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    all_voices = get_all_voices()
    local_voices = {k: v for k, v in all_voices.items() if k.startswith('local:')}
    openai_voices = {k: v for k, v in all_voices.items() if k.startswith('openai:')}

    return render_template_string(
        HTML_TEMPLATE,
        local_voices=local_voices,
        openai_voices=openai_voices,
        has_local=bool(local_voices)
    )

@app.route('/speak', methods=['POST'])
def speak():
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', '')
        speed = data.get('speed', 1.0)

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        # Handle local Piper voices
        if voice.startswith('local:'):
            return speak_local(text, voice, speed)

        # Handle OpenAI voices
        elif voice.startswith('openai:'):
            return speak_openai(text, voice, speed)

        else:
            return jsonify({'error': 'Invalid voice format'}), 400

    except Exception as e:
        return jsonify({'error': f'TTS generation failed: {str(e)}'}), 500

def speak_local(text, voice, speed):
    """Generate speech using local Piper TTS."""
    voice_name = voice.split(':')[1]
    model_path = VOICES_DIR / f"{voice_name}.onnx"
    config_path = VOICES_DIR / f"{voice_name}.onnx.json"

    if not model_path.exists():
        return jsonify({'error': f'Voice model not found: {voice_name}'}), 404

    try:
        from piper import PiperVoice
        import wave
    except ImportError:
        return jsonify({
            'error': 'Piper TTS not installed. Run: pip install piper-tts'
        }), 500

    # Generate speech with Piper Python API
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Load the voice model
        if config_path.exists():
            voice_model = PiperVoice.load(str(model_path), config_path=str(config_path))
        else:
            voice_model = PiperVoice.load(str(model_path))

        # Calculate length scale (< 1 is faster)
        length_scale = 1.0 / speed if speed != 1.0 else None

        # Synthesize speech
        with wave.open(tmp_path, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(voice_model.config.sample_rate)
            voice_model.synthesize(text, wav_file, length_scale=length_scale)

        # Read and return the audio file
        with open(tmp_path, 'rb') as f:
            audio_data = io.BytesIO(f.read())

        return send_file(
            audio_data,
            mimetype='audio/wav',
            as_attachment=False
        )

    except Exception as e:
        return jsonify({'error': f'Piper TTS error: {str(e)}'}), 500

    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def speak_openai(text, voice, speed):
    """Generate speech using OpenAI TTS API."""
    voice_name = voice.split(':')[1]

    # Check for API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'error': 'OPENAI_API_KEY environment variable not set'}), 500

    # Validate voice
    valid_voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
    if voice_name not in valid_voices:
        return jsonify({'error': f'Invalid OpenAI voice: {voice_name}'}), 400

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_name,
            input=text,
            speed=speed,
            response_format="mp3"
        )

        audio_data = io.BytesIO(response.content)
        audio_data.seek(0)

        return send_file(
            audio_data,
            mimetype='audio/mpeg',
            as_attachment=False
        )

    except ImportError:
        return jsonify({'error': 'OpenAI library not installed. Run: pip install openai'}), 500
    except Exception as e:
        error_msg = str(e)
        if 'api_key' in error_msg.lower() or 'authentication' in error_msg.lower():
            return jsonify({'error': 'Invalid API key. Please check your OPENAI_API_KEY.'}), 401
        return jsonify({'error': f'OpenAI TTS failed: {error_msg}'}), 500

def get_local_ip():
    """Get the local IP address for network access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    local_ip = get_local_ip()

    # Create voices directory if it doesn't exist
    VOICES_DIR.mkdir(exist_ok=True)

    # Check for local voices
    local_voices = get_local_voices()

    print("\n" + "="*50)
    print("  TTS Server with Custom Voice")
    print("="*50)
    print(f"\n  Local:   http://localhost:{port}")
    print(f"  Network: http://{local_ip}:{port}")
    print("\n  Access from your phone using the Network URL")
    print("  (Make sure your phone is on the same WiFi)\n")

    if local_voices:
        print("  Local voices found:")
        for v in local_voices:
            print(f"    - {v.split(':')[1]}")
    else:
        print("  No local voices found.")
        print(f"  Add .onnx files to: {VOICES_DIR}")

    print("\n" + "="*50 + "\n")

    # Run with host='0.0.0.0' to allow network access
    app.run(host='0.0.0.0', port=port, debug=False)
