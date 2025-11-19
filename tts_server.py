#!/usr/bin/env python3
"""
Text-to-Speech Web Server with Custom Voice Support
Supports both local Piper TTS (ONNX models) and OpenAI TTS API.

Run on your computer and access from any device on your network.
"""

import os
import io
import re
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

def markdown_to_tts(text):
    """Convert Markdown formatting to TTS-friendly text with natural reading pauses."""

    # Remove code blocks - summarize instead of reading code
    text = re.sub(r'```[\w]*\n.*?```', r'... Code example omitted. ...', text, flags=re.DOTALL)

    # Convert headings to natural section breaks
    # H1 - Major section, long pause before and after
    text = re.sub(r'^#\s+(.+)$', r'\n\n... ... \1. ... ...\n\n', text, flags=re.MULTILINE)
    # H2 - Subsection
    text = re.sub(r'^##\s+(.+)$', r'\n\n... \1. ...\n\n', text, flags=re.MULTILINE)
    # H3-H6 - Minor headings
    text = re.sub(r'^#{3,6}\s+(.+)$', r'\n... \1. ...\n', text, flags=re.MULTILINE)

    # Convert horizontal rules to section breaks
    text = re.sub(r'^[-*_]{3,}\s*$', r'\n... ... ...\n', text, flags=re.MULTILINE)

    # Convert blockquotes - indicate it's a quote
    text = re.sub(r'^>\s*(.+)$', r'Quote: "\1"', text, flags=re.MULTILINE)

    # Convert unordered lists - natural item reading
    def replace_unordered_list(match):
        return f'... {match.group(1)}.'
    text = re.sub(r'^[\*\-\+]\s+(.+)$', replace_unordered_list, text, flags=re.MULTILINE)

    # Convert ordered lists - read with ordinal feel
    def replace_ordered_list(match):
        return f'... {match.group(1)}.'
    text = re.sub(r'^\d+\.\s+(.+)$', replace_ordered_list, text, flags=re.MULTILINE)

    # Convert tables - skip them, too hard to read aloud
    text = re.sub(r'^\|.*\|$', r'', text, flags=re.MULTILINE)

    # Convert links [text](url) -> just the text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Convert images ![alt](url) -> describe briefly
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'... Image: \1. ...', text)

    # Remove inline code backticks
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Convert bold **text** or __text__ -> just text (TTS doesn't emphasize)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)

    # Convert italic *text* or _text_ -> just text
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Convert strikethrough ~~text~~ -> just text
    text = re.sub(r'~~([^~]+)~~', r'\1', text)

    # Add pause between paragraphs (double newlines)
    text = re.sub(r'\n\n+', r'\n... ...\n', text)

    # Clean up excessive pauses
    text = re.sub(r'(\.\.\.\s*){4,}', r'... ... ... ', text)

    # Clean up extra whitespace but preserve intentional pauses
    text = re.sub(r' {2,}', r' ', text)
    text = re.sub(r'\n{3,}', r'\n\n', text)

    # Apply natural reading for numbers, abbreviations, symbols
    text = natural_reading(text)

    return text.strip()

def natural_reading(text):
    """Convert text to more natural TTS-friendly format with number/symbol/abbreviation expansion."""

    # Common abbreviations
    abbreviations = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Miss',
        r'\bProf\.': 'Professor',
        r'\bSt\.(?=\s+[A-Z])': 'Saint',  # Saint before names
        r'\bSt\.(?=\s+\d)': 'Street',    # Street before numbers
        r'\bAve\.': 'Avenue',
        r'\bBlvd\.': 'Boulevard',
        r'\bRd\.': 'Road',
        r'\bDept\.': 'Department',
        r'\bCorp\.': 'Corporation',
        r'\bInc\.': 'Incorporated',
        r'\bLtd\.': 'Limited',
        r'\bvs\.': 'versus',
        r'\betc\.': 'etcetera',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
        r'\baka\.?': 'also known as',
        r'\bw/': 'with',
        r'\bw/o': 'without',
        r'\bJr\.': 'Junior',
        r'\bSr\.': 'Senior',
        r'\bNo\.': 'Number',
        r'\bVol\.': 'Volume',
        r'\bEd\.': 'Edition',
        r'\bPg\.': 'Page',
        r'\bpp\.': 'pages',
        r'\bFig\.': 'Figure',
        r'\bapprox\.': 'approximately',
    }

    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Symbols
    text = re.sub(r'&', ' and ', text)
    text = re.sub(r'@', ' at ', text)
    text = re.sub(r'\+', ' plus ', text)
    text = re.sub(r'=', ' equals ', text)
    text = re.sub(r'#(\d+)', r'number \1', text)  # #5 -> number 5
    text = re.sub(r'%', ' percent', text)

    # Currency
    text = re.sub(r'\$(\d+)\.(\d{2})', r'\1 dollars and \2 cents', text)
    text = re.sub(r'\$(\d+)', r'\1 dollars', text)
    text = re.sub(r'€(\d+)', r'\1 euros', text)
    text = re.sub(r'£(\d+)', r'\1 pounds', text)

    # Times
    text = re.sub(r'(\d{1,2}):(\d{2})\s*([AaPp][Mm])', r'\1 \2 \3', text)
    text = re.sub(r'(\d{1,2}):(\d{2})', r'\1 \2', text)

    # Dates (basic MM/DD/YYYY or DD/MM/YYYY)
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']

    def replace_date(match):
        m, d, y = int(match.group(1)), int(match.group(2)), match.group(3)
        if 1 <= m <= 12:
            return f'{months[m]} {d}, {y}'
        return match.group(0)

    text = re.sub(r'(\d{1,2})/(\d{1,2})/(\d{4})', replace_date, text)

    # Ordinal numbers
    def make_ordinal(n):
        n = int(n)
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f'{n}{suffix}'

    # Convert written ordinals (1st, 2nd, 3rd, 4th...)
    text = re.sub(r'\b(\d+)(?:st|nd|rd|th)\b', lambda m: make_ordinal(m.group(1)), text)

    # Numbers to words for small numbers (0-20) and round numbers
    number_words = {
        '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
        '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
        '10': 'ten', '11': 'eleven', '12': 'twelve', '13': 'thirteen',
        '14': 'fourteen', '15': 'fifteen', '16': 'sixteen', '17': 'seventeen',
        '18': 'eighteen', '19': 'nineteen', '20': 'twenty',
        '100': 'one hundred', '1000': 'one thousand'
    }

    # Convert standalone small numbers
    for num, word in number_words.items():
        text = re.sub(rf'\b{num}\b', word, text)

    # Clean up extra spaces
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()

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
        .advanced-toggle {
            background: #0f3460;
            border: none;
            color: #00d4ff;
            padding: 10px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            width: 100%;
            text-align: left;
            margin-top: 10px;
        }
        .advanced-toggle:hover {
            background: #1a4a7a;
        }
        .advanced-settings {
            display: none;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #0f3460;
        }
        .advanced-settings.show {
            display: block;
        }
        .story-mode-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
            padding: 10px;
            background: #0f3460;
            border-radius: 8px;
        }
        .story-mode-toggle input {
            width: 18px;
            height: 18px;
        }
        .story-mode-toggle label {
            margin: 0;
            cursor: pointer;
        }
        .story-format-hint {
            display: none;
            background: #1a4a7a;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 13px;
            line-height: 1.5;
        }
        .story-format-hint.show {
            display: block;
        }
        .story-format-hint code {
            background: #0f3460;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
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
            <div class="story-mode-toggle">
                <input type="checkbox" id="storyMode" name="storyMode">
                <label for="storyMode">Story Mode (multiple characters)</label>
            </div>

            <div class="story-mode-toggle">
                <input type="checkbox" id="markdownMode" name="markdownMode">
                <label for="markdownMode">Markdown Mode (convert .md formatting)</label>
            </div>

            <div class="story-format-hint" id="storyFormatHint">
                <strong>Story Format:</strong><br>
                Use <code>[CHARACTER:ID]</code> tags before each speaker's text.<br><br>
                <strong>Example:</strong><br>
                <code>[NARRATOR:21]</code> The detective stepped into the bar.<br>
                <code>[JAKE:45]</code> "I've been expecting you."<br>
                <code>[NARRATOR:21]</code> His voice was like gravel.<br>
                <code>[DETECTIVE:67]</code> "Where's the girl?"
            </div>

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

            <button type="button" class="advanced-toggle" id="advancedToggle">
                Advanced Settings +
            </button>

            <div class="advanced-settings" id="advancedSettings">
                <div class="speed-control">
                    <label for="expressiveness">Expressiveness: <span id="expressivenessValue">0.67</span></label>
                    <input type="range" id="expressiveness" name="expressiveness" min="0.0" max="1.0" step="0.05" value="0.67">
                    <div class="speed-label">
                        <span>Flat</span>
                        <span>Dramatic</span>
                    </div>
                </div>

                <div class="speed-control">
                    <label for="sentence_pause">Sentence Pause: <span id="sentencePauseValue">0.2s</span></label>
                    <input type="range" id="sentence_pause" name="sentence_pause" min="0.0" max="2.0" step="0.1" value="0.2">
                    <div class="speed-label">
                        <span>None</span>
                        <span>2s</span>
                    </div>
                </div>

                <div class="speed-control">
                    <label for="speaker_id">Speaker ID: <span id="speakerIdValue">0</span></label>
                    <input type="range" id="speaker_id" name="speaker_id" min="0" max="100" step="1" value="0">
                    <div class="speed-label">
                        <span>0</span>
                        <span>100+</span>
                    </div>
                    <div style="font-size: 11px; color: #888; margin-top: 5px;">
                        For multi-speaker models (e.g., libritts_r has 904 speakers)
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
        const expressivenessSlider = document.getElementById('expressiveness');
        const expressivenessValue = document.getElementById('expressivenessValue');
        const sentencePauseSlider = document.getElementById('sentence_pause');
        const sentencePauseValue = document.getElementById('sentencePauseValue');
        const speakerIdSlider = document.getElementById('speaker_id');
        const speakerIdValue = document.getElementById('speakerIdValue');

        speedSlider.addEventListener('input', () => {
            speedValue.textContent = speedSlider.value + 'x';
        });

        expressivenessSlider.addEventListener('input', () => {
            expressivenessValue.textContent = expressivenessSlider.value;
        });

        sentencePauseSlider.addEventListener('input', () => {
            sentencePauseValue.textContent = sentencePauseSlider.value + 's';
        });

        speakerIdSlider.addEventListener('input', () => {
            speakerIdValue.textContent = speakerIdSlider.value;
        });

        // Toggle advanced settings
        const advancedToggle = document.getElementById('advancedToggle');
        const advancedSettings = document.getElementById('advancedSettings');
        advancedToggle.addEventListener('click', () => {
            advancedSettings.classList.toggle('show');
            advancedToggle.textContent = advancedSettings.classList.contains('show')
                ? 'Advanced Settings -'
                : 'Advanced Settings +';
        });

        // Toggle story mode hint
        const storyModeCheckbox = document.getElementById('storyMode');
        const storyFormatHint = document.getElementById('storyFormatHint');
        storyModeCheckbox.addEventListener('change', () => {
            storyFormatHint.classList.toggle('show', storyModeCheckbox.checked);
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const text = document.getElementById('text').value.trim();
            const voice = document.getElementById('voice').value;
            const speed = parseFloat(document.getElementById('speed').value);
            const expressiveness = parseFloat(document.getElementById('expressiveness').value);
            const sentence_pause = parseFloat(document.getElementById('sentence_pause').value);
            const speaker_id = parseInt(document.getElementById('speaker_id').value);
            const storyMode = document.getElementById('storyMode').checked;
            const markdownMode = document.getElementById('markdownMode').checked;

            if (!text) {
                showStatus('Please enter some text', 'error');
                return;
            }

            speakBtn.disabled = true;
            speakBtn.textContent = 'Generating...';
            showStatus('Generating speech... This may take a moment.', 'loading');
            audioContainer.style.display = 'none';

            try {
                const endpoint = storyMode ? '/speak_story' : '/speak';
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text, voice, speed, expressiveness, sentence_pause, speaker_id, markdown_mode: markdownMode })
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
        expressiveness = data.get('expressiveness', 0.667)
        sentence_pause = data.get('sentence_pause', 0.2)
        speaker_id = data.get('speaker_id', 0)
        markdown_mode = data.get('markdown_mode', False)

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        # Convert Markdown to TTS-friendly text if enabled
        if markdown_mode:
            text = markdown_to_tts(text)

        # Always apply natural reading (numbers, abbreviations, symbols to spoken words)
        text = natural_reading(text)

        # Handle local Piper voices
        if voice.startswith('local:'):
            return speak_local(text, voice, speed, expressiveness, sentence_pause, speaker_id)

        # Handle OpenAI voices
        elif voice.startswith('openai:'):
            return speak_openai(text, voice, speed)

        else:
            return jsonify({'error': 'Invalid voice format'}), 400

    except Exception as e:
        return jsonify({'error': f'TTS generation failed: {str(e)}'}), 500

@app.route('/speak_story', methods=['POST'])
def speak_story():
    """Generate speech with multiple speakers for story narration."""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', '')
        speed = data.get('speed', 1.0)
        expressiveness = data.get('expressiveness', 0.667)
        sentence_pause = data.get('sentence_pause', 0.2)

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        if not voice.startswith('local:'):
            return jsonify({'error': 'Story mode only works with local multi-speaker voices'}), 400

        # Parse text for [CHARACTER:ID] tags
        # Pattern matches [NAME:ID] followed by text until next tag or end
        pattern = r'\[([^:\]]+):(\d+)\]\s*([^\[]*)'
        segments = re.findall(pattern, text)

        if not segments:
            return jsonify({
                'error': 'No valid segments found. Use format: [CHARACTER:ID] text'
            }), 400

        voice_name = voice.split(':')[1]
        model_path = VOICES_DIR / f"{voice_name}.onnx"
        config_path = VOICES_DIR / f"{voice_name}.onnx.json"

        if not model_path.exists():
            return jsonify({'error': f'Voice model not found: {voice_name}'}), 404

        try:
            from piper import PiperVoice, SynthesisConfig
            import wave
        except ImportError:
            return jsonify({
                'error': 'Piper TTS not installed. Run: pip install piper-tts'
            }), 500

        # Load voice model once
        if config_path.exists():
            voice_model = PiperVoice.load(str(model_path), config_path=str(config_path))
        else:
            voice_model = PiperVoice.load(str(model_path))

        # Generate audio for each segment
        all_audio = []
        sample_rate = None
        sample_width = None
        sample_channels = None

        for char_name, speaker_id, segment_text in segments:
            segment_text = segment_text.strip()
            if not segment_text:
                continue

            syn_config = SynthesisConfig(
                speaker_id=int(speaker_id),
                noise_scale=expressiveness,
                length_scale=1.0 / speed if speed != 1.0 else 1.0
            )

            # Collect audio chunks for this segment
            for chunk in voice_model.synthesize(segment_text, syn_config):
                if sample_rate is None:
                    sample_rate = chunk.sample_rate
                    sample_width = chunk.sample_width
                    sample_channels = chunk.sample_channels
                all_audio.append(chunk.audio_int16_bytes)

        if not all_audio:
            return jsonify({'error': 'No audio generated'}), 500

        # Write combined audio to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, 'wb') as wav_file:
                wav_file.setnchannels(sample_channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                for audio_bytes in all_audio:
                    wav_file.writeframes(audio_bytes)

            with open(tmp_path, 'rb') as f:
                audio_data = io.BytesIO(f.read())

            return send_file(
                audio_data,
                mimetype='audio/wav',
                as_attachment=False
            )

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        return jsonify({'error': f'Story TTS failed: {str(e)}'}), 500

def speak_local(text, voice, speed, expressiveness=0.667, sentence_pause=0.2, speaker_id=0):
    """Generate speech using local Piper TTS."""
    voice_name = voice.split(':')[1]
    model_path = VOICES_DIR / f"{voice_name}.onnx"
    config_path = VOICES_DIR / f"{voice_name}.onnx.json"

    if not model_path.exists():
        return jsonify({'error': f'Voice model not found: {voice_name}'}), 404

    try:
        from piper import PiperVoice, SynthesisConfig
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

        # Create synthesis config with parameters
        syn_config = SynthesisConfig(
            speaker_id=speaker_id if speaker_id > 0 else None,
            noise_scale=expressiveness,
            length_scale=1.0 / speed if speed != 1.0 else 1.0
        )

        # Synthesize speech - piper-tts 1.3.0 API
        with wave.open(tmp_path, 'wb') as wav_file:
            first_chunk = True
            for chunk in voice_model.synthesize(text, syn_config):
                if first_chunk:
                    wav_file.setnchannels(chunk.sample_channels)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setframerate(chunk.sample_rate)
                    first_chunk = False
                wav_file.writeframes(chunk.audio_int16_bytes)

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
    app.run(host='0.0.0.0', port=port, debug=True)
