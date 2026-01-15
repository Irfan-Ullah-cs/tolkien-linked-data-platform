from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

from configs.settings import CACHE_DIR_PAGES
from src.crawl.mw_client import MediaWikiClient


INDEX_PATH = "data/cache/pages_index.jsonl"


def ensure_dirs() -> None:
    os.makedirs(CACHE_DIR_PAGES, exist_ok=True)
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)


def read_titles(path: str) -> List[str]:
    titles: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if t:
                titles.append(t)
    return titles


def pageid_cache_path(pageid: int) -> str:
    return os.path.join(CACHE_DIR_PAGES, f"{pageid}.json")


def append_index_record(title: str, pageid: int) -> None:
    # append-only jsonl (fast, no locking complexity)
    with open(INDEX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"title": title, "pageid": pageid}, ensure_ascii=False) + "\n")


def fetch_one(client: MediaWikiClient, title: str, force: bool = False) -> Optional[Dict[str, Any]]:
    ensure_dirs()

    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext|links|images|templates|externallinks",
        "redirects": 1,
    }
    data = client.get_json(params)

    parse = data.get("parse") or {}
    pageid = parse.get("pageid")
    real_title = parse.get("title") or title

    if not isinstance(pageid, int):
        # Sometimes parse fails for weird pages. Keep log and skip.
        return None

    path = pageid_cache_path(pageid)
    if (not force) and os.path.exists(path):
        return data

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    append_index_record(real_title, pageid)
    return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--titles", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    client = MediaWikiClient()
    all_titles = read_titles(args.titles)
    titles = all_titles[args.start : args.start + args.limit]

    ok = 0
    fail = 0
    skipped = 0

    for t in titles:
        try:
            data = fetch_one(client, t, force=args.force)
            if data is None:
                skipped += 1
            else:
                ok += 1
        except Exception as e:
            print(f"[FAIL] {t}: {e}")
            fail += 1

    print(f"Done. start={args.start}, fetched={len(titles)}, ok={ok}, skipped={skipped}, fail={fail}")
    print(f"Index: {INDEX_PATH}")
