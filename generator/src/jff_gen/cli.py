import argparse
import logging
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from .config import Config, load_config
from .context import build_context
from .daily import generate_range, write_dimensions
from .sinks import Sink


def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date '{text}', expected YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jff-gen", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--out", required=True, help="local path or fsspec URL, e.g. s3://bucket/raw"
    )
    common.add_argument("--config", type=Path, help="YAML config replacing the packaged default")
    common.add_argument("--seed", type=int)
    common.add_argument("--branches", type=int, help="override number of branches")

    sub.add_parser("dims", parents=[common], help="write dimension CSVs")

    gen = sub.add_parser("generate", parents=[common], help="write daily transaction CSVs")
    gen.add_argument("--date", type=_parse_date, help="single date")
    gen.add_argument("--start", type=_parse_date, help="range start (inclusive)")
    gen.add_argument("--end", type=_parse_date, help="range end (inclusive)")
    gen.add_argument("--scale", type=float, help="order volume multiplier, e.g. 0.1 for dev")
    gen.add_argument("--clean", action="store_true", help="disable all injected defects")
    return parser


def _apply_overrides(cfg: Config, args: argparse.Namespace) -> Config:
    updates: dict[str, object] = {}
    if args.seed is not None:
        updates["seed"] = args.seed
    if args.branches is not None:
        updates["n_branches"] = args.branches
    if getattr(args, "scale", None) is not None:
        updates["scale"] = args.scale
    if getattr(args, "clean", False):
        updates["defects"] = cfg.defects.model_copy(update={"enabled": False})
    return cfg.model_copy(update=updates)


def _resolve_dates(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[date, date]:
    if args.date and (args.start or args.end):
        parser.error("use either --date or --start/--end")
    if args.date:
        return args.date, args.date
    if args.start and args.end:
        if args.end < args.start:
            parser.error("--end is before --start")
        return args.start, args.end
    parser.error("give --date or both --start and --end")
    raise SystemExit(2)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx = build_context(_apply_overrides(load_config(args.config), args))
    sink = Sink(args.out)
    if args.command == "dims":
        write_dimensions(ctx, sink)
        return 0
    start, end = _resolve_dates(parser, args)
    generate_range(ctx, start, end, sink)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
