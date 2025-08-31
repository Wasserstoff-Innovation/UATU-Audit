from datetime import datetime
from pathlib import Path
import os
import json
import typer
from rich import print
from .core import Orchestrator

app = typer.Typer(help="Contract Auditor CLI")

@app.command()
def audit(
    input: str = typer.Argument(..., help="Contract address or path"),
    kind: str = typer.Option("evm", "--kind", help="evm | stellar"),
    out: str = typer.Option("out", help="Output root folder"),
    llm: str = typer.Option("off", help="on | off (LLM augmentation)"),
    slither: str = typer.Option("auto", "--slither", help="static analysis mode: auto | host | stub"),
    eop: str = typer.Option("auto", "--eop", help="EoP test gating: auto | stride | heuristic | both | off"),
    llm_provider: str = typer.Option("auto", "--llm-provider", help="auto | openai | anthropic | off"),
    llm_model: str = typer.Option("", "--llm-model", help="override model name (optional)"),
    risk: str = typer.Option("on", "--risk", help="on | off (risk scoring)"),
    risk_config: str = typer.Option(None, "--risk-config", help="path to risk config JSON (optional)"),
    risk_baseline: str = typer.Option(None, "--risk-baseline", help="path to baseline risk.json for comparison"),
    risk_export: str = typer.Option("csv", "--risk-export", help="csv | none (export format)"),
    badge: str = typer.Option("on", "--badge", help="on | off (generate risk badge SVG)"),
    trend: str = typer.Option("on", "--trend", help="on | off (generate risk trend sparklines)"),
    trend_n: int = typer.Option(10, "--trend-n", help="number of history points to keep (default: 10)"),
    pdf: str = typer.Option("on", "--pdf", help="on | off (generate PDF report)")
):
    """
    Task 2:
    - prepare workdir (copy local sources OR fetch from Etherscan if address)
    - extract flows.json (regex-based)
    - generate journeys.json (fallback)
    - threats.json (empty buckets)
    - report.md/html
    """
    orchestrator = Orchestrator(input_path_or_address=input, kind=kind, out_root=Path(out), llm=(llm=="on"), static_mode=slither, eop_mode=eop, llm_provider=llm_provider, llm_model=llm_model, risk=(risk=="on"), risk_config_path=risk_config, risk_baseline=risk_baseline, risk_export=risk_export, badge=(badge=="on"), trend=(trend=="on"), trend_n=trend_n)
    outdir = orchestrator.run()
    print(f"[bold green]Audit completed[/bold green] → {outdir}")

@app.command()
def aggregate(
    inputs: str = typer.Option(None, "--inputs", help="Glob pattern or space-separated paths to risk.json files"),
    out: str = typer.Option("out-portfolio", "--out", help="Portfolio output root directory"),
    baseline: str = typer.Option(None, "--baseline", help="Path to portfolio baseline risk.json"),
    trend: str = typer.Option("on", "--trend", help="on | off (generate portfolio trend sparklines)"),
    trend_n: int = typer.Option(10, "--trend-n", help="number of history points to keep (default: 10)"),
    badge: str = typer.Option("on", "--badge", help="on | off (generate portfolio badge SVG)"),
    export: str = typer.Option("csv", "--export", help="csv | none (export format)")
):
    """
    Task 12: Aggregate risk data from multiple contracts into portfolio view.
    """
    from .portfolio.aggregate import aggregate_portfolio, export_portfolio_csv, save_portfolio
    from .badges.svg import render_badge
    from .trends.sparkline import render_sparkline
    from pathlib import Path
    import glob
    
    # Discover risk files
    risk_files = []
    if inputs:
        # Handle space-separated paths
        for pattern in inputs.split():
            if "*" in pattern:
                risk_files.extend(Path(p) for p in glob.glob(pattern))
            else:
                risk_files.append(Path(pattern))
    else:
        # Auto-discover all risk.json files
        risk_files = list(Path(".").glob("**/runs/risk/risk.json"))
    
    if not risk_files:
        print("[error] No risk.json files found")
        return
    
    print(f"Found {len(risk_files)} risk files")
    
    # Create output directory
    outdir = Path(out)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = outdir / ts
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Aggregate portfolio
    baseline_path = Path(baseline) if baseline else None
    portfolio = aggregate_portfolio(risk_files, baseline_path, outdir)
    
    # Save portfolio data
    portfolio_path = save_portfolio(portfolio, outdir)
    print(f"Portfolio saved to: {portfolio_path}")
    
    # Export CSV if requested
    if export == "csv":
        csv_path = export_portfolio_csv(portfolio, outdir)
        print(f"CSV exported to: {csv_path}")
    
    # Generate badge if requested
    if badge == "on":
        try:
            badge_path = render_badge(portfolio_path, outdir, label="portfolio")
            print(f"Portfolio badge generated: {badge_path}")
        except Exception as e:
            print(f"[warn] Portfolio badge generation failed: {e}")
    
    # Generate trend sparkline if requested
    if trend == "on":
        try:
            # Load portfolio history
            history = []
            if baseline_path and baseline_path.exists():
                baseline_dir = baseline_path.parent
                history_path = baseline_dir / "portfolio.history.json"
                if history_path.exists():
                    try:
                        history = json.loads(history_path.read_text())
                    except Exception:
                        pass
            
            # Append current point
            history.append({
                "ts": portfolio["generated_at"],
                "overall": portfolio["summary"]["overall"]
            })
            history = history[-trend_n:]  # Keep last N
            
            # Save local history
            history_path = outdir / "portfolio.history.json"
            history_path.write_text(json.dumps(history, indent=2))
            
            # Generate sparkline
            scores = [entry["overall"] for entry in history]
            sparkline_path, data_uri = render_sparkline(scores, portfolio["summary"]["grade"], outdir, width=200, height=30)
            
            # Rename to portfolio-specific filename
            portfolio_sparkline_path = outdir / "sparkline-portfolio.svg"
            if sparkline_path and sparkline_path.exists():
                sparkline_path.rename(portfolio_sparkline_path)
                sparkline_path = portfolio_sparkline_path
            
            # Save trend metadata
            trend_meta = {
                "count": len(history),
                "min": min(scores) if scores else 0.0,
                "max": max(scores) if scores else 0.0,
                "latest": portfolio["summary"]["overall"],
                "grade": portfolio["summary"]["grade"],
                "source": "local"
            }
            trend_meta_path = outdir / "portfolio.trend.meta.json"
            trend_meta_path.write_text(json.dumps(trend_meta, indent=2))
            
            print(f"Portfolio trend generated: {sparkline_path}")
            
        except Exception as e:
            print(f"[warn] Portfolio trend generation failed: {e}")
    
    # Generate reports
    try:
        from jinja2 import Environment, FileSystemLoader
        
        # Load templates
        tmpl_dir = Path(__file__).resolve().parent / "templates"
        env = Environment(loader=FileSystemLoader(str(tmpl_dir)))
        
        # Build context
        context = {
            "portfolio": portfolio,
            "portfolio_trend": None,
            "portfolio_badge": None
        }
        
        # Add trend data if available
        if trend == "on":
            trend_meta_path = outdir / "portfolio.trend.meta.json"
            if trend_meta_path.exists():
                try:
                    trend_meta = json.loads(trend_meta_path.read_text())
                    history_path = outdir / "portfolio.history.json"
                    if history_path.exists():
                        history = json.loads(history_path.read_text())
                        context["portfolio_trend"] = {
                            "series": [(entry["ts"], entry["overall"]) for entry in history],
                            "meta": trend_meta,
                            "svg_data_uri": ""
                        }
                        
                        # Try to load sparkline data URI
                        sparkline_path = outdir / "sparkline-portfolio.svg"
                        if sparkline_path.exists():
                            try:
                                svg_content = sparkline_path.read_text()
                                import base64
                                svg_bytes = svg_content.encode('utf-8')
                                data_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('utf-8')}"
                                context["portfolio_trend"]["svg_data_uri"] = data_uri
                            except Exception:
                                pass
                except Exception:
                    pass
        
        # Add badge data URI if available
        if badge == "on":
            badge_path = outdir / "badge-portfolio.svg"
            if badge_path.exists():
                try:
                    svg_content = badge_path.read_text()
                    import base64
                    svg_bytes = svg_content.encode('utf-8')
                    data_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('utf-8')}"
                    context["portfolio_badge"] = data_uri
                except Exception:
                    pass
        
        # Render reports
        html_template = env.get_template("portfolio_report.html.j2")
        md_template = env.get_template("portfolio_report.md.j2")
        
        html_content = html_template.render(**context)
        md_content = md_template.render(**context)
        
        # Save reports
        html_path = outdir / "portfolio.report.html"
        md_path = outdir / "portfolio.report.md"
        
        html_path.write_text(html_content)
        md_path.write_text(md_content)
        
        print(f"Portfolio reports generated:")
        print(f"  HTML: {html_path}")
        print(f"  Markdown: {md_path}")
        
    except Exception as e:
        print(f"[warn] Report generation failed: {e}")
    
    print(f"[bold green]Portfolio aggregation completed[/bold green] → {outdir}")

@app.command()
def version():
    from . import __version__
    print(__version__)

if __name__ == "__main__":
    app()
