from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

import mwparserfromhell
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

from configs.settings import KG_BASE, TG_WIKI_BASE, CACHE_DIR_PAGES
from src.transform.value_parsing import parse_value, strip_markup

# -------------------------
# Namespaces
# -------------------------
SCHEMA = Namespace("http://schema.org/")
RES = Namespace(KG_BASE.rstrip("/") + "/resource/")
PAGE = Namespace(KG_BASE.rstrip("/") + "/page/")
TG = Namespace(KG_BASE.rstrip("/") + "/vocab/")
PROP = Namespace(KG_BASE.rstrip("/") + "/prop/")

BAD_LINK_PREFIXES = ("category:", "file:", "template:", "help:", "special:", "talk:")

# URL detection inside wikitext like: [https://example.com label]
URL_RE = re.compile(r"https?://[^\s\]]+")


# -------------------------
# Graph helpers
# -------------------------
def add_prefixes(g: Graph) -> None:
    # Keep prefixes minimal. Avoid res:/page: qnames to reduce Turtle QName edge cases.
    g.bind("schema", SCHEMA)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)
    g.bind("tg", TG)
    g.bind("prop", PROP)


def normalize_template_name(name: str) -> str:
    # mapping keys match lowercased template names; underscore -> space
    return name.strip().lower().replace("_", " ")


def uri_escape_title(title: str) -> str:
    """
    Percent-encode titles so URIs are always safe.
    This prevents invalid Turtle tokens and upload errors.
    """
    t = title.strip().replace(" ", "_")
    return quote(t, safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.~-")

def resource_uri(title: str) -> URIRef:
    return URIRef(str(RES) + uri_escape_title(title))

def page_uri(title: str) -> URIRef:
    return URIRef(str(PAGE) + uri_escape_title(title))

def wiki_url(title: str) -> URIRef:
    return URIRef(TG_WIKI_BASE + uri_escape_title(title))


def safe_filename(title: str) -> str:
    s = title.strip()
    s = re.sub(r"[^\w\-. ]+", "_", s, flags=re.UNICODE).replace(" ", "_")
    return s[:200] if len(s) > 200 else s

def cached_path_for_title(title: str) -> str:
    return os.path.join(CACHE_DIR_PAGES, safe_filename(title) + ".json")


# -------------------------
# Safe IRI for external URLs
# -------------------------
def safe_iri(url: str) -> Optional[str]:
    """
    Percent-encode path/query/fragment. Returns None if not a normal URL.
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
    try:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return None
        path = quote(parts.path, safe="/:_()'-.,~%")
        query = quote(parts.query, safe="=&?/:_()'-.,~%")
        fragment = quote(parts.fragment, safe=":_()'-.,~%")
        return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))
    except Exception:
        return None


def extract_urls(raw: str) -> List[str]:
    """
    Extract http(s) URLs from raw wikitext value.
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    return URL_RE.findall(raw)


def normalize_url(u: str) -> Optional[str]:
    """
    Normalize:
    - if already http/https -> safe_iri
    - if looks like a bare domain -> add https:// and safe_iri
    """
    if not isinstance(u, str):
        return None
    u = strip_markup(u).strip()
    if not u:
        return None

    if u.startswith("http://") or u.startswith("https://"):
        return safe_iri(u)

    # bare domain like anke.edoras-art.de or www.example.com/path
    if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$", u):
        return safe_iri("https://" + u)

    return None


# -------------------------
# Load cached parse output
# -------------------------
def parse_cached_json(title: str) -> Dict[str, Any]:
    path = cached_path_for_title(title)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing cache for '{title}'. Expected: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_wikitext(parse_json: Dict[str, Any]) -> str:
    parse = parse_json.get("parse", {}) or {}
    wt = parse.get("wikitext", "")
    if isinstance(wt, dict):
        return wt.get("text", "") or ""
    return wt or ""

def extract_links(parse_json: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    parse = parse_json.get("parse", {}) or {}
    for l in parse.get("links", []) or []:
        if not isinstance(l, dict):
            continue
        title = l.get("title")
        if title and not title.lower().startswith(BAD_LINK_PREFIXES):
            out.append(title)
    return out

def extract_externallinks(parse_json: Dict[str, Any]) -> List[str]:
    parse = parse_json.get("parse", {}) or {}
    return [x for x in (parse.get("externallinks") or []) if isinstance(x, str)]


# -------------------------
# Template mapping
# -------------------------
def load_infobox_mappings(path: str = "configs/infobox_mappings.json") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {normalize_template_name(k): v for k, v in data.items()}

def find_mapped_templates(wikitext: str, mappings: Dict[str, Any]) -> List[Any]:
    code = mwparserfromhell.parse(wikitext)
    out = []
    for t in code.filter_templates(recursive=True):
        name = normalize_template_name(str(t.name))
        if name in mappings:
            out.append(t)
    return out


# -------------------------
# Infobox value helpers
# -------------------------
def image_filename_to_filepage_url(filename: str) -> Optional[str]:
    f = strip_markup(filename).strip()
    if not f:
        return None
    if f.lower().startswith("file:"):
        f = f[5:]
    return TG_WIKI_BASE + "File:" + uri_escape_title(f)


# -------------------------
# Core triples per page
# -------------------------
def add_core_triples(g: Graph, title: str) -> Tuple[URIRef, URIRef]:
    p = page_uri(title)
    r = resource_uri(title)

    # DBpedia-like separation: page is about resource
    g.add((p, SCHEMA.about, r))

    # Both page and resource should carry the canonical wiki URL
    wurl = wiki_url(title)
    g.add((p, SCHEMA.url, wurl))
    g.add((r, SCHEMA.url, wurl))

    # labels
    g.add((r, RDFS.label, Literal(title, lang="en")))
    g.add((p, RDFS.label, Literal(title, lang="en")))

    return p, r


# -------------------------
# Apply mapping to a template (schema type + tg type + fields)
# -------------------------
def apply_infobox(g: Graph, r: URIRef, tmpl: Any, mappings: Dict[str, Any]) -> None:
    name = normalize_template_name(str(tmpl.name))
    spec = mappings.get(name)
    if not spec:
        return

    # schema class
    schema_cls = spec.get("class")
    if schema_cls:
        g.add((r, RDF.type, URIRef(schema_cls)))

    # tg class (Priority A)
    tg_cls = spec.get("tg_class")
    if tg_cls:
        g.add((r, RDF.type, URIRef(tg_cls)))

    fields: Dict[str, Any] = spec.get("fields", {})

    for param in tmpl.params:
        key = str(param.name).strip().lower()
        if key not in fields:
            continue

        raw = str(param.value).strip()
        if not raw:
            continue

        rule = fields[key]
        prop = URIRef(rule["property"])
        kind = rule.get("kind", "auto")

        # SPECIAL: schema:url must be an IRI, not a Literal (fixes your remaining SHACL violations)
        if str(prop) == "http://schema.org/url":
            urls = extract_urls(raw)
            if urls:
                for u in urls:
                    nu = normalize_url(u)
                    if nu:
                        g.add((r, prop, URIRef(nu)))
            else:
                nu = normalize_url(raw)
                if nu:
                    g.add((r, prop, URIRef(nu)))
            # If we couldn't normalize into a URL, we skip (better than writing a bad literal)
            continue

        # images
        if kind == "image":
            url = image_filename_to_filepage_url(raw)
            if url:
                g.add((r, prop, URIRef(url)))
            continue

        linked_titles, literal_parts = parse_value(raw)

        # literal
        if kind == "literal":
            g.add((r, prop, Literal(strip_markup(raw))))
            continue

        # auto / wikilink_or_literal
        if kind in ("wikilink_or_literal", "auto"):
            for t in linked_titles:
                if t and not t.lower().startswith(BAD_LINK_PREFIXES):
                    g.add((r, prop, resource_uri(t)))
            for lit in literal_parts:
                if lit:
                    g.add((r, prop, Literal(lit)))
            if not linked_titles and not literal_parts:
                g.add((r, prop, Literal(strip_markup(raw))))
            continue

        # fallback
        g.add((r, prop, Literal(strip_markup(raw))))


# -------------------------
# Build graph for one title
# -------------------------
def build_graph_for_title(title: str, mappings: Dict[str, Any], include_infobox: bool) -> Graph:
    parse_json = parse_cached_json(title)
    wikitext = extract_wikitext(parse_json)
    links = extract_links(parse_json)
    externals = extract_externallinks(parse_json)

    g = Graph()
    add_prefixes(g)
    p, r = add_core_triples(g, title)

    # internal links between resources
    for lt in links:
        g.add((r, SCHEMA.relatedTo, resource_uri(lt)))

    # external links:
    # - wikipedia -> owl:sameAs (IRI)
    # - other -> schema:url on page (IRI if valid else literal)
    for u in externals:
        low = u.lower()
        safe = safe_iri(u)
        if "wikipedia.org/wiki/" in low and safe:
            g.add((r, OWL.sameAs, URIRef(safe)))
        else:
            if safe:
                g.add((p, SCHEMA.url, URIRef(safe)))
            else:
                g.add((p, SCHEMA.url, Literal(u)))

    if include_infobox:
        for tmpl in find_mapped_templates(wikitext, mappings):
            apply_infobox(g, r, tmpl, mappings)

    return g


def read_titles(path: str) -> List[str]:
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(s)
    return out
