"""Modo edit: constrói a EDL (Edit Decision List) a partir do vídeo bruto.

Quatro detectores rodam sobre a transcrição word-level do faster-whisper:

1. Comandos de voz — o criador fala "corta" depois de errar (removemos a
   tomada ruim para trás, incluindo o comando) ou delimita um trecho com
   "corta ... retoma" (removemos o intervalo inteiro).
2. Retakes — frases repetidas em sequência (com ou sem "corta") são detectadas
   por similaridade fuzzy; mantemos sempre a última tomada.
3. Silêncio / ar morto — gaps de fala acima do limiar do estilo viram jump cuts.
4. Vícios de fala — hesitações alongadas ("ééé", "hummm") são removidas
   quando o estilo permite.

O resultado é uma partição completa do vídeo em trechos keep/cut que o
usuário revisa antes do render.
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.core.logging import get_logger
from app.modules.editing.styles import EditStyle

logger = get_logger("editing.analysis")

CUT_MARKERS = {"corta", "cortar", "cut"}
RESUME_MARKERS = {"retoma", "retomar", "retomando", "voltei", "resume"}

# Janela máxima entre "corta" e "retoma" para tratar como região explícita
PAIR_WINDOW_SECONDS = 120.0
# Quanto olhar para trás ao remover uma tomada ruim após "corta" isolado
FLUB_LOOKBACK_SECONDS = 25.0
FLUB_UTTERANCE_GAP = 0.6
# "corta"/"retoma" só valem como comando se houver pausa depois da palavra —
# evita falso positivo com o verbo em fala normal ("corta ao meio", "retoma o assunto")
CUT_MARKER_MIN_PAUSE_AFTER = 0.5
RESUME_MARKER_MIN_PAUSE_AFTER = 0.3

FILLER_RE = re.compile(r"^(e+h+|é+h*|hu+m+|hm+|u+h+m*|a+h+n*|ã+h*|hã+)$")

REASON_PRIORITY = ["voice_command", "retake", "filler", "silence"]


@dataclass
class CutRegion:
    start: float
    end: float
    reason: str
    detail: str


def _norm(text: str) -> str:
    return re.sub(r"[^\wáéíóúâêôãõàç]+", "", text.lower(), flags=re.UNICODE)


def _utterances(words: list[dict], gap: float) -> list[list[int]]:
    """Agrupa índices de palavras em frases, separadas por pausas >= gap."""
    groups: list[list[int]] = []
    for i, word in enumerate(words):
        if groups and word["start"] - words[groups[-1][-1]]["end"] < gap:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


# ── Detectores ──────────────────────────────────────────────────────────────


def _is_marker(words: list[dict], i: int, markers: set[str], min_pause_after: float) -> bool:
    """Palavra de comando isolada: precisa de pausa depois (ou ser a última)."""
    if _norm(words[i]["text"]) not in markers:
        return False
    if i + 1 >= len(words):
        return True
    return words[i + 1]["start"] - words[i]["end"] >= min_pause_after


def _flub_start_index(words: list[dict], marker_idx: int) -> int:
    """Início da tomada ruim antes do marcador (última pausa longa, com limite)."""
    back = marker_idx
    while back > 0:
        gap = words[back]["start"] - words[back - 1]["end"]
        too_far = words[marker_idx]["end"] - words[back - 1]["start"] > FLUB_LOOKBACK_SECONDS
        if gap >= FLUB_UTTERANCE_GAP or too_far:
            break
        back -= 1
    return back


def _looks_like_retake(words: list[dict], marker_idx: int) -> bool:
    """A fala logo após o "corta" repete a fala anterior? Então foi erro de
    gravação (remoção para trás), não início de região "corta ... retoma"."""
    back = _flub_start_index(words, marker_idx)
    prev_text = " ".join(
        _norm(w["text"]) for w in words[back:marker_idx]
    )
    following = words[marker_idx + 1 : marker_idx + 13]
    next_text = " ".join(_norm(w["text"]) for w in following)
    if len(prev_text) < 8 or len(next_text) < 8:
        return False
    return fuzz.partial_ratio(prev_text, next_text) >= 70


def detect_voice_commands(words: list[dict]) -> list[CutRegion]:
    regions: list[CutRegion] = []
    i = 0
    n = len(words)
    while i < n:
        if not _is_marker(words, i, CUT_MARKERS, CUT_MARKER_MIN_PAUSE_AFTER):
            i += 1
            continue

        # Procura um "retoma" antes do próximo "corta", dentro da janela.
        # Exceção: se a fala seguinte repete a anterior, é um retake ("corta"
        # após erro) e a remoção é para trás.
        resume_idx = None
        if not _looks_like_retake(words, i):
            for j in range(i + 1, n):
                if words[j]["start"] - words[i]["end"] > PAIR_WINDOW_SECONDS:
                    break
                if _is_marker(words, j, CUT_MARKERS, CUT_MARKER_MIN_PAUSE_AFTER):
                    break
                if _is_marker(words, j, RESUME_MARKERS, RESUME_MARKER_MIN_PAUSE_AFTER):
                    resume_idx = j
                    break

        if resume_idx is not None:
            regions.append(
                CutRegion(
                    start=words[i]["start"],
                    end=words[resume_idx]["end"],
                    reason="voice_command",
                    detail='Trecho descartado por comando de voz ("corta ... retoma")',
                )
            )
            i = resume_idx + 1
            continue

        # "corta" isolado: remove a tomada ruim para trás (até a última pausa longa)
        back = _flub_start_index(words, i)
        regions.append(
            CutRegion(
                start=words[back]["start"],
                end=words[i]["end"],
                reason="voice_command",
                detail='Tomada com erro removida por comando de voz ("corta")',
            )
        )
        i += 1
    return regions


def detect_retakes(words: list[dict], style: EditStyle) -> list[CutRegion]:
    """Frases repetidas em sequência: corta as anteriores, mantém a última."""
    regions: list[CutRegion] = []
    groups = _utterances(words, style.utterance_gap)
    for k in range(1, len(groups)):
        prev, curr = groups[k - 1], groups[k]
        prev_text = " ".join(_norm(words[i]["text"]) for i in prev)
        curr_text = " ".join(_norm(words[i]["text"]) for i in curr)
        if len(prev) < 3 or not prev_text or not curr_text:
            continue
        # partial_ratio: a tomada ruim costuma ser um prefixo truncado da retomada
        score = fuzz.partial_ratio(prev_text, curr_text)
        if score >= style.retake_similarity:
            regions.append(
                CutRegion(
                    start=words[prev[0]]["start"],
                    end=words[prev[-1]]["end"],
                    reason="retake",
                    detail=f"Frase repetida em seguida (similaridade {score:.0f}%) — mantida a última tomada",
                )
            )
    return regions


def detect_fillers(words: list[dict]) -> list[CutRegion]:
    regions: list[CutRegion] = []
    for i, word in enumerate(words):
        norm = _norm(word["text"])
        if not FILLER_RE.match(norm):
            continue
        duration = word["end"] - word["start"]
        # Só remove hesitações claras: alongadas ou lentas e isoladas
        if len(norm) < 3 and duration < 0.35:
            continue
        gap_before = word["start"] - words[i - 1]["end"] if i > 0 else 1.0
        gap_after = words[i + 1]["start"] - word["end"] if i + 1 < len(words) else 1.0
        if gap_before < 0.1 and gap_after < 0.1:
            continue
        regions.append(
            CutRegion(
                start=word["start"],
                end=word["end"],
                reason="filler",
                detail=f'Hesitação "{word["text"].strip()}" removida',
            )
        )
    return regions


def detect_silences(
    words: list[dict], duration: float, style: EditStyle, existing: list[CutRegion]
) -> list[CutRegion]:
    """Gaps de fala acima do limiar do estilo (fora das regiões já cortadas)."""

    def covered(t: float) -> bool:
        return any(r.start <= t <= r.end for r in existing)

    kept = [w for w in words if not covered((w["start"] + w["end"]) / 2)]
    if not kept:
        return []

    regions: list[CutRegion] = []

    lead = kept[0]["start"] - style.pad_before_speech
    if lead > max(style.silence_gap, 0.5):
        regions.append(CutRegion(0.0, lead, "silence", f"Silêncio inicial de {lead:.1f}s"))

    for a, b in zip(kept, kept[1:]):
        gap = b["start"] - a["end"]
        if gap <= style.silence_gap:
            continue
        start = a["end"] + style.pad_after_speech
        end = b["start"] - style.pad_before_speech
        if end - start > 0.05:
            regions.append(
                CutRegion(start, end, "silence", f"Silêncio de {gap:.1f}s encurtado")
            )

    trail_start = kept[-1]["end"] + style.pad_after_speech
    if duration - trail_start > max(style.silence_gap, 0.5):
        regions.append(
            CutRegion(
                trail_start, duration, "silence", f"Silêncio final de {duration - trail_start:.1f}s"
            )
        )
    return regions


# ── Montagem da EDL ─────────────────────────────────────────────────────────


def _merge_regions(regions: list[CutRegion], duration: float) -> list[CutRegion]:
    clamped = [
        CutRegion(max(r.start, 0.0), min(r.end, duration), r.reason, r.detail)
        for r in regions
        if min(r.end, duration) - max(r.start, 0.0) > 0.01
    ]
    clamped.sort(key=lambda r: r.start)
    merged: list[CutRegion] = []
    for region in clamped:
        if merged and region.start <= merged[-1].end + 0.05:
            last = merged[-1]
            reason = min(
                (last.reason, region.reason), key=lambda x: REASON_PRIORITY.index(x)
            )
            detail = last.detail if reason == last.reason else region.detail
            merged[-1] = CutRegion(last.start, max(last.end, region.end), reason, detail)
        else:
            merged.append(region)
    return merged


def _words_in_range(words: list[dict], start: float, end: float) -> str:
    inside = [
        w["text"].strip()
        for w in words
        if start <= (w["start"] + w["end"]) / 2 < end
    ]
    return " ".join(inside)


def build_edl(words: list[dict], duration: float, style: EditStyle) -> list[dict]:
    """Particiona [0, duration] em trechos keep/cut com motivo e transcrição."""
    regions = detect_voice_commands(words)
    regions += detect_retakes(words, style)
    if style.remove_fillers:
        regions += detect_fillers(words)
    regions = _merge_regions(regions, duration)
    regions += detect_silences(words, duration, style, regions)
    regions = _merge_regions(regions, duration)

    # Remove micro-cortes e absorve micro-keeps entre cortes
    regions = [r for r in regions if r.end - r.start >= 0.12]
    absorbed: list[CutRegion] = []
    for region in regions:
        if absorbed and region.start - absorbed[-1].end < 0.25:
            last = absorbed[-1]
            reason = min(
                (last.reason, region.reason), key=lambda x: REASON_PRIORITY.index(x)
            )
            absorbed[-1] = CutRegion(last.start, region.end, reason, last.detail)
        else:
            absorbed.append(region)
    regions = absorbed

    # Partição alternada keep/cut cobrindo o vídeo inteiro
    edl: list[dict] = []
    cursor = 0.0
    for region in regions:
        if region.start - cursor > 0.05:
            edl.append(
                {
                    "start": round(cursor, 3),
                    "end": round(region.start, 3),
                    "action": "keep",
                    "reason": "speech",
                    "detail": "",
                }
            )
        edl.append(
            {
                "start": round(region.start, 3),
                "end": round(region.end, 3),
                "action": "cut",
                "reason": region.reason,
                "detail": region.detail,
            }
        )
        cursor = region.end
    if duration - cursor > 0.05:
        edl.append(
            {
                "start": round(cursor, 3),
                "end": round(duration, 3),
                "action": "keep",
                "reason": "speech",
                "detail": "",
            }
        )

    for entry in edl:
        entry["transcript"] = _words_in_range(words, entry["start"], entry["end"])

    kept = sum(e["end"] - e["start"] for e in edl if e["action"] == "keep")
    logger.info(
        "EDL: %d trechos (%.1fs mantidos de %.1fs)", len(edl), kept, duration
    )
    return edl


# ── Probe leve para uploads do modo edit ────────────────────────────────────


def probe_source(source_id: int) -> None:
    """Modo edit: só coleta metadados do upload (sem análise de visão/segmentos)."""
    from app.core.object_storage import get_object_storage
    from app.db.base import db_session
    from app.db.models import SourceAsset, SourceStatus
    from app.modules.sources.media import probe_media

    with db_session() as db:
        source = db.get(SourceAsset, source_id)
        if source is None:
            return
        try:
            abs_path = get_object_storage().ensure_local(source.path)
            if source.kind == "video":
                info = probe_media(abs_path)
                source.duration = info.duration
                source.width = info.width
                source.height = info.height
                source.meta = {**(source.meta or {}), "has_audio": info.has_audio, "fps": info.fps}
            source.status = SourceStatus.ready
            source.error = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao inspecionar fonte %s", source_id)
            source.status = SourceStatus.failed
            source.error = str(exc)
