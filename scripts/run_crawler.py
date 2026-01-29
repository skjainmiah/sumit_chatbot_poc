"""Run the schema crawler to index all database schemas."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.schema_crawler.crawler import SchemaCrawler
from backend.config import settings


def run_crawler():
    """Crawl all databases and index schemas."""
    print("=" * 60)
    print("Schema Crawler")
    print("=" * 60)

    crawler = SchemaCrawler()

    # Use the built-in index_schemas method which handles everything
    crawler.index_schemas()

    print("\n" + "=" * 60)
    print("Schema crawling complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_crawler()
