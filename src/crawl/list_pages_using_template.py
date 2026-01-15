from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, Optional

from configs.settings import CACHE_DIR_LISTS
from src.crawl.mw_client import MediaWikiClient


def safe_filename(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\-. ]+", "_", s, flags=re.UNICODE)
    s = s.replace(" ", "_")
    return s[:200] if len(s) > 200 else s


def iter_embeddedin(client: MediaWikiClient, template_title: str, limit: Optional[int] = None) -> Iterable[str]:
    """
    action=query + list=embeddedin
    Returns pages (namespace 0) that transclude the template.
    """
    if not template_title.lower().startswith("template:"):
        template_title = "Template:" + template_title

    eicontinue: Optional[str] = None
    yielded = 0

    while True:
        params: Dict[str, Any] = {
            "action": "query",
            "list": "embeddedin",
            "eititle": template_title,
            "eilimit": 500,
            "einamespace": 0,
        }
        if eicontinue:
            params["eicontinue"] = eicontinue

        data = client.get_json(params)
        pages = data.get("query", {}).get("embeddedin", []) or []
        for p in pages:
            title = p.get("title")
            if title:
                yield title
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

        cont = data.get("continue", {}) or {}
        eicontinue = cont.get("eicontinue")
        if not eicontinue:
            return


def save_titles(titles: Iterable[str], out_path: str) -> int:
    os.makedirs(CACHE_DIR_LISTS, exist_ok=True)
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
    parser.add_argument("--template", required=True, help="e.g. 'Template:Infobox character'")
    parser.add_argument("--out_dir", default=CACHE_DIR_LISTS)
    parser.add_argument("--limit", type=int, default=0, help="0 means unlimited")
    args = parser.parse_args()

    client = MediaWikiClient()
    lim = None if args.limit == 0 else args.limit

    out_path = os.path.join(args.out_dir, f"pages_using_{safe_filename(args.template)}.txt")
    n = save_titles(iter_embeddedin(client, args.template, limit=lim), out_path)
    print(f"{args.template}: wrote {n} pages -> {out_path}")
