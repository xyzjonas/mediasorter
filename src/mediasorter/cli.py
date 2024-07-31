import asyncio
import logging
import os
import sys
from typing import Annotated, Optional

import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Column
from rich.text import Text

from mediasorter import __version__
from mediasorter.lib.config import (
    ScanConfig,
    MediaType,
    CONFIG_PATH,
    read_config, default_config, MediaSorterConfig, ConfigurationError,
)
from mediasorter.lib.sort import MediaSorter

logging.getLogger('asyncio').setLevel(logging.WARNING)


app = typer.Typer()


def _get_config(path: str, console: Console) -> MediaSorterConfig:
    try:
        return read_config(path)
    except ConfigurationError as e:
        console.print(f"[bold red]{e}")
        console.print("[white]Consider using --setup to install default configuration file")
        sys.exit(2)


def _pretty_print_operation(sort_operation, console, before=False):
    if before and not sort_operation.is_error:
        console.print(Text(f"○ {sort_operation.input_path}", style="green"))
        console.print(Text(f"   ⤷  [{sort_operation.action}] {sort_operation.output_path}", style="green"))
    elif not sort_operation.is_error:
        console.print(Text(f" ✓ {sort_operation.output_path}", style="green"))

    elif sort_operation.is_error:
        console.print(Text(f"○ {sort_operation.input_path}", style="red"))
        console.print(Text(f"   ⤬ {sort_operation.exception}", style="#fe9797"))
    else:
        console.print(Text(f"⚠ {sort_operation.input_path}", style="yellow bold"))


@app.command()
def setup(
        configuration: Annotated[
            Optional[str],
            typer.Option(
                "--configuration", "-c",
                help="Use a non-default configuration file."
            )
        ] = None,
        verbose: Annotated[
            bool,
            typer.Option("--verbose", "-v", help="Show log messages.")
        ] = False,
):
    """Setup a default configuration file."""
    if not verbose:
        logger.disable("mediasorter")

    console = Console(quiet=False)
    new_config: MediaSorterConfig = default_config.copy()
    target = configuration or CONFIG_PATH

    logger.debug(f"Creating new config at {target}")
    if os.path.exists(target) and not Confirm.ask(f"File already exists {target}, overwrite?"):
        raise typer.Abort()

    api_key = Prompt.ask("Enter TMDB API key")
    if not api_key:
        console.print("[white]No TMDB api key provided.")
        raise typer.Abort()

    for api in new_config.api:
        if api.name == "tmdb":
            api.key = api_key

    config_obj = {
        "mediasorter": new_config.dict()
    }

    with open(target, "w") as file:
        yaml.safe_dump(config_obj, file)

    console.print(Text(f"Configuration file copied to {target}", style="green bold"))


@app.command()
def info(
        configuration: Annotated[
            Optional[str],
            typer.Option(
                "--configuration", "-c",
                help="Use a non-default configuration file."
            )
        ] = None,
        verbose: Annotated[
            bool,
            typer.Option("--verbose", "-v", help="Show log messages.")
        ] = False,
):
    """Show configuration details."""
    if not verbose:
        logger.disable("mediasorter")

    console = Console(quiet=False)
    parsed_config = _get_config(configuration, console)

    console.rule(title=f"[blue] Configured scans @ {CONFIG_PATH}", align="left", style="blue")
    for index, scan in enumerate(parsed_config.scan_sources):
        console.print(
            f"[white] {index + 1}) {scan.src_path} --> [MOV] {scan.movies_output}, [TV] {scan.tv_shows_output}")

    sys.exit(0)


@app.command()
def version(
        verbose: Annotated[
            bool,
            typer.Option("--verbose", "-v", help="Show log messages.")
        ] = False,
):
    """Show version."""
    if not verbose:
        logger.disable("mediasorter")

    console = Console(quiet=False)
    console.print(Text(__version__), style="bold green")


@app.command()
def sort(
        path: Annotated[
            Optional[str],
            typer.Argument(
                help="Path to a directory to be recursively scanned. "
                     "If empty, only path(s) from loaded configuration file shall be used."
            )
        ] = None,
        dst_path_tv: Annotated[
            Optional[str],
            typer.Argument(
                help="Destination path for sorted media files "
                     "(tv shows only if movies destination specified)"
            )
        ] = None,
        dst_path_mov: Annotated[
            Optional[str],
            typer.Argument(
                help="Destination path for sorted movie media files"
            )
        ] = None,
        mediatype: Annotated[
            Optional[str],
            typer.Option(
                "--mediatype", "-m",
                help="Constraint to a media type (tv, movie, auto)"
            )
        ] = "auto",
        action: Annotated[
            Optional[str],
            typer.Option(
                "--action", "-a",
                help="Constraint to a media type (move, copy, softlink, hardlink)"
            )
        ] = "copy",
        configuration: Annotated[
            Optional[str],
            typer.Option(
                "--configuration", "-c",
                help="Use a non-default configuration file."
            )
        ] = None,
        quiet: Annotated[
            bool,
            typer.Option(
                "--quiet", "-q",
                help="No console output. (!) Performs sorting operations without asking."
            )
        ] = False,
        verbose: Annotated[
            bool,
            typer.Option("--verbose", "-v", help="Show log messages.")
        ] = False,
):
    """Perform the media files sorting."""
    if not verbose:
        logger.disable("mediasorter")

    console = Console(quiet=quiet)

    parsed_config = _get_config(configuration, console)

    scans = None
    if path and dst_path_tv:
        scans = [ScanConfig(
            src_path=os.path.abspath(os.path.expanduser(path)),
            media_type=mediatype,
            action=action,
            tv_shows_output=os.path.abspath(os.path.expanduser(dst_path_tv)),
            movies_output=os.path.abspath(os.path.expanduser(dst_path_tv)),
        )]

    elif path and dst_path_tv and dst_path_mov:
        scans = [ScanConfig(
            src_path=os.path.abspath(os.path.expanduser(path)),
            media_type=MediaType(mediatype),
            action=action,
            tv_shows_output=os.path.abspath(os.path.expanduser(dst_path_tv)),
            movies_output=os.path.abspath(os.path.expanduser(dst_path_mov)),
        )]
    elif path:
        console.print(Text("Destination path(s) argument(s) missing.", style="bold red"))
        raise typer.Abort()

    if scans:
        parsed_config.scan_sources = scans

    if not parsed_config.scan_sources:
        console.print(Text("No scans requested.", style="bold red"))
        raise typer.Abort()

    sorter = MediaSorter(config=parsed_config)

    # Crawl through the source path and grab available sorting operations.
    s = console.status(Text("Scanning", style="green bold"))
    if not verbose:
        s.start()

    ops = asyncio.run(sorter.scan_all())

    s.stop()

    # Print pre-sort summary.
    console.print()
    console.rule(style="green")

    ops = sorted(ops, key=lambda o: o.is_error, reverse=False)
    for sort_operation in ops:
        _pretty_print_operation(sort_operation, console, before=True)

    to_be_sorted = [o for o in ops if not o.is_error]
    errored = [o for o in ops if o.is_error]

    console.print(
        Text(f"\nOK: {len(to_be_sorted)}", style="green"),
        Text(","),
        Text(f"SKIP: {len(errored)}", style="red" if errored else "green"),
    )

    console.rule(style="red" if any([op.is_error for op in ops]) else "green")

    if not to_be_sorted:
        if errored:
            logger.error(f"No valid files for sorting in, {len(errored)} errors.")
            console.print(Text("Nothing to sort!", style="bold red"))
            typer.Exit(1)
        else:
            logger.info(f"Nothing to sort.")
            console.print(Text("Nothing to sort.", style="green bold"))
            typer.Exit(0)

    confirmed = quiet or Confirm.ask("Continue?")

    if not confirmed:
        raise typer.Abort()

    # SORT!
    text = TextColumn("{task.description}", table_column=Column(ratio=2))
    bar = BarColumn(table_column=Column(ratio=1))
    with Progress(bar, text, expand=True, transient=True) as progress:
        task = progress.add_task("Sorting", total=len(ops), visible=not quiet)

        for operation in to_be_sorted:
            progress.update(task, description=os.path.basename(operation.output_path))
            try:
                asyncio.run(operation.handler.commit())
            except Exception as e:
                if verbose:
                    logger.exception(e)
                console.print(f"{e}", style="red bold")
            progress.update(task, advance=1)

    for sort_operation in to_be_sorted:
        _pretty_print_operation(sort_operation, console)

    # Return non-zero if any of the confirmed sort operations fails.
    if any([op.is_error for op in to_be_sorted]):
        typer.Exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
