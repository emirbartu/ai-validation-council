"""CLI entry point for the AI Validation Council.

Usage::

    python -m council analyze "AI-powered sales automation for dentists"
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from council.logging_config import setup_logging

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def analyze(
    idea: Annotated[str, typer.Argument(help="The startup idea to validate. Wrap in quotes.")],
    results: Annotated[
        int, typer.Option("--results", "-n", help="Max search results per source")
    ] = 10,
) -> None:
    setup_logging()

    console.print(
        Panel.fit(
            f"[bold]Analyzing:[/bold] {idea}",
            title="AI Validation Council",
            border_style="blue",
        )
    )

    async def _run() -> None:
        from council.pipeline import run_analysis

        console.print("[yellow]Collecting market data...[/yellow]")
        result = await run_analysis(idea)

        agent_outputs = result.get("agent_outputs", [])
        divergence_points = result.get("divergence_points", [])
        confidence_score = result.get("confidence_score", 0.0)

        for output in agent_outputs:
            role = output.get("role", "unknown").replace("_", " ").title()
            content = output.get("content", "")
            console.print(
                Panel(
                    content[:2000] + ("..." if len(content) > 2000 else ""),
                    title=f"[bold cyan]{role}[/bold cyan]",
                    border_style="cyan",
                )
            )

            if role.lower() == "devils advocate":
                kill_shots = output.get("kill_shots", [])
                verdict = output.get("verdict", "")
                forbidden_ok = output.get("forbidden_check_passed", True)

                if verdict:
                    console.print(f"[bold red]Verdict:[/bold red] {verdict}")

                if kill_shots:
                    ks_table = Table(title="Kill Shots", border_style="red")
                    ks_table.add_column("#", style="dim")
                    ks_table.add_column("Title", style="bold red")
                    for ks in kill_shots:
                        ks_table.add_row(ks.get("number", "?"), ks.get("title", "")[:100])
                    console.print(ks_table)

                if not forbidden_ok:
                    console.print(
                        "[yellow]⚠ Forbidden phrase check failed on initial response[/yellow]"
                    )

        div_table = Table(title="Divergence Points", border_style="magenta")
        div_table.add_column("Topic", style="bold")
        div_table.add_column("Resolution Test")
        for div in divergence_points:
            div_table.add_row(
                div.get("topic", "")[:80],
                div.get("resolution_test", "")[:120],
            )
        if divergence_points:
            console.print(div_table)
        else:
            console.print("[dim]No divergence points detected[/dim]")

        from council.debate.confidence import interpret_score

        score_color = (
            "green" if confidence_score >= 60 else "yellow" if confidence_score >= 30 else "red"
        )
        console.print(
            Panel(
                f"[bold {score_color}]Confidence Score: {confidence_score}/100[/bold {score_color}]\n"
                f"{interpret_score(confidence_score)}",
                title="Overall Confidence",
                border_style=score_color,
            )
        )

        report = result.get("report", {}) or {}

        div_report = report.get("divergence_report", [])
        if div_report:
            div_table = Table(title="Divergence Report", border_style="magenta")
            div_table.add_column("Topic", style="bold")
            div_table.add_column("Position A", style="cyan")
            div_table.add_column("Position B", style="red")
            div_table.add_column("Resolution Test")
            for div in div_report:
                div_table.add_row(
                    div.get("topic", "")[:40],
                    div.get("position_a", "")[:60],
                    div.get("position_b", "")[:60],
                    div.get("resolution_test", "")[:80],
                )
            console.print(div_table)

        risks = report.get("risk_ranking", [])
        if risks:
            risk_table = Table(title="Risk Ranking", border_style="red")
            risk_table.add_column("Name", style="bold")
            risk_table.add_column("Sev.")
            risk_table.add_column("Prob.")
            risk_table.add_column("Rev.")
            risk_table.add_column("Score", style="bold red")
            risk_table.add_column("Description")
            for risk in sorted(risks, key=lambda x: x.get("score", 0), reverse=True):
                risk_table.add_row(
                    risk.get("name", "")[:40],
                    str(risk.get("severity", "")),
                    str(risk.get("probability", "")),
                    str(risk.get("reversibility", "")),
                    str(risk.get("score", "")),
                    risk.get("description", "")[:100],
                )
            console.print(risk_table)

        assumptions = report.get("critical_assumptions", [])
        if assumptions:
            assumption_table = Table(title="Critical Assumptions", border_style="yellow")
            assumption_table.add_column("Assumption", style="bold")
            assumption_table.add_column("Why Critical")
            assumption_table.add_column("Evidence", style="bold")
            assumption_table.add_column("Summary")
            for ass in assumptions:
                assumption_table.add_row(
                    ass.get("assumption", "")[:50],
                    ass.get("why_critical", "")[:60],
                    ass.get("evidence_strength", ""),
                    ass.get("evidence_summary", "")[:80],
                )
            console.print(assumption_table)

        experiments = report.get("validation_experiments", [])
        if experiments:
            exp_table = Table(title="Validation Experiments", border_style="green")
            exp_table.add_column("Name", style="bold")
            exp_table.add_column("Cost")
            exp_table.add_column("Time")
            exp_table.add_column("Success Criteria")
            exp_table.add_column("What It Tests")
            for exp in experiments:
                exp_table.add_row(
                    exp.get("name", "")[:40],
                    exp.get("cost_estimate", "")[:20],
                    exp.get("time_required", "")[:15],
                    exp.get("success_criteria", "")[:60],
                    exp.get("what_it_tests", "")[:60],
                )
            console.print(exp_table)

    asyncio.run(_run())


@app.command()
def version() -> None:
    from council import __version__

    console.print(f"AI Validation Council v{__version__}")


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of past analyses to show"),
    show: str | None = typer.Option(
        None, "--show", "-s", help="Show full details of a specific analysis by ID"
    ),
) -> None:
    """View past council analyses."""
    from council.memory.writeback import get_analysis, list_analyses

    if show:
        result = get_analysis(show)
        if not result.get("market_analyst") and not result.get("devils_advocate"):
            console.print(f"[red]Analysis '{show}' not found.[/red]")
            raise typer.Exit(1)

        timestamp = result.get("timestamp", "")
        date_str = ""
        if timestamp:
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                date_str = timestamp

        console.print(
            Panel.fit(
                f"[bold]Query:[/bold] {result.get('query', '')}\n[bold]Date:[/bold] {date_str}",
                title=f"Analysis {result['analysis_id']}",
                border_style="blue",
            )
        )

        ma = result.get("market_analyst", {})
        if ma:
            content = ma.get("content", "")
            console.print(
                Panel(
                    content[:2000] + ("..." if len(content) > 2000 else ""),
                    title="[bold cyan]Market Analyst[/bold cyan]",
                    border_style="cyan",
                )
            )

        da = result.get("devils_advocate", {})
        if da:
            content = da.get("content", "")
            console.print(
                Panel(
                    content[:2000] + ("..." if len(content) > 2000 else ""),
                    title="[bold cyan]Devil's Advocate[/bold cyan]",
                    border_style="cyan",
                )
            )

            kill_shots = da.get("kill_shots", [])
            verdict = da.get("verdict", "")
            forbidden_ok = da.get("forbidden_check_passed", True)

            if verdict:
                console.print(f"[bold red]Verdict:[/bold red] {verdict}")

            if kill_shots:
                ks_table = Table(title="Kill Shots", border_style="red")
                ks_table.add_column("#", style="dim")
                ks_table.add_column("Title", style="bold red")
                for ks in kill_shots:
                    ks_table.add_row(
                        str(ks.get("number", "?")),
                        ks.get("title", "")[:100],
                    )
                console.print(ks_table)

            if not forbidden_ok:
                console.print(
                    "[yellow]⚠ Forbidden phrase check failed on initial response[/yellow]"
                )

        divergence_count = result.get("divergence_count", 0)
        if divergence_count:
            console.print(f"[bold magenta]Divergence Points:[/bold magenta] {divergence_count}")
        else:
            console.print("[dim]No divergence points detected[/dim]")

        from council.debate.confidence import interpret_score

        confidence = result.get("confidence", 0.0)
        score_color = "green" if confidence >= 60 else "yellow" if confidence >= 30 else "red"
        console.print(
            Panel(
                f"[bold {score_color}]Confidence Score: {confidence:.0f}/100[/bold {score_color}]\n"
                f"{interpret_score(confidence)}",
                title="Overall Confidence",
                border_style=score_color,
            )
        )
    else:
        analyses = list_analyses(limit=limit)
        if not analyses:
            console.print("[dim]No past analyses found.[/dim]")
            return

        table = Table(title="Past Council Analyses", border_style="blue")
        table.add_column("ID", style="bold cyan")
        table.add_column("Query", style="dim")
        table.add_column("Date", style="green")
        table.add_column("Agents", justify="right")
        table.add_column("Div.", justify="right")
        table.add_column("Confidence", justify="right")

        for a in analyses:
            ts = a.get("timestamp", "")
            date_str = ""
            if ts:
                try:
                    dt = datetime.datetime.fromisoformat(ts)
                    date_str = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date_str = ts[:10]
            query = a.get("query", "")
            table.add_row(
                a["analysis_id"],
                query[:50] + ("..." if len(query) > 50 else ""),
                date_str,
                str(a.get("agent_count", 0)),
                str(a.get("divergence_count", 0)),
                f"{a.get('confidence', 0.0):.0f}",
            )

        console.print(table)


if __name__ == "__main__":
    app()
