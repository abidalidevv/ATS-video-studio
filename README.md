# ⚡ Avatar Storyteller Engine — AI Video Studio (1080p 16:9)

> **Ultra-Fast Single-Pass GPU Faceless Video Generator for YouTube Storytellers & Documentaries**  
> *Author Avatar Isolation • Local B-Roll Footage Pool • 16:9 Atmospheric Blur • Smart Adaptive Kinetic Subtitles • 20s Live Director Preview*

---

## 🌟 Overview

**Avatar Storyteller Engine** is a specialized, production-ready desktop video studio engineered specifically for high-retention faceless storytelling channels (Stoicism, Ancient Philosophy, Dark Psychology, Reddit Mysteries, True Crime, Business Case Studies, and Deep Motivation).

Unlike generic AI video tools that download random stock footage from slow external APIs, Avatar Storyteller Engine draws from a **local high-speed B-roll pool**, composites a **custom author avatar with automated outer stroke glow**, softens the background with **16:9 cinematic blur and dark tint**, positions **viral kinetic captions opposite the avatar**, and renders 1-hour videos in **4 to 5 minutes** on standard GPUs via a unified single-pass FFmpeg filtergraph.

---

## 🚀 Key Superpowers & Features

### 1. 📂 Local B-Roll Footage Pool Engine
* **Zero API Latency**: No waiting for slow downloads from Pexels or Pixabay. Reads directly from any local directory on NVMe/SSD.
* **Non-Repeating Shuffle Accumulator**: Shuffles clips randomly without repeats until total duration matches audio length.
* **Cinematic Slow-Motion Multiplier**: Slows footage down (`0.5x`, `0.75x`, `0.85x`, `1.0x`) via monotonic `setpts` for calm documentary aesthetics.
* **Safety Buffer & Auto-Mute**: Adds a 4-second tail buffer so audio never gets cut, and strips native stock audio (`-an`).

### 2. 👤 Author Avatar Picture with Outer Stroke
* **Cutout Portrait Support**: Transparent PNG or JPEG author/expert image docked on **Left**, **Right**, or **Center**.
* **Automated Outer Glow Stroke**: Pillow-based alpha mask dilation generates a crisp, sharp outer border (**Clean White**, **Gold Glow**, **Electric Cyan**) so the portrait stands out against any background.
* **Aspect Ratio & Mirroring**: Supports horizontal flipping/mirroring and free drag-and-drop resizing on canvas.

### 3. 🌫️ 16:9 Background Blur & Ambient Dark Tint
* **Selective Background Blur**: `boxblur` (0–30px) softens stock video motion, eliminating background distractions.
* **Ambient Dark Tint Overlay**: Dimming overlay (0–80%) creates deep cinematic contrast.
* **Razor-Sharp Foreground**: The blur is applied *exclusively* to the stock video layer `[0:v]`. The Avatar portrait, Subtitles, and Visualizer remain **100% crisp, unblurred, and razor-sharp** on top.

### 4. 💬 Smart Adaptive Kinetic Subtitles
* **Collision-Free Positioning**: Automatically places subtitles in the free space opposite the avatar:
  * **Avatar Left** ➔ Subtitles Right (`MarginL=960, MarginR=60`).
  * **Avatar Right** ➔ Subtitles Left (`MarginL=60, MarginR=960`).
  * **Avatar Center** ➔ Bottom Center.
* **12 Viral Typography Presets**: CapCut Viral Yellow, Hormozi Green, Neon Cyber, Ali Abdaal, Luxury Gold, Bangers, and Stoic Slate.
* **Zero-Overlap Clamping**: Strict inter-chunk boundary clamping (`next_start - 0.04s`) prevents LibASS from vertically stacking or doubling lines during speaker transitions.

### 5. 🎙️ Audio DSP Studio & Background Music (BGM)
* **Voice Pitch Shifter**: Real-time pitch control (`-4st` deep broadcaster radio bass to `+4st` high tone).
* **Voice Tempo Control**: Speed controller (`0.8x` to `1.25x`) preserving pitch.
* **BGM Ambience Mixing**: Dedicated background music upload with volume ducking (default 7%) and `:normalize=0` to preserve full voiceover punch.
* **Groq Whisper Compression**: Pre-transcription downsampler (32kbps mono MP3 when >20MB) so 1-hour audio files never exceed Groq's 25MB ceiling.

### 6. 🟢 Custom Green-Screen Visualizer Video & Chroma Key
* **Custom Video Visualizer Upload**: Upload any animated soundwave, circular visualizer, or motion graphics (MP4, WebM, MOV).
* **Live In-App Chroma Keying**: Real-time HTML5 2D canvas pixel shader removes green/blue/black backgrounds with live tolerance and edge smoothing sliders.
* **Eyedropper Color Picker**: Click anywhere on the video frame to sample the background color and key it out instantly.

### 7. 🎬 16:9 Director Canvas & 20s Live Preview
* **Interactive WYSIWYG Stage**: Drag, reposition, and resize Avatar, Subtitle Boundary Box, and Visualizer Widget directly on video.
* **20-Second Demo Playback**: Synchronized preview of background video, voiceover, BGM, and kinetic captions before rendering.
* **Action Safe Grid**: 90% YouTube television/mobile safe area guide toggle.

### 8. ⚡ Single-Pass GPU NVENC Turbo Renderer
* **Unified FFmpeg Filtergraph**: Concat, slow-mo, background blur, dark tint, avatar overlay, visualizer, and ASS subtitle burning executed in **one single pass**.
* **Hardware Acceleration**: Auto-detects NVIDIA NVENC (`h264_nvenc`), Intel QSV (`h264_qsv`), AMD AMF (`h264_amf`), or CPU fallback (`libx264`).
* **Auto-Open Explorer**: Automatically launches Windows Explorer with the completed MP4 highlighted upon 100% completion.

---

## 📦 How to Build & Share Standalone Portable EXE (Zero Setup)

You can package the entire engine into a standalone, portable `.zip` that your friends or clients can run **without installing Python, FFmpeg, or any dependencies**:

1. Double-click `3_BUILD_NEW_Standalone_EXE.bat`.
2. The automated script will:
   - Verify Python and auto-install PyInstaller if needed.
   - Bundle portable static `ffmpeg.exe` and `ffprobe.exe` into `dist/ATSAuthor/bin/`.
   - Bundle all 12 viral TTF fonts into `dist/ATSAuthor/backend/assets/fonts/`.
   - Bundle the modern frontend UI and data folders.
   - Automatically compress the release into **`dist/ATSAuthor-Windows-Portable.zip`**.
3. **Send `ATSAuthor-Windows-Portable.zip` to your friend**:
   - They extract the ZIP anywhere.
   - Double-click **`ATSAuthor.exe`** (or `Launch-ATSAuthor.bat`).
   - The app opens instantly in a native desktop window. Zero installations required!

---

## 💻 How to Run from Source (Developer Mode)

### Requirements
* Windows 10/11 (64-bit)
* Python 3.10 to 3.14
* FFmpeg (or place `ffmpeg.exe` in `bin/`)

### Quick Start
```bash
# 1. Clone the repository
git clone https://github.com/abidalidevv/ATS-video-studio.git
cd ATSAuthor

# 2. Launch with 1-click batch runner
1_RUN_APP.bat

# Or run via Python directly:
pip install -r requirements.txt
python desktop_launcher.py
```

The application will start the local backend server at `http://127.0.0.1:8766` and launch in Microsoft Edge App Mode.

---

## 📁 Project Directory Structure

```
ATSAuthor/
├── 1_RUN_APP.bat                    # 1-Click development launcher
├── 3_BUILD_NEW_Standalone_EXE.bat   # 1-Click standalone portable EXE & ZIP builder
├── desktop_launcher.py              # Desktop launcher & Edge App Mode runner
├── ats_author.spec                  # PyInstaller build specification
├── requirements.txt                 # Python dependencies
├── documentation.html               # 📖 Master Standalone Offline Documentation
├── brain.md                         # 🧠 Master System Blueprint, Plans & Active API Registry
├── README.md                        # Project documentation
│
├── backend/                         # Backend Python Engine
│   ├── server.py                    # FastAPI server & REST API endpoints
│   ├── config.py                    # Settings, portable paths, GPU detection
│   ├── local_pool.py                # Local B-roll scanner & duration accumulator
│   ├── avatar_processor.py          # Avatar outer stroke & glow generator
│   ├── fast_renderer.py             # Single-pass GPU FFmpeg render engine
│   ├── subtitle_generator.py        # 12 viral kinetic subtitle styles & zero-overlap
│   ├── adaptive_subtitles.py        # Smart avatar-aware opposite placement
│   ├── audio_dsp.py                 # Voice pitch shifter, tempo, & BGM mixer
│   ├── transcriber.py               # Groq Whisper micro-timestamp transcriber
│   ├── visualizer_generator.py      # 10 audio visualizers & chroma key filtergraphs
│   └── assets/fonts/                # 12 bundled viral TTF fonts
│
├── bin/                             # Portable FFmpeg & FFprobe binaries
│   ├── ffmpeg.exe                   # Static FFmpeg binary
│   └── ffprobe.exe                  # Static FFprobe binary
│
├── data/                            # Persistent Application Data
│   ├── settings.json                # User settings & API key registry
│   ├── output/                      # Rendered 1080p MP4 master videos
│   ├── avatars/                     # Processed author avatars with strokes
│   └── temp/                        # Audio processing & subtitle cache
│
└── frontend/                        # Modern Dark Glassmorphic Web UI
    ├── index.html                   # 5-Step Wizard & 16:9 Director Canvas
    ├── styles.css                   # Responsive dark mode CSS
    ├── app.js                       # Reactive state, canvas drag/resize, live preview
    ├── docs.html                    # In-app Web documentation & manual
    └── favicon.ico                  # Application icon
```

---

## 📖 Complete Documentation & Manuals

* **Offline Interactive Manual**: Open [documentation.html](file:///c:/Users/Abid/Desktop/ATSAuthor/documentation.html) directly in any browser (no server needed).
* **In-App Studio Documentation**: Open [frontend/docs.html](file:///c:/Users/Abid/Desktop/ATSAuthor/frontend/docs.html) or click the **📖 Docs** button in the studio header (`http://127.0.0.1:8766/static/docs.html`).
* **Master System Brain & API Registry**: View [brain.md](file:///c:/Users/Abid/Desktop/ATSAuthor/brain.md) for full architectural plans, active API keys, endpoints, and JSON blocks.

---

## 🔑 API Keys & Configuration

API configurations are saved in `data/settings.json`. You can manage keys inside the in-app **⚙️ Settings** panel or configure them directly:

* **Groq Whisper API**: Used for word-level speech-to-text timestamps in ~1.5 seconds.
* **Pexels & Pixabay APIs**: Optional APIs for cloud stock fetching (see [brain.md](file:///c:/Users/Abid/Desktop/ATSAuthor/brain.md)).
* **Google Gemini API**: Optional for semantic scene analysis and high-CTR YouTube metadata.

See [brain.md](file:///c:/Users/Abid/Desktop/ATSAuthor/brain.md) for full active keys, endpoints, and JSON blocks.

---

## 📜 License & Credits

Built for high-performance YouTube storytelling creators.  
Engineered with FastAPI, FFmpeg Hardware Acceleration (NVENC/QSV/AMF), Pillow, and LibASS.
