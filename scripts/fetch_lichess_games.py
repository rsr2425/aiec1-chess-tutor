"""Fetch CC0-licensed games from the Lichess open database for the benchmark.

Downloads one month of rapid games, filters for both players < 1500 rating,
samples ~20 games with 30–60 moves, and saves PGNs to
evals/planted_mistakes/games/.

Usage:
    python scripts/fetch_lichess_games.py [--year 2024] [--month 01] [--count 20]
"""

from __future__ import annotations

import argparse
import io
import os
import random
import sys
import zstandard as zstd

try:
    import chess.pgn
except ImportError:
    print("python-chess required: pip install python-chess")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("requests required: pip install requests")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "evals", "planted_mistakes", "games")

MIN_RATING = 0
MAX_RATING = 1500
MIN_MOVES = 30
MAX_MOVES = 60


def fetch_and_sample(year: int, month: int, count: int) -> list[str]:
    month_str = f"{month:02d}"
    url = f"https://database.lichess.org/standard/lichess_db_standard_rated_{year}-{month_str}.pgn.zst"

    print(f"Downloading {url} …")
    print("(This is a large file — may take several minutes)")

    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    dctx = zstd.ZstdDecompressor()
    buffer = io.StringIO()
    games: list[str] = []

    with dctx.stream_reader(response.raw) as reader:
        text_reader = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        while len(games) < count * 10:  # oversample and filter
            game = chess.pgn.read_game(text_reader)
            if game is None:
                break

            # Filter: both players < MAX_RATING, move count in range
            try:
                white_elo = int(game.headers.get("WhiteElo", "0"))
                black_elo = int(game.headers.get("BlackElo", "0"))
                time_control = game.headers.get("TimeControl", "")
                # Only rapid (600+ seconds per side)
                if "+" in time_control:
                    base = int(time_control.split("+")[0])
                else:
                    base = int(time_control) if time_control.isdigit() else 0
                if base < 600:
                    continue
            except (ValueError, AttributeError):
                continue

            if not (MIN_RATING <= white_elo <= MAX_RATING and MIN_RATING <= black_elo <= MAX_RATING):
                continue

            # Count half-moves
            node = game
            ply = 0
            while node.variations:
                node = node.variations[0]
                ply += 1

            if MIN_MOVES * 2 <= ply <= MAX_MOVES * 2:
                games.append(str(game))

    sampled = random.sample(games, min(count, len(games)))
    print(f"Sampled {len(sampled)} games (from {len(games)} candidates)")
    return sampled


def save_games(games: list[str], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    for i, pgn_text in enumerate(games):
        path = os.path.join(output_dir, f"game_{i+1:02d}.pgn")
        with open(path, "w") as f:
            f.write(pgn_text)
    print(f"Saved {len(games)} games to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch CC0 Lichess games for benchmark")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()

    games = fetch_and_sample(args.year, args.month, args.count)
    save_games(games, OUTPUT_DIR)


if __name__ == "__main__":
    main()
