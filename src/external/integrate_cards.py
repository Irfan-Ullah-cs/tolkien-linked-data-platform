import json
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

# --------------------
# Paths
# --------------------
CARDS_JSON = Path("data/external/cards.json")
OUTPUT_TTL = Path("data/kg/cards.ttl")

# --------------------
# Namespaces
# --------------------
SCHEMA = Namespace("http://schema.org/")
TKG = Namespace("http://localhost:5000/vocab/")
RES = Namespace("http://localhost:5000/resource/")

# --------------------
# Helpers
# --------------------
def load_cards_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"cards.json not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def best_lang_value(obj: dict, fallback: str = None) -> str | None:
    """
    Pick English value if available, otherwise any value.
    """
    if not isinstance(obj, dict):
        return fallback
    if "en" in obj:
        return obj["en"]
    return next(iter(obj.values()), fallback)

# --------------------
# Main integration
# --------------------
def main():
    data = load_cards_json(CARDS_JSON)

    g = Graph()
    g.bind("schema", SCHEMA)
    g.bind("tkg", TKG)
    g.bind("rdfs", RDFS)

    card_count = 0

    for set_id, set_obj in data.items():
        if "cards" not in set_obj:
            continue

        # Card set resource
        set_uri = RES[f"CardSet/{set_id}"]
        g.add((set_uri, RDF.type, SCHEMA.CreativeWork))
        g.add((set_uri, SCHEMA.identifier, Literal(set_id)))

        set_name = best_lang_value(set_obj.get("name"))
        if set_name:
            g.add((set_uri, SCHEMA.name, Literal(set_name, lang="en")))

        image_base = set_obj.get("imageBaseUrl", {}).get("en")

        for card_id, card_obj in set_obj["cards"].items():
            card_uri = RES[f"card/{set_id}-{card_id}"]

            # Type
            g.add((card_uri, RDF.type, TKG.Card))

            # Identifier
            g.add((card_uri, SCHEMA.identifier, Literal(f"{set_id}-{card_id}")))

            # Name
            name = best_lang_value(card_obj.get("name"))
            if name:
                g.add((card_uri, SCHEMA.name, Literal(name, lang="en")))

            # Link to set
            g.add((card_uri, SCHEMA.isPartOf, set_uri))

            # Image
            if image_base and "image" in card_obj:
                img_url = image_base.rstrip("/") + "/" + card_obj["image"].lstrip("/")
                g.add((card_uri, SCHEMA.image, URIRef(img_url)))

            card_count += 1

    OUTPUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(OUTPUT_TTL, format="turtle")

    print(f"✔ cards.ttl written to {OUTPUT_TTL}")
    print(f"✔ Total cards created: {card_count}")
    print(f"✔ Total triples: {len(g)}")

if __name__ == "__main__":
    main()
