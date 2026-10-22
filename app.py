"""Local ultrasound video annotation prototype. Run: streamlit run app.py"""
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image
import streamlit.components.v1 as components

annotator = components.declare_component("us_annotator_canvas", path=str(Path(__file__).parent / "annotator_component"))

st.set_page_config(page_title="US Vessel Annotator", layout="wide")
st.markdown("""<style>
:root {--accent:#10bfa3;}
.stApp {background:linear-gradient(155deg,#f1f7fa 0%,#ffffff 45%,#eff7f7 100%);}
.block-container {padding-top:1.7rem;max-width:1440px;}
[data-testid="stSidebar"] {background:#112b3a;}
[data-testid="stSidebar"] * {color:#eaf5f7;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#172b36;}
[data-testid="stSidebar"] input {color:#172b36;}
.us-kicker {font-size:.76rem;letter-spacing:.17em;font-weight:800;color:#078a7d;margin-bottom:.35rem;}
.us-title {font-size:2.35rem;font-weight:850;color:#122f3f;line-height:1.15;margin-bottom:.4rem;}
.us-subtitle {color:#526d78;font-size:.95rem;margin-bottom:1.3rem;}
.us-status {background:#e6f7f2;color:#176b59;border:1px solid #b8e5d8;border-radius:12px;padding:.7rem 1rem;font-weight:650;}
.us-tip {background:#edf3f7;border-left:4px solid #0ea891;border-radius:8px;padding:.85rem 1rem;color:#244555;margin:.8rem 0 1rem;}
div.st-key-save_frame button {background:#138a55!important;color:#fff!important;border:0!important;border-radius:10px!important;font-weight:750!important;}
div.st-key-export_all button {background:#1764b0!important;color:#fff!important;border:0!important;border-radius:10px!important;font-weight:750!important;}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="us-kicker">ULTRASOUND · ANNOTATION STUDIO</div><div class="us-title">US Vessel Annotator</div><div class="us-subtitle">Contorni vascolari su ecografia · Vena e arteria · Esportazione per machine learning</div>', unsafe_allow_html=True)


def safe_stem(name):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(name).stem)[:70] or "video"


@st.cache_data(show_spinner="Estrazione frame...")
def sample_video(data, extension, n):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Video non leggibile da OpenCV.")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if total <= 0:
            raise ValueError("Numero di frame non disponibile.")
        indices = np.unique(np.linspace(0, total - 1, min(n, total), dtype=int))
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, bgr = cap.read()
            if not ok:
                continue
            frames.append((int(idx), cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
        cap.release()
        if not frames:
            raise ValueError("Impossibile decodificare i frame selezionati.")
        return frames, fps, total
    finally:
        path.unlink(missing_ok=True)


def png_bytes(array):
    output = io.BytesIO()
    Image.fromarray(array).save(output, format="PNG")
    return output.getvalue()


def canvas_to_mask(canvas_image, label, existing):
    """Interpret nontransparent canvas strokes as a class-specific edit."""
    result = existing.copy()
    if canvas_image is None:
        return result
    rgba = np.asarray(canvas_image).astype(np.uint8)
    if rgba.shape[:2] != existing.shape:
        rgba = cv2.resize(rgba, (existing.shape[1], existing.shape[0]), interpolation=cv2.INTER_NEAREST)
    painted = rgba[:, :, 3] > 10
    result[painted] = label
    return result


uploaded = st.file_uploader("Carica video ecografico", type=["mp4", "avi", "mov", "mkv"])
n = st.sidebar.number_input("Frame equidistanti", min_value=1, max_value=500, value=10)
if uploaded is None:
    st.info("Carica un video per iniziare.")
    st.stop()

content = uploaded.getvalue()
try:
    frames, fps, total = sample_video(content, Path(uploaded.name).suffix, int(n))
except ValueError as exc:
    st.error(str(exc))
    st.stop()

session_id = (uploaded.name, len(content), hash(content), int(n))
if st.session_state.get("session_id") != session_id:
    st.session_state.session_id = session_id
    st.session_state.masks = {idx: np.zeros(frame.shape[:2], np.uint8) for idx, frame in frames}
    st.session_state.history = {}
    st.session_state.future = {}
    st.session_state.frame_position = 0
    st.session_state.canvas_version = 0
    st.session_state.saved = {idx: False for idx, _ in frames}
    st.session_state.export_bytes = None

if "next_frame_position" in st.session_state:
    st.session_state.frame_position = st.session_state.pop("next_frame_position")

st.sidebar.write(f"Video: {total} frame · FPS: {fps:.2f}" if fps > 0 else f"Video: {total} frame")
position = st.sidebar.selectbox(
    "Frame da annotare", range(len(frames)),
    format_func=lambda i: f"{'✓ ' if st.session_state.saved[frames[i][0]] else '○ '}{i+1}/{len(frames)} · frame {frames[i][0]}",
    key="frame_position",
)
st.sidebar.caption(f"Frame salvati: {sum(st.session_state.saved.values())}/{len(frames)}")
st.sidebar.progress(sum(st.session_state.saved.values()) / len(frames))
idx, rgb = frames[position]
h, w = rgb.shape[:2]
mask = st.session_state.masks[idx]

label_name = st.sidebar.radio("Classe", ["Vena", "Arteria", "Gomma"], horizontal=False)
label = {"Vena": 1, "Arteria": 2, "Gomma": 0}[label_name]
brush = st.sidebar.slider("Diametro pennello (px)", 1, 20, 3)
zoom = st.sidebar.slider("Zoom visualizzazione", 1.0, 3.0, 1.0, 0.25)
opacity = st.sidebar.slider("Opacità maschera", 0.0, 0.8, 0.35, 0.05)

# Canvas works in image coordinates. Zoom is implemented by uniformly scaling
# the displayed image and strokes; the saved mask is always original resolution.
display_w, display_h = int(w * zoom), int(h * zoom)
base = rgb.copy()
base[mask == 1] = ((1-opacity)*base[mask == 1] + opacity*np.array([0, 230, 170])).astype(np.uint8)
base[mask == 2] = ((1-opacity)*base[mask == 2] + opacity*np.array([255, 145, 35])).astype(np.uint8)
background = Image.fromarray(base).resize((display_w, display_h))

st.markdown(f'<div class="us-status">FRAME {position+1:02d} / {len(frames):02d} &nbsp; · &nbsp; {"SALVATO" if st.session_state.saved[idx] else "DA COMPLETARE"} &nbsp; · &nbsp; Originale {w} × {h} px</div>', unsafe_allow_html=True)
st.markdown('<div class="us-tip"><b>Annotazione:</b> traccia il contorno completo del vaso con un unico gesto. Al rilascio, l’area interna viene riempita. Verde acqua = vena; arancione = arteria.</div>', unsafe_allow_html=True)
color = {1: "#00e6aa", 2: "#ff9123", 0: "#ff5555"}[label]
# The browser component draws on top of the ultrasound and returns only
# stroke coordinates. Masks remain on the server at original resolution.
image_b64 = __import__("base64").b64encode(png_bytes(np.asarray(background))).decode("ascii")
stroke = annotator(
    image=image_b64, width=display_w, height=display_h,
    color=color, brush=float(brush * zoom),
    key=f"canvas_{idx}_{st.session_state.canvas_version}", default=None,
)
if isinstance(stroke, dict) and stroke.get("points"):
    points = np.asarray(stroke["points"], dtype=float)
    if points.ndim == 2 and points.shape[1] == 2 and len(points) <= 20000:
        edit = np.zeros((h, w), np.uint8)
        coords = np.rint(points / zoom).astype(int)
        coords[:, 0] = np.clip(coords[:, 0], 0, w - 1)
        coords[:, 1] = np.clip(coords[:, 1], 0, h - 1)
        thickness = max(1, int(round(brush)))
        # Contour mode: a closed outline is converted into a filled region.
        # Avoid filling a stray click or a short accidental stroke.
        if label in (1, 2):
            unique_points = np.unique(coords, axis=0)
            if len(unique_points) < 8:
                st.warning("Contorno troppo corto: disegna il perimetro completo del vaso.")
                st.stop()
            contour = coords.reshape(-1, 1, 2).astype(np.int32)
            area = abs(cv2.contourArea(contour))
            if area < 10:
                st.warning("Contorno non valido: riprova disegnando tutto il perimetro.")
                st.stop()
            cv2.fillPoly(edit, [contour], 255)
            cv2.polylines(edit, [contour], True, 255, thickness, lineType=cv2.LINE_8)
        else:
            if len(coords) == 1:
                cv2.circle(edit, tuple(coords[0]), max(1, thickness // 2), 255, -1)
            else:
                cv2.polylines(edit, [coords.reshape(-1, 1, 2)], False, 255, thickness, lineType=cv2.LINE_8)
        st.session_state.history.setdefault(idx, []).append(mask.copy())
        st.session_state.future[idx] = []
        updated = mask.copy()
        updated[edit > 0] = label
        st.session_state.masks[idx] = updated
        st.session_state.saved[idx] = False
        st.session_state.export_bytes = None
        st.session_state.canvas_version += 1
        st.rerun()

left, mid, right = st.columns(3)
with left:
    undo = st.button("Undo", use_container_width=True)
with mid:
    redo = st.button("Redo", use_container_width=True)
with right:
    clear = st.button("Svuota frame", use_container_width=True)

if undo and st.session_state.history.get(idx):
    st.session_state.future.setdefault(idx, []).append(mask.copy())
    st.session_state.masks[idx] = st.session_state.history[idx].pop()
    st.session_state.saved[idx] = False
    st.session_state.export_bytes = None
    st.session_state.canvas_version += 1
    st.rerun()
if redo and st.session_state.future.get(idx):
    st.session_state.history.setdefault(idx, []).append(mask.copy())
    st.session_state.masks[idx] = st.session_state.future[idx].pop()
    st.session_state.saved[idx] = False
    st.session_state.export_bytes = None
    st.session_state.canvas_version += 1
    st.rerun()
if clear:
    st.session_state.history.setdefault(idx, []).append(mask.copy())
    st.session_state.future[idx] = []
    st.session_state.masks[idx] = np.zeros_like(mask)
    st.session_state.saved[idx] = False
    st.session_state.export_bytes = None
    st.session_state.canvas_version += 1
    st.rerun()

st.caption("masks/ = bianco e nero (0/255) · class_masks/ = etichette numeriche (0/1/2) · class_previews/ = colori visibili")

save_col, export_col = st.columns(2)
with save_col:
    save_clicked = st.button("✓ Salva frame e vai al successivo", key="save_frame", type="primary", use_container_width=True)
with export_col:
    export_clicked = st.button("↓ Esporta tutte", key="export_all", use_container_width=True)

if save_clicked:
    if not np.any(st.session_state.masks[idx] > 0):
        st.warning("Non ci sono vasi annotati in questo frame. Disegna prima un contorno.")
    else:
        st.session_state.saved[idx] = True
        st.session_state.export_bytes = None
        if position + 1 < len(frames):
            st.session_state.next_frame_position = position + 1
            st.rerun()
        else:
            st.success("Ultimo frame salvato. Puoi tornare ai precedenti oppure esportare tutto.")

if export_clicked:
    output = io.BytesIO()
    stem = safe_stem(uploaded.name)
    metadata = {"video": uploaded.name, "fps": fps, "total_frames": total, "sampled_frames": len(frames),
                "labels": {"0": "background", "1": "vein", "2": "artery"},
                "mask_formats": {"masks": "binary 0/255", "class_masks": "raw class ids 0/1/2", "class_previews": "RGB visualization: vein teal, artery orange"}, "frames": []}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for frame_idx, frame in frames:
            prefix = f"{stem}_frame_{frame_idx:06d}"
            archive.writestr(f"images/{prefix}_img.png", png_bytes(frame))
            seg = st.session_state.masks[frame_idx]
            archive.writestr(f"masks/{prefix}_mask.png", png_bytes((seg > 0).astype(np.uint8) * 255))
            archive.writestr(f"class_masks/{prefix}_classes.png", png_bytes(seg))
            preview = np.zeros((*seg.shape, 3), dtype=np.uint8)
            preview[seg == 1] = [0, 230, 170]
            preview[seg == 2] = [255, 145, 35]
            archive.writestr(f"class_previews/{prefix}_preview.png", png_bytes(preview))
            archive.writestr(f"binary_masks/{prefix}_vein.png", png_bytes((seg == 1).astype(np.uint8) * 255))
            archive.writestr(f"binary_masks/{prefix}_artery.png", png_bytes((seg == 2).astype(np.uint8) * 255))
            archive.writestr(f"binary_masks/{prefix}_vessels.png", png_bytes((seg > 0).astype(np.uint8) * 255))
            metadata["frames"].append({"index": frame_idx, "time_seconds": frame_idx/fps if fps > 0 else None,
                                       "image": f"images/{prefix}_img.png", "mask": f"masks/{prefix}_mask.png", "class_mask": f"class_masks/{prefix}_classes.png", "class_preview": f"class_previews/{prefix}_preview.png", "saved": bool(st.session_state.saved[frame_idx]), "binary_vein": f"binary_masks/{prefix}_vein.png", "binary_artery": f"binary_masks/{prefix}_artery.png", "binary_vessels": f"binary_masks/{prefix}_vessels.png"})
        archive.writestr("metadata.json", json.dumps(metadata, indent=2))
    st.session_state.export_bytes = output.getvalue()
if st.session_state.get("export_bytes") is not None:
    st.download_button("Scarica ZIP completo", st.session_state.export_bytes,
                       file_name=f"{safe_stem(uploaded.name)}_annotations.zip", mime="application/zip")
