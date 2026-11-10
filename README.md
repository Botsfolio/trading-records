# Botsfolio trading records

Every filled trade from [Botsfolio](https://botsfolio.com), sealed every hour so that any later change shows.

How to verify this, in plain words: https://botsfolio.com/track-record/verify

## What's here

| Path | What it is |
|---|---|
| [`paper/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/paper/latest.csv) | The newest 500 paper trades. The easiest place to start. Built from the sealed files, and `verify.py` checks that it matches them |
| `paper/YYYY/MM/DD/*.csv` | All paper trades, one file per seal |
| [`real-money/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/real-money/latest.csv) | The newest 500 real-money trades, also checked by `verify.py` |
| `real-money/YYYY/MM/DD/*.csv` | All real-money trades, one file per seal |
| [`battle/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/battle/latest.csv) | Every row of the Botsfolio AI vs Claude battle, from its first live close |
| `battle/YYYY/MM/DD/*.csv` | The battle, one file per seal |
| [`copy-trading-battle/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/copy-trading-battle/latest.csv) | Every row of the copy trading vs Botsfolio AI battle, from its start |
| `copy-trading-battle/YYYY/MM/DD/*.csv` | That battle, one file per seal |
| [`gpt-battle/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/gpt-battle/latest.csv) | Every row of the Botsfolio AI vs GPT battle, from its first live close |
| `gpt-battle/YYYY/MM/DD/*.csv` | That battle, one file per seal |
| [`korea-stocks/latest.csv`](https://raw.githubusercontent.com/botsfolio/trading-records/main/korea-stocks/latest.csv) | Every row of the Korea stocks paper portfolios (Korea 200, Korea Top 10, Korea Tech: Korea Exchange ETFs, in won), from their start |
| `korea-stocks/YYYY/MM/DD/*.csv` | Those portfolios, one file per seal |
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

Real trades on real exchange accounts, after the exchange filled them. Each row has `time_utc`, `asset_type`, `instrument`, `currency`, `side`, `price` (the average fill price), `exchange`, `fee_pct` (the exchange's fee as a percent of the value traded), `corrects` and `signer`. A row never shows a name, email, account, order ID, portfolio, or the size of the trade, and real trades are not grouped by person.

Seals written before these rows were published say `"published": false` for their real-money file. Its SHA-256 is in that seal, written at the time, so the file checks out the same way.

## Botsfolio AI vs Claude battle

Botsfolio AI and two Claude models, Claude Fable 5.1 and Claude Opus 5.5, each trade $50,000 of paper money in bitcoin and ether, with the same fees and one decision at every daily close. The standings: https://botsfolio.com/blog/can-claude-trade-crypto. This log starts at the first close every Claude model decided live, within 12 hours of that close.

Each row's `kind`:

- `close`: a player's value after the close, in `value_usd`. Holding both coins from the battle's start (`hold`) is in these rows too.
- `decision`: a Claude model's answer. `time_utc` is when it decided. Then the share of the portfolio it set for each coin, its stop prices, and its own note in full. `thinking_sha256` is the SHA-256 of its private reasoning, which stays private: if it is ever shown, it can be checked against this. `refused` true means the model gave no decision, so its portfolio stayed as it was.
- `trade`: a fill on either side. `price` includes the 0.01% slippage, and the 0.06% fee comes out separately. Claude's orders fill at the close, and a stop during the next day on 15-minute prices. Botsfolio AI's trades show what it did, never why, and its same-time trades in one coin are one row.

## Copy trading vs Botsfolio AI battle

Six players each start with $50,000 at the November 2, 2026 daily close: Botsfolio AI twice (bitcoin and ether, and five altcoins), holding half bitcoin and half ether, and one copier for each of Hyperliquid, Binance and OKX. A copier splits its money equally across that platform's top 10 traders by 30-day return that are still taking copiers, and picks again every 30 days. The standings: https://botsfolio.com/battle/copy-trading-vs-ai. `player` is one of `botsfolio`, `botsfolio_alts`, `hold`, `hyperliquid`, `binance` and `okx`, and `name` is how the battle page names it.

Each row's `kind`:

- `close`: a player's value after the close, in `value_usd`. Botsfolio AI's values are after Botsfolio's fee, and `fees_usd` is that fee so far. A close counts once every player has that day, as on the battle page. Binance and OKX days end at 16:00 UTC.
- `start`: what each Botsfolio AI player held at the start close: each coin's `quantity` at that close's `price`, and its cash (`instrument` is `USD`). It is a public paper portfolio's own holding scaled to $50,000, and its trades are that portfolio's trades scaled by the same factor.
- `trade`: a Botsfolio AI fill after the start. `price` includes the portfolio's slippage. Botsfolio AI's trades show what it did, never why, and its same-time trades in one coin are one row.
- `pick`: one trader a copier copies for one round: `round`, `rank`, `trader_url` (the trader's public page on its platform), `picked_ret30_pct` (its 30-day return when picked) and `profit_share_pct` (the share of gains the trader takes).
- `pick_day`: one pick's day as the battle counted it: `pnl_usd` (the trader's profit that day), `balance_usd` (the balance it started the day with) and `day_return` (the first over the second, counted as 0 above 200%, which is bad data). A copier's value is its money split equally across its picks, each grown by its daily returns, less the trader's share of that pick's gain in the round.

The first file covers every day from the start up to its seal. A copier's days are read again for a week after they happen, so a later reading can change one: if a value moves by more than 0.01%, a correction row replaces it.

## Botsfolio AI vs GPT battle

The same game as the Claude battle, against OpenAI's GPT-6 Astra and GPT-6 Sol: the same prompt, rules, answer format and costs, from the November 3, 2026 close. The standings: https://botsfolio.com/battle/botsfolio-ai-vs-gpt. The file has the Claude battle's columns and kinds, with `player` one of `botsfolio_ai`, `gpt_astra`, `gpt_sol` and `hold`.

- Botsfolio AI is the same public paper portfolio as in the Claude battle, scaled to $50,000 at the November 3 close with that day's fees added back, as on the battle page. `start` rows show what it held at that close (each coin's `quantity` at that close's `price`, and its cash as `instrument` `USD`). Its trades after that are the portfolio's trades scaled by the same factor.
- Holding buys half bitcoin and half ether at the November 3 close, paying the same fee and slippage, and never sells.

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
