"""제주한눈 brand: palette, page CSS, logo, and header markup.

All assets are local. The app makes no network requests for fonts or images,
so it runs the same on an offline center PC.
"""

import base64
import html
import io
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
LOGO_FILE = ASSETS / "logo.png"

NAME = "제주한눈"
NAME_EN = "JejuOneEyes"
TAGLINE = "제주빅데이터센터 자연어 데이터 탐색·분석 Agent"

# Dark-navy variant of the palette. Orange is reserved for status and active marks.
PRIMARY = "#0F1B2D"
PRIMARY_HOVER = "#1E2F4A"
SECONDARY = "#38BDF8"
TINT = "#EEF5FF"
ACCENT = "#FF7A00"
BACKGROUND = "#F5F8FC"
SURFACE = "#FFFFFF"
BORDER = "#DCE5F0"
TEXT = "#0F172A"
MUTED = "#52657A"

# Fallback mark drawn after the logo: eye outline, data bars, Hallasan, pupil with an orange point.
LOGO_SVG = f"""<svg viewBox="0 0 120 72" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{NAME} 로고">
  <defs><clipPath id="jo-eye"><path d="M8 36 Q60 -10 112 36 Q60 82 8 36 Z"/></clipPath></defs>
  <path d="M8 36 Q60 -10 112 36 Q60 82 8 36 Z" fill="#fff"/>
  <g clip-path="url(#jo-eye)">
    <g fill="#7CC4FA"><rect x="22" y="38" width="5" height="22"/><rect x="31" y="30" width="5" height="30"/>
      <rect x="83" y="24" width="5" height="36"/><rect x="92" y="32" width="5" height="28"/></g>
    <path d="M40 34 A20 20 0 0 1 80 34" fill="none" stroke="#2B8BEA" stroke-width="3"/>
    <circle cx="60" cy="36" r="12" fill="#14508E"/>
    <circle cx="65" cy="31" r="2.6" fill="{ACCENT}"/>
    <path d="M26 66 L52 44 Q56 41 60 44 Q64 41 68 44 L94 66 Z" fill="#2B8BEA"/>
  </g>
  <path d="M8 36 Q60 -10 112 36 Q60 82 8 36 Z" fill="none" stroke="#14508E" stroke-width="6" stroke-linejoin="round"/>
</svg>"""


@lru_cache(maxsize=1)
def _logo_images():
    """Trim the white margin of logo.png. Returns (full logo data URI, square mark) or None."""
    if not LOGO_FILE.is_file():
        return None
    from PIL import Image, ImageChops

    image = Image.open(LOGO_FILE).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    box = ImageChops.difference(image, background).convert("L").point(lambda value: 255 if value > 24 else 0).getbbox()
    if box:
        image = image.crop(box)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    # The mark is the left part of the logo; keep it square for the browser tab icon.
    mark = image.crop((0, 0, min(image.height, image.width), image.height))
    return uri, mark


def page_icon():
    images = _logo_images()
    return images[1] if images else "🌊"


def logo_markup(*, size: int) -> str:
    """Logo for the header and sidebar. The PNG already carries the wordmark."""
    images = _logo_images()
    if images:
        return f'<img class="jo-logo-img" src="{images[0]}" alt="{NAME} {NAME_EN}" style="height:{size}px">'
    # Inline SVG is stripped by the HTML sanitizer, so the mark is embedded as an image.
    svg = "data:image/svg+xml;base64," + base64.b64encode(LOGO_SVG.encode()).decode()
    return (
        f'<img class="jo-mark" src="{svg}" alt="{NAME} 로고" style="width:{size * 5 // 3}px;height:{size}px">'
        f'<span class="jo-wordmark"><b>{NAME}</b><span>{NAME_EN}</span></span>'
    )


def header_markup(status: str, ready: bool) -> str:
    state = "ok" if ready else "warn"
    return f"""
<header class="jo-header" aria-label="{NAME}">
  <div class="jo-brand">{logo_markup(size=38)}<span class="jo-tagline">{TAGLINE}</span></div>
  <span class="jo-status jo-status-{state}"><span class="jo-dot" aria-hidden="true"></span>{html.escape(status)}</span>
</header>"""


def step_badge(number: int, title: str, note: str = "") -> str:
    tail = f'<span class="jo-step-note">{html.escape(note)}</span>' if note else ""
    return f'<div class="jo-step"><span class="jo-step-no">{number}</span><b>{html.escape(title)}</b>{tail}</div>'


CSS = f"""
<style>
:root {{
  --jo-primary:{PRIMARY}; --jo-primary-hover:{PRIMARY_HOVER}; --jo-secondary:{SECONDARY}; --jo-tint:{TINT};
  --jo-accent:{ACCENT}; --jo-bg:{BACKGROUND}; --jo-surface:{SURFACE}; --jo-border:{BORDER};
  --jo-text:{TEXT}; --jo-muted:{MUTED};
  --jo-shadow: 0 1px 2px rgba(15,23,42,.05), 0 6px 20px rgba(15,27,45,.06);
}}

/* Layout: readable column, room for the sticky header. */
[data-testid="stMainBlockContainer"] {{ max-width:1080px; padding-top:0.75rem; padding-bottom:6rem; }}
[data-testid="stBottomBlockContainer"] {{ max-width:1080px; }}
[data-testid="stHeader"] {{ background:transparent; height:0; }}
h1, h2, h3, h4 {{ scroll-margin-top:96px; color:var(--jo-text); }}

/* Sticky brand header. The element container is the sticky box so it spans the page. */
[data-testid="stElementContainer"]:has(.jo-header) {{ position:sticky; top:0; z-index:999; }}
.jo-header {{
  display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
  padding:10px 16px; margin:0 -16px; background:rgba(255,255,255,0.92); backdrop-filter:blur(8px);
  -webkit-backdrop-filter:blur(8px); border-bottom:1px solid var(--jo-border);
}}
.jo-brand {{ display:flex; align-items:center; gap:12px; min-width:0; }}
.jo-mark {{ display:block; flex:none; }}
.jo-wordmark {{ display:flex; flex-direction:column; line-height:1.1; }}
.jo-wordmark b {{ font-size:1.25rem; color:var(--jo-primary); letter-spacing:-0.02em; }}
.jo-wordmark span {{ font-size:0.8rem; color:#0284C7; font-weight:600; }}
.jo-logo-img {{ display:block; width:auto; }}
.jo-tagline {{ color:var(--jo-muted); font-size:0.85rem; border-left:1px solid var(--jo-border); padding-left:12px; }}
.jo-status {{ display:inline-flex; align-items:center; gap:8px; font-size:0.82rem; font-weight:600;
  padding:5px 12px; border-radius:999px; border:1px solid var(--jo-border); background:var(--jo-surface); color:var(--jo-text); }}
.jo-dot {{ width:8px; height:8px; border-radius:50%; background:var(--jo-accent); }}
.jo-status-warn {{ color:#9A3412; border-color:#FDBA74; background:#FFF7ED; }}
@media (max-width: 720px) {{ .jo-tagline {{ display:none; }} .jo-header {{ padding-left:48px; }} }}

/* Sidebar */
[data-testid="stSidebar"] {{ border-right:1px solid var(--jo-border); }}
.jo-side-brand {{ display:flex; align-items:center; gap:10px; margin-bottom:4px; }}
.jo-side-intro {{ color:var(--jo-muted); font-size:0.85rem; margin:0 0 4px; }}
.jo-data {{ font-size:0.85rem; }}
.jo-data h5 {{ font-size:0.8rem; color:var(--jo-muted); margin:10px 0 6px; font-weight:700; }}
.jo-data ul {{ list-style:none; margin:0; padding:0; }}
.jo-data li {{ display:flex; gap:8px; align-items:flex-start; padding:6px 0; border-top:1px solid var(--jo-border); }}
.jo-data li:first-child {{ border-top:0; }}
.jo-pill {{ flex:none; font-size:0.72rem; font-weight:700; padding:1px 8px; border-radius:999px; margin-top:2px; }}
.jo-pill-ok {{ background:#E0F2FE; color:#075985; }}
.jo-pill-off {{ background:#FFF7ED; color:#9A3412; }}
.jo-pill-plan {{ background:#F1F5F9; color:#475569; }}
.jo-data small {{ display:block; color:var(--jo-muted); }}
[class*="st-key-history_"] button {{ min-height:40px; }}
[class*="st-key-history_"] button > div {{ justify-content:flex-start; width:100%; }}
[class*="st-key-history_"] button p {{ text-align:left; font-size:0.86rem; }}

/* Cards: quick start, question box, answer. */
.st-key-qs_market, .st-key-qs_arrivals, .st-key-qs_join {{
  position:relative; background:var(--jo-surface); border:1px solid var(--jo-border); border-top:3px solid var(--jo-primary);
  border-radius:10px; padding:14px 16px 10px; box-shadow:var(--jo-shadow); transition:transform .15s ease, border-color .15s ease;
}}
.st-key-qs_arrivals {{ border-top-color:{SECONDARY}; }}
.st-key-qs_join {{ border-top-color:#94A3B8; }}
.st-key-qs_market:hover, .st-key-qs_arrivals:hover, .st-key-qs_join:hover {{ transform:translateY(-2px); border-color:var(--jo-secondary); }}
/* The whole card is the button. */
.st-key-qs_market [data-testid="stElementContainer"], .st-key-qs_arrivals [data-testid="stElementContainer"],
.st-key-qs_join [data-testid="stElementContainer"],
.st-key-qs_market .stButton, .st-key-qs_arrivals .stButton, .st-key-qs_join .stButton,
.st-key-qs_market .stButton button, .st-key-qs_arrivals .stButton button, .st-key-qs_join .stButton button {{ position:static; }}
.st-key-qs_market .stButton button::after, .st-key-qs_arrivals .stButton button::after, .st-key-qs_join .stButton button::after {{
  content:""; position:absolute; inset:0; border-radius:10px; z-index:1;
}}
.jo-qs-tag {{ display:inline-block; font-size:0.72rem; font-weight:700; padding:1px 8px; border-radius:999px; background:var(--jo-tint); color:var(--jo-primary); }}
.jo-qs-title {{ font-size:1.02rem; font-weight:700; margin:6px 0 2px; color:var(--jo-text); }}
.jo-qs-body {{ font-size:0.86rem; color:var(--jo-muted); margin:0; min-height:2.6em; }}

.st-key-ask_card [data-testid="stForm"] {{ background:var(--jo-surface); border:1px solid var(--jo-border); border-radius:12px; box-shadow:var(--jo-shadow); padding:18px 20px; }}
.st-key-ask_card [data-baseweb="textarea"]:focus-within {{ border-color:var(--jo-secondary) !important; box-shadow:0 0 0 3px rgba(56,189,248,.25); }}
.st-key-ask_card textarea {{ font-size:1rem; }}
.jo-input-meta {{ display:flex; align-items:center; flex-wrap:wrap; gap:8px; color:var(--jo-muted); font-size:0.85rem; }}
.jo-kbd {{ font-family:inherit; font-size:0.78rem; border:1px solid var(--jo-border); border-bottom-width:2px; border-radius:5px; padding:0 6px; background:var(--jo-surface); color:var(--jo-text); }}
.jo-mode {{ font-size:0.75rem; font-weight:700; padding:1px 9px; border-radius:999px; background:var(--jo-tint); color:var(--jo-primary); }}
.jo-mode-example {{ background:#FFF1E2; color:#9A3412; }}

.st-key-headline {{ background:var(--jo-surface); border:1px solid var(--jo-border); border-left:4px solid var(--jo-primary); border-radius:10px; padding:4px 18px 2px; box-shadow:var(--jo-shadow); }}
.st-key-headline h4 {{ color:var(--jo-primary); line-height:1.45; }}

/* Buttons: primary is navy; secondary is a quiet outline. */
button[kind="primary"], button[kind="primaryFormSubmit"] {{ background:var(--jo-primary); border-color:var(--jo-primary); }}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {{ background:var(--jo-primary-hover); border-color:var(--jo-primary-hover); }}
button:focus-visible {{ outline:3px solid var(--jo-secondary) !important; outline-offset:2px; }}

/* Tabs: active tab is bold with a navy underline. */
[data-baseweb="tab-list"] button[role="tab"] p {{ color:var(--jo-muted); font-size:0.95rem; }}
[data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] p {{ color:var(--jo-primary); font-weight:700; }}
[data-baseweb="tab-highlight"] {{ background-color:var(--jo-primary) !important; height:3px; }}
[data-baseweb="tab-border"] {{ background-color:var(--jo-border); }}

/* Role pills: navy when selected, white with a border otherwise. */
.st-key-role button[aria-checked="false"] {{ background:var(--jo-surface); border:1px solid var(--jo-border); color:var(--jo-text); padding:4px 14px; }}
.st-key-role button[aria-checked="false"]:hover {{ border-color:var(--jo-secondary); color:var(--jo-primary); }}
.st-key-role button[aria-checked="true"] {{ background:var(--jo-primary) !important; border-color:var(--jo-primary) !important; }}
.st-key-role button[aria-checked="true"] p {{ color:#fff; font-weight:700; }}

/* Example question cards (two columns). */
.st-key-examples .stButton button {{
  justify-content:flex-start; text-align:left; min-height:56px; padding:10px 14px; background:var(--jo-surface);
  border:1px solid var(--jo-border); border-radius:10px; transition:transform .15s ease, border-color .15s ease, box-shadow .15s ease;
}}
.st-key-examples .stButton button > div {{ justify-content:flex-start; width:100%; }}
.st-key-examples .stButton button p {{ text-align:left; }}
.st-key-examples .stButton button:hover {{ border-color:var(--jo-secondary); transform:translateY(-2px); box-shadow:var(--jo-shadow); color:var(--jo-text); }}

/* Guided choices: numbered steps. */
.jo-step {{ display:flex; align-items:center; gap:10px; margin:2px 0 6px; color:var(--jo-text); }}
.jo-step-no {{ display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%;
  background:var(--jo-primary); color:#fff; font-size:0.8rem; font-weight:700; }}
.jo-step-note {{ color:var(--jo-muted); font-size:0.82rem; }}
div[class*="st-key-"][class*="_step_"] {{ background:var(--jo-surface); border:1px solid var(--jo-border); border-radius:10px; padding:12px 14px; }}

[data-testid="stMetric"] {{ background:var(--jo-surface); }}

@media (prefers-reduced-motion: reduce) {{
  * {{ transition:none !important; }}
  .st-key-qs_market:hover, .st-key-qs_arrivals:hover, .st-key-qs_join:hover, .st-key-examples .stButton button:hover {{ transform:none; }}
}}
</style>
"""
