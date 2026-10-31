# Botsfolio trading records

Every filled trade from [Botsfolio](https://botsfolio.com), sealed every hour so that any later change shows.

How to verify this, in plain words: https://botsfolio.com/track-record/verify

## What's here

| Path | What it is |
|---|---|
| [`paper/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/paper/latest.csv) | The newest 500 paper trades. The easiest place to start. Built from the sealed files, and `verify.py` checks that it matches them |
| `paper/YYYY/MM/DD/*.csv` | All paper trades, one file per seal |
| `seals/*.json` | One seal per batch: when it was made, the SHA-256 of each file, and the SHA-256 of the seal before it |
| `seals/*.json.sig` | Botsfolio's Ed25519 signature on that seal |
| `seals/*.json.ots` | An OpenTimestamps proof that the seal existed by a Bitcoin block |
| [`latest.json`](https://raw.githubusercontent.com/botsfolio/trading-records/main/latest.json) | The newest seal, and the newest one anchored in Bitcoin |
| `public-key.pem` | The public key that checks the signatures |
| `verify.py` | Checks all of it |

## Paper trades

Live trading with paper money: each trade happens as the market moves, at live Coinbase prices. Two groups, marked in `group`:

- `botsfolio_ai`: Botsfolio AI's own portfolios. `portfolio` is the name and `portfolio_url` its public page, where every order shows.
- `user_paper`: portfolios real users run with the AI on cryptos they picked. `portfolio` is an anonymous ID that stays the same for a portfolio. Nothing here identifies a user.

| Column | Meaning |
|---|---|
| `row_id` | This row's ID |
| `seal` | The seal that covers it |
| `time_utc` | When it traded, to the minute. Buys happen at the daily close (00:00 UTC) |
| `asset_type`, `instrument` | What traded. `asset_type` is `crypto` today, and other assets would be new values in this same log |
| `currency` | What `price` is in |
| `side`, `price`, `quantity` | The trade. `price` is the market price, before the costs below |
| `fee_pct`, `slippage_pct` | The cost taken out of this trade, as a percent of its value |
| `corrects` | If set, this row replaces that `row_id`. Sealed rows are never edited |
| `signer` | The fingerprint of the key that signs the seals: `758189603fa8abd5` |

## Real-money trades

Real trades are sealed in the same seals, marked `"published": false`. Their rows are held back for now, so only each file's SHA-256 is public. When a file is published, its hash can be checked against the seal written at the time.

## How to verify

**1. Who wrote it.** The key is published three ways, and only whoever controls botsfolio.com can change the first two:

- On the site: https://botsfolio.com/.well-known/botsfolio-records.json
- In DNS: `nslookup -type=TXT _botsfolio-records.botsfolio.com`
- Here: `public-key.pem`

The `signer` in every row, `758189603fa8abd5`, is the first 16 hex characters of the SHA-256 of the raw public key. It says which key to check. The signature is what shows that key signed.

**2. That nothing changed.** Each seal lists its files' SHA-256 and the SHA-256 of the seal before it, so editing or removing anything breaks every seal after it. Each seal is signed.

**3. When it existed.** Each `.ots` proof ties a seal to a Bitcoin block, which nobody can backdate. A proof completes a few hours after its seal. Check one with `verify.py`, or at https://opentimestamps.org. Seal 000001 covers trades from before it: it shows those rows existed by that seal's time.

**4. The prices.** A paper buy equals Coinbase's daily close for that day. A paper sell is inside that minute's Coinbase candle. `python verify.py --prices 25` checks the newest 25.

To run everything:

```
pip install cryptography
python verify.py
```

To check the newest signature in a few lines:

```python
import base64, json, urllib.request
from cryptography.hazmat.primitives.serialization import load_pem_public_key

get = lambda url: urllib.request.urlopen(url).read()
raw = "https://raw.githubusercontent.com/botsfolio/trading-records/main/"
key = json.loads(get("https://botsfolio.com/.well-known/botsfolio-records.json"))["publicKeyPem"]
latest = json.loads(get(raw + "latest.json"))
seal, signature = get(raw + latest["seal"]), base64.b64decode(get(raw + latest["signature"]))
load_pem_public_key(key.encode()).verify(signature, seal)  # raises if it doesn't match
print("signed by the key on botsfolio.com:", latest["seal"])
```

## License

The data here is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Use it freely and credit Botsfolio, with a link to https://botsfolio.com. Past results don't predict future ones.
