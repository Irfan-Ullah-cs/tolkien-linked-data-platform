from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from rdflib import Graph

from configs.settings import TTL_OUT_DIR
from src.transform.build_kg import (
    build_graph_for_title,
    load_infobox_mappings,
    read_titles,
    add_prefixes,
)

def ensure_dirs() -> None:
    os.makedirs(TTL_OUT_DIR, exist_ok=True)

def build_kg_chunked(
    titles: List[str],
    out_prefix: str,
    mappings: Dict[str, Any],
    include_infobox: bool,
    chunk_size: int = 500,
    max_pages: Optional[int] = None,
) -> List[str]:
    ensure_dirs()
    produced: List[str] = []

    chunk = Graph()
    add_prefixes(chunk)

    processed = 0
    part = 1

    def flush() -> None:
        nonlocal part, chunk
        if len(chunk) == 0:
            return
        out_name = f"{out_prefix}_part{part:04d}.ttl"
        out_path = os.path.join(TTL_OUT_DIR, out_name)
        chunk.serialize(destination=out_path, format="turtle")
        produced.append(out_path)
        print(f"Wrote {out_path} (triples={len(chunk)})")
        chunk = Graph()
        add_prefixes(chunk)
        part += 1

    for title in titles:
        if max_pages is not None and processed >= max_pages:
            break
        try:
            g = build_graph_for_title(title, mappings, include_infobox=include_infobox)
            for triple in g:
                chunk.add(triple)

            processed += 1
            if processed % 50 == 0:
                print(f"Processed {processed} pages...")

            if processed % chunk_size == 0:
                flush()

        except Exception as e:
            print(f"[WARN] {title}: {e}")

    flush()
    print(f"Done. pages={processed}, files={len(produced)}")
    return produced

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--titles", required=True)
    parser.add_argument("--out_prefix", required=True)
    parser.add_argument("--chunk_size", type=int, default=500)
    parser.add_argument("--max", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--infobox", choices=["on", "off"], default="off")
    args = parser.parse_args()

    mappings = load_infobox_mappings()
    titles = read_titles(args.titles)
    max_pages = None if args.max == 0 else args.max
    include_infobox = (args.infobox == "on")

    build_kg_chunked(
        titles=titles,
        out_prefix=args.out_prefix,
        mappings=mappings,
        include_infobox=include_infobox,
        chunk_size=args.chunk_size,
        max_pages=max_pages,
    )
