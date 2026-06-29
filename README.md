# Yoga Pose Estimation & Correction Engine

A real-time yoga pose correction system built with **MediaPipe** and **OpenCV**. It shows a reference yoga video in a small picture-in-picture window, lets the user mirror the movement through the webcam, and corrects non-standard motion by comparing live skeleton features against the current reference frame.

---

## Demo

```
Reference yoga video plays in a small window
→ user mirrors the motion in the webcam
→ live skeleton is compared with the reference skeleton
→ the app shows a match score and the most important correction
```

The system gives real-time feedback on body alignment, arm/hand position, elbow shape, torso tilt, and visibility.

---

## Features

- **Live webcam pose detection** at 25–30 FPS on CPU (no GPU required)
- **Reference video picture-in-picture** for imitation and pacing
- **Frame-by-frame pose matching** against the reference skeleton
- **6 live match checks** shown in the status panel
- **Camera-distance independent** — checks use normalized body features
- **Body-size independent** — works for any person regardless of height
- **Match score** with a visual progress bar
- **Joint angle display** overlaid on skeleton
- **Landmark coordinates** printed to screen and terminal
- **Modular codebase** — clean separation of detection, correction, and UI

---

## Reference Match Checks

| # | Check | Method |
|---|-------|--------|
| 1 | Left arm match | Shoulder angle + wrist height vs reference |
| 2 | Right arm match | Shoulder angle + wrist height vs reference |
| 3 | Elbows match | Left/right elbow angles vs reference |
| 4 | Hands aligned | Wrist-height asymmetry upper bound |
| 5 | Torso centered | Trunk lean vs reference |
| 6 | Body visible | Live and reference skeleton visibility |

The static Urdhva Hastasana rules still live in `correction.py`, but the default `main.py` flow uses the reference-video checks above.

---

## Project Structure

```
├── main.py           # Entry point — webcam/reference-video app loop
├── desktop_app.py    # Cross-platform Tk desktop app with buttons
├── pose_engine.py    # MediaPipe pose detection & webcam management
├── reference_video.py # Reference video reader, pose extraction & PiP overlay
├── correction.py     # Rule-based pose correction logic (6 checks)
├── template_correction.py # Template/reference feature comparison
├── pose_features.py  # Shared pose feature extraction
├── utils.py          # Angle calculation, drawing helpers, FPS counter
├── config.py         # All thresholds with justification comments
├── videos/           # Reference demonstration videos
├── models/           # MediaPipe .task model files
├── requirements.txt  # Python dependencies
├── requirements-build.txt # Packaging dependencies
├── YogaPoseCoach.spec # PyInstaller macOS app bundle config
├── YogaPoseCoachWindows.spec # PyInstaller Windows config
├── build_mac_app.sh  # Builds dist/Yoga Pose Coach.app
├── create_dmg.sh     # Builds a shareable macOS .dmg
├── build_windows_app.ps1 # Builds the Windows app and ZIP
├── build_windows_app.bat # Windows double-click wrapper
├── .github/workflows/build-windows.yml # Cloud Windows build
└── README.md
```

---

## Setup & Installation

### Prerequisites
- Python **3.11** (required — MediaPipe `solutions` API is not available on Python 3.12+)
- Webcam

### Install Python 3.11 (Mac)
```bash
brew install python@3.11
```

### Clone & Install Dependencies
```bash
git clone https://github.com/YOUR_USERNAME/yoga-pose-correction.git
cd yoga-pose-correction

python3.11 -m pip install -r requirements.txt
```

### Run
```bash
python3.11 main.py
```

Run the desktop app with buttons:

```bash
python3.11 desktop_app.py
```

Run with a custom reference video:

```bash
python3.11 main.py --reference-video path/to/demo.mp4
```

### Build macOS App

```bash
./build_mac_app.sh
```

The packaged app will be created at:

```bash
dist/Yoga Pose Coach.app
```

Create a DMG for sharing:

```bash
./create_dmg.sh
```

The DMG will be created at:

```bash
dist/YogaPoseCoach.dmg
```

If your Python 3.11 executable has another path:

```bash
PYTHON_BIN=/path/to/python3.11 ./build_mac_app.sh
```

### Build Windows App

PyInstaller must build the Windows executable on Windows. From PowerShell:

```powershell
.\build_windows_app.ps1
```

You can also run:

```bat
build_windows_app.bat
```

The executable and shareable ZIP will be created at:

```text
dist\YogaPoseCoach\YogaPoseCoach.exe
dist\YogaPoseCoach-Windows.zip
```

Send `YogaPoseCoach-Windows.zip` to the other device. The recipient should
extract the entire folder before opening `YogaPoseCoach.exe`.

### Build Windows App on GitHub

If you only have a Mac, push the complete project to GitHub, including the
`models/` and `videos/` files. Then open:

```text
GitHub repository -> Actions -> Build Windows App -> Run workflow
```

When the workflow finishes, download the `YogaPoseCoach-Windows` artifact.

> **Mac users:** Grant camera permission to Terminal via  
> System Settings → Privacy & Security → Camera → Terminal ✓

---

## Controls

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `Space` | Pause/play reference video |
| `R` | Restart reference video |

The desktop app also provides buttons for Start, Stop, Pause Reference, Restart Reference, Choose Video, and Quit.

---

## Reference-Guided Mode

The default app flow is:

```
Reference video frame → reference skeleton/features
Webcam frame → user skeleton/features
Feature comparison → match score + primary correction
```

The comparison uses normalized pose features such as shoulder angle, elbow angle, wrist height, hand-height asymmetry, trunk lean, and landmark visibility. This keeps the feedback less sensitive to body size and camera distance than raw pixel matching.

---

## How It Works

### Framework: MediaPipe BlazePose
MediaPipe was selected over MoveNet, OpenPose, and Detectron2 for:
- **33 landmarks** including ear landmarks (required for arm-to-ear check)
- **25–30 FPS on CPU** — no GPU needed
- **3D world coordinates** in metric units
- Simple pip install, Apache 2.0 license

### Pose Detection Pipeline
```
Reference frame → MediaPipe Pose → reference features
Webcam frame → MediaPipe Pose → user features
    → Feature comparison → score + feedback overlay → Display
```

### Angle Calculation
Joint angles use the **dot product formula**:
```
BA = A - B,  BC = C - B
angle = arccos( (BA · BC) / (|BA| × |BC|) )
```
Applied to (SHOULDER, ELBOW, WRIST) triplets to detect arm extension.

### Scale Invariance
All distance-based checks divide by shoulder width:
```
ratio = ankle_gap / shoulder_width
```
Since both values scale identically with camera distance and body size, the ratio is a pure measure of posture — valid for any person at any distance.

### State Machine
```
SETUP → (all 4 spatial checks pass) → HOLD → (16s timer) → REST → (8s timer) → SETUP
                                                                  ↓ (after 3 reps)
                                                               COMPLETE
```

---

## Threshold Justification

| Threshold | Value | Justification |
|-----------|-------|---------------|
| Feet ratio min | 0.22 | 15cm/40cm = 0.375 expected; −40% tolerance |
| Feet ratio max | 0.55 | 15cm/40cm = 0.375 expected; +40% tolerance |
| Elbow angle | 160° | Physiotherapy definition of functional full extension |
| Arm-ear offset | 0.30× shoulder | Wrist directly above ear = 0; 0.30 allows natural variation |
| Palm gap | 0.20× shoulder | Pressed palms still have ~5cm natural spread |
| Hold duration | 16 sec | 4 breaths × 4 sec/breath (average adult resting rate) |
| Rest duration | 8 sec | 2 breaths × 4 sec/breath |
| Min visibility | 0.50 | MediaPipe confidence filter before computing angles |

---

## Review Questions (Assignment)

**Q1. How does MediaPipe detect joints internally?**  
Two-stage pipeline: (1) BlazeFace-based person detector estimates bounding ROI on first frame; (2) BlazePose landmark model regresses 33 3D coordinates directly inside the ROI. Subsequent frames reuse the previous ROI via a tracker — the detector only re-runs if tracking confidence drops below threshold.

**Q2. Why is MediaPipe suitable for this yoga use case?**  
It detects 33 landmarks (including ears — required for arm-to-ear check), runs at 25–30 FPS on CPU, provides 3D world coordinates for metric measurements, and has published 100% posture classification accuracy on yoga poses.

**Q3. How are angles computed?**  
Dot product formula: `arccos((BA · BC) / (|BA| × |BC|))` with `np.clip` to prevent domain errors. Applied to (SHOULDER, ELBOW, WRIST) triplets for elbow angle detection.

**Q4. Why those thresholds?**  
All thresholds are derived from anatomy (shoulder/foot proportions), the exercise specification (15 cm, 4 breaths), and physiotherapy standards (160° full extension). See table above.

**Q5. How to extend to multiple poses?**  
Add a `POSE_RULES` dictionary mapping pose names to rule sets. A lightweight classifier (kNN on joint angle feature vectors) identifies the current pose, then loads the corresponding rule set. No retraining of the CNN is needed.

---

## Dependencies

See `requirements.txt`. Core dependencies:
- `mediapipe==0.10.x` (install via pip under Python 3.11)
- `opencv-python`
- `numpy`

---

## License

MIT License — free to use, modify, and distribute.
