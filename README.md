# Just Fast Food: sales analytics pipeline

Bootcamp final project: end-to-end sales analytics for a fictional fast food chain, on generated data.
This README is a stub for Check Point 1. The full README (setup per OS, architecture, demo) comes in Phase 4.

## Layout

- `generator/`: seeded synthetic data generator (Python CLI, tests)
- `docs/`: data model, ER diagram, data profile, CLI guide (`cli-guide.md`)
- `sample-data/`: seven days (2026-10-03 to 2026-10-09) at `--scale 0.02`, for review

## Generate data

```
cd generator
pip install -c constraints.txt -e ".[dev]"
jff-gen dim all --out ../data
jff-gen generate --start 2026-09-16 --end 2026-10-30 --scale 0.1 --out ../data
jff-gen profile --data ../data --out ../docs/data-profile.md
pytest && ruff check . && mypy src tests
```

Full command reference: `docs/cli-guide.md`. Dataset profile: `docs/data-profile.md`.

The same date always produces identical files for the same seed and library versions, so keep `constraints.txt` pinned.
