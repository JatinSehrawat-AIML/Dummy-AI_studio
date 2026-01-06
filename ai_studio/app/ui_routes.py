from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.script_service import generate_script_from_file
from tts.audio_generator import script_to_audio

import os
import uuid
import re

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------- HELPERS ----------------

SLIDE_HEADER_RE = re.compile(r"^slide\s+(\d+)\s*:?", re.IGNORECASE)


def parse_slides_from_script(script: str) -> list[dict]:
    slides = []
    current = None

    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = SLIDE_HEADER_RE.match(line)
        if match:
            if current:
                slides.append(current)

            slide_num = match.group(1)
            current = {
                "title": f"Slide {slide_num}:",
                "text": ""
            }
            continue

        if current:
            current["text"] += line + " "

    if current:
        slides.append(current)

    # Fallback safety
    if not slides:
        slides = [{
            "title": "Slide 1:",
            "text": script.strip()
        }]

    return slides


def assign_slide_timings(slides: list[dict], duration: float):
    per_slide = duration / max(len(slides), 1)
    t = 0.0

    for idx, slide in enumerate(slides):
        slide["start"] = round(t, 2)
        slide["end"] = round(t + per_slide, 2)
        slide["slide_index"] = idx
        t += per_slide


def attach_words_to_slides(slides: list[dict], words: list[dict]):
    """
    Attach word-level timestamps to their corresponding slide.
    """
    word_idx = 0
    total_words = len(words)

    for slide in slides:
        slide_words = []

        while word_idx < total_words:
            w = words[word_idx]

            if w["start"] >= slide["start"] and w["end"] <= slide["end"]:
                slide_words.append(w)
                word_idx += 1
            elif w["start"] > slide["end"]:
                break
            else:
                word_idx += 1

        slide["words"] = slide_words


# ---------------- HOME ----------------

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "script": None}
    )


# ---------------- SCRIPT GENERATION ----------------

@router.post("/ui/generate", response_class=HTMLResponse)
async def generate_script_ui(
    request: Request,
    file: UploadFile = File(...)
):
    filename = file.filename.lower()

    if not filename.endswith((".pdf", ".pptx")):
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "script": "Only PDF and PPTX files are supported."
            }
        )

    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        script = generate_script_from_file(file_path)
    except Exception as e:
        script = f"Error: {str(e)}"
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "script": script
        }
    )


# ---------------- AUDIO + SLIDE PLAYER ----------------

@router.post("/ui/audio", response_class=HTMLResponse)
def generate_audio_ui(
    request: Request,
    script: str = Form(...)
):
    # 1️⃣ TTS + WORD TIMESTAMPS
    audio_result = script_to_audio(script)
    audio_url = audio_result["audio_url"]
    duration = audio_result["duration"]
    words = audio_result["timestamps"]

    # 2️⃣ Slides
    slides = parse_slides_from_script(script)
    assign_slide_timings(slides, duration)

    # 3️⃣ Attach word timestamps
    attach_words_to_slides(slides, words)

    return templates.TemplateResponse(
        "player.html",
        {
            "request": request,
            "audio_url": audio_url,
            "slides": slides
        }
    )
