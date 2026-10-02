import argparse
import sys

from . import __version__


def main() -> int:
    ap = argparse.ArgumentParser(prog="cachy-widget", description="Today + tomorrow weather and headlines, as a desktop card.")
    ap.add_argument("--demo", action="store_true", help="use built-in sample data (no network)")
    ap.add_argument("--screenshot", metavar="PNG", help="render once to a PNG and exit (use with QT_QPA_PLATFORM=offscreen)")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args()
    from .app import run  # imported late so --help/--version work without Qt

    return run(sys.argv, demo_mode=args.demo, screenshot=args.screenshot)


if __name__ == "__main__":
    sys.exit(main())
