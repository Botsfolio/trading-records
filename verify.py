#!/usr/bin/env python3
"""Checks the Botsfolio trade log. Run it from a copy of https://github.com/botsfolio/trading-records:

    pip install cryptography
    python verify.py                 # every seal: signature, chain, file hashes and Bitcoin proof
    python verify.py --prices 25     # also the newest 25 paper prices against Coinbase's public candles

It trusts nothing in this repo on its own: the public key is compared with the one on botsfolio.com, Bitcoin blocks are
read from mempool.space and prices from Coinbase. The server that writes the log uses this same file.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import sys
import time
import urllib.request
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEY_URL = "https://botsfolio.com/.well-known/botsfolio-records.json"
BLOCKS = "https://mempool.space/api"
CANDLES = "https://api.exchange.coinbase.com"

OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
PENDING_TAG = bytes.fromhex("83dfe30d2ef90c8e")
BITCOIN_TAG = bytes.fromhex("0588960d73d71901")
_SHA256, _SHA1, _RIPEMD160, _APPEND, _PREPEND, _REVERSE, _HEXLIFY = 0x08, 0x02, 0x03, 0xf0, 0xf1, 0xf2, 0xf3
_WITH_ARG = (_APPEND, _PREPEND)


# ------------------------------------------------------------------ the OpenTimestamps proof format
def _varuint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _varbytes(b: bytes) -> bytes:
    return _varuint(len(b)) + b


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data, self.i = data, 0

    def take(self, n: int) -> bytes:
        if self.i + n > len(self.data):
            raise ValueError("the proof is cut short")
        out = self.data[self.i:self.i + n]
        self.i += n
        return out

    def varuint(self) -> int:
        value = shift = 0
        while True:
            b = self.take(1)[0]
            value |= (b & 0x7f) << shift
            if not b & 0x80:
                return value
            shift += 7

    def varbytes(self) -> bytes:
        return self.take(self.varuint())


def _apply(tag: int, arg: bytes, msg: bytes) -> bytes:
    if tag == _APPEND:
        return msg + arg
    if tag == _PREPEND:
        return arg + msg
    if tag == _SHA256:
        return hashlib.sha256(msg).digest()
    if tag == _SHA1:
        return hashlib.sha1(msg).digest()
    if tag == _RIPEMD160:
        return hashlib.new("ripemd160", msg).digest()
    if tag == _REVERSE:
        return msg[::-1]
    if tag == _HEXLIFY:
        return msg.hex().encode()
    raise ValueError(f"unknown step in the proof: {tag:#x}")


class Stamp:
    """A message, the attestations on it, and the steps that lead from it to further messages."""

    def __init__(self, msg: bytes) -> None:
        self.msg = msg
        self.attestations: list[tuple[bytes, bytes]] = []
        self.ops: dict[tuple[int, bytes], Stamp] = {}

    @classmethod
    def read(cls, r: Reader, msg: bytes, depth: int = 0) -> Stamp:
        if depth > 256:
            raise ValueError("the proof is too deep")
        stamp = cls(msg)

        def one(tag: int) -> None:
            if tag == 0:
                attestation = (r.take(8), r.varbytes())
                if attestation not in stamp.attestations:
                    stamp.attestations.append(attestation)
            else:
                arg = r.varbytes() if tag in _WITH_ARG else b""
                stamp.ops[(tag, arg)] = cls.read(r, _apply(tag, arg, msg), depth + 1)

        tag = r.take(1)[0]
        while tag == 0xff:
            one(r.take(1)[0])
            tag = r.take(1)[0]
        one(tag)
        return stamp

    def write(self) -> bytes:
        items = [b"\x00" + t + _varbytes(p) for t, p in sorted(self.attestations)]
        items += [bytes([t]) + (_varbytes(a) if t in _WITH_ARG else b"") + s.write() for (t, a), s in sorted(self.ops.items(), key=lambda kv: kv[0])]
        if not items:
            raise ValueError("an empty proof")
        return b"".join(b"\xff" + x for x in items[:-1]) + items[-1]

    def merge(self, other: Stamp) -> None:
        for a in other.attestations:
            if a not in self.attestations:
                self.attestations.append(a)
        for op, s in other.ops.items():
            if op in self.ops:
                self.ops[op].merge(s)
            else:
                self.ops[op] = s

    def walk(self) -> Iterator[Stamp]:
        yield self
        for s in self.ops.values():
            yield from s.walk()


def read_ots(data: bytes) -> tuple[bytes, Stamp]:
    r = Reader(data)
    if r.take(len(OTS_MAGIC)) != OTS_MAGIC or r.varuint() != 1 or r.take(1)[0] != _SHA256:
        raise ValueError("not an OpenTimestamps proof of a SHA-256")
    digest = r.take(32)
    return digest, Stamp.read(r, digest)


def write_ots(digest: bytes, stamp: Stamp) -> bytes:
    return OTS_MAGIC + _varuint(1) + bytes([_SHA256]) + digest + stamp.write()


def pending_calendars(stamp: Stamp) -> list[tuple[Stamp, str]]:
    return [(s, Reader(p).varbytes().decode()) for s in stamp.walk() for t, p in s.attestations if t == PENDING_TAG]


def bitcoin_blocks(stamp: Stamp) -> list[tuple[int, bytes]]:
    """(block height, the message that must equal that block's merkle root)."""
    return sorted((Reader(p).varuint(), s.msg) for s in stamp.walk() for t, p in s.attestations if t == BITCOIN_TAG)


# ------------------------------------------------------------------ the checks
def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "botsfolio-trade-log-verify"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def block_merkle_root(height: int) -> str:
    block_hash = _get(f"{BLOCKS}/block-height/{height}").decode().strip()
    return json.loads(_get(f"{BLOCKS}/block/{block_hash}"))["merkle_root"]


def price_problem(row: dict) -> str | None:
    """A buy is at the daily close, so it equals that day's Coinbase close. A sell is inside its minute's candle."""
    if row["asset_type"] != "crypto":
        return None     # only cryptos have public Coinbase candles to compare with
    product = f"{row['instrument']}-{row['currency']}"
    at = datetime.strptime(row["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)  # noqa: UP017 (this file runs on older Pythons too)
    price = float(row["price"])
    size = 86400 if row["side"] == "buy" else 60
    start = at - timedelta(days=1) if row["side"] == "buy" else at
    end = start + timedelta(seconds=size)
    query = f"granularity={size}&start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    candles = [c for c in json.loads(_get(f"{CANDLES}/products/{product}/candles?{query}")) if int(c[0]) == int(start.timestamp())]
    if not candles:
        return f"{row['row_id']}: Coinbase has no candle for {product} at {start:%Y-%m-%d %H:%M}"
    low, high, _open, close = (float(x) for x in candles[0][1:5])
    if row["side"] == "buy":
        if abs(price - close) > close * 1e-6:
            return f"{row['row_id']}: {product} buy at {price}, Coinbase's close was {close}"
    elif not low * (1 - 1e-6) <= price <= high * (1 + 1e-6):
        return f"{row['row_id']}: {product} sell at {price}, outside that minute's {low} to {high}"
    return None


def key_fingerprint(raw_public_key: bytes) -> str:
    return hashlib.sha256(raw_public_key).hexdigest()[:16]


def check(root: Path, *, site_key: str | None = None, read_blocks: bool = True) -> dict:
    """Every seal under `root`. `site_key` is the PEM public key published on botsfolio.com."""
    from cryptography.hazmat.primitives import serialization

    problems: list[str] = []
    pem = (root / "public-key.pem").read_text()
    public = serialization.load_pem_public_key(pem.encode())
    signer = key_fingerprint(public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    if site_key is not None and site_key.strip() != pem.strip():
        problems.append("public-key.pem is not the key published on botsfolio.com")

    previous, seals, published, held, anchored, waiting, newest_block = None, 0, 0, 0, 0, 0, None
    sealed_rows: dict[str, list[str]] = {}
    paths = sorted((root / "seals").glob("*.json"))
    for i, path in enumerate(paths, start=1):
        raw = path.read_bytes()
        seal = json.loads(raw)
        name = path.name
        seals += 1
        if seal.get("seq") != i:
            problems.append(f"{name}: expected seal number {i}, a seal is missing")
        if seal.get("previous_seal_sha256") != previous:
            problems.append(f"{name}: doesn't follow the seal before it")
        if seal.get("signer") != signer:
            problems.append(f"{name}: names a different key")
        previous = hashlib.sha256(raw).hexdigest()
        try:
            public.verify(base64.b64decode((root / "seals" / f"{name}.sig").read_text()), raw)
        except Exception:
            problems.append(f"{name}: the signature doesn't match")
        for f in seal.get("files", []):
            on_disk = (root / f["path"]).exists()
            if not f.get("published") and not on_disk:     # sealed with its rows held back, and not published since
                held += 1
                continue
            data = (root / f["path"]).read_bytes() if on_disk else None
            if data is None or hashlib.sha256(data).hexdigest() != f["sha256"]:
                problems.append(f"{f['path']}: doesn't match seal {name}")
                continue
            published += 1
            for row in csv.DictReader(data.decode().splitlines()):
                if row.get("signer") != signer:
                    problems.append(f"{f['path']}: row {row.get('row_id')} names a different key")
                sealed_rows[row["row_id"]] = list(row.values())
        try:
            digest, stamp = read_ots((root / "seals" / f"{name}.ots").read_bytes())
            if digest.hex() != previous:
                problems.append(f"{name}.ots: is a proof of something else")
            found = False
            for height, msg in bitcoin_blocks(stamp) if read_blocks else []:
                if msg[::-1].hex() == block_merkle_root(height):
                    found, newest_block = True, height
                    break
                problems.append(f"{name}.ots: block {height} doesn't contain it")
            anchored, waiting = (anchored + 1, waiting) if found else (anchored, waiting + 1)
        except (OSError, ValueError) as e:
            problems.append(f"{name}.ots: {e}")

    for name in ("paper", "real-money", "battle", "copy-trading-battle"):
        latest = root / name / "latest.csv"
        if latest.exists():
            for row in csv.DictReader(latest.read_text().splitlines()):
                if sealed_rows.get(row["row_id"]) != list(row.values()):
                    problems.append(f"{name}/latest.csv: row {row['row_id']} isn't the sealed one")
    return {"problems": problems, "signer": signer, "seals": seals, "published": published, "held": held, "anchored": anchored,
            "waiting": waiting, "newest_block": newest_block}


def main() -> int:
    ap = argparse.ArgumentParser(description="Checks the Botsfolio trade log.")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--prices", type=int, default=0, help="also check this many of the newest paper prices against Coinbase")
    args = ap.parse_args()
    root = Path(args.dir)

    site_key = None
    try:
        site_key = json.loads(_get(KEY_URL))["publicKeyPem"]
    except Exception as e:
        print(f"Couldn't read the key on botsfolio.com ({e}), so the key was not compared with it.")
    res = check(root, site_key=site_key)
    problems = res["problems"]

    latest = root / "paper" / "latest.csv"
    if args.prices and latest.exists():
        rows = [r for r in csv.DictReader(latest.read_text().splitlines()) if not r["corrects"]][-args.prices:]
        for row in rows:
            if (p := price_problem(row)) is not None:
                problems.append(p)
            time.sleep(0.4)
        print(f"Paper prices checked against Coinbase: {len(rows)}")

    print(f"Key fingerprint: {res['signer']}" + (", same as botsfolio.com" if site_key else ""))
    print(f"Seals: {res['seals']}, each signed and chained to the one before")
    print(f"Files: {res['published']} published and matching, {res['held']} sealed with rows held back")
    print(f"Bitcoin: {res['anchored']} seals anchored" + (f", newest in block {res['newest_block']}" if res["newest_block"] else "") + f", {res['waiting']} waiting for a block")
    for p in problems:
        print(f"PROBLEM: {p}")
    print("All checks passed." if not problems else f"{len(problems)} problem(s) found.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
