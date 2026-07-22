from app.db.models import AssetKind
from app.modules.publishing.service import generate_publish_meta
from app.pipeline.stage import Stage, StageContext


class PublishMetaStage(Stage):
    name = "publish_meta"
    label = "Metadados de publicação"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        scenes = sorted(project.scenes, key=lambda s: s.index)
        narration = " ".join(s.narration_text for s in scenes)

        ctx.set_status("Gerando títulos e descrições para cada plataforma...")
        ctx.log("Gerando título, descrição, hashtags e keywords por plataforma")
        meta = generate_publish_meta(
            title=project.title or project.topic,
            topic=project.topic,
            narration=narration,
            language=project.language,
        )

        path = ctx.project_dir / "publish_meta.json"
        path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        ctx.save_asset(
            AssetKind.publish_meta,
            path,
            meta={"platforms": [p.platform for p in meta.platforms]},
        )
        ctx.set_status("Metadados de publicação prontos!")
        ctx.log(f"Metadados prontos para: {', '.join(p.platform for p in meta.platforms)}")
