"""
SHACL validation for the Tolkien Gateway Knowledge Graph

- Loads the merged RDF graph (data/kg/all.ttl)
- Loads SHACL shapes (data/kg/shapes.ttl)
- Runs SHACL validation using pySHACL
- Writes a validation report to report/shacl_report.txt
"""

from rdflib import Graph
from pyshacl import validate
from pathlib import Path

DATA_FILE = "data/tolkien_complete.ttl"
SHAPES_FILE = "data/shapes.ttl"
REPORT_FILE = "chacl_report/shacl_report.txt"


def main():
    print("Loading RDF data graph...")
    data_graph = Graph()
    data_graph.parse(DATA_FILE, format="turtle")
    print(f"Data graph loaded ({len(data_graph)} triples)")

    print("Loading SHACL shapes graph...")
    shapes_graph = Graph()
    shapes_graph.parse(SHAPES_FILE, format="turtle")
    print(f"Shapes graph loaded ({len(shapes_graph)} triples)")

    print("Running SHACL validation...")
    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True
    )

    # Ensure report directory exists
    Path(REPORT_FILE).parent.mkdir(parents=True, exist_ok=True)

    # Write report to file
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n=== SHACL VALIDATION RESULT ===")
    print(f"Conforms: {conforms}")
    print(f"Report written to: {REPORT_FILE}")

    if not conforms:
        print(" Validation completed with violations (see report file)")
    else:
        print("Validation successful (no violations)")


if __name__ == "__main__":
    main()
