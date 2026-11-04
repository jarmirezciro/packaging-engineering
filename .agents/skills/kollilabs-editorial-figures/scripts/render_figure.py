#!/usr/bin/env python3
"""Deterministic KolliLabs editorial figure composer (subject artwork supplied separately).

This is not a packing-geometry engine, image generator, or source-evidence validator.
It composes labels/cards from a small JSON specification and full-resolution art.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is needed to render figures: python -m pip install Pillow") from exc

SKILL = Path(__file__).resolve().parents[1]
DEFAULT_TOKENS = SKILL / "assets" / "design-tokens.json"
LAYOUTS = {"setup_flow", "concept_flow", "tradeoff", "comparison", "summary", "single_explainer"}
REQUIRED = ("version", "role", "layout", "purpose", "headline", "subtitle", "cards", "caption", "alt_text")
COLOR_KEYS = ("background", "card", "navy", "muted", "green", "mint", "border", "detail_strip", "takeaway")


def fail(message: str):
    raise ValueError(message)


def check_spec(spec: dict, spec_file: Path) -> list[Path]:
    if not isinstance(spec, dict):
        fail("Specification must be a JSON object.")
    for key in REQUIRED:
        if key not in spec:
            fail(f"Missing required field: {key}")
    if spec["version"] != "1.0":
        fail("Expected figure spec version 1.0")
    if spec["role"] not in {"conceptual", "evidence_derived"}:
        fail("role must be conceptual or evidence_derived")
    if spec["layout"] not in LAYOUTS:
        fail("Invalid layout")
    for k in ("purpose", "headline", "subtitle", "caption", "alt_text"):
        if not isinstance(spec[k], str) or not spec[k].strip():
            fail(f"{k} must be nonempty text")
    if spec["role"] == "evidence_derived" and not str(spec.get("source_notes", "")).strip():
        fail("Evidence-derived figures require source_notes; composition alone cannot verify evidence")
    cards = spec["cards"]
    if not isinstance(cards, list) or not 1 <= len(cards) <= 5:
        fail("cards must contain between one and five entries")
    if spec["layout"] == "single_explainer" and len(cards) > 2:
        fail("single_explainer allows at most two cards")
    resolved = []
    origin = spec_file.parent.resolve()
    for i, item in enumerate(cards, 1):
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            fail(f"Card {i} requires a title")
        detail = item.get("detail_lines", [])
        if not isinstance(detail, list) or len(detail) > 3 or any(not isinstance(v, str) for v in detail):
            fail(f"Card {i} detail_lines must have 0–3 text strings")
        if not isinstance(item.get("illustration"), str):
            fail(f"Card {i} requires an illustration file")
        art_path = (origin / item["illustration"]).resolve()
        try:
            art_path.relative_to(origin)
        except ValueError:
            fail(f"Card {i} illustration path must remain inside the spec directory")
        if not art_path.is_file():
            fail(f"Missing illustration: {art_path}")
        try:
            with Image.open(art_path) as art:
                art.verify()
        except Exception as exc:
            fail(f"Card {i} illustration is not readable: {exc}")
        resolved.append(art_path)
    return resolved


def font_path(weight: str) -> str:
    """Choose an installed font; never distribute or embed font binaries."""
    styles = {"bold": [
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ], "regular": [
        "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]}
    for p in styles[weight]:
        if Path(p).is_file():
            return p
    try:
        family = "Inter:style=Bold" if weight == "bold" else "Inter:style=Regular"
        p = subprocess.check_output(["fc-match", "-f", "%{file}", family], text=True).strip()
        if p and Path(p).is_file():
            return p
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return "DejaVuSans-Bold.ttf" if weight == "bold" else "DejaVuSans.ttf"


FONTS = {}

def get_font(size: int, weight: str):
    key = (size, weight)
    if key not in FONTS:
        try:
            FONTS[key] = ImageFont.truetype(font_path(weight), size)
        except OSError as exc:
            raise ValueError("No usable system sans-serif font. Provide Inter/Arial/DejaVu Sans.") from exc
    return FONTS[key]


def measure(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    words = text.strip().split()
    if not words:
        return []
    lines = [words[0]]
    for word in words[1:]:
        proposed = lines[-1] + " " + word
        if measure(draw, proposed, font) <= max_w:
            lines[-1] = proposed
        else:
            lines.append(word)
    if any(measure(draw, ln, font) > max_w for ln in lines):
        fail("One word or token is too wide for the layout; shorten or introduce an explicit space")
    return lines


def fitting_lines(draw, text, max_w, max_lines, start_size, min_size, weight="regular"):
    for size in range(start_size, min_size - 1, -1):
        font = get_font(size, weight)
        lines = wrap_text(draw, text, font, max_w)
        if len(lines) <= max_lines:
            return lines, font, size
    fail(f"Text does not fit at readable size: {text[:70]!r}. Shorten the copy.")


def centered(draw, x, y, text, font, color, width):
    tw = measure(draw, text, font)
    draw.text((int(x + (width - tw) / 2), int(y)), text, fill=color, font=font)


def draw_arrow(draw, x1, y, x2, color):
    if x2 - x1 < 24:
        return
    d = 9
    draw.line([(x1, y), (x2-10, y)], fill=color, width=7, joint="curve")
    draw.polygon([(x2, y), (x2-16, y-d), (x2-16, y+d)], fill=color)


def draw_card(img, draw, card, art_path, x, y, w, h, index, tk):
    color = tk["colors"]
    z = tk["layout"]
    typo = tk["typography"]
    draw.rounded_rectangle((x, y, x+w, y+h), radius=z["card_radius"], fill=color["card"], outline=color["border"], width=2)
    bx, by = x+24, y+25
    draw.rounded_rectangle((bx,by,bx+z["badge_width"],by+z["badge_height"]),radius=z["badge_radius"],fill=color["mint"])
    centered(draw,bx,by+11,f"{index:02d}",get_font(typo["badge_size"], "bold"),color["green"],z["badge_width"])
    head_x = x+119
    title_lines, tf, ts = fitting_lines(draw, card["title"], w-147, 2, typo["card_title_size"], 24, "bold")
    for j, line in enumerate(title_lines):
        draw.text((head_x, y+37+j*(ts+2)), line, font=tf,fill=color["navy"])
    if card.get("subheading"):
        sub_lines, sf, ss = fitting_lines(draw,card["subheading"],w-147,1,typo["card_subtitle_size"],18)
        draw.text((head_x,y+41+len(title_lines)*(ts+3)),sub_lines[0],font=sf,fill=color["muted"])

    art_top = y+z["art_top_offset"]
    art_bottom = y+h-z["art_bottom_gap"]
    art_box = (x+23, art_top, x+w-23, art_bottom)
    with Image.open(art_path) as src:
        art = src.convert("RGBA")
    maxw = art_box[2]-art_box[0]
    maxh = art_box[3]-art_box[1]
    art.thumbnail((maxw,maxh),Image.Resampling.LANCZOS)
    ix = int(art_box[0]+(maxw-art.width)/2)
    iy = int(art_box[1]+(maxh-art.height)/2)
    if art.getpixel((0,0))[3] < 255:
        img.alpha_composite(art,(ix,iy))
    else:
        img.paste(art,(ix,iy))

    lines = card.get("detail_lines", [])
    if lines:
        strip_h = z["strip_height"]
        sx1=x+22; sx2=x+w-22; sy2=y+h-z["strip_bottom_margin"]; sy1=sy2-strip_h
        draw.rounded_rectangle((sx1,sy1,sx2,sy2),radius=20, fill=color["detail_strip"])
        blocks = []
        for phrase in lines:
            lns,font,size = fitting_lines(draw, phrase, sx2-sx1-26, 2, typo["detail_size"], 20)
            blocks.append((lns,font,size))
        total_lines = sum(len(t[0]) for t in blocks)
        line_h = 29 if total_lines <= 3 else 24
        total = (total_lines-1)*line_h+28
        start_y = int(sy1+(strip_h-total)/2)
        for lns,font,size in blocks:
            for ln in lns:
                centered(draw,sx1,start_y,ln,font,color["muted"],sx2-sx1)
                start_y += line_h
            if start_y > sy2:
                fail("Card strip text overflow; shorten details")


def render(spec, arts, tokens):
    n=len(spec["cards"])
    tk=tokens
    colors=tk["colors"]; z=tk["layout"]; typo=tk["typography"]
    rows=(n+2)//3
    W=tk["canvas"]["width"]
    H=tk["canvas"]["single_row_height"] if rows==1 else tk["canvas"]["two_row_height"]
    img=Image.new("RGBA",(W,H),colors["background"])
    draw=ImageDraw.Draw(img)
    draw.rounded_rectangle((z["header_line_x"],z["header_line_y"],z["header_line_x"]+z["header_line_width"],z["header_line_y"]+z["header_line_height"]),radius=6,fill=colors["green"])
    headline, font, size=fitting_lines(draw,spec["headline"],W-105,1,typo["headline_size"],52,"bold")
    draw.text((z["header_line_x"],z["headline_y"]),headline[0],font=font,fill=colors["navy"])
    subt, font, ss = fitting_lines(draw,spec["subtitle"],W-105,2,typo["subtitle_size"],24)
    for idx, line in enumerate(subt):
        draw.text((z["header_line_x"],z["subtitle_y"]+idx*(ss+7)),line,font=font,fill=colors["muted"])

    global_index=0
    y=z["cards_top"]
    # Balanced 2x2 for four cards; 3+2 for five cards, never 3+1.
    row_sizes = ([2, 2] if n == 4 else [3, 2] if n == 5 else [n])
    offset = 0
    for row, row_size in enumerate(row_sizes):
        row_items=spec["cards"][offset:offset+row_size]
        row_art=arts[offset:offset+row_size]
        offset += row_size
        m=len(row_items)
        if rows==2 and m==1:
            # Avoid a huge full-width card in the second row; center one normal-width card.
            w=int((W-2*z["page_margin"]-2*z["card_gap_x"])/3)
            xs=[int((W-w)/2)]
        else:
            w=int((W-2*z["page_margin"]-(m-1)*z["card_gap_x"])/m)
            total=m*w+(m-1)*z["card_gap_x"]
            x0=int((W-total)/2)
            xs=[x0+i*(w+z["card_gap_x"]) for i in range(m)]
        for i, (card, art) in enumerate(zip(row_items,row_art)):
            global_index += 1
            draw_card(img,draw,card,art,xs[i],y,w,z["card_height"],global_index,tk)
        directional = spec.get("arrows")
        if directional is None:
            directional=spec["layout"] in {"setup_flow","concept_flow"}
        if directional:
            for i in range(m-1):
                draw_arrow(draw,xs[i]+w+12,y+int(z["card_height"]*.48),xs[i+1]-12,colors["green"])
        y+=z["card_height"]+z["card_gap_y"]

    takeaway=spec.get("takeaway","").strip()
    if takeaway:
        fy=y-z["card_gap_y"]+z["takeaway_gap"]
        if fy+z["takeaway_height"]>H-18:
            fail("Takeaway would extend beyond the canvas")
        draw.rounded_rectangle((z["page_margin"],fy,W-z["page_margin"],fy+z["takeaway_height"]),radius=z["takeaway_radius"],fill=colors["takeaway"])
        draw.rounded_rectangle((z["page_margin"]+44,fy+22,z["page_margin"]+51,fy+z["takeaway_height"]-22),radius=3,fill=colors["green"])
        tx=z["page_margin"]+84
        msg,f,fs=fitting_lines(draw,takeaway,W-z["page_margin"]-tx-35,2,typo["takeaway_size"],24,"bold")
        total=len(msg)*(fs+7)
        ty=fy+(z["takeaway_height"]-total)/2-2
        for i,s in enumerate(msg):
            draw.text((tx,int(ty+i*(fs+7))),s,font=f,fill=colors["navy"])
    return img.convert("RGB")


def render_mobile(spec, arts, tokens):
    """Reflow as vertically stacked 720px retina artwork for a 360 CSS-pixel device.

    Merely shrinking three desktop columns would leave card labels illegible.
    """
    tk = copy.deepcopy(tokens)
    tk["canvas"]["width"] = 720
    z=tk["layout"]
    z.update({
        "page_margin": 25, "header_line_x": 30, "header_line_y": 25,
        "header_line_width": 82, "header_line_height": 9,
        "headline_y": 59, "card_height": 620, "card_radius": 22,
        "art_top_offset": 128, "art_bottom_gap": 151,
        "strip_height": 116, "strip_bottom_margin": 21,
        "card_gap_y": 24, "takeaway_gap": 23,
        "takeaway_height": 132,
    })
    fonts=tk["typography"]
    fonts.update({
        "headline_size": 59, "subtitle_size": 29,
        "card_title_size": 36, "card_subtitle_size": 24,
        "badge_size": 37, "detail_size": 29,
        "takeaway_size": 30,
    })
    color=tk["colors"]
    layout_font=Image.new("RGB",(720,30),"white")
    temp_draw=ImageDraw.Draw(layout_font)
    head_lines, head_font, hs=fitting_lines(temp_draw,spec["headline"],660,2,fonts["headline_size"],46,"bold")
    subtitle_lines, subt_font, ss=fitting_lines(temp_draw,spec["subtitle"],660,3,fonts["subtitle_size"],23)
    head_end=z["headline_y"]+len(head_lines)*(hs+8)
    subtitle_y=head_end+9
    card_top=subtitle_y+len(subtitle_lines)*(ss+8)+28
    tk["layout"]["cards_top"]=card_top
    n=len(spec["cards"])
    end_cards=card_top+n*z["card_height"]+(n-1)*z["card_gap_y"]
    has_takeaway=bool(spec.get("takeaway","").strip())
    H=end_cards+(z["takeaway_gap"]+z["takeaway_height"] if has_takeaway else 0)+34
    img=Image.new("RGBA",(720,H),color["background"])
    draw=ImageDraw.Draw(img)
    draw.rounded_rectangle((z["header_line_x"],z["header_line_y"],z["header_line_x"]+z["header_line_width"],z["header_line_y"]+z["header_line_height"]),radius=5,fill=color["green"])
    for i,line in enumerate(head_lines):
        draw.text((z["header_line_x"],z["headline_y"]+i*(hs+8)),line,fill=color["navy"],font=head_font)
    for i,line in enumerate(subtitle_lines):
        draw.text((z["header_line_x"],subtitle_y+i*(ss+8)),line,fill=color["muted"],font=subt_font)
    for i,(card,art) in enumerate(zip(spec["cards"],arts)):
        yy=card_top+i*(z["card_height"]+z["card_gap_y"])
        draw_card(img,draw,card,art,z["page_margin"],yy,720-2*z["page_margin"],z["card_height"],i+1,tk)
    if has_takeaway:
        fy=end_cards+z["takeaway_gap"]
        draw.rounded_rectangle((z["page_margin"],fy,720-z["page_margin"],fy+z["takeaway_height"]),radius=24,fill=color["takeaway"])
        draw.rounded_rectangle((z["page_margin"]+20,fy+22,z["page_margin"]+27,fy+z["takeaway_height"]-22),radius=3,fill=color["green"])
        tx=z["page_margin"]+45
        lines,f,fs=fitting_lines(draw,spec["takeaway"],720-tx-z["page_margin"]-20,3,fonts["takeaway_size"],23,"bold")
        total=len(lines)*(fs+6)
        ty=fy+(z["takeaway_height"]-total)/2-2
        for j,line in enumerate(lines):
            draw.text((tx,int(ty+j*(fs+6))),line,font=f,fill=color["navy"])
    return img.convert("RGB")


def sha(path):
    digest=hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda:file.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec",required=True,type=Path)
    p.add_argument("--out",type=Path)
    p.add_argument("--preview",type=Path)
    p.add_argument("--report",type=Path)
    p.add_argument("--tokens",type=Path,default=DEFAULT_TOKENS)
    p.add_argument("--validate-only",action="store_true")
    args=p.parse_args()
    try:
        spec=json.loads(args.spec.read_text(encoding="utf-8"))
        tokens=json.loads(args.tokens.read_text(encoding="utf-8"))
        for key in COLOR_KEYS:
            if key not in tokens["colors"]:
                fail("Missing design token color: "+key)
        arts=check_spec(spec,args.spec)
        if args.validate_only:
            print("VALID: figure specification and illustration assets")
            return
        if not args.out:
            fail("--out is required unless --validate-only")
        image=render(spec,arts,tokens)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        image.save(args.out,quality=int(tokens["image"]["output_quality"]),method=6)
        if args.preview:
            args.preview.parent.mkdir(parents=True,exist_ok=True)
            mobile=render_mobile(spec,arts,tokens)
            # 720 physical pixels = 2x for typical 360 CSS-pixel mobile display.
            mobile.save(args.preview,quality=88,method=6)
        report={
            "spec_path":str(args.spec),"spec_sha256":sha(args.spec),
            "design_tokens_sha256":sha(args.tokens),
            "font_regular_resolved":font_path("regular"),
            "font_bold_resolved":font_path("bold"),
            "role":spec["role"],
            "layout":spec["layout"],"illustrations":[{"path":str(v),"sha256":sha(v)} for v in arts],
            "render_path":str(args.out),"render_sha256":sha(args.out),
            "mobile_preview_path":str(args.preview) if args.preview else None,
            "mobile_preview_size_px":list(mobile.size) if args.preview else None,
            "mobile_preview_sha256":sha(args.preview) if args.preview else None,
            "size_px":list(image.size),"render_status":"CREATED",
            "visual_qa":"NOT REVIEWED","evidence_validation":"NOT PERFORMED",
            "owner_approval":"REQUIRED","caption":spec["caption"],"alt_text":spec["alt_text"]
        }
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"CREATED {args.out} ({image.width}x{image.height}); visual QA still required")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.exit(2, f"ERROR: {exc}\n")


if __name__=="__main__":
    main()
