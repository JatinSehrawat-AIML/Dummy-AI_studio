# from google import genai
# from config.settings import GEMINI_API_KEY

# client = genai.Client(api_key=GEMINI_API_KEY)

# models = client.models.list()

# for model in models:
#     print(model.name)


import os
import json
from gtts import gTTS
from google import genai
from google.genai import types
from moviepy import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    TextClip
)

# ==============================
# CONFIG
# ==============================
GOOGLE_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
ASSETS_DIR = "assets"

os.makedirs(ASSETS_DIR, exist_ok=True)

client = genai.Client(api_key=GOOGLE_API_KEY)

# ==============================
# 1. GENERATE SCRIPT (GEMINI)
# ==============================
def generate_storyboard(topic):
    print(f"🎬 [1/4] Generating script for: {topic}")

    prompt = f"""
    Create a cinematic 5-scene video script about "{topic}".
    Return ONLY valid JSON in this format:
    [
      {{
        "text": "Narration text",
        "image_prompt": "Cinematic visual description"
      }}
    ]
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    return json.loads(response.text)


# ==============================
# 2. GENERATE AUDIO (gTTS)
# ==============================
def generate_audio(text, index):
    print(f"🎙️ [2/4] Generating audio for scene {index}...")

    tts = gTTS(text=text, lang="en", slow=False)
    audio_path = f"{ASSETS_DIR}/audio_{index}.mp3"
    tts.save(audio_path)

    return audio_path


# ==============================
# 3. GENERATE IMAGE (IMAGEN)
# ==============================
def generate_visual(prompt, index):
    print(f"🎨 [3/4] Generating image {index}...")

    response = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="16:9"
        )
    )

    image_path = f"{ASSETS_DIR}/image_{index}.png"
    response.generated_images[0].image.save(image_path)

    return image_path


# ==============================
# 4. ASSEMBLE VIDEO
# ==============================
def assemble_movie(scenes, output="final_video.mp4"):
    print("✂️ [4/4] Rendering final video...")

    clips = []

    for i, scene in enumerate(scenes):
        audio = AudioFileClip(f"{ASSETS_DIR}/audio_{i}.mp3")
        image = ImageClip(f"{ASSETS_DIR}/image_{i}.png").set_duration(audio.duration)

        image = image.resize(lambda t: 1 + 0.02 * t)

        subtitle = TextClip(
            scene["text"],
            fontsize=40,
            color="white",
            method="caption",
            size=(1600, 220)
        ).set_position(("center", 850)).set_duration(audio.duration)

        video = CompositeVideoClip([image.resize(width=1920), subtitle])
        video.audio = audio

        clips.append(video)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output, fps=24, codec="libx264")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    topic = input("🎬 Enter video topic: ")

    storyboard = generate_storyboard(topic)

    for i, scene in enumerate(storyboard):
        generate_audio(scene["text"], i)
        generate_visual(scene["image_prompt"], i)

    assemble_movie(storyboard)

    print("\n✅ Video successfully created!")
