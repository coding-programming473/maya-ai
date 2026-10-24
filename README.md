# 🤖 Maya AI — Real-Time Voice Assistant

A real-time, low-latency AI voice assistant built in Python using the **Google Gemini Live API**. Maya listens to your microphone, understands your speech, and responds back with a natural, expressive voice — complete with emotions, memory, and personality.

> **Maya** is a girlfriend-style assistant: cute, emotional, caring, and fun. She remembers your conversations, helps with tasks (YouTube, phone, search), and speaks in warm Hindi/Hinglish.

---

## ✨ Features

- 🎤 **Real-time microphone input** — streams live audio to Gemini at 16 kHz
- 🗣️ **Natural voice responses** — Gemini 24 kHz audio output played instantly
- 🧠 **Full memory & context** — remembers your preferences, tasks, and past chats
- 💬 **Input & output transcription** — see both sides of the conversation
- ⚡ **Async architecture** — low-latency, non-blocking audio pipeline
- 🎭 **Rich emotion library** — laughter, shyness, anger, sadness, excitement, and more
- 📺 **YouTube / phone control** — open YouTube, play songs, control device (via `youtube_control.py`)
- 🔐 **Secure API key handling** — keys loaded from `.env`, never hardcoded

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Microphone │ ──► │  main.py     │ ──► │ Gemini Live API │
│  (PyAudio)  │     │  (asyncio)   │     │  (audio stream) │
└─────────────┘     └──────┬───────┘     └────────┬────────┘
                           │                      │
                           ▼                      ▼
                    ┌──────────────┐     ┌─────────────────┐
                    │ Speaker      │ ◄── │ Audio response  │
                    │ (PyAudio)    │     │  (24 kHz PCM)   │
                    └──────────────┘     └─────────────────┘
```

- `main.py` — core voice loop, audio capture/playback, Gemini Live session
- `prompts.py` — Maya's personality, voice config, and system instruction
- `youtube_control.py` — YouTube / device control helpers
- `run_jarvis.bat` — Windows launcher with environment checks

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- A working microphone & speakers
- A [Google Gemini API key](https://aistudio.google.com/apikey)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/coding-programming473/maya-ai.git
cd maya-ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file
echo GOOGLE_API_KEY=your_api_key_here > .env
```

### Dependencies

See `requirements.txt` for the full list (PyAudio, google-genai, python-dotenv, etc.).

---

## ⚙️ Configuration

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_api_key_here
```

> ⚠️ **Never commit your `.env` file.** It is already listed in `.gitignore`.

You can customize Maya's personality and voice in `prompts.py`:

- `VOICE_NAME` — Gemini prebuilt voice (e.g. `Laomedeia`, `Aoede`)
- `INSTRUCTION` — system prompt defining Maya's behavior

---

## 🚀 Run

### Windows

```bat
run_jarvis.bat
```

### Manual

```bash
python main.py
```

Speak into your microphone — Maya will respond in real time.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| AI Model | Google Gemini Live API |
| Audio I/O | PyAudio |
| Concurrency | AsyncIO |
| Config | python-dotenv |

---

## 🔐 Security

- API keys are read from environment variables only — **never hardcoded**.
- `.env` and `__pycache__/` are git-ignored.
- No secrets are stored in the repository.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

- Built with ❤️ by **Pahlad Sir** (creator of Maya)
- Powered by [Google Gemini](https://ai.google.dev/)

---

> *"Maya — meri jaan, tumhari awaaz, tumhara saath."* 💖