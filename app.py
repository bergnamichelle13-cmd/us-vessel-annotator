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
st.title("US Vessel Annotator")
st.caption("Annotazione manuale di vene (1) e arterie (2). Prototipo di ricerca, non dispositivo medico.")


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
n = st.sidebar.number_input("Frame equidistanti", min_value=1, max_value=500, value=30)
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

st.sidebar.write(f"Video: {total} frame · FPS: {fps:.2f}" if fps > 0 else f"Video: {total} frame")
position = st.sidebar.selectbox("Frame da annotare", range(len(frames)), format_func=lambda i: f"{i+1}/{len(frames)} · frame {frames[i][0]}", key="frame_position")
idx, rgb = frames[position]
h, w = rgb.shape[:2]
mask = st.session_state.masks[idx]

label_name = st.sidebar.radio("Classe", ["Vena", "Arteria", "Gomma"], horizontal=False)
label = {"Vena": 1, "Arteria": 2, "Gomma": 0}[label_name]
brush = st.sidebar.slider("Diametro pennello (px)", 1, 70, 12)
zoom = st.sidebar.slider("Zoom visualizzazione", 1.0, 3.0, 1.0, 0.25)
opacity = st.sidebar.slider("Opacità maschera", 0.0, 0.8, 0.35, 0.05)

# Canvas works in image coordinates. Zoom is implemented by uniformly scaling
# the displayed image and strokes; the saved mask is always original resolution.
display_w, display_h = int(w * zoom), int(h * zoom)
base = rgb.copy()
base[mask == 1] = ((1-opacity)*base[mask == 1] + opacity*np.array([0, 230, 170])).astype(np.uint8)
base[mask == 2] = ((1-opacity)*base[mask == 2] + opacity*np.array([255, 145, 35])).astype(np.uint8)
background = Image.fromarray(base).resize((display_w, display_h))

st.markdown("**Disegna direttamente sull’ecografia.** Rilascia il mouse per applicare il tratto. Usa Undo per annullarlo.")
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
        if len(coords) == 1:
            cv2.circle(edit, tuple(coords[0]), max(1, thickness // 2), 255, -1)
        else:
            cv2.polylines(edit, [coords.reshape(-1, 1, 2)], False, 255, thickness, lineType=cv2.LINE_8)
            for xy in (coords[0], coords[-1]):
                cv2.circle(edit, tuple(xy), max(1, thickness // 2), 255, -1)
        st.session_state.history.setdefault(idx, []).append(mask.copy())
        st.session_state.future[idx] = []
        updated = mask.copy()
        updated[edit > 0] = label
        st.session_state.masks[idx] = updated
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
    st.session_state.canvas_version += 1
    st.rerun()
if redo and st.session_state.future.get(idx):
    st.session_state.history.setdefault(idx, []).append(mask.copy())
    st.session_state.masks[idx] = st.session_state.future[idx].pop()
    st.session_state.canvas_version += 1
    st.rerun()
if clear:
    st.session_state.history.setdefault(idx, []).append(mask.copy())
    st.session_state.future[idx] = []
    st.session_state.masks[idx] = np.zeros_like(mask)
    st.session_state.canvas_version += 1
    st.rerun()

st.caption("Colori: verde acqua = vena; arancione = arteria. Maschere: 0 sfondo, 1 vena, 2 arteria. Zoom aumenta le dimensioni del canvas, non la risoluzione dei file.")

if st.button("Prepara esportazione ZIP"):
    output = io.BytesIO()
    stem = safe_stem(uploaded.name)
    metadata = {"video": uploaded.name, "fps": fps, "total_frames": total,
                "labels": {"0": "background", "1": "vein", "2": "artery"}, "frames": []}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for frame_idx, frame in frames:
            prefix = f"{stem}_frame_{frame_idx:06d}"
            archive.writestr(f"images/{prefix}_img.png", png_bytes(frame))
            archive.writestr(f"masks/{prefix}_mask.png", png_bytes(st.session_state.masks[frame_idx]))
            metadata["frames"].append({"index": frame_idx, "time_seconds": frame_idx/fps if fps > 0 else None,
                                       "image": f"images/{prefix}_img.png", "mask": f"masks/{prefix}_mask.png"})
        archive.writestr("metadata.json", json.dumps(metadata, indent=2))
    st.session_state.export_bytes = output.getvalue()
if "export_bytes" in st.session_state:
    st.download_button("Scarica immagini, maschere e metadata", st.session_state.export_bytes,
                       file_name=f"{safe_stem(uploaded.name)}_annotations.zip", mime="application/zip")
