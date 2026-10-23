"""US Vessel Studio V18.1 — header spacing correction."""
import base64
import hashlib
import html
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
:root {--orange:#ed6730;--coral:#e94a4c;--magenta:#c23b85;--purple:#63538e;--teal:#5baaa5;--ink:#353840}
.stApp {background:linear-gradient(135deg,#fff9f6 0%,#fdf9fc 52%,#f4fbfa 100%);color:#333841}
.block-container{max-width:1380px;padding-top:.8rem;padding-bottom:2rem}
[data-testid="stSidebar"]{background:#faf6fb}
[data-testid="stSidebar"] *{color:#413a50}
h1,h2,h3{color:#40394b}
.stButton button{border-radius:11px;font-weight:650;min-height:2.7rem;border:1px solid #e5dce8;color:#483f53;background:#fff}
.stButton button:hover{border-color:#c23b85;color:#9b2870;background:#fff7fc}
.stButton button[kind="primary"]{background:#c23b85;border-color:#c23b85;color:#fff}
.stButton button[kind="primary"]:hover{background:#a92d70;border-color:#a92d70;color:#fff}
/* Navigation: selected page solid purple; other page muted. */
div.st-key-nav_prepare button,div.st-key-nav_annotate button{font-weight:750!important;transition:background .15s ease,opacity .15s ease}
div.st-key-nav_prepare button[kind="primary"],div.st-key-nav_annotate button[kind="primary"]{background:#63538e!important;border:1px solid #63538e!important;color:#fff!important;opacity:1!important}
div.st-key-nav_prepare button[kind="secondary"],div.st-key-nav_annotate button[kind="secondary"]{background:#f0ebf8!important;border:1px solid #d9cee9!important;color:#63538e!important;opacity:.58!important}
div.st-key-nav_prepare button:hover,div.st-key-nav_annotate button:hover{opacity:1!important}
/* Uploader: prominent, subtle lavender backdrop. */
[data-testid="stFileUploader"]{background:#f4effa;border:1px solid #d9c9e9;border-radius:14px;padding:13px 17px;margin:8px 0 12px}
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] p{font-weight:850!important;font-size:1.12rem!important;color:#63538e!important}
[data-testid="stFileUploaderDropzone"]{background:#faf7fd!important;border:1.5px dashed #baa6d5!important;border-radius:12px!important}
[data-testid="stFileUploaderDropzone"] button{background:#63538e!important;color:white!important;border:1px solid #63538e!important;font-weight:800!important;font-size:1rem!important}
[data-testid="stFileUploaderDropzone"] button:hover{background:#514174!important}
div.st-key-paint_tool [data-testid="stWidgetLabel"] p{color:#63538e!important;font-weight:850!important;font-size:1.02rem!important}
div.st-key-export_project button{background:#63538e!important;color:#fff!important;border-color:#63538e!important}
div.st-key-no_vessel_action button{background:#fceef1!important;color:#a93854!important;border:1px solid #f1bccb!important}
div.st-key-save_frame_action button{background:#18864c!important;border-color:#18864c!important;color:#fff!important}
div.st-key-save_frame_action button:hover{background:#106b3b!important;border-color:#106b3b!important}
div.st-key-frame_prev button,div.st-key-frame_next button{background:#f1ebf9!important;color:#5d4885!important;border:1px solid #d6c7e8!important}
div.st-key-frame_prev button:hover,div.st-key-frame_next button:hover{background:#e8dcf4!important}
div.st-key-delete_last_stroke button{background:#fff3ed!important;color:#bc4d27!important;border:1px solid #f1cbb9!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:#e8ddea!important}
.stProgress > div > div > div > div{background:#c23b85!important}
.hero{background:linear-gradient(103deg,#ed6730 0%,#e94a4c 23%,#c23b85 49%,#63538e 74%,#5baaa5 100%);border-radius:16px;padding:14px 22px;color:white;margin-bottom:10px;box-shadow:0 10px 28px #7c4a7b1e}
.hero .eyebrow{font-size:.72rem;letter-spacing:.16em;color:#fff0e8;font-weight:800}
.hero .heading{font-size:1.55rem;font-weight:800;margin:2px 0;color:white}
.hero .subtitle{color:#fff6fa;font-size:.92rem}
.stage{display:inline-block;border-radius:999px;padding:5px 12px;font-size:.82rem;font-weight:700;background:#fbe9f2;color:#a42f75;margin-bottom:4px}
.metric{background:white;border:1px solid #efe1eb;border-radius:13px;padding:14px 18px;margin-bottom:12px}
.note{background:#f8edf5;border-left:4px solid #c23b85;padding:12px 16px;border-radius:8px;margin:12px 0}
.frame-title{font-size:1rem;font-weight:750;color:#50415d;margin:4px 0}
[data-testid="stImage"] img{border-radius:10px}

/* Simple, uncluttered tool labels. */
.status-card{display:inline-block;padding:9px 16px;border-radius:11px;font-size:1.05rem;font-weight:850;margin:8px 0 12px;border:1px solid #e0d6e9}
.status-annotated{background:#e9f6f0;color:#167246;border-color:#b8e4cc}
.status-no_vessel{background:#f3eafa;color:#63538e;border-color:#d8c7eb}
.status-pending{background:#fff2e8;color:#a64d21;border-color:#f4d4bd}
div.st-key-save_frame_action button{background:#18864c!important;color:#fff!important;border-color:#18864c!important}
div.st-key-frame_prev button,div.st-key-frame_next button{background:#63538e!important;color:white!important;border-color:#63538e!important;font-size:1.4rem!important;font-weight:900!important}
div.st-key-frame_prev button:hover,div.st-key-frame_next button:hover{background:#4d3c76!important;color:white!important}
div.st-key-nav_review button[kind="primary"]{background:#63538e!important;color:white!important;border-color:#63538e!important;opacity:1!important}
div.st-key-nav_review button[kind="secondary"]{background:#f0ebf8!important;color:#63538e!important;border-color:#d9cee9!important;opacity:.58!important}
div.st-key-nav_review button:hover{opacity:1!important}

/* V17 — visual refinement only. Original HUVANT color variables retained. */
html {scroll-behavior:smooth}
.stApp {font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.block-container {max-width:1320px;padding-top:4.5rem!important;padding-left:2.2rem;padding-right:2.2rem}
.hero {border-radius:20px;padding:26px 30px 22px;margin:12px 0 20px;box-shadow:0 14px 34px #63538e20;overflow:visible;scroll-margin-top:6rem}
.hero .heading {font-size:1.9rem;letter-spacing:-.035em;line-height:1.15;margin:6px 0}
.hero .subtitle {font-size:.98rem;opacity:.97}
.hero .eyebrow {letter-spacing:.19em;font-size:.72rem}
[data-testid="stHeadingWithActionElements"] h3 {letter-spacing:-.02em;font-weight:780}
/* Consistent white surfaces and generous hierarchy. */
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:17px!important;border:1px solid #e8ddea!important;background:#ffffffee!important;box-shadow:0 5px 22px #63538e0a}
[data-testid="stMetric"] {background:#fbf9fd;border:1px solid #eee7f4;border-radius:12px;padding:10px 14px}
[data-testid="stMetricLabel"] {color:#75677f;font-weight:650}
[data-testid="stMetricValue"] {color:#4c3d66;font-weight:800;letter-spacing:-.035em}
.stButton button, .stDownloadButton button {transition:background .18s,border-color .18s,transform .12s,box-shadow .18s;box-shadow:0 2px 5px #63538e0a}
.stButton button:hover,.stDownloadButton button:hover {box-shadow:0 5px 14px #63538e20;transform:translateY(-1px)}
.stButton button:focus-visible,.stDownloadButton button:focus-visible {outline:3px solid #5baaa5;outline-offset:2px}
/* Step navigation: strong active state, readable inactive state. */
div.st-key-nav_prepare button,div.st-key-nav_annotate button,div.st-key-nav_review button {border-radius:13px!important;min-height:3.05rem!important;font-weight:760!important}
div.st-key-nav_prepare button[kind="secondary"],div.st-key-nav_annotate button[kind="secondary"],div.st-key-nav_review button[kind="secondary"] {opacity:.75!important}
/* Upload area. */
[data-testid="stFileUploader"] {padding:19px 21px;border-radius:17px;box-shadow:0 5px 20px #63538e0b}
[data-testid="stFileUploaderDropzone"] {padding:20px!important;min-height:110px}
[data-testid="stFileUploaderDropzone"]:hover {border-color:#63538e!important;background:#f3ecfa!important}
/* Form elements and paint toolbar. */
[data-testid="stRadio"] label p,[data-testid="stSlider"] label p,[data-testid="stSelectSlider"] label p {font-weight:650;color:#534661}
[data-testid="stRadio"] [role="radiogroup"] {gap:.8rem}
[data-testid="stSlider"] [data-baseweb="slider"] {padding-top:.4rem}
[data-testid="stImage"] img {border-radius:12px;box-shadow:0 5px 16px #35384010}
.note {border-radius:12px;background:#f9f0f7;line-height:1.55}
.frame-title {font-size:1.07rem;font-weight:800;padding:7px 0;letter-spacing:-.01em}
.status-card {border-radius:999px;font-size:.92rem;padding:8px 15px;box-shadow:0 2px 8px #63538e0c}
/* Keep save as the only green action; other controls follow existing palette. */
div.st-key-save_frame_action button {min-height:3.15rem!important;font-weight:800!important;box-shadow:0 6px 16px #18864c24!important}
div.st-key-no_vessel_action button {min-height:3.15rem!important;font-weight:760!important}
div.st-key-frame_prev button,div.st-key-frame_next button {border-radius:12px!important;min-height:2.9rem!important}
div.st-key-delete_last_stroke button {font-weight:750!important}
[data-testid="stProgress"] {margin-top:.35rem;margin-bottom:.65rem}
[data-testid="stExpander"] {border:1px solid #e8ddea;border-radius:14px;background:#fff}
[data-testid="stExpander"] summary {font-weight:740;color:#63538e}
[data-testid="stDownloadButton"] button {background:#63538e!important;color:#fff!important;border-color:#63538e!important;font-weight:800!important;min-height:3.15rem}
[data-testid="stDownloadButton"] button:hover {background:#514174!important;color:#fff!important}
@media(max-width:800px) {.block-container{padding-left:1rem;padding-right:1rem;padding-top:4.5rem!important}.hero{padding:20px 19px}.hero .heading{font-size:1.55rem}}

/* V18: focused, compact workspace. Original HUVANT palette unchanged. */
.workspace-heading{display:flex;justify-content:space-between;align-items:center;gap:18px;margin:10px 0 8px}
.workspace-kicker{font-size:.75rem;font-weight:800;letter-spacing:.11em;color:#63538e;text-transform:uppercase}
.workspace-name{font-size:1.45rem;line-height:1.25;font-weight:850;color:#40394b;margin:3px 0}
.workspace-meta{font-size:.87rem;color:#776b7e}
.workspace-note{font-size:.86rem;color:#6b6071;margin:3px 0 10px}
.workspace-section{font-weight:800;font-size:.95rem;color:#50415d;margin:3px 0 7px}
/* Tool buttons: clear active selection; no radio circles. */
div.st-key-tool_vein button,div.st-key-tool_artery button,div.st-key-tool_eraser button{min-height:2.95rem!important;font-weight:800!important;border:1px solid #d9cee9!important;background:#fff!important;color:#63538e!important}
div.st-key-tool_vein button[kind="primary"],div.st-key-tool_artery button[kind="primary"],div.st-key-tool_eraser button[kind="primary"]{background:#63538e!important;color:white!important;border-color:#63538e!important;box-shadow:0 3px 12px #63538e25!important}
/* Image-first layout; do not interfere with the custom component iframe. */
div.st-key-annotation_canvas_panel{background:#22252b;border-radius:16px;padding:10px 12px 2px;box-shadow:0 8px 22px #35384022}
div.st-key-annotation_canvas_panel [data-testid="stCaptionContainer"] p{color:#e2dce8!important}
div.st-key-annotation_canvas_panel iframe{display:block;max-width:100%}
div.st-key-annotation_actions{padding-top:5px}
div.st-key-annotation_tools [data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important}
div.st-key-frame_prev button,div.st-key-frame_next button{min-height:2.65rem!important}
@media(max-width:800px){.workspace-heading{align-items:flex-start;flex-direction:column}.workspace-name{font-size:1.2rem}}

div.st-key-segmentation_finished button {
  background:#18864c!important;color:white!important;border-color:#18864c!important;
  font-weight:800!important;min-height:3.15rem!important;
}
div.st-key-segmentation_finished button:disabled {
  background:#edf0ee!important;color:#87918b!important;border-color:#dce2de!important;
  opacity:.58!important;box-shadow:none!important;
}
</style>""", unsafe_allow_html=True)

if st.session_state.get("stage", 0) == 0:
    st.markdown('<div class="hero"><div class="eyebrow">ULTRASOUND · ANNOTATION WORKSPACE</div><div class="heading">US Vessel Studio</div><div class="subtitle">Prepara i frame, annota vene e arterie, esporta un unico dataset multi-video.</div></div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="workspace-kicker">US VESSEL STUDIO · WORKSPACE</div>', unsafe_allow_html=True)


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
nav_a, nav_b, nav_d = st.columns([1, 1, 1], vertical_alignment="center")
with nav_a:
    if st.button("← 1 · Preparazione", use_container_width=True, type="primary" if st.session_state.stage == 0 else "secondary", key="nav_prepare"):
        st.session_state.stage = 0
        st.rerun()
with nav_b:
    if st.button("2 · Annotazione →", use_container_width=True, type="primary" if st.session_state.stage == 1 else "secondary", key="nav_annotate"):
        st.session_state.stage = 1
        st.rerun()
with nav_d:
    if st.button("3 · Revisione ed esportazione →", use_container_width=True, type="primary" if st.session_state.stage == 2 else "secondary", key="nav_review"):
        st.session_state.stage = 2
        st.rerun()
st.caption("Naviga liberamente tra le tre schermate: le annotazioni restano nella sessione finché non la azzeri.")

@st.dialog("Creare una nuova sessione?")
def confirm_new_session():
    st.warning("Questa operazione cancella tutti i video caricati e tutte le annotazioni non esportate. Non può essere annullata.")
    yes, no = st.columns(2)
    with yes:
        if st.button("Sì, elimina e ricomincia", type="primary", use_container_width=True):
            for key in ("projects", "export_bytes", "export_signature", "cursor", "stage"):
                st.session_state.pop(key, None)
            st.session_state.upload_nonce = st.session_state.get("upload_nonce", 0) + 1
            st.rerun()
    with no:
        if st.button("Annulla", use_container_width=True):
            st.rerun()

with st.sidebar:
    st.markdown("### Gestione sessione")
    if st.button("Nuova sessione · elimina corrente", use_container_width=True):
        confirm_new_session()

# Keep the uploader mounted on every rerun to preserve uploaded files.
# Hide it visually outside Preparazione, without destroying its widget state.
if st.session_state.stage != 0:
    st.markdown("<style>div.st-key-video_upload_shell{display:none!important}</style>", unsafe_allow_html=True)
with st.container(key="video_upload_shell"):
    uploads = st.file_uploader(
        "Carica video ecografici", type=["mp4", "avi", "mov", "mkv"],
        accept_multiple_files=True, key=f"videos_{st.session_state.upload_nonce}",
        label_visibility="visible",
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
if st.session_state.stage == 2:
    st.markdown('### <span class="stage">FASE 3</span> Revisione ed esportazione', unsafe_allow_html=True)
    completed_review = sum(st.session_state.projects[key]["statuses"].get(idx) in ("annotated", "no_vessel") for key, _, _, _ in catalog for idx in st.session_state.projects[key]["indices"])
    st.progress(completed_review / len(sequence), text=f"Frame completati: {completed_review}/{len(sequence)}")
    st.markdown("Verifica le maschere per ogni video. **Modifica** apre direttamente il frame nella schermata Annotazione. Le maschere bianche indicano i vasi, quelle nere lo sfondo.")
    for video_key, video_upload, _, _ in catalog:
        video_project = st.session_state.projects[video_key]
        with st.expander(f"{video_upload.name} · {len(video_project['indices'])} frame", expanded=True):
            indices = video_project["indices"]
            for start in range(0, len(indices), 3):
                cols = st.columns(3)
                for offset, position in enumerate(range(start, min(start + 3, len(indices)))):
                    index = indices[position]
                    with cols[offset]:
                        frame_status = video_project["statuses"].get(index, "pending")
                        st.markdown(f"**Frame {position+1} · originale #{index}**")
                        st.caption({"annotated":"Annotato", "no_vessel":"Nessun vaso", "pending":"Da completare"}[frame_status])
                        mask_review = video_project["masks"].get(index)
                        if mask_review is None:
                            try:
                                frame_shape = read_frame(video_upload.getvalue(), Path(video_upload.name).suffix, index).shape[:2]
                                mask_review = np.zeros(frame_shape, dtype=np.uint8)
                            except ValueError as exc:
                                st.error(str(exc))
                                continue
                        st.image((mask_review > 0).astype(np.uint8) * 255, caption="Maschera vessels", clamp=True, use_container_width=True)
                        if st.button("Modifica questo frame", key=f"review_edit_{video_key}_{position}", use_container_width=True):
                            st.session_state.cursor = next(i for i, (k, slot, _) in enumerate(sequence) if k == video_key and slot == position)
                            st.session_state.stage = 1
                            st.rerun()
    st.divider()
    if completed_review < len(sequence):
        st.warning(f"{len(sequence)-completed_review} frame ancora da completare. L'esportazione li includerà come 'pending'.")
    st.subheader("Scarica il dataset completo")
    st.caption("Un unico ZIP: cartelle separate per video, immagini, maschere binarie vein/artery/vessels e metadata.json.")
    if st.button("Nuova sessione · cancella progetto corrente", key="reset_from_review"):
        confirm_new_session()
if st.session_state.stage == 1:
    video_id, slot, frame_idx = sequence[st.session_state.cursor]
    project = st.session_state.projects[video_id]
    up, total, fps = catalog_by_key[video_id]

    completed = sum(
        st.session_state.projects[key]["statuses"].get(idx) in ("annotated", "no_vessel")
        for key, _, _, _ in catalog
        for idx in st.session_state.projects[key]["indices"]
    )
    status = project["statuses"].get(frame_idx, "pending")
    status_text = {"annotated": "✓ Annotato", "no_vessel": "✓ Nessun vaso", "pending": "○ Da completare"}[status]
    st.markdown(
        f'<div class="workspace-heading"><div><div class="workspace-kicker">FASE 2 · ANNOTAZIONE · {html.escape(up.name)}</div>'
        f'<div class="workspace-name">Frame {slot+1} di {len(project["indices"])}</div>'
        f'<div class="workspace-meta">Originale #{frame_idx} · Sequenza {st.session_state.cursor+1} di {len(sequence)}</div>'
        f'</div><div class="status-card status-{status}">{status_text}</div></div>',
        unsafe_allow_html=True,
    )
    st.progress(completed / len(sequence), text=f"Progetto: {completed}/{len(sequence)} frame completati")

    with st.container(key="annotation_tools", border=True):
        st.markdown('<div class="workspace-section">Strumenti di segmentazione</div>', unsafe_allow_html=True)
        if "paint_tool_choice" not in st.session_state:
            st.session_state.paint_tool_choice = "Vena"
        tc1, tc2, tc3 = st.columns(3, gap="small")
        for column, name, button_key in (
            (tc1, "Vena", "tool_vein"),
            (tc2, "Arteria", "tool_artery"),
            (tc3, "Gomma", "tool_eraser"),
        ):
            with column:
                if st.button(
                    name, key=button_key, use_container_width=True,
                    type="primary" if st.session_state.paint_tool_choice == name else "secondary",
                ):
                    st.session_state.paint_tool_choice = name
                    st.rerun()
        tool = st.session_state.paint_tool_choice
        t1, t2, t3 = st.columns(3, gap="medium")
        with t1:
            brush = st.slider("Diametro pennello (px)", 1, 10, 3, key="paint_brush")
        with t2:
            zoom = st.select_slider("Zoom", options=[1.0, 1.25, 1.5, 2.0, 2.5, 3.0], value=2.0, key="paint_zoom")
        with t3:
            opacity = st.slider("Opacità maschera (%)", 0, 80, 38, 5, key="paint_opacity") / 100

    with st.expander("Come segmentare un vaso", expanded=False):
        st.markdown(
            "**1.** Seleziona Vena o Arteria. **2.** Traccia il contorno completo del vaso "
            "con un unico gesto e rilascia: l'interno viene riempito automaticamente. "
            "**3.** Usa Gomma, Annulla o Ripristina per correggere. "
            "**4.** Salva il frame per confermarlo e passare al successivo. "
            "Se non ci sono vasi, scegli **Nessun vaso**."
        )

    # Three actions just below the segmentation instructions.
    all_frames_completed = all(
        st.session_state.projects[vid]["statuses"].get(idx) in ("annotated", "no_vessel")
        for vid, _, _, _ in catalog
        for idx in st.session_state.projects[vid]["indices"]
    )
    with st.container(key="annotation_actions"):
        save_col, empty_col, finished_col = st.columns([1.65, 1, 1.25], vertical_alignment="center")
        with save_col:
            save_clicked = st.button("✓ Salva e passa al prossimo →", key="save_frame_action", use_container_width=True)
        with empty_col:
            no_vessel_clicked = st.button("Nessun vaso", key="no_vessel_action", use_container_width=True)
        with finished_col:
            if st.button(
                "✓ Segmentazione finita", key="segmentation_finished",
                disabled=not all_frames_completed,
                help="Vai alla revisione" if all_frames_completed else "Conferma tutti i frame prima di terminare",
                use_container_width=True,
            ):
                st.session_state.stage = 2
                st.rerun()

    try:
        rgb = read_frame(up.getvalue(), Path(up.name).suffix, frame_idx)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    h, w = rgb.shape[:2]
    mask = project["masks"].setdefault(frame_idx, np.zeros((h, w), np.uint8))
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

    with st.container(key="annotation_canvas_panel"):
        st.caption("AREA DI ANNOTAZIONE · Traccia un contorno chiuso")
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

    # Frecce compatte sotto l'immagine, allineate a sinistra.
    left_nav, right_nav, space_nav = st.columns([0.65, 0.65, 5], vertical_alignment="center")
    with left_nav:
        if st.button("❮", help="Frame precedente", key="frame_prev", disabled=st.session_state.cursor == 0, use_container_width=True):
            navigate(-1)
    with right_nav:
        if st.button("❯", help="Frame successivo", key="frame_next", disabled=st.session_state.cursor == len(sequence)-1, use_container_width=True):
            navigate(1)

    st.caption("❮ / ❯: naviga tra i frame · Le modifiche diventano confermate con Salva e passa al prossimo")

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
        if st.button("↶ Cancella ultimo tratto", key="delete_last_stroke", use_container_width=True, disabled=not project["history"].get(frame_idx)):
            project["future"].setdefault(frame_idx, []).append(mask.copy())
            project["masks"][frame_idx] = project["history"][frame_idx].pop()
            project["statuses"][frame_idx] = "pending"
            project["revision"] += 1
            invalidate_export()
            st.rerun()


    # Handle confirmation after the current mask has been loaded.
    if save_clicked:
        if not np.any(project["masks"][frame_idx]):
            st.warning("Nessuna annotazione: usa 'Nessun vaso' se il frame non contiene vasi.")
        else:
            project["statuses"][frame_idx] = "annotated"
            invalidate_export()
            if st.session_state.cursor < len(sequence) - 1:
                navigate(1)
            else:
                st.rerun()

    if no_vessel_clicked:
        current_mask = project["masks"][frame_idx]
        project["history"].setdefault(frame_idx, []).append(current_mask.copy())
        project["future"][frame_idx] = []
        project["masks"][frame_idx] = np.zeros_like(current_mask)
        project["statuses"][frame_idx] = "no_vessel"
        project["revision"] += 1
        invalidate_export()
        if st.session_state.cursor < len(sequence) - 1:
            navigate(1)
        else:
            st.rerun()





def build_export_zip():
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
                    raise ValueError(f"Esportazione interrotta: {video_upload.name}, frame {index}: {exc}")
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
    return output.getvalue()

if st.session_state.stage == 2:
    # A single download control: ZIP is ready before the click, without an extra "Esporta" step.
    # Cache the prepared archive while annotations and video selection remain unchanged.
    export_signature = (
        tuple((key, tuple(st.session_state.projects[key]["indices"]), st.session_state.projects[key]["revision"]) for key, _, _, _ in catalog),
        tuple((key, tuple(sorted(st.session_state.projects[key]["statuses"].items()))) for key, _, _, _ in catalog),
    )
    if st.session_state.get("export_signature") != export_signature:
        st.session_state.pop("export_bytes", None)
    try:
        if "export_bytes" not in st.session_state:
            with st.spinner("Preparazione dell'archivio ZIP..."):
                st.session_state.export_bytes = build_export_zip()
            st.session_state.export_signature = export_signature
        st.download_button(
            "Scarica tutte le annotazioni (ZIP)",
            data=st.session_state.export_bytes,
            file_name="ultrasound_annotations_all_videos.zip",
            mime="application/zip",
            use_container_width=True,
            key="download_all_videos",
        )
    except ValueError as exc:
        st.error(str(exc))
