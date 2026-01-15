from __future__ import annotations

import os
from typing import List

from configs.settings import CACHE_DIR_LISTS
from src.crawl.mw_client import MediaWikiClient
from src.crawl.list_pages import iter_category_members, save_titles


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="Infobox templates")
    parser.add_argument("--out", default="data/cache/lists/infobox_templates.txt")
    parser.add_argument("--limit", type=int, default=0, help="0 means unlimited")
    args = parser.parse_args()

    os.makedirs(CACHE_DIR_LISTS, exist_ok=True)
    lim = None if args.limit == 0 else args.limit

    client = MediaWikiClient()

    # Templates are namespace 10
    templates = list(iter_category_members(client, args.category, limit=lim, namespace=10))
    templates = [t for t in templates if t.lower().startswith("template:")]

    save_titles(templates, args.out)
    print(f"Wrote {len(templates)} templates -> {args.out}")
