"""
EventPulse — Python LLM Service
================================
Handles:
  1. HuggingFace LLM → generates announcement text from event details
  2. Pillow          → creates a styled event poster (PNG)
  3. Flask REST API  → exposes endpoints called by your JS frontend

Endpoints:
  POST /generate-announcement   → returns AI-generated text
  POST /generate-poster         → returns poster as base64 PNG
  POST /generate-all            → both text + poster in one call

Run:
  python llm_service.py
"""

import os
import io
import base64
import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import math

# ── Load secrets from config file (never hardcode tokens) ──
from config import HF_TOKEN   # reads from config.py

app = Flask(__name__)
CORS(app)  # allow calls from your HTML frontend

# ─────────────────────────────────────────────────
#  HUGGINGFACE SETTINGS
# ─────────────────────────────────────────────────
HF_MODEL   = "mistralai/Mistral-7B-Instruct-v0.3"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type":  "application/json"
}

# ─────────────────────────────────────────────────
#  HELPER: Call HuggingFace Inference API
# ─────────────────────────────────────────────────
def call_huggingface(prompt: str, max_tokens: int = 300) -> str:
    """
    Sends prompt to HuggingFace Mistral model.
    Returns the generated text string.
    Raises an exception on API error.
    """
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens":  max_tokens,
            "temperature":     0.75,
            "top_p":           0.92,
            "do_sample":       True,
            "return_full_text": False
        }
    }

    response = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload, timeout=60)

    if response.status_code == 503:
        raise Exception("Model is loading on HuggingFace servers. Please retry in 20 seconds.")
    if response.status_code == 401:
        raise Exception("Invalid HuggingFace token. Please check config.py.")
    if not response.ok:
        err = response.json().get("error", f"HTTP {response.status_code}")
        raise Exception(f"HuggingFace API error: {err}")

    data = response.json()
    if isinstance(data, list) and data and "generated_text" in data[0]:
        return data[0]["generated_text"].strip()
    raise Exception("Unexpected response format from HuggingFace API.")


# ─────────────────────────────────────────────────
#  PROMPT BUILDER — LangChain-style templates
# ─────────────────────────────────────────────────
def build_announcement_prompt(title, date, time, venue, description, category):
    """
    Builds a structured Mistral instruction prompt for
    generating a professional event announcement email body.
    """
    return f"""<s>[INST] You are a professional event marketing copywriter for EventPulse.

Write a compelling, enthusiastic event announcement email body for the following event.
- Use 2-3 short paragraphs
- Include emojis naturally
- Highlight the key details (date, time, venue)
- End with a clear call-to-action
- Keep it under 150 words total

Event Details:
- Title:       {title}
- Date:        {date}{f' at {time}' if time else ''}
- Venue:       {venue}
- Category:    {category or 'General'}
- Description: {description or 'A fantastic event you do not want to miss!'}

Write ONLY the email body. No subject line. No extra commentary. [/INST]"""


def build_subject_prompt(title, date, category):
    """Builds a prompt to generate a catchy email subject line."""
    return f"""<s>[INST] Write ONE catchy email subject line for this event announcement.
Include one relevant emoji at the start. Keep it under 60 characters.
Event: "{title}" on {date}, Category: {category or 'General'}
Respond with ONLY the subject line, nothing else. [/INST]"""


# ─────────────────────────────────────────────────
#  POSTER GENERATOR — using Pillow (no external API)
# ─────────────────────────────────────────────────

# 5 color themes — each has bg_colors, accent, text_color
POSTER_THEMES = [
    # 0: Deep Purple (default)
    {
        "name": "Deep Space",
        "bg_top":    (10,  10,  20),
        "bg_bottom": (26,  10,  46),
        "accent1":   (124, 58,  237),
        "accent2":   (0,   217, 255),
        "text":      (232, 232, 240),
        "muted":     (107, 107, 136),
    },
    # 1: Crimson
    {
        "name": "Crimson Fire",
        "bg_top":    (15,  0,   8),
        "bg_bottom": (26,  0,   16),
        "accent1":   (255, 77,  109),
        "accent2":   (255, 159, 28),
        "text":      (255, 240, 243),
        "muted":     (160, 100, 110),
    },
    # 2: Emerald
    {
        "name": "Emerald Dark",
        "bg_top":    (2,   13,  8),
        "bg_bottom": (1,   26,  14),
        "accent1":   (0,   230, 118),
        "accent2":   (0,   188, 212),
        "text":      (224, 247, 233),
        "muted":     (80,  140, 100),
    },
    # 3: Gold
    {
        "name": "Amber Dusk",
        "bg_top":    (18,  12,  0),
        "bg_bottom": (30,  17,  0),
        "accent1":   (255, 214, 0),
        "accent2":   (255, 109, 0),
        "text":      (255, 248, 225),
        "muted":     (160, 130, 60),
    },
    # 4: Monochrome
    {
        "name": "Mono Noir",
        "bg_top":    (14,  14,  14),
        "bg_bottom": (26,  26,  26),
        "accent1":   (255, 255, 255),
        "accent2":   (170, 170, 170),
        "text":      (255, 255, 255),
        "muted":     (120, 120, 120),
    },
]


def hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def lerp_color(c1, c2, t):
    """Linear interpolation between two RGB tuples."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a rounded rectangle on a PIL ImageDraw."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def generate_poster(title, date, time_str, venue, category, theme_index=0) -> bytes:
    """
    Creates an 800×600 event poster using Pillow.
    Returns raw PNG bytes.
    """
    W, H   = 800, 600
    theme  = POSTER_THEMES[theme_index % len(POSTER_THEMES)]
    img    = Image.new("RGB", (W, H), theme["bg_top"])
    draw   = ImageDraw.Draw(img)

    # ── Gradient background (vertical) ──
    for y in range(H):
        t   = y / H
        col = lerp_color(theme["bg_top"], theme["bg_bottom"], t)
        draw.line([(0, y), (W, y)], fill=col)

    # ── Grid overlay (subtle) ──
    for x in range(0, W, 50):
        draw.line([(x, 0), (x, H)], fill=(*theme["muted"], 18))
    for y in range(0, H, 50):
        draw.line([(0, y), (W, y)], fill=(*theme["muted"], 18))

    # ── Left accent bar ──
    for i in range(6):
        t   = i / 5
        col = lerp_color(theme["accent1"], theme["accent2"], t)
        draw.line([(i, 0), (i, H)], fill=col)

    # ── Glow circle (top right decoration) ──
    glow_r = 120
    for r in range(glow_r, 0, -2):
        alpha_val = int(40 * (1 - r/glow_r))
        col = (*theme["accent1"], alpha_val)
        draw.ellipse(
            [(650 - r, 60 - r), (650 + r, 60 + r)],
            fill=theme["accent1"] if r < 8 else None,
            outline=(*theme["accent1"], max(5, alpha_val))
        )

    # ── Decorative geometric shape (varies by theme) ──
    cx, cy = 660, 120
    r_size = 65
    if theme_index % 5 == 0:   # Hexagon
        pts = [(cx + r_size * math.cos(math.pi/3*i - math.pi/6),
                cy + r_size * math.sin(math.pi/3*i - math.pi/6)) for i in range(6)]
        draw.polygon(pts, outline=(*theme["accent1"], 120), width=2)
    elif theme_index % 5 == 1: # Circle ring
        draw.ellipse([(cx-r_size, cy-r_size), (cx+r_size, cy+r_size)],
                     outline=(*theme["accent1"], 120), width=2)
        draw.ellipse([(cx-r_size-14, cy-r_size-14), (cx+r_size+14, cy+r_size+14)],
                     outline=(*theme["accent1"], 40), width=1)
    elif theme_index % 5 == 2: # Triangle
        pts = [(cx, cy-r_size), (cx+r_size*0.87, cy+r_size*0.5), (cx-r_size*0.87, cy+r_size*0.5)]
        draw.polygon(pts, outline=(*theme["accent1"], 120), width=2)
    elif theme_index % 5 == 3: # Diamond
        pts = [(cx, cy-r_size), (cx+r_size*0.7, cy), (cx, cy+r_size), (cx-r_size*0.7, cy)]
        draw.polygon(pts, outline=(*theme["accent1"], 120), width=2)
    else:                       # Plus
        draw.line([(cx-r_size, cy), (cx+r_size, cy)], fill=(*theme["accent1"], 120), width=2)
        draw.line([(cx, cy-r_size), (cx, cy+r_size)], fill=(*theme["accent1"], 120), width=2)

    # ── Try to load fonts (fallback to default) ──
    try:
        font_title  = ImageFont.truetype("arial.ttf", 62)
        font_label  = ImageFont.truetype("arial.ttf", 11)
        font_body   = ImageFont.truetype("arial.ttf", 15)
        font_meta   = ImageFont.truetype("arial.ttf", 13)
        font_brand  = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        # Linux fallback
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
            font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            font_body  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
            font_meta  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
            font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        except OSError:
            font_title = font_label = font_body = font_meta = font_brand = ImageFont.load_default()

    # ── EVENTPULSE brand label ──
    draw.text((38, 38), "EVENTPULSE", font=font_brand, fill=theme["accent2"])

    # ── Divider line ──
    draw.line([(38, 58), (480, 58)], fill=(*theme["accent1"], 100), width=1)

    # ── Event title (word-wrapped, max 2 lines) ──
    words      = title.upper().split()
    lines      = []
    cur_line   = ""
    max_width  = 520

    for word in words:
        test = (cur_line + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font_title)
        if bbox[2] - bbox[0] > max_width and cur_line:
            lines.append(cur_line)
            cur_line = word
        else:
            cur_line = test
    if cur_line:
        lines.append(cur_line)
    lines = lines[:3]  # max 3 lines

    ty = 82
    for i, line in enumerate(lines):
        # Gradient-like effect: first line gets accent color
        color = theme["accent2"] if i == 0 else theme["text"]
        draw.text((38, ty + i * 68), line, font=font_title, fill=color)

    # ── Bottom info strip ──
    strip_y = H - 160
    for y in range(strip_y, H):
        alpha = int(180 * (y - strip_y) / (H - strip_y))
        draw.line([(0, y), (W, y)], fill=lerp_color(theme["bg_bottom"], (0, 0, 0), alpha/255))

    # ── Separator line ──
    draw.line([(38, H-148), (W-38, H-148)], fill=(*theme["accent1"], 70), width=1)

    # ── Date pill ──
    date_text = f"  {date}{f'  ·  {time_str}' if time_str else ''}  "
    bbox      = draw.textbbox((0, 0), date_text, font=font_meta)
    pill_w    = bbox[2] - bbox[0] + 22
    pill_h    = 28
    pill_x    = 38
    pill_y    = H - 132
    draw_rounded_rect(draw,
        [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
        radius=6,
        fill=(*theme["accent1"], 35),
        outline=(*theme["accent1"], 100),
        width=1
    )
    draw.text((pill_x + 11, pill_y + 7), date_text.strip(), font=font_meta, fill=theme["text"])

    # ── Venue ──
    draw.text((38, H - 88), f"  {venue}", font=font_body,
              fill=(*theme["text"], 180))

    # ── Category tag ──
    if category:
        cat_text = f"  #{category}  "
        bbox2    = draw.textbbox((0, 0), cat_text, font=font_label)
        cw       = bbox2[2] - bbox2[0] + 16
        draw_rounded_rect(draw,
            [38, H - 58, 38 + cw, H - 38],
            radius=4,
            fill=(*theme["accent2"], 22),
            outline=(*theme["accent2"], 60),
            width=1
        )
        draw.text((46, H - 55), cat_text.strip(), font=font_label, fill=theme["accent2"])

    # ── Watermark ──
    wm_text = "eventpulse.app"
    bbox_wm = draw.textbbox((0, 0), wm_text, font=font_label)
    wm_w    = bbox_wm[2] - bbox_wm[0]
    draw.text((W - wm_w - 30, H - 28), wm_text, font=font_label,
              fill=(*theme["text"], 40))

    # ── Convert to PNG bytes ──
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ─────────────────────────────────────────────────
#  FLASK API ENDPOINTS
# ─────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "model": HF_MODEL})


@app.route("/generate-announcement", methods=["POST"])
def generate_announcement():
    """
    Input JSON:
      { title, date, time, venue, description, category }
    Returns:
      { announcement_text, subject_line }
    """
    data        = request.get_json()
    title       = data.get("title", "").strip()
    date        = data.get("date", "").strip()
    time_str    = data.get("time", "").strip()
    venue       = data.get("venue", "").strip()
    description = data.get("description", "").strip()
    category    = data.get("category", "").strip()

    if not title or not date or not venue:
        return jsonify({"error": "title, date, and venue are required"}), 400

    try:
        # Generate announcement body
        ann_prompt   = build_announcement_prompt(title, date, time_str, venue, description, category)
        ann_text     = call_huggingface(ann_prompt, max_tokens=300)

        # Generate subject line
        subj_prompt  = build_subject_prompt(title, date, category)
        subject_line = call_huggingface(subj_prompt, max_tokens=30)

        return jsonify({
            "announcement_text": ann_text,
            "subject_line":      subject_line.strip()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate-poster", methods=["POST"])
def generate_poster_endpoint():
    """
    Input JSON:
      { title, date, time, venue, category, theme_index }
    Returns:
      { poster_base64: "data:image/png;base64,..." }
    """
    data        = request.get_json()
    title       = data.get("title", "Event").strip()
    date        = data.get("date", "TBA").strip()
    time_str    = data.get("time", "").strip()
    venue       = data.get("venue", "Venue TBA").strip()
    category    = data.get("category", "").strip()
    theme_index = int(data.get("theme_index", 0))

    try:
        png_bytes   = generate_poster(title, date, time_str, venue, category, theme_index)
        b64_str     = base64.b64encode(png_bytes).decode("utf-8")
        return jsonify({
            "poster_base64": f"data:image/png;base64,{b64_str}",
            "theme_name":    POSTER_THEMES[theme_index % len(POSTER_THEMES)]["name"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate-all", methods=["POST"])
def generate_all():
    """
    Calls both LLM + poster generator in one request.
    Input JSON:
      { title, date, time, venue, description, category, theme_index }
    Returns:
      { announcement_text, subject_line, poster_base64, theme_name }
    """
    data        = request.get_json()
    title       = data.get("title", "").strip()
    date        = data.get("date", "").strip()
    time_str    = data.get("time", "").strip()
    venue       = data.get("venue", "").strip()
    description = data.get("description", "").strip()
    category    = data.get("category", "").strip()
    theme_index = int(data.get("theme_index", 0))

    if not title or not date or not venue:
        return jsonify({"error": "title, date, and venue are required"}), 400

    result = {}

    # LLM generation
    try:
        ann_prompt        = build_announcement_prompt(title, date, time_str, venue, description, category)
        result["announcement_text"] = call_huggingface(ann_prompt, max_tokens=300)

        subj_prompt       = build_subject_prompt(title, date, category)
        result["subject_line"] = call_huggingface(subj_prompt, max_tokens=30).strip()
    except Exception as e:
        result["llm_error"] = str(e)
        result["announcement_text"] = ""
        result["subject_line"]      = f"📣 New Event: {title}"

    # Poster generation
    try:
        png_bytes            = generate_poster(title, date, time_str, venue, category, theme_index)
        b64_str              = base64.b64encode(png_bytes).decode("utf-8")
        result["poster_base64"] = f"data:image/png;base64,{b64_str}"
        result["theme_name"]    = POSTER_THEMES[theme_index % len(POSTER_THEMES)]["name"]
    except Exception as e:
        result["poster_error"] = str(e)

    return jsonify(result)


# ─────────────────────────────────────────────────
#  RUN SERVER
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  EventPulse LLM Service")
    print("  Running on http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)