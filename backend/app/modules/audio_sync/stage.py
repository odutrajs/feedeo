import json

from app.db.models import AssetKind
from app.modules.audio_sync.service import align_words_to_scenes, build_timeline, transcribe_words
from app.modules.video.ffmpeg import probe_duration
from app.pipeline.stage import Stage, StageContext


class AudioSyncStage(Stage):
    name = "audio_sync"
    label = "Sincronização"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        scenes = sorted(project.scenes, key=lambda s: s.index)

        audio_asset = ctx.current_asset(AssetKind.audio)
        if audio_asset is None:
            raise RuntimeError("Nenhum áudio encontrado; rode a etapa de narração primeiro")
        audio_path = ctx.abspath(audio_asset.path)
        duration = probe_duration(audio_path)
        ctx.set_status("Transcrevendo o áudio com Whisper...")
        ctx.log(f"Transcrevendo áudio ({duration:.1f}s) com whisper local (idioma auto)")

        # Idioma detectado do áudio: garante legendas no mesmo idioma da narração
        words, detected_language = transcribe_words(audio_path, language=None)
        project_lang = (project.language or "").split("-")[0].lower()
        if detected_language and project_lang and detected_language != project_lang:
            ctx.log(
                f"Atenção: idioma detectado no áudio ({detected_language}) difere do "
                f"idioma do projeto ({project.language}); as legendas seguirão o áudio"
            )
        ctx.set_status(f"Alinhando {len(words)} palavras com {len(scenes)} cenas...")
        ctx.log(f"{len(words)} palavras transcritas; alinhando com {len(scenes)} cenas")

        align_words_to_scenes(words, [s.narration_text for s in scenes])
        timeline = build_timeline(words, len(scenes), duration)

        # Persist scene boundaries on the DB rows
        for scene, boundary in zip(scenes, timeline["scenes"]):
            scene.start_time = boundary["start"]
            scene.end_time = boundary["end"]
        ctx.db.commit()

        path = ctx.project_dir / "timeline.json"
        path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.save_asset(
            AssetKind.timeline,
            path,
            meta={"words": len(words), "duration": duration, "language": detected_language},
        )
        ctx.log("timeline.json gerado com marcações de cena e palavra")
