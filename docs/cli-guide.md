# CLI guide: `jff-gen`

`jff-gen` generates the synthetic Just Fast Food dataset as CSV files. The same seed, config and library versions always give the same bytes.

Requirements: Python 3.11 or newer (tested on 3.12 on Linux).

## Install

Run from the `generator/` folder. `constraints.txt` pins the library versions that make output reproducible.

| OS | Commands |
|---|---|
| Windows (PowerShell) | `py -3.12 -m venv .venv`<br>`.\.venv\Scripts\Activate.ps1`<br>`pip install -c constraints.txt -e ".[dev]"` |
| Linux / macOS | `python3 -m venv .venv`<br>`source .venv/bin/activate`<br>`pip install -c constraints.txt -e ".[dev]"` |

If PowerShell refuses to run the activate script: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
Check the install with `jff-gen --help`.

## Typical workflow

```
jff-gen dim all --out ../data
jff-gen generate --start 2026-09-16 --end 2026-10-30 --scale 0.1 --out ../data
jff-gen profile --data ../data --out ../docs/data-profile.md
```

1. `dim` writes the dimension tables once.
2. `generate` writes the daily transaction files. The range above is the default development window (45 days), about 540 thousand orders and 109 MB.
3. `profile` checks what was produced.

## Commands

### `jff-gen dim <table>`

Writes dimension tables to `<out>/dimensions/<table>.csv`. Each table has its own generator.

| Argument or option | Meaning |
|---|---|
| `table` (required) | `branches`, `menu_items`, `promos`, `channels`, or `all` |
| `--out` (required) | Local folder or an fsspec URL such as `s3://bucket/raw` |
| `--config` | YAML file that replaces the packaged default config entirely |
| `--seed` | Overrides `seed` from the config (default 42) |
| `--branches` | Overrides the number of branches (default 120). Only affects `branches` |

Notes:

- Re-running overwrites the file with identical content.
- `generate` rebuilds the dimensions in memory from the same config. **Use the same `--seed`, `--branches` and `--config` for `dim` and `generate`**, otherwise the dimension files will not match the transactions.

### `jff-gen generate`

Writes one or more days of transactions.

| Option | Meaning |
|---|---|
| `--out` (required) | Local folder or fsspec URL |
| `--date YYYY-MM-DD` | A single day. Cannot be combined with `--start` or `--end` |
| `--start`, `--end` | Inclusive range. Both are required together, `--end` must not be before `--start` |
| `--scale` | Order volume multiplier, default 1.0 (about 1,000 orders per branch per day). Use 0.1 for development |
| `--clean` | Turns off every injected defect (duplicates, late orders, missing branches, dirty labels, mismatched totals, unknown menu items) |
| `--seed`, `--branches`, `--config` | Same meaning as in `dim` |

Output per day, with `dt=` the file date:

```
orders/dt=2026-10-05/orders.csv
order_items/dt=2026-10-05/order_items.csv
order_changes/dt=2026-10-05/order_changes.csv
_manifests/dt=2026-10-05/manifest.json
dimensions/*.csv                     (from `dim`)
```

Behaviour worth knowing:

- **Idempotent.** Re-running a date overwrites its files with identical content. A range produces the same bytes as running each day on its own, in any order.
- **Manifest last.** `manifest.json` is written after the CSV files, so its presence means the day is complete. It records row counts, the scale and seed, expected and dropped branches, and how many defects of each type were injected.
- **Files are not one-to-one with business days.** A day's `orders.csv` also holds orders from the previous day that a branch synced late. `order_changes.csv` holds refunds for orders from up to 8 days earlier. Single-date runs still work without generating earlier days.
- **Cost.** About 1 second per day at `--scale 0.1` and about 3 seconds per day at full scale. Memory stays bounded because files are written branch by branch.

### `jff-gen profile`

Reads a generated dataset and writes a Markdown profile: overview, dimensions, orders, items, refunds, empty values, and a table comparing defects found in the data with defects the manifest says were injected.

| Option | Meaning |
|---|---|
| `--data` (required) | Local folder that holds the generated files, including `_manifests/` and `dimensions/` |
| `--out` | Write the Markdown here. Without it the profile is printed |

`profile` reads local paths only. It exits with an error if the folder has no manifests or files.

Memory: `profile` loads the whole dataset, about 650 MB of RAM for the 45-day development window (540 thousand orders), roughly 1.2 GB per million orders. Use it on development windows, not on a full-scale month or year.

## Using a different config

`--config` replaces the packaged default completely. Copy `src/jff_gen/default_config.yaml`, edit it, then pass it to both `dim` and `generate`. Business assumptions live there: base volume, weekday factors, regional profiles, channel mix, promos, lifecycle rates, and every defect rate.

## Remote output

`--out s3://bucket/prefix` writes through fsspec. Install the S3 driver first with `pip install s3fs`, and set credentials and the endpoint through fsspec or `s3fs` settings (verify the exact variable names).

## Recipes

| Goal | Command |
|---|---|
| One day at full scale | `jff-gen generate --date 2026-10-05 --out ../data` |
| Development window | `jff-gen generate --start 2026-09-16 --end 2026-10-30 --scale 0.1 --out ../data` |
| Clean data to verify metrics | add `--clean` |
| A different dataset | add `--seed 7` to both `dim` and `generate` |
| Rebuild the committed sample | `jff-gen dim all --out ../sample-data` then `jff-gen generate --start 2026-10-03 --end 2026-10-09 --scale 0.02 --out ../sample-data` |
| Run the checks | `pytest`, `ruff check .`, `mypy src tests` |

## Errors

| Message | Cause |
|---|---|
| `give --date or both --start and --end` | No date given, or only one end of a range |
| `use either --date or --start/--end` | Both forms given |
| `--end is before --start` | Reversed range |
| `invalid date '...', expected YYYY-MM-DD` | Date typed in another format |
| `invalid settings: scale: Input should be greater than 0` (similar for `n_branches`, `seed`) | A flag or config value outside its allowed range. Probabilities and rates must be between 0 and 1 |
| `no manifests under ...` | `profile` pointed at a folder without generated data |

Exit code 0 means success, 2 means a usage error. In PowerShell, continue a long command on the next line with a backtick, and quote paths that contain spaces.
