from __future__ import annotations

import os
from typing import List

from configs.settings import CACHE_DIR_LISTS
from src.crawl.mw_client import MediaWikiClient
from src.crawl.list_pages_using_template import iter_embeddedin, save_titles, safe_filename


def read_lines(path: str) -> List[str]:
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(s)
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--templates", required=True, help="Path to infobox_templates.txt")
    parser.add_argument("--min_pages", type=int, default=200)
    parser.add_argument("--max_templates", type=int, default=0, help="0 means all")
    args = parser.parse_args()

    os.makedirs(CACHE_DIR_LISTS, exist_ok=True)
    client = MediaWikiClient()

    templates = read_lines(args.templates)
    if args.max_templates and args.max_templates > 0:
        templates = templates[: args.max_templates]

    kept = 0
    for t in templates:
        titles = list(iter_embeddedin(client, t, limit=None))
        n = len(titles)

        if n >= args.min_pages:
            out_path = os.path.join(CACHE_DIR_LISTS, f"pages_using_{safe_filename(t)}.txt")
            save_titles(titles, out_path)
            print(f"[KEEP] {t} -> {n} pages ({out_path})")
            kept += 1
        else:
            print(f"[SKIP] {t} -> {n} pages (< {args.min_pages})")

    print(f"Done. Templates kept: {kept}")
