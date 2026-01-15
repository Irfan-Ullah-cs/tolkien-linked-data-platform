from pathlib import Path
from rdflib import Graph

IN_DIR = Path("data/ttl")
PATTERN = "tolkien_all_part*.ttl"   # must match your out_prefix
OUT = Path("data/kg/tolkien.ttl")

def main():
    files = sorted(IN_DIR.glob(PATTERN))
    if not files:
        raise SystemExit(f"No TTL files found in {IN_DIR} matching {PATTERN}")

    g = Graph()
    for f in files:
        print(f"Loading {f}")
        g.parse(f, format="turtle")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(g.serialize(format="turtle"), encoding="utf-8")
    print(f"Wrote {OUT} triples={len(g)}")

if __name__ == "__main__":
    main()
