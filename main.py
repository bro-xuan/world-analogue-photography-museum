"""World Analogue Photography Museum — Data Collection Pipeline.

Usage:
    uv run python scripts/collect_all.py     # Run full Tier 1 collection
    uv run python -m src.collectors.wikidata  # Run individual collector
    uv run python -m src.collectors.flickr
    uv run python -m src.collectors.wikipedia
    uv run python -m src.normalization.merge  # Run merge only
"""


def main():
    from scripts.collect_all import main as collect_main
    collect_main()


if __name__ == "__main__":
    main()
