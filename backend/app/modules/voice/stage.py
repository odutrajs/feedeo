from app.db.models import AssetKind
from app.modules.voice.service import synthesize
from app.pipeline.stage import Stage, StageContext


class VoiceStage(Stage):
    name = "voice"
    label = "Narração"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        config = project.config or {}
        scenes = sorted(project.scenes, key=lambda s: s.index)
        if not scenes:
            raise RuntimeError("Projeto não tem cenas; rode a etapa de roteiro primeiro")

        narration = " ".join(s.narration_text.strip() for s in scenes)
        ctx.set_status("Gravando a narração com voz sintética...")
        ctx.log(f"Sintetizando narração ({len(narration)} caracteres)")

        voice_settings = config.get("voice", {})
        audio_bytes = synthesize(
            narration,
            voice_id=voice_settings.get("voice_id"),
            stability=float(voice_settings.get("stability", 0.5)),
            similarity_boost=float(voice_settings.get("similarity_boost", 0.75)),
            style=float(voice_settings.get("style", 0.3)),
            speed=float(voice_settings.get("speed", 1.0)),
        )

        version = ctx.next_version(AssetKind.audio)
        path = ctx.subdir("audio") / f"v{version}.mp3"
        path.write_bytes(audio_bytes)
        ctx.set_status("Salvando o áudio da narração...")
        ctx.save_asset(AssetKind.audio, path, meta={"chars": len(narration)})
        ctx.log(f"Áudio salvo: {path.name} ({len(audio_bytes) / 1024:.0f} KB)")
