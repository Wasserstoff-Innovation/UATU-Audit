from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from ..colors import get_grade_color

def _color_for(grade: str) -> str:
    return get_grade_color(grade)

def render_badge(risk_json_path: Path, outdir: Path, label: str = "risk") -> Path:
    data = __import__("json").loads(risk_json_path.read_text())
    score = float(data.get("summary", {}).get("overall", 0.0))
    grade = str(data.get("summary", {}).get("grade", "Info"))
    color = _color_for(grade)

    tmpl_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(tmpl_dir)))
    svg = env.get_template("badge.svg.j2").render(score=score, grade=grade, color=color, label=label)

    outdir.mkdir(parents=True, exist_ok=True)
    badge_filename = f"badge-{label}.svg"
    badge_path = outdir / badge_filename
    badge_path.write_text(svg)
    return badge_path
