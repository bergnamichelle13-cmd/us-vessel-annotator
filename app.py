"""US Vessel Annotator V9 — two-stage, multi-video annotation workspace."""
import base64
import hashlib
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="US Vessel Studio", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")
COMPONENT = components.declare_component("us_vessel_paint_v9", path=str(Path(__file__).parent / "annotator_component"))

st.markdown("""<style>
:root {--navy:#183342;--teal:#05aeb1;--orange:#f36c21;--red:#d83c39;--muted:#647987}
.stApp {background:linear-gradient(130deg,#fff7f0 0%,#f7fcfd 45%,#eaf9f8 100%);color:#173446}
.block-container{max-width:1380px;padding-top:.8rem;padding-bottom:2rem}
[data-testid="stSidebar"]{background:#122f40}
[data-testid="stSidebar"] *{color:#edf6fa}
[data-testid="stSidebar"] [data-baseweb="select"] *{color:#1a3441}
h1,h2,h3{color:#14384b}
.stButton button{border-radius:11px;font-weight:650;min-height:2.7rem}
.stButton button[kind="primary"]{background:#f36c21;border-color:#f36c21;color:#fff}
.stButton button[kind="primary"]:hover{background:#d85612;border-color:#d85612;color:#fff}
div.st-key-export_project button{background:#06a7b3!important;color:white!important;border:0!important}
div.st-key-no_vessel_action button{background:#d83c39!important;color:white!important;border:0!important}
div.st-key-save_frame_action button{background:#168b51!important;border-color:#168b51!important;color:white!important}
div.st-key-save_frame_action button:hover{background:#0c713f!important;border-color:#0c713f!important}
div.st-key-frame_prev button,div.st-key-frame_next button{background:#e7f7f8!important;color:#0a6971!important;border:1px solid #88d8dc!important}
div.st-key-frame_prev button:hover,div.st-key-frame_next button:hover{background:#c6f0f1!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:#cce8e8!important}
.stProgress > div > div > div > div{background:#05aeb1!important}
.hero{background:linear-gradient(105deg,#183342 0%,#166d78 65%,#05aeb1 100%);border-left:7px solid #f36c21;border-radius:16px;padding:14px 22px;color:white;margin-bottom:10px;box-shadow:0 10px 28px #12344918}
.hero .eyebrow{font-size:.72rem;letter-spacing:.16em;color:#ffd7b9;font-weight:800}
.hero .heading{font-size:1.55rem;font-weight:800;margin:2px 0}
.hero .subtitle{color:#d1e0e7;font-size:.92rem}
.stage{display:inline-block;border-radius:999px;padding:5px 12px;font-size:.82rem;font-weight:700;background:#ffe6d5;color:#b34a0c;margin-bottom:4px}
.metric{background:white;border:1px solid #e0eaf0;border-radius:13px;padding:14px 18px;margin-bottom:12px}
.note{background:#eaf4f8;border-left:4px solid #149e94;padding:12px 16px;border-radius:8px;margin:12px 0}
.frame-title{font-size:1rem;font-weight:750;color:#123a4b;margin:4px 0}
[data-testid="stImage"] img{border-radius:10px}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="eyebrow">ULTRASOUND · ANNOTATION WORKSPACE</div><div class="heading">US Vessel Studio</div><div class="subtitle">Prepara i frame, annota vene e arterie, esporta un unico dataset multi-video.</div></div>', unsafe_allow_html=True)


def safe_stem(name):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(name).stem)[:55] or "video"


def png_bytes(array):
    out = io.BytesIO()
    Image.fromarray(array).save(out, format="PNG")
    return out.getvalue()


def file_key(upload):
    return f"{safe_stem(upload.name)}_{hashlib.sha256(upload.getvalue()).hexdigest()[:10]}"


@st.cache_data(show_spinner=False, max_entries=40)
def info_video(data, extension):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Video non leggibile")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        if total < 1:
            raise ValueError("Numero di frame non disponibile")
        return total, fps
    finally:
        path.unlink(missing_ok=True)


@st.cache_data(show_spinner=False, max_entries=160)
def read_frame(data, extension, index):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Impossibile aprire il video")
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, bgr = cap.read()
        cap.release()
        if not ok:
            raise ValueError(f"Impossibile leggere il frame {index}")
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    finally:
        path.unlink(missing_ok=True)


def reset_project(key, upload, total, fps, count):
    indices = np.unique(np.linspace(0, total - 1, min(count, total), dtype=int)).tolist()
    st.session_state.projects[key] = {
        "name": upload.name, "total": total, "fps": fps, "indices": indices,
        "masks": {}, "statuses": {}, "history": {}, "future": {}, "revision": 0,
    }


def invalidate_export():
    st.session_state.pop("export_bytes", None)


def navigate(delta):
    position = st.session_state.get("cursor", 0) + delta
    st.session_state.cursor = max(0, min(position, len(sequence) - 1))
    st.rerun()


if "projects" not in st.session_state:
    st.session_state.projects = {}
if "stage" not in st.session_state:
    st.session_state.stage = 0
if "cursor" not in st.session_state:
    st.session_state.cursor = 0
if "upload_nonce" not in st.session_state:
    st.session_state.upload_nonce = 0

# The top navigation remains visible in both screens.
nav_a, nav_b, nav_c = st.columns([2, 2, 5], vertical_alignment="center")
with nav_a:
    if st.button("← 1 · Preparazione", use_container_width=True, type="primary" if st.session_state.stage == 0 else "secondary"):
        st.session_state.stage = 0
        st.rerun()
with nav_b:
    if st.button("2 · Annotazione →", use_container_width=True, type="primary" if st.session_state.stage == 1 else "secondary"):
        st.session_state.stage = 1
        st.rerun()
with nav_c:
    st.caption("Puoi tornare alla preparazione in qualsiasi momento. Le maschere dei frame non sostituiti vengono conservate.")

uploads = st.file_uploader(
    "Carica video ecografici", type=["mp4", "avi", "mov", "mkv"],
    accept_multiple_files=True, key=f"videos_{st.session_state.upload_nonce}",
    label_visibility="collapsed" if st.session_state.stage == 1 else "visible",
)

catalog = []
seen = set()
for up in uploads or []:
    key = file_key(up)
    if key in seen:
        continue
    seen.add(key)
    try:
        total, fps = info_video(up.getvalue(), Path(up.name).suffix)
    except ValueError as exc:
        st.error(f"{up.name}: {exc}")
        continue
    catalog.append((key, up, total, fps))
    if key not in st.session_state.projects:
        reset_project(key, up, total, fps, min(10, total))

# Remove stale video projects if the user changes the upload selection.
active = {item[0] for item in catalog}
for stale in list(st.session_state.projects):
    if stale not in active:
        del st.session_state.projects[stale]
        invalidate_export()

if not catalog:
    st.info("Carica uno o più video per iniziare. Potrai scegliere e ispezionare i frame prima dell'annotazione.")
    st.stop()

catalog_by_key = {key: (up, total, fps) for key, up, total, fps in catalog}


def replace_slot(video_id, slot, new_idx):
    project = st.session_state.projects[video_id]
    old_idx = project["indices"][slot]
    if new_idx == old_idx:
        return
    if new_idx in project["indices"]:
        st.warning("Questo frame è già selezionato per il video.")
        return
    project["indices"][slot] = new_idx
    project["masks"].pop(old_idx, None)
    project["statuses"].pop(old_idx, None)
    project["history"].pop(old_idx, None)
    project["future"].pop(old_idx, None)
    project["revision"] += 1
    invalidate_export()


@st.dialog("Sostituisci il frame", width="large")
def frame_dialog(video_id, slot):
    up, total, fps = catalog_by_key[video_id]
    project = st.session_state.projects[video_id]
    original = project["indices"][slot]
    st.caption(f"{up.name} · posizione {slot+1}/{len(project['indices'])} · frame corrente {original}")
    selected = st.slider("Scorri i frame originali", 0, total - 1, original, key=f"browse_{video_id}_{slot}_{project['revision']}")
    left, center, right = st.columns([1, 3, 1], vertical_alignment="center")
    with left:
        if st.button("◀", key="browse_left", disabled=selected == 0, use_container_width=True):
            st.session_state[f"browse_{video_id}_{slot}_{project['revision']}"] = selected - 1
            st.rerun()
    with center:
        st.caption(f"Frame {selected}/{total-1} · {selected/fps:.2f} s" if fps > 0 else f"Frame {selected}/{total-1}")
    with right:
        if st.button("▶", key="browse_right", disabled=selected == total - 1, use_container_width=True):
            st.session_state[f"browse_{video_id}_{slot}_{project['revision']}"] = selected + 1
            st.rerun()
    try:
        st.image(read_frame(up.getvalue(), Path(up.name).suffix, selected), use_container_width=True)
    except ValueError as exc:
        st.error(str(exc))
        return
    duplicate = selected in project["indices"] and selected != original
    if duplicate:
        st.warning("Frame già usato in un'altra posizione: scegli un altro frame.")
    if st.button("Usa questo frame per la segmentazione", type="primary", disabled=duplicate or selected == original, use_container_width=True):
        replace_slot(video_id, slot, selected)
        st.rerun()


if st.session_state.stage == 0:
    st.markdown('### <span class="stage">FASE 1</span> Preparazione e selezione dei frame', unsafe_allow_html=True)
    st.markdown('<div class="note">Configura quanti frame annotare per ogni video, poi clicca <b>Ispeziona</b>. Ogni miniatura può essere sostituita con un frame originale vicino, prima di passare alla segmentazione.</div>', unsafe_allow_html=True)
    for key, up, total, fps in catalog:
        project = st.session_state.projects[key]
        with st.container(border=True):
            st.subheader(up.name)
            m1, m2, m3 = st.columns(3)
            m1.metric("Frame totali", total)
            m2.metric("Frame rate", f"{fps:.2f} FPS")
            m3.metric("Selezionati", len(project["indices"]))
            count = st.number_input("Numero di frame da segmentare", min_value=1, max_value=min(total, 500), value=len(project["indices"]), key=f"count_{key}")
            if count != len(project["indices"]):
                # Preserve existing work if possible only when indices do not change.
                reset_project(key, up, total, fps, count)
                invalidate_export()
                st.rerun()
            inspect = st.toggle("Ispeziona i frame selezionati", key=f"inspect_{key}")
            if inspect:
                slots = project["indices"]
                for start in range(0, len(slots), 4):
                    cols = st.columns(4)
                    for offset, slot in enumerate(range(start, min(start + 4, len(slots)))):
                        index = slots[slot]
                        with cols[offset]:
                            try:
                                st.image(read_frame(up.getvalue(), Path(up.name).suffix, index), use_container_width=True)
                            except ValueError as exc:
                                st.error(str(exc))
                                continue
                            st.caption(f"Selezione {slot+1} · frame {index}")
                            if st.button("Sostituisci", key=f"replace_{key}_{slot}", use_container_width=True):
                                frame_dialog(key, slot)
    st.divider()
    total_selected = sum(len(st.session_state.projects[key]["indices"]) for key, _, _, _ in catalog)
    st.caption(f"{len(catalog)} video · {total_selected} frame complessivi selezionati")
    if st.button("Salva configurazione e avanti →", type="primary", use_container_width=True):
        st.session_state.stage = 1
        st.session_state.cursor = 0
        st.rerun()
    st.stop()

# One continuous sequence, with per-video IDs retained for export.
sequence = [(key, slot, idx) for key, _, _, _ in catalog for slot, idx in enumerate(st.session_state.projects[key]["indices"])]
if not sequence:
    st.warning("Nessun frame selezionato. Torna alla preparazione.")
    st.stop()
st.session_state.cursor = min(st.session_state.cursor, len(sequence) - 1)
video_id, slot, frame_idx = sequence[st.session_state.cursor]
project = st.session_state.projects[video_id]
up, total, fps = catalog_by_key[video_id]

st.markdown('<span class="stage">FASE 2 · SEGMENTAZIONE</span>', unsafe_allow_html=True)
completed = sum(st.session_state.projects[key]["statuses"].get(idx) in ("annotated", "no_vessel") for key, _, _, _ in catalog for idx in st.session_state.projects[key]["indices"])
st.progress(completed / len(sequence), text=f"Completati {completed}/{len(sequence)} frame")
st.markdown(f'<div class="frame-title">{up.name} &nbsp; · &nbsp; Frame {slot+1}/{len(project["indices"])} &nbsp; · &nbsp; Originale #{frame_idx} &nbsp; · &nbsp; Sequenza {st.session_state.cursor+1}/{len(sequence)}</div>', unsafe_allow_html=True)

# Paint-like toolbar, above the image.
with st.container(border=True):
    t1, t2, t3, t4 = st.columns([2.2, 1.5, 1.5, 1.5], vertical_alignment="bottom")
    with t1:
        tool = st.radio("Strumento", ["Vena", "Arteria", "Gomma"], horizontal=True, key="paint_tool")
    with t2:
        brush = st.slider("Diametro (px)", 1, 20, 3, key="paint_brush")
    with t3:
        zoom = st.select_slider("Zoom", options=[1.0, 1.25, 1.5, 2.0, 2.5, 3.0], value=1.0, key="paint_zoom")
    with t4:
        opacity = st.slider("Maschera (%)", 0, 80, 38, 5, key="paint_opacity") / 100

try:
    rgb = read_frame(up.getvalue(), Path(up.name).suffix, frame_idx)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
h, w = rgb.shape[:2]
mask = project["masks"].setdefault(frame_idx, np.zeros((h, w), np.uint8))
status = project["statuses"].get(frame_idx, "pending")
st.caption({"annotated": "Stato: annotato", "no_vessel": "Stato: nessun vaso", "pending": "Stato: da completare"}[status])

base = rgb.copy()
base[mask == 1] = ((1 - opacity) * base[mask == 1] + opacity * np.array([0, 226, 174])).astype(np.uint8)
base[mask == 2] = ((1 - opacity) * base[mask == 2] + opacity * np.array([255, 148, 40])).astype(np.uint8)
# Adatta il frame alla finestra: comandi subito sotto senza scorrere.
fit = min(1.0, 850 / w, 460 / h)
dw, dh = max(1, int(w * fit * zoom)), max(1, int(h * fit * zoom))
display_scale_x, display_scale_y = dw / w, dh / h
background = Image.fromarray(base).resize((dw, dh))
label = {"Vena": 1, "Arteria": 2, "Gomma": 0}[tool]
color = {1: "#00e2ae", 2: "#ff9428", 0: "#ef5350"}[label]

stroke = COMPONENT(
    image=base64.b64encode(png_bytes(np.asarray(background))).decode("ascii"),
    width=dw, height=dh, color=color, brush=float(brush * display_scale_x),
    key=f"draw_{video_id}_{frame_idx}_{project['revision']}", default=None,
)
if isinstance(stroke, dict) and stroke.get("points"):
    pts = np.asarray(stroke["points"], dtype=float)
    if pts.ndim == 2 and pts.shape[1] == 2 and 1 <= len(pts) <= 20000:
        coords = np.rint(pts / np.array([display_scale_x, display_scale_y])).astype(np.int32)
        coords[:, 0] = np.clip(coords[:, 0], 0, w - 1)
        coords[:, 1] = np.clip(coords[:, 1], 0, h - 1)
        edit = np.zeros((h, w), dtype=np.uint8)
        if label in (1, 2):
            if len(np.unique(coords, axis=0)) < 8 or abs(cv2.contourArea(coords.reshape(-1, 1, 2))) < 10:
                st.warning("Contorno troppo breve. Traccia il perimetro del vaso con un unico gesto.")
                st.stop()
            cv2.fillPoly(edit, [coords.reshape(-1, 1, 2)], 255)
            cv2.polylines(edit, [coords.reshape(-1, 1, 2)], True, 255, int(brush))
        else:
            if len(coords) == 1:
                cv2.circle(edit, tuple(coords[0]), max(1, brush // 2), 255, -1)
            else:
                cv2.polylines(edit, [coords.reshape(-1, 1, 2)], False, 255, int(brush))
        project["history"].setdefault(frame_idx, []).append(mask.copy())
        project["future"][frame_idx] = []
        new_mask = mask.copy()
        new_mask[edit > 0] = label
        project["masks"][frame_idx] = new_mask
        project["statuses"][frame_idx] = "pending"
        project["revision"] += 1
        invalidate_export()
        st.rerun()

st.caption("Contorno chiuso → riempimento automatico · Gomma → cancella un tratto")

u1, u2, u3 = st.columns([1, 1, 1])
with u1:
    if st.button("↶ Annulla", use_container_width=True, disabled=not project["history"].get(frame_idx)):
        project["future"].setdefault(frame_idx, []).append(mask.copy())
        project["masks"][frame_idx] = project["history"][frame_idx].pop()
        project["statuses"][frame_idx] = "pending"
        project["revision"] += 1
        invalidate_export()
        st.rerun()
with u2:
    if st.button("↷ Ripristina", use_container_width=True, disabled=not project["future"].get(frame_idx)):
        project["history"].setdefault(frame_idx, []).append(mask.copy())
        project["masks"][frame_idx] = project["future"][frame_idx].pop()
        project["statuses"][frame_idx] = "pending"
        project["revision"] += 1
        invalidate_export()
        st.rerun()
with u3:
    if st.button("Cancella annotazione", use_container_width=True):
        project["history"].setdefault(frame_idx, []).append(mask.copy())
        project["future"][frame_idx] = []
        project["masks"][frame_idx] = np.zeros_like(mask)
        project["statuses"][frame_idx] = "pending"
        project["revision"] += 1
        invalidate_export()
        st.rerun()

p1, p2, p3, p4 = st.columns([1.2, 1.3, 1.2, 1.2], vertical_alignment="center")
with p1:
    if st.button("← Frame precedente", key="frame_prev", disabled=st.session_state.cursor == 0, use_container_width=True):
        navigate(-1)
with p2:
    if st.button("Frame successivo →", key="frame_next", disabled=st.session_state.cursor == len(sequence) - 1, use_container_width=True):
        navigate(1)
with p3:
    if st.button("✓ Salva e vai avanti", key="save_frame_action", use_container_width=True):
        if not np.any(mask):
            st.warning("Nessuna annotazione: usa 'Nessun vaso' se il frame non contiene vasi.")
        else:
            project["statuses"][frame_idx] = "annotated"
            invalidate_export()
            if st.session_state.cursor < len(sequence) - 1:
                navigate(1)
            else:
                st.success("Ultimo frame completato. Puoi esportare l'intero progetto.")
with p4:
    if st.button("Nessun vaso", key="no_vessel_action", use_container_width=True):
        project["history"].setdefault(frame_idx, []).append(mask.copy())
        project["future"][frame_idx] = []
        project["masks"][frame_idx] = np.zeros_like(mask)
        project["statuses"][frame_idx] = "no_vessel"
        project["revision"] += 1
        invalidate_export()
        if st.session_state.cursor < len(sequence) - 1:
            navigate(1)
        else:
            st.success("Ultimo frame completato. Puoi esportare l'intero progetto.")

st.divider()
st.subheader("Esportazione progetto")
st.caption("Un solo ZIP con una cartella per ciascun video. Include immagini originali, maschere binarie separate (vena, arteria, vasi) e metadata.json.")
if completed < len(sequence):
    st.warning(f"Ci sono ancora {len(sequence) - completed} frame da completare. Puoi comunque esportare: saranno indicati come 'pending'.")
if st.button("Esporta tutte le annotazioni", key="export_project", use_container_width=True):
    output = io.BytesIO()
    metadata = {"labels": {"0": "background", "1": "vein", "2": "artery"}, "mask_format": "0 background / 255 foreground", "videos": []}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, video_upload, video_total, video_fps in catalog:
            p = st.session_state.projects[key]
            folder = f"videos/{key}"
            entry = {"name": p["name"], "folder": folder, "total_frames": video_total, "fps": video_fps, "frames": []}
            for position, index in enumerate(p["indices"]):
                try:
                    frame = read_frame(video_upload.getvalue(), Path(video_upload.name).suffix, index)
                except ValueError as exc:
                    st.error(f"Esportazione interrotta: {video_upload.name}, frame {index}: {exc}")
                    st.stop()
                current_mask = p["masks"].get(index)
                if current_mask is None:
                    current_mask = np.zeros(frame.shape[:2], np.uint8)
                prefix = f"{safe_stem(p['name'])}_frame_{index:06d}"
                image_path = f"{folder}/images/{prefix}_img.png"
                archive.writestr(image_path, png_bytes(frame))
                paths = {}
                for class_name, pixels in (("vein", current_mask == 1), ("artery", current_mask == 2), ("vessels", current_mask > 0)):
                    path = f"{folder}/binary_masks/{prefix}_{class_name}.png"
                    archive.writestr(path, png_bytes(pixels.astype(np.uint8) * 255))
                    paths[class_name] = path
                entry["frames"].append({"slot": position, "index": index, "time_seconds": index / video_fps if video_fps > 0 else None, "status": p["statuses"].get(index, "pending"), "image": image_path, "binary_masks": paths})
            metadata["videos"].append(entry)
        archive.writestr("metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))
    st.session_state.export_bytes = output.getvalue()
if "export_bytes" in st.session_state:
    st.download_button("Scarica ZIP completo", st.session_state.export_bytes, file_name="ultrasound_annotations_all_videos.zip", mime="application/zip", use_container_width=True)
