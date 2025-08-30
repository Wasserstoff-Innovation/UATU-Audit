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
    slither: str = typer.Option("auto", "--slither", help="static analysis mode: auto | host | stub")
):
    """
    Task 2:
    - prepare workdir (copy local sources OR fetch from Etherscan if address)
    - extract flows.json (regex-based)
    - generate journeys.json (fallback)
    - threats.json (empty buckets)
    - report.md/html
    """
    orchestrator = Orchestrator(input_path_or_address=input, kind=kind, out_root=Path(out), llm=(llm=="on"), static_mode=slither)
    outdir = orchestrator.run()
    print(f"[bold green]Audit completed[/bold green] → {outdir}")

@app.command()
def version():
    from . import __version__
    print(__version__)

if __name__ == "__main__":
    app()
