import zlib

import numpy as np


def make_rng(seed: int, stream: str, *keys: int) -> np.random.Generator:
    """RNG fully determined by (seed, stream, keys). No shared state between calls."""
    entropy = [seed, zlib.crc32(stream.encode("utf-8")), *keys]
    return np.random.default_rng(np.random.SeedSequence(entropy))
