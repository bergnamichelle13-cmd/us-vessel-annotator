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
div.st-key-no_vessel button {background:#6b7280!important;color:#fff!important;border:0!important;border-radius:10px!important;font-weight:750!important;}
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


@st.cache_data(show_spinner=False, max_entries=96)
def read_video_frame(data, extension, frame_index):
    """Decode a requested original video frame without changing sampled slots."""
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Impossibile aprire il video per la navigazione.")
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, bgr = cap.read()
        cap.release()
        if not ok:
            raise ValueError(f"Impossibile leggere il frame {frame_index}.")
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
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


# Multi-video workspace: each video retains independent masks, statuses and history.
import hashlib

def video_key(upload):
    digest = hashlib.sha256(upload.getvalue()).hexdigest()[:16]
    return f"{safe_stem(upload.name)}_{digest}"

@st.cache_data(show_spinner="Lettura informazioni video...")
def video_info(data, extension):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Video non leggibile da OpenCV")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        if total < 1:
            raise ValueError("Numero di frame non disponibile")
        return total, fps
    finally:
        path.unlink(missing_ok=True)

if "video_projects" not in st.session_state:
    st.session_state.video_projects = {}
if "upload_version" not in st.session_state:
    st.session_state.upload_version = 0

uploaded_files = st.file_uploader(
    "Carica uno o più video ecografici", type=["mp4", "avi", "mov", "mkv"],
    accept_multiple_files=True, key=f"multi_upload_{st.session_state.upload_version}",
)
if not uploaded_files:
    st.info("Carica più video insieme. Per ognuno potrai scegliere quanti frame annotare.")
    st.stop()

catalog = []
used_names = set()
for upload in uploaded_files:
    key = video_key(upload)
    if key in used_names:
        continue
    used_names.add(key)
    try:
        total_frames, video_fps = video_info(upload.getvalue(), Path(upload.name).suffix)
    except ValueError as exc:
        st.error(f"{upload.name}: {exc}")
        continue
    catalog.append((key, upload, total_frames, video_fps))
if not catalog:
    st.stop()

st.sidebar.markdown("### Video caricati")
st.sidebar.caption("Passa liberamente da un video all’altro: tutte le annotazioni restano nella sessione e si esportano insieme.")
for key, upload, total_frames, video_fps in catalog:
    st.sidebar.caption(f"{upload.name} · {total_frames} frame · {video_fps:.2f} FPS")

selected_key = st.sidebar.selectbox(
    "Video da segmentare", [item[0] for item in catalog],
    format_func=lambda k: next(u.name for x,u,_,_ in catalog if x == k),
    key="selected_video_key",
)

# Independent number of samples for every video. Changing it resets only that video.
requested = {}
with st.expander("Configurazione frame per ciascun video", expanded=True):
    st.caption("I frame sono distribuiti uniformemente dal primo all’ultimo. Cambiare il numero di frame azzera le annotazioni del solo video interessato. La sostituzione di un frame cancella la maschera di quello slot.")
    for key, upload, total_frames, video_fps in catalog:
        c1, c2 = st.columns([3, 2])
        with c1:
            st.write(f"**{upload.name}** — {total_frames} frame totali · {video_fps:.2f} FPS")
        with c2:
            requested[key] = st.number_input(
                f"Frame da annotare · {upload.name}", min_value=1,
                max_value=min(500, total_frames), value=min(10, total_frames),
                step=1, key=f"count_{key}",
            )

for key, upload, total_frames, video_fps in catalog:
    previous = st.session_state.video_projects.get(key)
    if previous is not None and previous["requested"] == requested[key]:
        continue
    try:
        video_frames, fps, total = sample_video(upload.getvalue(), Path(upload.name).suffix, requested[key])
    except ValueError as exc:
        st.error(f"{upload.name}: {exc}")
        st.stop()
    st.session_state.video_projects[key] = {
        "name": upload.name, "requested": requested[key], "frames": video_frames,
        "fps": fps, "total": total,
        "masks": {i: np.zeros(frame.shape[:2], np.uint8) for i, frame in video_frames},
        "history": {}, "future": {}, "saved": {i: False for i, _ in video_frames},
        "frame_status": {i: "pending" for i, _ in video_frames},
        "canvas_version": 0,
    }

# All state below is scoped to the selected video.
project = st.session_state.video_projects[selected_key]
frames, fps, total = project["frames"], project["fps"], project["total"]
position_key = f"position_{selected_key}"
if position_key not in st.session_state:
    st.session_state[position_key] = 0
next_key = f"next_{selected_key}"
if next_key in st.session_state:
    st.session_state[position_key] = st.session_state.pop(next_key)

st.sidebar.write(f"Video selezionato: {total} frame · FPS: {fps:.2f}")
position = st.sidebar.selectbox(
    "Frame da annotare", range(len(frames)),
    format_func=lambda i: f"{'— ' if project['frame_status'][frames[i][0]] == 'no_vessel' else ('✓ ' if project['saved'][frames[i][0]] else '○ ')}{i+1}/{len(frames)} · frame {frames[i][0]}",
    key=position_key,
)
st.sidebar.caption(f"Frame salvati: {sum(project['saved'].values())}/{len(frames)}")
st.sidebar.progress(sum(project['saved'].values()) / len(frames))
st.sidebar.caption(f"Senza vaso: {sum(v == 'no_vessel' for v in project['frame_status'].values())}")
idx, rgb = frames[position]
h, w = rgb.shape[:2]
mask = project["masks"][idx]

label_name = st.sidebar.radio("Classe", ["Vena", "Arteria", "Gomma"], horizontal=False)
label = {"Vena": 1, "Arteria": 2, "Gomma": 0}[label_name]
brush = st.sidebar.slider("Diametro pennello (px)", 1, 20, 3)
zoom = st.sidebar.slider("Zoom visualizzazione", 1.0, 3.0, 1.0, 0.25)
opacity = st.sidebar.slider("Opacità maschera", 0.0, 0.8, 0.35, 0.05)

idx, rgb = frames[position]
# Navigazione rapida tra i frame selezionati, indipendente dal salvataggio.
st.markdown("### Navigazione frame")
prev_col, counter_col, next_col = st.columns([1, 3, 1])
with prev_col:
    if st.button("◀ Precedente", disabled=position == 0, use_container_width=True):
        st.session_state[next_key] = position - 1
        st.rerun()
with counter_col:
    st.markdown(f"**{position + 1} / {len(frames)}** · frame originale **{idx}** / {total - 1}")
with next_col:
    if st.button("Successivo ▶", disabled=position == len(frames) - 1, use_container_width=True):
        st.session_state[next_key] = position + 1
        st.rerun()

# Il browser mostra TUTTI i frame originali del video, non soltanto quelli selezionati.
# L'utente può sostituire il frame corrente mantenendo lo stesso slot di annotazione.
with st.sidebar.expander("Visualizza frame vicini", expanded=False):
    st.caption("Scorri il video originale e scegli un frame alternativo per la posizione corrente.")
    browser_key = f"browser_frame_{selected_key}_{position}"
    if browser_key not in st.session_state:
        st.session_state[browser_key] = idx
    browser_index = st.slider(
        "Frame originale", min_value=0, max_value=total - 1,
        key=browser_key,
    )
    try:
        preview = read_video_frame(
            next(u.getvalue() for k, u, _, _ in catalog if k == selected_key),
            Path(project["name"]).suffix, browser_index,
        )
        st.image(preview, caption=f"Frame {browser_index} · {browser_index / fps:.2f} s" if fps > 0 else f"Frame {browser_index}", use_column_width=True)
        already_used = any(j == browser_index for slot, (j, _) in enumerate(frames) if slot != position)
        if already_used:
            st.warning("Questo frame è già selezionato in un'altra posizione.")
        if st.button("Sostituisci frame corrente", disabled=already_used or browser_index == idx, use_container_width=True):
            # Non trasferiamo una maschera disegnata su un'immagine diversa.
            project["frames"][position] = (browser_index, preview)
            project["masks"].pop(idx, None)
            project["saved"].pop(idx, None)
            project["frame_status"].pop(idx, None)
            project["history"].pop(idx, None)
            project["future"].pop(idx, None)
            project["masks"][browser_index] = np.zeros(preview.shape[:2], np.uint8)
            project["saved"][browser_index] = False
            project["frame_status"][browser_index] = "pending"
            project["canvas_version"] += 1
            st.session_state.pop("all_export_bytes", None)
            st.rerun()
    except ValueError as exc:
        st.error(str(exc))

# Canvas works in image coordinates. Zoom is implemented by uniformly scaling
# the displayed image and strokes; the saved mask is always original resolution.
display_w, display_h = int(w * zoom), int(h * zoom)
base = rgb.copy()
base[mask == 1] = ((1-opacity)*base[mask == 1] + opacity*np.array([0, 230, 170])).astype(np.uint8)
base[mask == 2] = ((1-opacity)*base[mask == 2] + opacity*np.array([255, 145, 35])).astype(np.uint8)
background = Image.fromarray(base).resize((display_w, display_h))

st.markdown(f'<div class="us-status">FRAME {position+1:02d} / {len(frames):02d} &nbsp; · &nbsp; {("SENZA VASO" if project["frame_status"][idx] == "no_vessel" else "SALVATO") if project["saved"][idx] else "DA COMPLETARE"} &nbsp; · &nbsp; Originale {w} × {h} px</div>', unsafe_allow_html=True)
st.markdown('<div class="us-tip"><b>Annotazione:</b> traccia il contorno completo del vaso con un unico gesto. Al rilascio, l’area interna viene riempita. Verde acqua = vena; arancione = arteria.</div>', unsafe_allow_html=True)
color = {1: "#00e6aa", 2: "#ff9123", 0: "#ff5555"}[label]
# The browser component draws on top of the ultrasound and returns only
# stroke coordinates. Masks remain on the server at original resolution.
image_b64 = __import__("base64").b64encode(png_bytes(np.asarray(background))).decode("ascii")
stroke = annotator(
    image=image_b64, width=display_w, height=display_h,
    color=color, brush=float(brush * zoom),
    key=f"canvas_{selected_key}_{idx}_{project['canvas_version']}", default=None,
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
        project["history"].setdefault(idx, []).append(mask.copy())
        project["future"][idx] = []
        updated = mask.copy()
        updated[edit > 0] = label
        project["masks"][idx] = updated
        project["saved"][idx] = False
        project["frame_status"][idx] = "pending"
        st.session_state.pop("all_export_bytes", None)
        project["canvas_version"] += 1
        st.rerun()

left, mid, right = st.columns(3)
with left:
    undo = st.button("Undo", use_container_width=True)
with mid:
    redo = st.button("Redo", use_container_width=True)
with right:
    clear = st.button("Svuota frame", use_container_width=True)

if undo and project["history"].get(idx):
    project["future"].setdefault(idx, []).append(mask.copy())
    project["masks"][idx] = project["history"][idx].pop()
    project["saved"][idx] = False
    project["frame_status"][idx] = "pending"
    st.session_state.pop("all_export_bytes", None)
    project["canvas_version"] += 1
    st.rerun()
if redo and project["future"].get(idx):
    project["history"].setdefault(idx, []).append(mask.copy())
    project["masks"][idx] = project["future"][idx].pop()
    project["saved"][idx] = False
    project["frame_status"][idx] = "pending"
    st.session_state.pop("all_export_bytes", None)
    project["canvas_version"] += 1
    st.rerun()
if clear:
    project["history"].setdefault(idx, []).append(mask.copy())
    project["future"][idx] = []
    project["masks"][idx] = np.zeros_like(mask)
    project["saved"][idx] = False
    project["frame_status"][idx] = "pending"
    st.session_state.pop("all_export_bytes", None)
    project["canvas_version"] += 1
    st.rerun()

st.caption("Puoi saltare i frame con le frecce senza salvarli. Le maschere sono binarie (0/255) per vena, arteria e tutti i vasi.")

save_col, no_vessel_col, export_col = st.columns(3)
with save_col:
    save_clicked = st.button("✓ Salva frame e vai al successivo", key=f"save_frame_{selected_key}", type="primary", use_container_width=True)
with no_vessel_col:
    no_vessel_clicked = st.button("⊘ Nessun vaso · salva e avanti", key=f"no_vessel_{selected_key}", use_container_width=True)
with export_col:
    export_clicked = st.button("↓ Esporta tutte", key="export_all", use_container_width=True)

if save_clicked:
    if not np.any(project["masks"][idx] > 0):
        st.warning("Non ci sono vasi annotati in questo frame. Disegna prima un contorno.")
    else:
        project["saved"][idx] = True
        project["frame_status"][idx] = "annotated"
        st.session_state.pop("all_export_bytes", None)
        if position + 1 < len(frames):
            st.session_state[next_key] = position + 1
            st.rerun()
        else:
            st.success("Ultimo frame salvato. Puoi tornare ai precedenti oppure esportare tutto.")

if no_vessel_clicked:
    # Una scelta esplicita del medico: la maschera di questo frame deve essere completamente nera.
    project["history"].setdefault(idx, []).append(project["masks"][idx].copy())
    project["future"][idx] = []
    project["masks"][idx] = np.zeros((h, w), dtype=np.uint8)
    project["saved"][idx] = True
    project["frame_status"][idx] = "no_vessel"
    st.session_state.pop("all_export_bytes", None)
    project["canvas_version"] += 1
    if position + 1 < len(frames):
        st.session_state[next_key] = position + 1
        st.rerun()
    else:
        st.success("Ultimo frame contrassegnato come senza vaso. Puoi esportare tutte le maschere.")

if export_clicked:
    output = io.BytesIO()
    metadata = {
        "labels": {"0": "background", "1": "vein", "2": "artery"},
        "mask_formats": {"binary_masks": "0 background, 255 vessel"},
        "videos": [],
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for video_id, upload, _, _ in catalog:
            current = st.session_state.video_projects[video_id]
            folder = f"videos/{video_id}"
            entry = {
                "name": current["name"], "folder": folder,
                "fps": current["fps"], "total_frames": current["total"],
                "sampled_frames": len(current["frames"]), "frames": [],
            }
            for slot, (frame_idx, frame) in enumerate(current["frames"]):
                prefix = f"{safe_stem(current['name'])}_frame_{frame_idx:06d}"
                img_name = f"{folder}/images/{prefix}_img.png"
                archive.writestr(img_name, png_bytes(frame))
                seg = current["masks"][frame_idx]
                paths = {}
                for class_name, pixels in (
                    ("vein", seg == 1),
                    ("artery", seg == 2),
                    ("vessels", seg > 0),
                ):
                    path = f"{folder}/binary_masks/{prefix}_{class_name}.png"
                    archive.writestr(path, png_bytes(pixels.astype(np.uint8) * 255))
                    paths[class_name] = path
                entry["frames"].append({
                    "index": frame_idx, "slot": slot,
                    "time_seconds": frame_idx / current["fps"] if current["fps"] > 0 else None,
                    "image": img_name, "binary_masks": paths,
                    "saved": bool(current["saved"][frame_idx]),
                    "status": current["frame_status"][frame_idx],
                })
            metadata["videos"].append(entry)
        archive.writestr("metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))
    st.session_state.all_export_bytes = output.getvalue()

if st.session_state.get("all_export_bytes") is not None:
    st.download_button(
        "Scarica ZIP di tutti i video", st.session_state.all_export_bytes,
        file_name="ultrasound_annotations_all_videos.zip", mime="application/zip",
    )

st.markdown("---")
st.markdown("### Stato del progetto")
for video_id, upload, _, _ in catalog:
    current = st.session_state.video_projects[video_id]
    completed = sum(current["saved"].values())
    st.write(f"**{upload.name}** — {completed}/{len(current['frames'])} frame completati")
if not all(all(st.session_state.video_projects[k]["saved"].values()) for k,_,_,_ in catalog):
    st.warning("Alcuni frame non sono ancora completati. L'esportazione li include con stato 'pending' e maschera corrente: controlla prima di utilizzare il dataset.")
