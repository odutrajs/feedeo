"""Análise de mídia enviada: segmenta vídeos por corte de cena, transcreve a fala,
descreve e pontua cada trecho com IA de visão (pensando em criativos de anúncio).

Roda em background logo após o upload, para o usuário ver e escolher os trechos
antes mesmo de gerar o criativo.
"""

import base64
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.ai import get_openai
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.object_storage import get_object_storage
from app.db.models import SourceAsset, SourceSegment, SourceStatus
from app.modules.sources.media import (
    build_segments,
    detect_scene_cuts,
    extract_preview,
    extract_thumbnail,
    make_image_thumbnail,
    probe_media,
)

logger = get_logger("sources.analysis")

VISION_BATCH_SIZE = 8


class SegmentInsight(BaseModel):
    segment_index: int = Field(description="Índice do segmento analisado (na ordem enviada)")
    description: str = Field(
        description="Descrição objetiva do que aparece no trecho (1-2 frases, no idioma do projeto)"
    )
    tags: list[str] = Field(
        description=(
            "Tags do trecho, ex.: product_closeup, product_in_use, talking_head, "
            "unboxing, before_after, lifestyle, text_on_screen, hands_demo, "
            "reaction, transformation, low_quality, blurry"
        )
    )
    score: float = Field(
        description=(
            "Nota 0-10 do potencial deste trecho para um criativo de anúncio: "
            "nitidez, composição, produto visível, potencial de prender atenção"
        )
    )
    hook_potential: float = Field(
        description="Nota 0-10 do potencial deste trecho como HOOK (primeiros 3s do anúncio)"
    )
    score_reason: str = Field(description="Justificativa curta da nota")


class VisionAnalysis(BaseModel):
    segments: list[SegmentInsight]


VISION_SYSTEM_PROMPT = """\
Você é um diretor de criativos de performance (anúncios para TikTok/Reels/Shorts).
Você receberá frames de trechos de vídeos brutos enviados por um anunciante, com a
transcrição da fala de cada trecho (quando houver).

Para CADA trecho, avalie o potencial dele dentro de um criativo de anúncio:
- Qualidade visual (nitidez, enquadramento, iluminação).
- O que ele mostra: produto em close, produto em uso, pessoa falando (talking head),
  unboxing, antes/depois, reação, lifestyle, demonstração com as mãos etc.
- Potencial de HOOK: movimento, surpresa, transformação, close chamativo — coisas
  que param o scroll nos primeiros 3 segundos.
Seja criterioso: notas altas (8+) apenas para trechos realmente fortes.
"""


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _analyze_batch(
    entries: list[dict], language: str
) -> list[SegmentInsight]:
    """entries: [{"index": int, "thumbnail": Path, "transcript": str, "duration": float}]"""
    settings = get_settings()
    client = get_openai()

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Idioma das descrições: {language}. "
                f"Analise os {len(entries)} trechos a seguir. Para cada um envio o frame "
                "central e a transcrição da fala."
            ),
        }
    ]
    for entry in entries:
        content.append(
            {
                "type": "text",
                "text": (
                    f"Trecho {entry['index']} — duração {entry['duration']:.1f}s — "
                    f"fala: {entry['transcript'] or '(sem fala)'}"
                ),
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{_encode_image(entry['thumbnail'])}",
                    "detail": "low",
                },
            }
        )

    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=VisionAnalysis,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("O modelo não retornou análise dos trechos")
    return parsed.segments


def _transcribe_source(path: Path, language: str | None) -> list[dict]:
    """Transcreve o vídeo com detecção automática de idioma (fala pode não bater
    com o idioma do projeto). Retorna [{"text", "start", "end"}]."""
    from faster_whisper import WhisperModel

    settings = get_settings()
    lang = language.split("-")[0].lower() if language else None
    model = WhisperModel(settings.whisper_model_size, device="auto", compute_type="auto")
    segments, _info = model.transcribe(
        str(path), language=lang, word_timestamps=True, vad_filter=True
    )
    words = []
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                words.append({"text": text, "start": w.start, "end": w.end})
    return words


def _words_in_range(words: list[dict], start: float, end: float) -> str:
    inside = [
        w["text"]
        for w in words
        if (w["start"] + w["end"]) / 2 >= start and (w["start"] + w["end"]) / 2 < end
    ]
    return " ".join(inside)


def analyze_source(source_id: int) -> None:
    """Pipeline completo de análise de uma fonte (roda em background)."""
    from app.db.base import db_session

    settings = get_settings()
    with db_session() as db:
        source = db.get(SourceAsset, source_id)
        if source is None:
            return
        project = source.project
        source.status = SourceStatus.processing
        db.commit()

        sources_dir = settings.project_dir(project.id) / "sources" / str(source.id)

        try:
            # Baixa do MinIO se o arquivo não estiver no disco local
            abs_path = get_object_storage().ensure_local(source.path)
            if source.kind == "image":
                _analyze_image(db, source, abs_path, sources_dir, project.language)
            else:
                _analyze_video(db, source, abs_path, sources_dir, project.language)
            source.status = SourceStatus.ready
            source.error = None
        except Exception as exc:
            logger.exception("Falha ao analisar fonte %s", source_id)
            db.rollback()
            source = db.get(SourceAsset, source_id)
            source.status = SourceStatus.failed
            source.error = str(exc)
        db.commit()


def _analyze_image(db, source: SourceAsset, abs_path: Path, out_dir: Path, language: str) -> None:
    settings = get_settings()
    thumb = out_dir / "thumb.jpg"
    make_image_thumbnail(abs_path, thumb)
    get_object_storage().put_file(thumb, str(thumb.relative_to(settings.storage_dir)))

    insights = _analyze_batch(
        [{"index": 0, "thumbnail": thumb, "transcript": "", "duration": 0.0}],
        language,
    )
    insight = insights[0] if insights else None

    # Uma imagem vira um "segmento" único, para entrar na mesma seleção dos vídeos
    for old in list(source.segments):
        db.delete(old)
    db.flush()
    segment = SourceSegment(
        source_id=source.id,
        project_id=source.project_id,
        index=0,
        start=0.0,
        end=0.0,
        thumbnail_path=str(thumb.relative_to(settings.storage_dir)),
        transcript="",
        description=insight.description if insight else "",
        tags=insight.tags if insight else [],
        score=insight.score if insight else 5.0,
        score_reason=insight.score_reason if insight else "",
        meta={"hook_potential": insight.hook_potential if insight else 0.0, "kind": "image"},
    )
    db.add(segment)


def _analyze_video(db, source: SourceAsset, abs_path: Path, out_dir: Path, language: str) -> None:
    settings = get_settings()

    info = probe_media(abs_path)
    source.duration = info.duration
    source.width = info.width
    source.height = info.height
    source.meta = {**(source.meta or {}), "has_audio": info.has_audio, "fps": info.fps}
    db.commit()

    logger.info("Fonte %s: detectando cortes de cena (%.1fs)", source.id, info.duration)
    cuts = detect_scene_cuts(abs_path)
    windows = build_segments(info.duration, cuts)
    if not windows:
        windows = [(0.0, info.duration)]

    words: list[dict] = []
    if info.has_audio:
        logger.info("Fonte %s: transcrevendo fala (idioma auto)", source.id)
        try:
            words = _transcribe_source(abs_path, language=None)
        except Exception:
            logger.exception("Transcrição falhou; seguindo sem fala")

    # Extrai thumbnail + preview de cada janela
    storage = get_object_storage()
    entries: list[dict] = []
    for i, (start, end) in enumerate(windows):
        mid = (start + end) / 2
        thumb = out_dir / f"seg_{i:03d}.jpg"
        preview = out_dir / f"seg_{i:03d}.mp4"
        extract_thumbnail(abs_path, mid, thumb)
        extract_preview(abs_path, start, end, preview)
        storage.put_file(thumb, str(thumb.relative_to(settings.storage_dir)))
        storage.put_file(preview, str(preview.relative_to(settings.storage_dir)))
        entries.append(
            {
                "index": i,
                "start": start,
                "end": end,
                "thumbnail": thumb,
                "preview": preview,
                "transcript": _words_in_range(words, start, end),
                "duration": end - start,
            }
        )

    # Análise de visão em lotes
    insights: dict[int, SegmentInsight] = {}
    for batch_start in range(0, len(entries), VISION_BATCH_SIZE):
        batch = entries[batch_start : batch_start + VISION_BATCH_SIZE]
        try:
            for insight in _analyze_batch(
                [
                    {
                        "index": e["index"],
                        "thumbnail": e["thumbnail"],
                        "transcript": e["transcript"],
                        "duration": e["duration"],
                    }
                    for e in batch
                ],
                language,
            ):
                insights[insight.segment_index] = insight
        except Exception:
            logger.exception("Análise de visão falhou para um lote; seguindo com nota neutra")

    # Persiste segmentos (re-análise substitui os anteriores)
    for old in list(source.segments):
        db.delete(old)
    db.flush()

    for entry in entries:
        insight = insights.get(entry["index"])
        segment = SourceSegment(
            source_id=source.id,
            project_id=source.project_id,
            index=entry["index"],
            start=entry["start"],
            end=entry["end"],
            thumbnail_path=str(entry["thumbnail"].relative_to(settings.storage_dir)),
            preview_path=str(entry["preview"].relative_to(settings.storage_dir)),
            transcript=entry["transcript"],
            description=insight.description if insight else "",
            tags=insight.tags if insight else [],
            score=insight.score if insight else 5.0,
            score_reason=insight.score_reason if insight else "",
            meta={
                "hook_potential": insight.hook_potential if insight else 0.0,
                "kind": "video",
            },
        )
        db.add(segment)
    logger.info("Fonte %s: %d segmentos analisados", source.id, len(entries))
