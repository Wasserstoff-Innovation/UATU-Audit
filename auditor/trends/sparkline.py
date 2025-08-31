from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import base64
from ..colors import get_grade_color

def _color_for(grade: str) -> str:
    return get_grade_color(grade)

def _normalize_scores(scores: list[float]) -> list[float]:
    """Normalize scores to [0, 1] range, handling flat series."""
    if not scores:
        return []
    
    min_score = min(scores)
    max_score = max(scores)
    
    if max_score == min_score:
        # Flat series - return all 0.5 (middle)
        return [0.5] * len(scores)
    
    return [(score - min_score) / (max_score - min_score) for score in scores]

def _scores_to_points(scores: list[float], width: int = 140, height: int = 24) -> str:
    """Convert normalized scores to SVG polyline points."""
    if not scores:
        return ""
    
    # Add padding
    padding = 4
    plot_width = width - 2 * padding
    plot_height = height - 2 * padding
    
    points = []
    for i, score in enumerate(scores):
        x = padding + (i / (len(scores) - 1)) * plot_width if len(scores) > 1 else padding
        y = padding + (1 - score) * plot_height  # Invert Y so higher scores are lower on screen
        points.append(f"{x:.1f},{y:.1f}")
    
    return " ".join(points)

def render_sparkline(scores: list[float], grade: str, outdir: Path, width: int = 140, height: int = 24) -> tuple[Path, str]:
    """Render sparkline SVG and return file path + data URI."""
    if not scores:
        return None, ""
    
    # Normalize scores and convert to points
    normalized = _normalize_scores(scores)
    points = _scores_to_points(normalized, width, height)
    color = _color_for(grade)
    
    # Render SVG template
    tmpl_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(tmpl_dir)))
    svg = env.get_template("sparkline.svg.j2").render(
        w=width, h=height, color=color, points=points
    )
    
    # Save SVG file
    outdir.mkdir(parents=True, exist_ok=True)
    sparkline_path = outdir / "sparkline-risk.svg"
    sparkline_path.write_text(svg)
    
    # Generate data URI
    svg_bytes = svg.encode('utf-8')
    data_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('utf-8')}"
    
    return sparkline_path, data_uri
