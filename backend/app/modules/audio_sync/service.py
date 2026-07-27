"""Módulo 3: análise do áudio com faster-whisper (word-level timestamps)
e alinhamento das palavras com as cenas do roteiro.

Saída: timeline com início/fim de cada cena e timestamp de cada palavra,
usada pela montagem do vídeo (M6) e pelas legendas (M7).
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("audio_sync")


@dataclass
class Word:
    text: str
    start: float
    end: float
    scene_index: int = -1


def _normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.lower())
    word = "".join(c for c in word if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", word)


def transcribe_words(
    audio_path: Path, language: str | None = None
) -> tuple[list[Word], str]:
    """Transcribe the narration returning word-level timestamps.

    O idioma é detectado automaticamente a partir do áudio (não forçado a partir
    da configuração do projeto): se a narração saiu em outro idioma, as legendas
    acompanham o áudio em vez de virar uma transcrição errada. Retorna também o
    idioma detectado (ex.: "en", "pt").
    """
    from faster_whisper import WhisperModel

    settings = get_settings()
    lang = language.split("-")[0].lower() if language else None
    logger.info("Carregando modelo whisper '%s'", settings.whisper_model_size)
    model = WhisperModel(settings.whisper_model_size, device="auto", compute_type="auto")
    segments, info = model.transcribe(
        str(audio_path), language=lang, word_timestamps=True, vad_filter=True
    )
    words: list[Word] = []
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                # Cast to native float: whisper returns np.float64, which
                # psycopg2 stringifies as "np.float64(...)" and breaks Postgres.
                words.append(Word(text=text, start=float(w.start), end=float(w.end)))
    detected = info.language or (lang or "")
    logger.info(
        "Idioma detectado no áudio: %s (probabilidade %.2f)",
        detected,
        info.language_probability or 0.0,
    )
    return words, detected


def align_words_to_scenes(words: list[Word], scene_texts: list[str]) -> None:
    """Assign each transcribed word to a scene using sequence alignment.

    The narration was synthesized from the exact scene texts, so the
    transcript is nearly identical; SequenceMatcher on normalized tokens
    handles the small ASR differences.
    """
    script_tokens: list[str] = []
    script_scene_of: list[int] = []
    for scene_index, text in enumerate(scene_texts):
        for token in text.split():
            normalized = _normalize(token)
            if normalized:
                script_tokens.append(normalized)
                script_scene_of.append(scene_index)

    trans_tokens = [_normalize(w.text) for w in words]

    matcher = SequenceMatcher(a=script_tokens, b=trans_tokens, autojunk=False)
    for op, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if op in ("equal", "replace"):
            span = max(a_end - a_start, 1)
            for offset in range(b_start, b_end):
                # Map transcript position proportionally into the script span
                rel = (offset - b_start) / max(b_end - b_start, 1)
                a_pos = min(a_start + int(rel * span), len(script_scene_of) - 1)
                words[offset].scene_index = script_scene_of[a_pos]

    # Fill unmatched words with the previous word's scene (or the next known one)
    last = 0
    for w in words:
        if w.scene_index < 0:
            w.scene_index = last
        last = w.scene_index
    # Enforce monotonically increasing scene indices
    for i in range(1, len(words)):
        if words[i].scene_index < words[i - 1].scene_index:
            words[i].scene_index = words[i - 1].scene_index


def build_timeline(
    words: list[Word], scene_count: int, audio_duration: float
) -> dict:
    """Compute contiguous scene boundaries from the aligned words."""
    boundaries: list[dict] = []
    for scene_index in range(scene_count):
        scene_words = [w for w in words if w.scene_index == scene_index]
        if scene_words:
            start, end = scene_words[0].start, scene_words[-1].end
        else:
            start = end = None  # resolved below by interpolation
        boundaries.append({"index": scene_index, "start": start, "end": end})

    # Interpolate scenes with no matched words
    for i, b in enumerate(boundaries):
        if b["start"] is None:
            prev_end = boundaries[i - 1]["end"] if i > 0 else 0.0
            next_start = None
            for later in boundaries[i + 1:]:
                if later["start"] is not None:
                    next_start = later["start"]
                    break
            if next_start is None:
                next_start = audio_duration
            b["start"], b["end"] = prev_end, next_start

    # Make boundaries contiguous: split the gap between scenes at the midpoint
    if boundaries:
        boundaries[0]["start"] = 0.0
        boundaries[-1]["end"] = float(audio_duration)
        for i in range(scene_count - 1):
            midpoint = float(
                (boundaries[i]["end"] + boundaries[i + 1]["start"]) / 2
            )
            boundaries[i]["end"] = midpoint
            boundaries[i + 1]["start"] = midpoint

    # Ensure all times are native floats (never np.float64) for DB/JSON.
    for b in boundaries:
        if b["start"] is not None:
            b["start"] = float(b["start"])
        if b["end"] is not None:
            b["end"] = float(b["end"])

    return {
        "audio_duration": float(audio_duration),
        "scenes": boundaries,
        "words": [
            {
                "text": w.text,
                "start": float(w.start),
                "end": float(w.end),
                "scene_index": w.scene_index,
            }
            for w in words
        ],
    }
