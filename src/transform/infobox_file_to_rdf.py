from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional
import re

import mwparserfromhell
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

from configs.settings import KG_BASE, TG_WIKI_BASE

SCHEMA = Namespace("http://schema.org/")
RES = Namespace(KG_BASE + "/resource/")

def uri_escape_title(title: str) -> str:
    t = title.strip().replace(" ", "_")
    t = re.sub(r"[^\w\-.~:/?#\[\]@!$&'()*+,;=%]", "_", t)
    return t

def res_uri(title: str) -> URIRef:
    return URIRef(str(RES) + uri_escape_title(title))

def wiki_url(title: str) -> URIRef:
    return URIRef(TG_WIKI_BASE + uri_escape_title(title))

def wikilink_title(v: str) -> Optional[str]:
    v = v.strip()
    m = re.match(r"^\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]$", v)
    return m.group(1).strip() if m else None

def image_filepage_url(filename: str) -> Optional[str]:
    f = filename.strip()
    if not f:
        return None
    if f.lower().startswith("file:"):
        f = f[5:]
    return TG_WIKI_BASE + "File:" + uri_escape_title(f)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity", required=True, help="Entity title, e.g. Elrond")
    parser.add_argument("--template_file", required=True, help="Path to saved template wikitext")
    parser.add_argument("--out", default="data/ttl/elrond_infobox.ttl")
    args = parser.parse_args()

    template_text = Path(args.template_file).read_text(encoding="utf-8")
    code = mwparserfromhell.parse(template_text)
    templates = code.filter_templates()
    if not templates:
        raise SystemExit("No template found in template_file.")

    tmpl = templates[0]
    name = str(tmpl.name).strip().lower()
    if not name.startswith("infobox"):
        raise SystemExit(f"Expected an infobox template, got: {tmpl.name}")

    g = Graph()
    g.bind("schema", SCHEMA)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)

    subj = res_uri(args.entity)

    # Minimal class for character
    g.add((subj, RDF.type, SCHEMA.Person))
    g.add((subj, RDFS.label, Literal(args.entity, lang="en")))
    g.add((subj, SCHEMA.url, wiki_url(args.entity)))

    # Map key parameters from your Elrond example
    # Keep it simple and safe: if it looks like a wikilink, turn into a resource URI, else literal.
    param_map = {
        "name": (SCHEMA.name, "literal"),
        "gender": (SCHEMA.gender, "literal"),
        "titles": (SCHEMA.jobTitle, "wikilink_or_literal"),
        "location": (SCHEMA.homeLocation, "wikilink_or_literal"),
        "affiliation": (SCHEMA.memberOf, "wikilink_or_literal"),
        "birthlocation": (SCHEMA.birthPlace, "wikilink_or_literal"),
        "spouse": (SCHEMA.spouse, "wikilink_or_literal"),
        "children": (SCHEMA.children, "wikilink_or_literal"),
        "parentage": (SCHEMA.parent, "wikilink_or_literal"),
        "image": (SCHEMA.image, "image"),
        "age": (SCHEMA.age, "literal"),
        "language": (SCHEMA.knowsLanguage, "wikilink_or_literal"),
        "othernames": (SCHEMA.alternateName, "literal"),
        "people": (SCHEMA.additionalType, "wikilink_or_literal"),
        "race": (SCHEMA.additionalType, "wikilink_or_literal"),
        "house": (SCHEMA.additionalType, "wikilink_or_literal"),
    }

    for p in tmpl.params:
        key = str(p.name).strip().lower()
        if key not in param_map:
            continue

        pred, kind = param_map[key]
        raw = str(p.value).strip()
        if not raw:
            continue

        if kind == "literal":
            g.add((subj, pred, Literal(raw)))
        elif kind == "image":
            u = image_filepage_url(raw)
            if u:
                g.add((subj, pred, URIRef(u)))
        else:
            # Handle values that may contain multiple wikilinks separated by commas, <br>, & etc.
            # We’ll extract all [[...]] targets we see; if none, store as literal.
            targets = re.findall(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]", raw)
            if targets:
                for t in targets:
                    g.add((subj, pred, res_uri(t.strip())))
            else:
                g.add((subj, pred, Literal(raw)))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_path), format="turtle")
    print(f"Wrote {out_path} (triples={len(g)})")

if __name__ == "__main__":
    main()
