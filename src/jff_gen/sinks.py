import json
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from datetime import date
from typing import Any, TextIO

import fsspec
import pandas as pd

from .schema import DAILY_ENTITIES


class DayWriter:
    """Appends chunks of one day's CSV files; headers are written once when the day opens."""

    def __init__(self, handles: dict[str, TextIO]) -> None:
        self._handles = handles

    def write(self, entity: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        columns = DAILY_ENTITIES[entity]
        frame[columns].to_csv(self._handles[entity], header=False, index=False, lineterminator="\n")


class Sink:
    """Local path or any fsspec URL (s3://bucket/prefix). Layout: <entity>/dt=YYYY-MM-DD/<file>."""

    def __init__(self, root: str, storage_options: Mapping[str, Any] | None = None) -> None:
        self.fs, self.root = fsspec.core.url_to_fs(root, **dict(storage_options or {}))
        self.root = self.root.rstrip("/")

    def _day_dir(self, entity: str, day: date) -> str:
        return f"{self.root}/{entity}/dt={day.isoformat()}"

    def _open_text(self, path: str) -> TextIO:
        self.fs.makedirs(path.rsplit("/", 1)[0], exist_ok=True)
        return self.fs.open(path, "w", encoding="utf-8", newline="")

    @contextmanager
    def open_day(self, day: date) -> Iterator[DayWriter]:
        with ExitStack() as stack:
            handles = {}
            for entity, columns in DAILY_ENTITIES.items():
                handle = stack.enter_context(
                    self._open_text(f"{self._day_dir(entity, day)}/{entity}.csv")
                )
                handle.write(",".join(columns) + "\n")
                handles[entity] = handle
            yield DayWriter(handles)

    def write_manifest(self, day: date, manifest: Mapping[str, Any]) -> None:
        """Written last: its presence marks the day as complete."""
        with self._open_text(f"{self._day_dir('_manifests', day)}/manifest.json") as handle:
            handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def write_dimension(self, name: str, frame: pd.DataFrame) -> None:
        with self._open_text(f"{self.root}/dimensions/{name}.csv") as handle:
            frame.to_csv(handle, index=False, lineterminator="\n")
