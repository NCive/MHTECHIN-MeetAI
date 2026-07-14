"""
Meetingly — Minutes of Meeting (MoM) Generator
Meeting audio/video is never retained; only user accounts are stored.
"""

from __future__ import annotations
import logging
import os
import tempfile

import uuid
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Any
from faster_whisper import WhisperModel
from llama_cpp import Llama
import ffmpeg
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

load_dotenv()

from auth import (  # noqa: E402
    AuthResponse,
    CurrentUser,
    LoginRequest,
    MeResponse,
    SignupRequest,
    create_access_token,
    hash_password,
    user_to_public,
    verify_password,
)
from database import create_user, get_user_by_email, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meetingly")

# ── Config ──────────────────────────────────────────────────────────────────

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
LLM_MODEL_PATH = Path(os.getenv("LLM_MODEL")).resolve()
if not LLM_MODEL_PATH.exists():
    raise RuntimeError(f"Model not found: {LLM_MODEL_PATH}")
LLAMA_CONTEXT = int(os.getenv("LLAMA_CONTEXT", "4096"))
LLAMA_THREADS = int(os.getenv("LLAMA_THREADS", "8"))
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm"}
ALLOWED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

whisper_model = WhisperModel(
WHISPER_MODEL_NAME,
device="cpu",
compute_type="int8"
)
if not LLM_MODEL_PATH:

    raise RuntimeError(

        "LLM_MODEL missing in .env"

    )
llm = Llama(
model_path=LLM_MODEL_PATH,
n_ctx=LLAMA_CONTEXT,
n_threads=LLAMA_THREADS,
verbose=False
)

# ── Schemas ───────────────────────────

class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ActionItem(BaseModel):
    task: str = Field(description="Clear description of the action to be taken")
    owner: str = Field(description="Person or team responsible; 'Unassigned' if unclear")
    due_date: str = Field(
        description="Due date if mentioned, otherwise 'Not specified'"
    )
    priority: Priority = Field(description="Inferred priority of the action item")


class KeyDecision(BaseModel):
    decision: str = Field(description="What was decided")
    rationale: str = Field(
        description="Why it was decided, or 'Not stated' if not discussed"
    )
    stakeholders: list[str] = Field(
        description="People involved in or affected by the decision"
    )


class MeetingMoM(BaseModel):
    title: str = Field(description="Concise meeting title inferred from content")
    date_context: str = Field(
        description="Date/time references from the meeting, or 'Not mentioned'"
    )
    participants: list[str] = Field(
        description="Identified speakers/participants; empty list if unknown"
    )
    executive_summary: str = Field(
        description=(
            "2–4 paragraph executive summary covering purpose, main discussion "
            "themes, and outcomes. Written in professional prose."
        )
    )
    key_decisions: list[KeyDecision] = Field(
        description="Decisions made during the meeting; empty if none"
    )
    action_items: list[ActionItem] = Field(
        description="Concrete follow-ups with owners; empty if none"
    )
    topics_discussed: list[str] = Field(
        description="Bullet-style list of major topics covered"
    )
    next_steps: list[str] = Field(
        description="High-level next steps or follow-up meetings mentioned"
    )


# ── Prompt ───────────────────────────────────────────────────────────

LOCAL_PROMPT = """
You are an expert meeting assistant.

Your ONLY job is to convert the meeting transcript into Minutes of Meeting.

Return ONLY valid JSON.

Do NOT explain anything.

Do NOT use markdown.

Do NOT wrap the JSON in ```.

Missing information should be "Not specified".

JSON Schema:

{
"title":"",
"date_context":"",
"participants":[],
"executive_summary":"",
"topics_discussed":[],
"next_steps":[],
"action_items":[
{
"task":"",
"owner":"",
"due_date":"",
"priority":"high|medium|low"
}
],
"key_decisions":[
{
"decision":"",
"rationale":"",
"stakeholders":[]
}
]
}
"""

# ── App lifecycle ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):

    init_db()
    logger.info("User database ready")
    logger.info("Whisper model loaded")
    logger.info("LLM loaded")
    yield


app = FastAPI(
    title="Meetingly",
    description="Minutes of Meeting generator powered by Faster-Whisper + Qwen",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extension(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _is_video(ext: str) -> bool:
    return ext in VIDEO_EXTENSIONS


def extract_audio_to_temp(video_path: Path, work_dir: Path) -> Path:
    """
    Strip audio from video via ffmpeg into a temporary MP3.
    Runs as a transient subprocess; no persistent storage.
    """
    out_path = work_dir / f"{uuid.uuid4().hex}.mp3"
    try:
        (
            ffmpeg.input(str(video_path))
            .output(
                str(out_path),
                acodec="libmp3lame",
                audio_bitrate="128k",
                ac=1,  # mono — enough for speech, smaller payload
                ar="16000",
                vn=None,  # drop video
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        logger.error("ffmpeg failed: %s", stderr)
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract audio from video: {stderr[:500]}",
        ) from exc

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise HTTPException(
            status_code=422,
            detail="No audio stream found in the uploaded video.",
        )
    return out_path

def transcribe_audio(audio_path: Path):

    segments, info = whisper_model.transcribe(
        str(audio_path),
        beam_size=2,
        vad_filter=True,
        language="en"
    )

    transcript = ""
    for segment in segments:
        transcript += segment.text + " "
    return transcript.strip()

def generate_mom_from_audio(audio_path: Path) -> dict[str, Any]:
    try:
        transcript = transcribe_audio(audio_path)
        logger.info(transcript)
        prompt = f"""
        {LOCAL_PROMPT}
        Meeting Transcript
        {transcript}
        """
        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": LOCAL_PROMPT
                },
                {
                    "role": "user",
                    "content": transcript
                }
            ],
            temperature=0.2,
            response_format={
                "type": "json_object"
            }
        )
    except Exception as e:

        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
    text = response["choices"][0]["message"]["content"]
    try:
        mom = MeetingMoM.model_validate_json(text)
    except Exception:
        logger.error(text)
        raise HTTPException(
        status_code=500,
            detail="LLM returned invalid JSON."
        )
    
    return mom.model_dump()
    

# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "speech_model": WHISPER_MODEL_NAME,
        "llm_model": LLM_MODEL_PATH.name
    }


@app.post("/api/auth/signup", response_model=AuthResponse)
async def signup(body: SignupRequest) -> AuthResponse:
    email = str(body.email).strip().lower()
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    if get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    try:
        user = create_user(
            email=email,
            name=name,
            password_hash=hash_password(body.password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    token = create_access_token(user_id=user.id, email=user.email)
    logger.info("User signed up: %s", user.email)
    return AuthResponse(access_token=token, user=user_to_public(user))


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    email = str(body.email).strip().lower()
    user = get_user_by_email(email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user_id=user.id, email=user.email)
    logger.info("User logged in: %s", user.email)
    return AuthResponse(access_token=token, user=user_to_public(user))


@app.get("/api/auth/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    return user_to_public(user)


@app.post("/api/generate-mom")
async def generate_mom(
    user: CurrentUser,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Accept a video or audio upload (authenticated), extract audio if needed, and return
    structured Minutes of Meeting. Media is not persisted beyond the request.
    """
    ext = _extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext or 'unknown'}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Read into a temp workspace — deleted after the request
    work_dir = Path(tempfile.mkdtemp(prefix="meetingly_"))
    source_path = work_dir / f"source{ext}"
    audio_path: Path | None = None

    try:
        # Stream upload to disk in chunks (still ephemeral)
        total = 0
        with open(source_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                out.write(chunk)

        if total == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        logger.info("User %s uploaded %s (%d bytes)", user.email, file.filename, total)

        if _is_video(ext):
            logger.info("Video detected — extracting audio with ffmpeg")
            audio_path = extract_audio_to_temp(source_path, work_dir)
        else:
            audio_path = source_path

        mom = generate_mom_from_audio(audio_path)
        return {
            "success": True,
            "filename": file.filename,
            "mom": mom,
        }
    finally:
        # Ephemeral media: wipe the entire temp workspace
        try:
            for p in work_dir.glob("**/*"):
                if p.is_file():
                    p.unlink(missing_ok=True)
            work_dir.rmdir()
        except Exception:
            logger.warning("Temp cleanup incomplete for %s", work_dir, exc_info=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
