"""Compare the native (toon-rust) codec against pure-Python toon_format.

Run: uv run python benchmarks/bench_codec.py
"""

import json
import timeit

import toon_format

from drf_toon import _native


def make_rows(n):
    return [
        {
            "id": i,
            "name": f"user {i}",
            "email": f"user{i}@example.com",
            "active": i % 2 == 0,
            "score": i * 1.5,
            "tags": ["a", "b", "c"],
        }
        for i in range(n)
    ]


def bench(label, fn, number):
    best = min(timeit.repeat(fn, number=number, repeat=5)) / number
    print(f"  {label:<28}{best * 1e3:9.3f} ms")
    return best


def run(n, number):
    data = {"count": n, "results": make_rows(n)}
    raw = json.dumps(data).encode()
    toon_text = toon_format.dumps(data)
    assert _native.encode_json(raw) == toon_text, "encoders disagree"
    assert _native.decode(toon_text) == toon_format.loads(toon_text) == data
    print(f"{n} rows ({len(raw) / 1024:.0f} KiB json, {len(toon_text) / 1024:.0f} KiB toon)")
    py_enc = bench(
        "encode  python (json.loads+)", lambda: toon_format.dumps(json.loads(raw)), number
    )
    rs_enc = bench("encode  rust   (from bytes)", lambda: _native.encode_json(raw), number)
    py_dec = bench("decode  python", lambda: toon_format.loads(toon_text), number)
    rs_dec = bench("decode  rust", lambda: _native.decode(toon_text), number)
    print(f"  speedup: encode x{py_enc / rs_enc:.1f}, decode x{py_dec / rs_dec:.1f}\n")


for n, number in ((10, 2000), (1_000, 30), (20_000, 2)):
    run(n, number)
