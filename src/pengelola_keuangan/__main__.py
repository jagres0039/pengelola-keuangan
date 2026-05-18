"""CLI entry point for ``python -m pengelola_keuangan``."""

from __future__ import annotations

from pengelola_keuangan.bot.app import run


def main() -> None:
    """Run the bot. Used as the project entry point."""
    run()


if __name__ == "__main__":
    main()
