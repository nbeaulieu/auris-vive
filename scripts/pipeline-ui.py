#!/usr/bin/env python3
"""
scripts/pipeline-ui.py
Terminal UI for the Auris Vive pipeline.

Usage:
    source .venv-ml/bin/activate
    python3 scripts/pipeline-ui.py
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich import box
    from rich.text import Text
    from rich.columns import Columns
except ImportError:
    print("installing rich...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich", "-q"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich import box
    from rich.text import Text
    from rich.columns import Columns

console = Console()

# ── Song library ──────────────────────────────────────────────────────────────
# Add new songs here as we go. Each entry:
#   name        : short display name
#   slug        : directory name under test_audio/
#   url         : YouTube URL
#   start       : timestamp to clip from
#   duration    : clip length in seconds
#   notes       : anything interesting about this track for testing

SONGS = [
    {
        "name":     "Fate of Ophelia — Taylor Swift",
        "slug":     "tswift",
        "url":      "https://www.youtube.com/watch?v=ko70cExuzZM",
        "start":    "2:10",
        "duration": 30,
        "notes":    "Strings + vocals. Piano stem near-silent (correct). Vocals excellent.",
    },
    {
        "name":     "Piano Man — Billy Joel",
        "slug":     "piano-man",
        "url":      "https://www.youtube.com/watch?v=gxEPV4kolz0",
        "start":    "1:25",
        "duration": 30,
        "notes":    "Dense live mix. Piano stem noisy (harmonica bleed). Vocals stellar.",
    },
    {
        "name":     "Earth Flyover — Crystal Method",
        "slug":     "earth-flyover",
        "url":      "https://www.youtube.com/watch?v=bBG743nNry4",
        "start":    "3:00",
        "duration": 30,
        "notes":    "Electronic. Testing how Demucs handles synth-heavy material.",
    },
]

REPO_ROOT = Path(__file__).parent.parent


# ── Helpers ───────────────────────────────────────────────────────────────────

def header():
    console.print()
    console.print(Panel(
        Text("AURIS VIVE", style="bold #A084C8", justify="center") ,
        subtitle="[#C9A96E]pipeline console[/#C9A96E]",
        border_style="#7B5EA7",
        padding=(1, 4),
    ))
    console.print()


def song_table(songs: list[dict]) -> Table:
    table = Table(box=box.SIMPLE, border_style="#7B5EA7", show_header=True)
    table.add_column("#",       style="#C9A96E", width=3)
    table.add_column("song",    style="bold #E8E0D5")
    table.add_column("start",  style="#A084C8", width=7)
    table.add_column("dur",    style="#A084C8", width=5)
    table.add_column("clip",   style="dim", width=6)
    table.add_column("stems",  style="dim", width=6)
    table.add_column("notes",  style="italic #8a8a8a")

    for i, song in enumerate(songs, 1):
        clip_path  = REPO_ROOT / "test_audio" / song["slug"] / "clip.wav"
        stems_path = REPO_ROOT / "test_audio" / song["slug"] / "stems"
        has_clip   = "✓" if clip_path.exists()  else "·"
        has_stems  = "✓" if stems_path.exists() else "·"
        table.add_row(
            str(i),
            song["name"],
            song["start"],
            str(song["duration"]) + "s",
            has_clip,
            has_stems,
            song["notes"],
        )

    return table


def run_command(cmd: list[str], env: dict = None) -> int:
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, env=merged_env)
    return result.returncode


def grab_clip(song: dict):
    console.print(f"\n[#C9A96E]▸[/#C9A96E] grabbing clip: [bold]{song['name']}[/bold]")
    rc = run_command([
        str(REPO_ROOT / "scripts" / "grab-clip.sh"),
        song["url"],
        song["slug"],
        song["start"],
        str(song["duration"]),
    ])
    if rc != 0:
        console.print("[red]✗ grab failed[/red]")
    else:
        console.print("[#A084C8]✓ clip saved[/#A084C8]")


def run_stems(song: dict):
    clip_path = REPO_ROOT / "test_audio" / song["slug"] / "clip.wav"
    if not clip_path.exists():
        console.print("[red]✗ no clip found — grab it first[/red]")
        return

    console.print(f"\n[#C9A96E]▸[/#C9A96E] running stems: [bold]{song['name']}[/bold]")
    rc = run_command(
        [
            str(REPO_ROOT / "scripts" / "run-stems.sh"),
            str(clip_path),
            song["slug"],
        ],
        env={"AURIS_DEVICE": os.environ.get("AURIS_DEVICE", "auto")},
    )
    if rc != 0:
        console.print("[red]✗ separation failed[/red]")
    else:
        console.print("[#A084C8]✓ stems written[/#A084C8]")


def add_song_interactive() -> dict | None:
    console.print("\n[#C9A96E]▸[/#C9A96E] add a new song\n")
    name     = Prompt.ask("  display name")
    slug     = Prompt.ask("  slug (directory name, no spaces)")
    url      = Prompt.ask("  YouTube URL")
    start    = Prompt.ask("  start time", default="0:00")
    duration = int(Prompt.ask("  duration (seconds)", default="30"))
    notes    = Prompt.ask("  notes (optional)", default="")

    song = {"name": name, "slug": slug, "url": url,
            "start": start, "duration": duration, "notes": notes}

    console.print(f"\n  [dim]{song}[/dim]")
    if Confirm.ask("  add this song?"):
        return song
    return None


# ── Main menu ─────────────────────────────────────────────────────────────────

def main():
    songs = list(SONGS)  # mutable copy for this session

    while True:
        header()
        console.print(song_table(songs))
        console.print()
        console.print("  [#C9A96E]g[/#C9A96E]  grab clip      "
                      "[#C9A96E]s[/#C9A96E]  run stems      "
                      "[#C9A96E]b[/#C9A96E]  grab + stems")
        console.print("  [#C9A96E]a[/#C9A96E]  add song       "
                      "[#C9A96E]q[/#C9A96E]  quit")
        console.print()

        action = Prompt.ask("  action", default="q").strip().lower()

        if action == "q":
            console.print("\n[dim]bye.[/dim]\n")
            break

        elif action == "a":
            new_song = add_song_interactive()
            if new_song:
                songs.append(new_song)
                console.print("[#A084C8]✓ added — grab the clip to get started[/#A084C8]")

        elif action in ("g", "s", "b"):
            console.print()
            console.print(song_table(songs))
            idx = Prompt.ask("  song number").strip()
            try:
                song = songs[int(idx) - 1]
            except (ValueError, IndexError):
                console.print("[red]invalid selection[/red]")
                continue

            if action in ("g", "b"):
                grab_clip(song)
            if action in ("s", "b"):
                run_stems(song)

        else:
            console.print("[dim]unknown action[/dim]")


if __name__ == "__main__":
    main()
