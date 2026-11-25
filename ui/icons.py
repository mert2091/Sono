"""
Sono Vektör İkon Motoru (Lucide SVG -> HiDPI Çift Temalı CTkImage).

`assets/icons/` altındaki MIT lisanslı Lucide SVG dosyalarını dış kütüphane
gerektirmeden (saf Python + Pillow 8x supersampling) yuvarlatılmış uçlu keskin
çizgi ikonlara dönüştürür. Her ikon hem Açık hem Koyu tema renk çiftleriyle
(`CTkImage(light_image=..., dark_image=...)`) üretilir ve önbelleklenir.
"""

from __future__ import annotations

import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Union

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui.theme import ColorToken, TEXT_MAIN

_SVG_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_ICON_CACHE: Dict[tuple, ctk.CTkImage] = {}

_ALIASES = {
    "home": "audio-waveform",
    "studio": "audio-waveform",
    "book": "book-open",
    "upload": "cloud-upload",
    "volume_on": "volume-2",
    "volume_mute": "volume-x",
    "alert": "info",
    "trash-2": "trash",
    "circle-alert": "info",
}


def _icons_dir() -> str:
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "assets", "icons")


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _sample_cubic(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    steps: int = 18,
) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = (mt**3) * p0[0] + 3 * (mt**2) * t * p1[0] + 3 * mt * (t**2) * p2[0] + (t**3) * p3[0]
        y = (mt**3) * p0[1] + 3 * (mt**2) * t * p1[1] + 3 * mt * (t**2) * p2[1] + (t**3) * p3[1]
        pts.append((x, y))
    return pts


def _sample_quadratic(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    steps: int = 14,
) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = (mt**2) * p0[0] + 2 * mt * t * p1[0] + (t**2) * p2[0]
        y = (mt**2) * p0[1] + 2 * mt * t * p1[1] + (t**2) * p2[1]
        pts.append((x, y))
    return pts


def _sample_svg_arc(
    x1: float,
    y1: float,
    rx: float,
    ry: float,
    phi_deg: float,
    large_arc: int,
    sweep: int,
    x2: float,
    y2: float,
    steps: int = 20,
) -> List[Tuple[float, float]]:
    """SVG 1.1 F.6.5 endpoint-to-center eliptik yay örneklemesi."""
    if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-9 or ry < 1e-9:
        return [(x2, y2)]

    phi = math.radians(phi_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx2 = (x1 - x2) / 2.0
    dy2 = (y1 - y2) / 2.0
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1.0:
        s = math.sqrt(lam)
        rx *= s
        ry *= s

    num = max(0.0, rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(num / den) if den > 1e-12 else 0.0
    if large_arc == sweep:
        coef = -coef

    cxp = coef * (rx * y1p / ry)
    cyp = coef * (-ry * x1p / rx)

    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2.0

    def _angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        mag = math.hypot(ux, uy) * math.hypot(vx, vy)
        if mag < 1e-12:
            return 0.0
        val = max(-1.0, min(1.0, dot / mag))
        ang = math.acos(val)
        return -ang if (ux * vy - uy * vx) < 0 else ang

    theta1 = _angle(1.0, 0.0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = _angle(
        (x1p - cxp) / rx,
        (y1p - cyp) / ry,
        (-x1p - cxp) / rx,
        (-y1p - cyp) / ry,
    )
    if not sweep and dtheta > 0:
        dtheta -= 2.0 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2.0 * math.pi

    n = max(8, int(steps * abs(dtheta) / (math.pi / 2.0)))
    pts: List[Tuple[float, float]] = []
    for i in range(1, n + 1):
        ang = theta1 + dtheta * (i / n)
        ca, sa = math.cos(ang), math.sin(ang)
        px = cos_p * rx * ca - sin_p * ry * sa + cx
        py = sin_p * rx * ca + cos_p * ry * sa + cy
        pts.append((px, py))
    return pts


_SVG_NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _parse_svg_path(d: str) -> List[Tuple[List[Tuple[float, float]], bool]]:
    """SVG 1.1 path `d` dizesini alt yol polilinelerine [(pts, closed), ...] çevirir."""
    subpaths: List[Tuple[List[Tuple[float, float]], bool]] = []
    cur: List[Tuple[float, float]] = []
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0
    last_ctrl: Optional[Tuple[float, float]] = None
    last_cmd = ""
    n = len(d)
    pos = 0

    def _skip_sep() -> None:
        nonlocal pos
        while pos < n and d[pos] in " \t\r\n,":
            pos += 1

    def _has_num() -> bool:
        _skip_sep()
        return pos < n and (d[pos] in "+-." or d[pos].isdigit())

    def _next_float() -> float:
        nonlocal pos
        _skip_sep()
        m = _SVG_NUM_RE.match(d, pos)
        if not m:
            raise ValueError(f"Expected number at {pos} in SVG path: {d[pos:pos+16]!r}")
        pos = m.end()
        return float(m.group(0))

    def _next_flag() -> int:
        nonlocal pos
        _skip_sep()
        if pos < n and d[pos] in ("0", "1"):
            val = int(d[pos])
            pos += 1
            return val
        raise ValueError(f"Expected arc flag 0/1 at {pos} in SVG path: {d[pos:pos+16]!r}")

    cmd = ""
    while True:
        _skip_sep()
        if pos >= n:
            break
        if d[pos].isalpha():
            cmd = d[pos]
            pos += 1
        elif not cmd:
            break

        if cmd in ("M", "m"):
            if cur:
                subpaths.append((cur, False))
                cur = []
            x, y = _next_float(), _next_float()
            if cmd == "m":
                x += cx
                y += cy
            cx, cy = x, y
            sx, sy = x, y
            cur = [(cx, cy)]
            last_ctrl = None
            last_cmd = cmd
            cmd = "L" if cmd == "M" else "l"
            continue

        if cmd in ("L", "l"):
            while _has_num():
                x, y = _next_float(), _next_float()
                if cmd == "l":
                    x += cx
                    y += cy
                cx, cy = x, y
                cur.append((cx, cy))
            last_ctrl = None

        elif cmd in ("H", "h"):
            while _has_num():
                x = _next_float()
                cx = cx + x if cmd == "h" else x
                cur.append((cx, cy))
            last_ctrl = None

        elif cmd in ("V", "v"):
            while _has_num():
                y = _next_float()
                cy = cy + y if cmd == "v" else y
                cur.append((cx, cy))
            last_ctrl = None

        elif cmd in ("C", "c"):
            while _has_num():
                x1, y1 = _next_float(), _next_float()
                x2, y2 = _next_float(), _next_float()
                x, y = _next_float(), _next_float()
                if cmd == "c":
                    x1 += cx
                    y1 += cy
                    x2 += cx
                    y2 += cy
                    x += cx
                    y += cy
                cur.extend(_sample_cubic((cx, cy), (x1, y1), (x2, y2), (x, y)))
                last_ctrl = (x2, y2)
                cx, cy = x, y

        elif cmd in ("S", "s"):
            while _has_num():
                if last_cmd in ("C", "c", "S", "s") and last_ctrl is not None:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                x2, y2 = _next_float(), _next_float()
                x, y = _next_float(), _next_float()
                if cmd == "s":
                    x2 += cx
                    y2 += cy
                    x += cx
                    y += cy
                cur.extend(_sample_cubic((cx, cy), (x1, y1), (x2, y2), (x, y)))
                last_ctrl = (x2, y2)
                cx, cy = x, y

        elif cmd in ("Q", "q"):
            while _has_num():
                x1, y1 = _next_float(), _next_float()
                x, y = _next_float(), _next_float()
                if cmd == "q":
                    x1 += cx
                    y1 += cy
                    x += cx
                    y += cy
                cur.extend(_sample_quadratic((cx, cy), (x1, y1), (x, y)))
                last_ctrl = (x1, y1)
                cx, cy = x, y

        elif cmd in ("A", "a"):
            while _has_num():
                rx = _next_float()
                ry = _next_float()
                rot = _next_float()
                large = _next_flag()
                sweep = _next_flag()
                x, y = _next_float(), _next_float()
                if cmd == "a":
                    x += cx
                    y += cy
                cur.extend(_sample_svg_arc(cx, cy, rx, ry, rot, large, sweep, x, y))
                cx, cy = x, y
            last_ctrl = None

        elif cmd in ("Z", "z"):
            if cur:
                if math.hypot(cx - sx, cy - sy) > 1e-4:
                    cur.append((sx, sy))
                subpaths.append((cur, True))
                cur = []
            cx, cy = sx, sy
            last_ctrl = None

        last_cmd = cmd

    if cur:
        subpaths.append((cur, False))
    return subpaths


def _draw_rounded_polyline(
    draw: ImageDraw.ImageDraw,
    pts: List[Tuple[float, float]],
    rgba: Tuple[int, int, int, int],
    width: int,
    closed: bool = False,
    filled: bool = False,
) -> None:
    if not pts:
        return
    r = width / 2.0
    if filled and len(pts) >= 3:
        draw.polygon(pts, fill=rgba)
        return
    if len(pts) == 1:
        x, y = pts[0]
        draw.ellipse((x - r, y - r, x + r, y + r), fill=rgba)
        return

    draw.line(pts, fill=rgba, width=width, joint="curve")
    # Yuvarlatılmış uçlar (stroke-linecap: round) ve keskin köşe dikişleri
    endpoints = [pts[0], pts[-1]] if not closed else []
    for x, y in endpoints:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=rgba)
    for x, y in pts[1:-1]:
        draw.ellipse((x - r * 0.92, y - r * 0.92, x + r * 0.92, y + r * 0.92), fill=rgba)


def _render_svg_to_pil(
    svg_path: str,
    size: int,
    hex_color: str,
    stroke_width: float = 2.0,
    filled: bool = False,
) -> Image.Image:
    render_scale = 8
    out_scale = 3
    canvas_px = size * render_scale
    scale = canvas_px / 24.0

    img = Image.new("RGBA", (canvas_px, canvas_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rgba = _hex_to_rgba(hex_color)
    w = max(3, int(round(stroke_width * scale)))

    tree = ET.parse(svg_path)
    root = tree.getroot()

    for el in root:
        tag = el.tag.split("}")[-1]
        if tag == "path":
            d = el.attrib.get("d", "")
            for pts, closed in _parse_svg_path(d):
                scaled = [(x * scale, y * scale) for x, y in pts]
                _draw_rounded_polyline(draw, scaled, rgba, w, closed=closed, filled=filled)

        elif tag == "circle":
            cx = float(el.attrib.get("cx", 0)) * scale
            cy = float(el.attrib.get("cy", 0)) * scale
            r = float(el.attrib.get("r", 0)) * scale
            bbox = (cx - r, cy - r, cx + r, cy + r)
            if filled:
                draw.ellipse(bbox, fill=rgba)
            else:
                draw.ellipse(bbox, outline=rgba, width=w)

        elif tag == "rect":
            x = float(el.attrib.get("x", 0)) * scale
            y = float(el.attrib.get("y", 0)) * scale
            rw = float(el.attrib.get("width", 0)) * scale
            rh = float(el.attrib.get("height", 0)) * scale
            rx = float(el.attrib.get("rx", el.attrib.get("ry", 0))) * scale
            bbox = (x, y, x + rw, y + rh)
            if filled:
                draw.rounded_rectangle(bbox, radius=rx, fill=rgba)
            else:
                draw.rounded_rectangle(bbox, radius=rx, outline=rgba, width=w)

        elif tag == "line":
            x1 = float(el.attrib.get("x1", 0)) * scale
            y1 = float(el.attrib.get("y1", 0)) * scale
            x2 = float(el.attrib.get("x2", 0)) * scale
            y2 = float(el.attrib.get("y2", 0)) * scale
            _draw_rounded_polyline(draw, [(x1, y1), (x2, y2)], rgba, w)

        elif tag in ("polyline", "polygon"):
            nums = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", el.attrib.get("points", ""))]
            pts = [(nums[j] * scale, nums[j + 1] * scale) for j in range(0, len(nums) - 1, 2)]
            if tag == "polygon" and pts:
                pts.append(pts[0])
            _draw_rounded_polyline(draw, pts, rgba, w, closed=(tag == "polygon"), filled=filled)

    out_px = size * out_scale
    return img.resize((out_px, out_px), Image.Resampling.LANCZOS)


def _fallback_pil(size: int, hex_color: str) -> Image.Image:
    out_px = size * 3
    img = Image.new("RGBA", (out_px, out_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rgba = _hex_to_rgba(hex_color)
    m = out_px * 0.25
    draw.ellipse((m, m, out_px - m, out_px - m), outline=rgba, width=max(2, out_px // 12))
    return img


def get_icon(
    name: str,
    size: int = 16,
    color: ColorToken = TEXT_MAIN,
    stroke_width: float = 1.9,
    filled: bool = False,
) -> ctk.CTkImage:
    """
    Lucide SVG ikonunu Açık ve Koyu tema renk çiftiyle HiDPI CTkImage olarak döndürür.

    `color` tek hex ('#FFFFFF') ya da `(light_hex, dark_hex)` ikilisi olabilir.
    """
    resolved_name = _ALIASES.get(name, name)
    if isinstance(color, tuple) and len(color) >= 2:
        light_hex, dark_hex = color[0], color[1]
    else:
        light_hex = dark_hex = str(color)

    cache_key = (resolved_name, size, light_hex, dark_hex, round(stroke_width, 2), bool(filled))
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    svg_path = os.path.join(_icons_dir(), f"{resolved_name}.svg")
    if os.path.exists(svg_path):
        try:
            light_img = _render_svg_to_pil(svg_path, size, light_hex, stroke_width=stroke_width, filled=filled)
            dark_img = (
                light_img
                if dark_hex == light_hex
                else _render_svg_to_pil(svg_path, size, dark_hex, stroke_width=stroke_width, filled=filled)
            )
        except Exception:
            light_img = _fallback_pil(size, light_hex)
            dark_img = _fallback_pil(size, dark_hex)
    else:
        light_img = _fallback_pil(size, light_hex)
        dark_img = _fallback_pil(size, dark_hex)

    ctk_img = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))
    _ICON_CACHE[cache_key] = ctk_img
    return ctk_img
