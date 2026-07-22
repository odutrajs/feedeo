"""Etapas do pipeline do modo edit: análise dos cortes e render final."""

import json

from app.core.object_storage import get_object_storage
from app.db.models import AssetKind, EditCut, SourceAsset, SourceStatus
from app.modules.editing.analysis import build_edl
from app.modules.editing.render import KeepSegment, render_edit
from app.modules.editing.styles import get_style
from app.modules.sources.media import extract_preview, extract_thumbnail, probe_media
from app.pipeline.stage import Stage, StageContext

MAX_PREVIEWS = 120  # limite de previews gerados (proteção para vídeos muito longos)


def _get_raw_video(ctx: StageContext) -> SourceAsset:
    videos = [
        s
        for s in ctx.project.sources
        if s.kind == "video" and s.status != SourceStatus.failed
    ]
    if not videos:
        raise RuntimeError("Envie o vídeo bruto antes de rodar a edição")
    if len(videos) > 1:
        ctx.log(
            f"{len(videos)} vídeos enviados; usando o primeiro "
            f"({videos[0].filename}). Edição multi-arquivo ainda não é suportada."
        )
    return videos[0]


def _transcribe(ctx: StageContext, path, language: str | None) -> list[dict]:
    from faster_whisper import WhisperModel

    lang = language.split("-")[0].lower() if language else None
    model = WhisperModel(
        ctx.settings.whisper_model_size, device="auto", compute_type="auto"
    )
    segments, _info = model.transcribe(
        str(path), language=lang, word_timestamps=True, vad_filter=True
    )
    words: list[dict] = []
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                words.append({"text": text, "start": w.start, "end": w.end})
    return words


class EditAnalysisStage(Stage):
    name = "edit_analysis"
    label = "Análise dos cortes"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        config = project.config or {}
        style = get_style(config.get("edit_style"))
        source = _get_raw_video(ctx)

        abs_path = get_object_storage().ensure_local(source.path)
        info = probe_media(abs_path)
        if source.duration is None:
            source.duration = info.duration
            ctx.db.commit()

        ctx.set_status("Transcrevendo o vídeo (timestamps por palavra)...")
        ctx.log(f"Estilo de edição: {style.label}")
        words: list[dict] = []
        if info.has_audio:
            words = _transcribe(ctx, abs_path, project.language)
            ctx.log(f"Transcrição: {len(words)} palavras")
        else:
            ctx.log("Vídeo sem áudio: sem cortes por fala; mantendo o vídeo inteiro")

        transcript_path = ctx.subdir("editing") / "transcript.json"
        transcript_path.write_text(
            json.dumps({"words": words, "duration": info.duration}, ensure_ascii=False),
            encoding="utf-8",
        )
        ctx.save_asset(AssetKind.transcript, transcript_path, meta={"words": len(words)})

        ctx.set_status("Detectando comandos de voz, retakes e silêncios...")
        edl = build_edl(words, info.duration, style)

        # Substitui a EDL anterior (re-análise é idempotente)
        for old in list(project.edit_cuts):
            ctx.db.delete(old)
        ctx.db.flush()

        media_dir = ctx.subdir("editing") / "cuts"
        storage = get_object_storage()
        cuts: list[EditCut] = []
        for i, entry in enumerate(edl):
            cut = EditCut(
                project_id=project.id,
                source_id=source.id,
                index=i,
                start=entry["start"],
                end=entry["end"],
                action=entry["action"],
                reason=entry["reason"],
                transcript=entry.get("transcript", ""),
                detail=entry.get("detail", ""),
            )
            ctx.db.add(cut)
            cuts.append(cut)
        ctx.db.commit()

        ctx.set_status("Gerando miniaturas e prévias dos trechos...")
        for i, (cut, entry) in enumerate(zip(cuts, edl)):
            mid = (entry["start"] + entry["end"]) / 2
            thumb = media_dir / f"cut_{i:04d}.jpg"
            extract_thumbnail(abs_path, mid, thumb)
            cut.thumbnail_path = ctx.relpath(thumb)
            storage.put_file(thumb, cut.thumbnail_path)
            if i < MAX_PREVIEWS:
                preview = media_dir / f"cut_{i:04d}.mp4"
                extract_preview(abs_path, entry["start"], entry["end"], preview)
                cut.preview_path = ctx.relpath(preview)
                storage.put_file(preview, cut.preview_path)
        ctx.db.commit()

        kept = sum(c.duration for c in cuts if c.action == "keep")
        removed = info.duration - kept
        n_cuts = sum(1 for c in cuts if c.action == "cut")
        ctx.set_status(
            f"{n_cuts} cortes sugeridos — {removed:.0f}s removidos de {info.duration:.0f}s"
        )
        ctx.log(
            f"EDL pronta: {len(cuts)} trechos, {n_cuts} cortes, "
            f"{kept:.1f}s mantidos ({removed:.1f}s removidos)"
        )


class EditRenderStage(Stage):
    name = "edit_render"
    label = "Render final"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        config = project.config or {}
        style = get_style(config.get("edit_style"))
        aspect = str(config.get("aspect", "original"))
        source = _get_raw_video(ctx)
        abs_path = get_object_storage().ensure_local(source.path)

        keeps = sorted(
            (c for c in project.edit_cuts if c.action == "keep"), key=lambda c: c.start
        )
        if not keeps:
            raise RuntimeError("Nenhum trecho marcado para manter; revise os cortes")

        # Junta keeps adjacentes (ex.: usuário reverteu um corte no meio)
        merged: list[list[float]] = []
        for cut in keeps:
            if merged and cut.start - merged[-1][1] < 0.05:
                merged[-1][1] = cut.end
            else:
                merged.append([cut.start, cut.end])

        segments: list[KeepSegment] = []
        prev_end: float | None = None
        for start, end in merged:
            removed = (start - prev_end) if prev_end is not None else 0.0
            segments.append(KeepSegment(start=start, end=end, removed_before=removed))
            prev_end = end

        version = ctx.next_version(AssetKind.video)
        output_path = ctx.subdir("video") / f"final_v{version}.mp4"
        workdir = ctx.subdir("editing") / "render_tmp"

        transition = str(config.get("transition", "auto"))
        audio_enhance = str(config.get("audio_enhance", "full"))
        ctx.log(
            f"Renderizando {len(segments)} trechos mantidos "
            f"(estilo {style.label}, aspecto {aspect}, transição {transition}, "
            f"áudio {audio_enhance})"
        )

        def on_progress(done: int, total: int) -> None:
            if done % 5 == 0 or done == total:
                ctx.set_status(f"Cortando trechos... {done}/{total}")

        meta = render_edit(
            source_path=abs_path,
            segments=segments,
            style=style,
            output_path=output_path,
            workdir=workdir,
            aspect=aspect,
            transition=transition,
            audio_enhance=audio_enhance,
            on_progress=on_progress,
        )

        asset = ctx.save_asset(AssetKind.video, output_path, meta=meta)
        ctx.set_status(
            f"Vídeo editado: {meta['duration']:.0f}s "
            f"(original {meta['source_duration']:.0f}s)"
        )
        ctx.log("Vídeo final renderizado")
        if get_object_storage().put_file(output_path, asset.path):
            ctx.log("Vídeo final salvo no MinIO")
