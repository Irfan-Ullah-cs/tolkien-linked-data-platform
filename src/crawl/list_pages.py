from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional

from configs.settings import CACHE_DIR_LISTS
from src.crawl.mw_client import MediaWikiClient


def ensure_dirs() -> None:
    os.makedirs(CACHE_DIR_LISTS, exist_ok=True)


def iter_category_members(
    client: MediaWikiClient,
    category: str,
    limit: Optional[int] = None,
    namespace: Optional[int] = 0,
) -> Iterable[str]:
    """
    MediaWiki: action=query + list=categorymembers with pagination.
    limit=None means unlimited.
    """
    if not category.lower().startswith("category:"):
        category = "Category:" + category

    cmcontinue: Optional[str] = None
    yielded = 0

    while True:
        params: Dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": 500,
        }
        if namespace is not None:
            params["cmnamespace"] = namespace
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        data = client.get_json(params)
        members = data.get("query", {}).get("categorymembers", []) or []
        for m in members:
            title = m.get("title")
            if title:
                yield title
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

        cont = data.get("continue", {}) or {}
        cmcontinue = cont.get("cmcontinue")
        if not cmcontinue:
            return


def iter_all_pages(client: MediaWikiClient, limit: Optional[int] = None, namespace: int = 0) -> Iterable[str]:
    """
    MediaWiki: action=query + list=allpages with pagination.
    limit=None means unlimited.
    """
    apcontinue: Optional[str] = None
    yielded = 0

    while True:
        params: Dict[str, Any] = {
            "action": "query",
            "list": "allpages",
            "aplimit": 500,
            "apnamespace": namespace,
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        data = client.get_json(params)
        pages = data.get("query", {}).get("allpages", []) or []
        for p in pages:
            title = p.get("title")
            if title:
                yield title
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

        cont = data.get("continue", {}) or {}
        apcontinue = cont.get("apcontinue")
        if not apcontinue:
            return


def save_titles(titles: Iterable[str], out_path: str) -> int:
    ensure_dirs()
    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for t in titles:
            t = t.strip().replace("\n", " ")
            if t:
                f.write(t + "\n")
                n += 1
    return n


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["category", "allpages"], required=True)
    parser.add_argument("--category", help="Category name (for mode=category), without 'Category:' prefix")
    parser.add_argument("--limit", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--out", required=True, help="Output file path, e.g., data/cache/lists/allpages.txt")
    args = parser.parse_args()

    lim = None if args.limit == 0 else args.limit
    client = MediaWikiClient()

    if args.mode == "category":
        if not args.category:
            raise SystemExit("For --mode category you must provide --category")
        titles_iter = iter_category_members(client, args.category, limit=lim, namespace=0)
    else:
        titles_iter = iter_all_pages(client, limit=lim, namespace=0)

    n = save_titles(titles_iter, args.out)
    print(f"Wrote {n} titles to {args.out}")
