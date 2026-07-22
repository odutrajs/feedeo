import json

from app.db.models import AssetKind, Scene
from app.modules.script.service import generate_script
from app.pipeline.stage import Stage, StageContext


class ScriptStage(Stage):
    name = "script"
    label = "Roteiro"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        config = project.config or {}

        from app.modules.workspace.context import project_extra_instructions

        ctx.set_status("Escrevendo o roteiro com IA...")
        ctx.log(f"Gerando roteiro para o tema: {project.topic!r}")
        if project.workspace is not None:
            ctx.log(f"Usando contexto do projeto: {project.workspace.name!r}")
        script = generate_script(
            topic=project.topic,
            language=project.language,
            min_seconds=int(config.get("min_duration", 40)),
            max_seconds=int(config.get("max_duration", 75)),
            extra_instructions=project_extra_instructions(project, config),
        )
        ctx.set_status(f"Roteiro pronto! Salvando {len(script.scenes)} cenas...")
        ctx.log(f"Roteiro gerado: {script.title!r} com {len(script.scenes)} cenas")

        # Persist the script JSON as a versioned asset
        path = ctx.project_dir / "script.json"
        path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        ctx.save_asset(AssetKind.script, path, meta={"title": script.title})

        # Replace scene rows (idempotent re-run)
        for old in list(project.scenes):
            ctx.db.delete(old)
        project.scenes.clear()
        ctx.db.flush()

        for i, s in enumerate(script.scenes):
            scene = Scene(
                project_id=project.id,
                index=i,
                role=s.role,
                narration_text=s.narration,
                visual_description=s.visual_description,
                estimated_duration=s.estimated_duration_seconds,
            )
            project.scenes.append(scene)

        if not project.title:
            project.title = script.title
        ctx.db.commit()

        total = sum(s.estimated_duration_seconds for s in script.scenes)
        ctx.log(f"Duração estimada total: {total:.0f}s")
