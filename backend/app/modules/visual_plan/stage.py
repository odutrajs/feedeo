import json

from app.db.models import AssetKind
from app.modules.visual_plan.service import generate_visual_plan
from app.pipeline.stage import Stage, StageContext


class VisualPlanStage(Stage):
    name = "visual_plan"
    label = "Planejamento visual"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        scenes = sorted(project.scenes, key=lambda s: s.index)
        if not scenes:
            raise RuntimeError("Projeto não tem cenas; rode a etapa de roteiro primeiro")

        ctx.set_status("Criando o estilo visual e prompts para cada cena...")
        ctx.log("Gerando style guide e prompts de imagem por cena")
        plan = generate_visual_plan(
            scenes=[
                {
                    "index": s.index,
                    "role": s.role,
                    "narration": s.narration_text,
                    "visual_description": s.visual_description,
                }
                for s in scenes
            ],
            topic=project.topic,
            style_preset=(project.config or {}).get("style_preset"),
        )

        plans_by_index = {p.scene_index: p for p in plan.scene_plans}
        for scene in scenes:
            scene_plan = plans_by_index.get(scene.index)
            if scene_plan is None:
                raise RuntimeError(f"Plano visual não cobriu a cena {scene.index}")
            scene.image_prompt = scene_plan.image_prompt
            scene.motion = scene_plan.motion
        ctx.db.commit()

        path = ctx.project_dir / "visual_plan.json"
        path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        ctx.save_asset(AssetKind.style_guide, path, meta={"style_guide": plan.style_guide[:200]})
        ctx.set_status("Salvando o plano visual...")
        ctx.log(f"Style guide definido: {plan.style_guide[:120]}...")
