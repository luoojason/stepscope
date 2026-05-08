import typer

from stepscope._funnel import render_funnel, render_loops

app = typer.Typer(help="stepscope — funnel analytics for AI agents")


@app.command()
def funnel(
    db_path: str = typer.Argument(..., help="Path to SQLite DB"),
    since: str = typer.Option("24h", help="Window: 24h, 7d, all"),
) -> None:
    """Render an ASCII funnel of step drop-off."""
    typer.echo(render_funnel(db_path, since=since))


@app.command()
def loops(
    db_path: str = typer.Argument(..., help="Path to SQLite DB"),
    since: str = typer.Option("24h", help="Window: 24h, 7d, all"),
    threshold: int = typer.Option(3, help="Min fires to flag as a loop"),
) -> None:
    """List sessions where the same step fires >= threshold times."""
    typer.echo(render_loops(db_path, since=since, threshold=threshold))


@app.command()
def sessions(db_path: str = typer.Argument(..., help="Path to SQLite DB")) -> None:
    """List recent sessions. (W2.)"""
    raise typer.Exit("Not implemented yet — W2 deliverable.")


if __name__ == "__main__":
    app()
