from __future__ import annotations

import argparse
from pathlib import Path
import mwparserfromhell

from src.transform.build_kg import parse_cached_json, extract_wikitext

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True, help="Page title, e.g. Elrond")
    parser.add_argument("--infobox", default="infobox character", help="Infobox template name to extract")
    parser.add_argument("--out", default="data/cache/infobox_elrond.wikitext")
    args = parser.parse_args()

    parse_json = parse_cached_json(args.title)
    wikitext = extract_wikitext(parse_json)

    code = mwparserfromhell.parse(wikitext)
    target = args.infobox.strip().lower()

    for t in code.filter_templates(recursive=True):
        name = str(t.name).strip().lower()
        if name == target:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(str(t), encoding="utf-8")
            print(f"Wrote infobox template to {args.out}")
            return

    raise SystemExit(f"Could not find template '{args.infobox}' on page '{args.title}'")

if __name__ == "__main__":
    main()
