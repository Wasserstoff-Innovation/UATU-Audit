from datetime import datetime
from pathlib import Path
import os
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
    risk_export: str = typer.Option("csv", "--risk-export", help="csv | none (export format)")
):
    """
    Task 2:
    - prepare workdir (copy local sources OR fetch from Etherscan if address)
    - extract flows.json (regex-based)
    - generate journeys.json (fallback)
    - threats.json (empty buckets)
    - report.md/html
    """
    orchestrator = Orchestrator(input_path_or_address=input, kind=kind, out_root=Path(out), llm=(llm=="on"), static_mode=slither, eop_mode=eop, llm_provider=llm_provider, llm_model=llm_model, risk=(risk=="on"), risk_config_path=risk_config, risk_baseline=risk_baseline, risk_export=risk_export)
    outdir = orchestrator.run()
    print(f"[bold green]Audit completed[/bold green] → {outdir}")

@app.command()
def version():
    from . import __version__
    print(__version__)

if __name__ == "__main__":
    app()
