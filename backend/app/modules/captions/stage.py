import json

from app.db.models import AssetKind
from app.modules.captions.service import render_caption_frames, write_concat_file
from app.modules.captions.styles import get_style
from app.pipeline.stage import Stage, StageContext


class CaptionsStage(Stage):
    name = "captions"
    label = "Legendas"

    def run(self, ctx: StageContext) -> None:
        timeline_asset = ctx.current_asset(AssetKind.timeline)
        if timeline_asset is None:
            raise RuntimeError("timeline.json não encontrado; rode a sincronização primeiro")
        timeline = json.loads(ctx.abspath(timeline_asset.path).read_text(encoding="utf-8"))

        style_name = (ctx.project.config or {}).get("caption_style", "default")
        style = get_style(style_name)
        ctx.set_status("Criando legendas estilo karaokê...")
        ctx.log(f"Renderizando legendas karaokê (preset: {style.name})")

        captions_dir = ctx.subdir("captions")
        # Clean previous renders so re-runs don't mix frames
        for old in captions_dir.glob("*.png"):
            old.unlink()

        frames = render_caption_frames(
            timeline["words"],
            style,
            captions_dir,
            width=ctx.settings.video_width,
            height=ctx.settings.video_height,
        )
        concat_path = write_concat_file(
            frames,
            blank_path=captions_dir / "blank.png",
            concat_path=captions_dir / "captions.ffconcat",
            total_duration=timeline["audio_duration"],
            width=ctx.settings.video_width,
            height=ctx.settings.video_height,
        )
        ctx.save_asset(
            AssetKind.captions,
            concat_path,
            meta={"style": style.name, "frames": len(frames)},
        )
        ctx.set_status(f"{len(frames)} quadros de legenda prontos!")
        ctx.log(f"{len(frames)} quadros de legenda gerados")
