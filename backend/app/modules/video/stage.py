import json

from app.core.object_storage import get_object_storage
from app.db.models import AssetKind
from app.modules.video.service import SceneClip, render_video
from app.pipeline.stage import Stage, StageContext


class RenderStage(Stage):
    name = "render"
    label = "Montagem do vídeo"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        scenes = sorted(project.scenes, key=lambda s: s.index)

        audio_asset = ctx.current_asset(AssetKind.audio)
        timeline_asset = ctx.current_asset(AssetKind.timeline)
        captions_asset = ctx.current_asset(AssetKind.captions)
        if audio_asset is None or timeline_asset is None:
            raise RuntimeError("Áudio ou timeline ausentes; rode as etapas anteriores")

        timeline = json.loads(ctx.abspath(timeline_asset.path).read_text(encoding="utf-8"))
        boundaries = {b["index"]: b for b in timeline["scenes"]}

        clips: list[SceneClip] = []
        for scene in scenes:
            boundary = boundaries[scene.index]
            duration = boundary["end"] - boundary["start"]
            visual = scene.visual_source or "ai_image"

            if visual == "segment" and scene.source_segment is not None:
                segment = scene.source_segment
                source = segment.source
                clips.append(
                    SceneClip(
                        duration=duration,
                        motion=scene.motion or "zoom_in",
                        video_path=get_object_storage().ensure_local(source.path),
                        video_start=segment.start,
                        video_end=segment.end,
                    )
                )
                ctx.log(
                    f"Cena {scene.index}: trecho de {source.filename} "
                    f"({segment.start:.1f}s–{segment.end:.1f}s)"
                )
                continue

            if visual == "source_image" and scene.source_asset is not None:
                clips.append(
                    SceneClip(
                        duration=duration,
                        motion=scene.motion or "zoom_in",
                        image_path=get_object_storage().ensure_local(scene.source_asset.path),
                    )
                )
                ctx.log(f"Cena {scene.index}: imagem enviada {scene.source_asset.filename}")
                continue

            image_asset = ctx.current_asset(AssetKind.image, scene_id=scene.id)
            if image_asset is None:
                raise RuntimeError(f"Cena {scene.index} sem imagem gerada")
            clips.append(
                SceneClip(
                    duration=duration,
                    motion=scene.motion or "zoom_in",
                    image_path=ctx.abspath(image_asset.path),
                )
            )

        config = project.config or {}
        music_path = None
        music_name = config.get("music")
        if music_name:
            candidate = ctx.settings.music_dir / music_name
            if candidate.exists():
                music_path = candidate
                ctx.log(f"Trilha sonora: {music_name}")
            else:
                ctx.log(f"Trilha '{music_name}' não encontrada em storage/music; seguindo sem música")

        version = ctx.next_version(AssetKind.video)
        output_path = ctx.subdir("video") / f"final_v{version}.mp4"
        ctx.set_status(f"Montando o vídeo final com {len(clips)} cenas...")
        ctx.log(f"Renderizando {len(clips)} cenas em {output_path.name}")

        render_video(
            clips=clips,
            narration_path=ctx.abspath(audio_asset.path),
            captions_path=ctx.abspath(captions_asset.path) if captions_asset else None,
            output_path=output_path,
            music_path=music_path,
            music_volume=float(config.get("music_volume", 0.22)),
        )
        asset = ctx.save_asset(
            AssetKind.video,
            output_path,
            meta={"duration": timeline["audio_duration"], "scenes": len(clips)},
        )
        ctx.set_status("Vídeo renderizado com sucesso!")
        ctx.log("Vídeo final renderizado")
        if get_object_storage().put_file(output_path, asset.path):
            ctx.log("Vídeo final salvo no MinIO")
