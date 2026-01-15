#!/usr/bin/env python3
"""
Analyze RDF data structure to inform SHACL shape creation
Queries Fuseki to understand actual data patterns
"""

from SPARQLWrapper import SPARQLWrapper, JSON

FUSEKI_ENDPOINT = "http://localhost:3030/tolkien/query"

def query_fuseki(query):
    """Execute SPARQL query and return results"""
    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()

def main():
    print("=" * 70)
    print("ANALYZING RDF DATA STRUCTURE FOR SHACL VALIDATION")
    print("=" * 70)
    
    # 1. What classes exist?
    print("\n1. CLASS DISTRIBUTION")
    print("-" * 70)
    query = """
    SELECT ?class (COUNT(?s) as ?count)
    WHERE {
        ?s a ?class .
    }
    GROUP BY ?class
    ORDER BY DESC(?count)
    LIMIT 20
    """
    results = query_fuseki(query)
    for result in results["results"]["bindings"]:
        cls = result["class"]["value"].split("/")[-1].split("#")[-1]
        count = result["count"]["value"]
        print(f"  {cls:40} {count:>10}")
    
    # 2. What properties are used?
    print("\n2. MOST COMMON PROPERTIES")
    print("-" * 70)
    query = """
    SELECT ?property (COUNT(?s) as ?count)
    WHERE {
        ?s ?property ?o .
        FILTER(?property != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
    }
    GROUP BY ?property
    ORDER BY DESC(?count)
    LIMIT 30
    """
    results = query_fuseki(query)
    for result in results["results"]["bindings"]:
        prop = result["property"]["value"].split("/")[-1].split("#")[-1]
        count = result["count"]["value"]
        print(f"  {prop:40} {count:>10}")
    
    # 3. Sample Person/Character entities
    print("\n3. SAMPLE PERSON/CHARACTER PROPERTIES")
    print("-" * 70)
    query = """
    SELECT ?person ?prop ?value
    WHERE {
        ?person a ?type .
        FILTER(CONTAINS(STR(?type), "Person") || CONTAINS(STR(?type), "Character"))
        ?person ?prop ?value .
    }
    LIMIT 50
    """
    results = query_fuseki(query)
    person_props = set()
    for result in results["results"]["bindings"]:
        prop = result["prop"]["value"].split("/")[-1].split("#")[-1]
        person_props.add(prop)
    
    for prop in sorted(person_props):
        print(f"  - {prop}")
    
    # 4. Sample Place/Location entities
    print("\n4. SAMPLE PLACE/LOCATION PROPERTIES")
    print("-" * 70)
    query = """
    SELECT ?place ?prop ?value
    WHERE {
        ?place a ?type .
        FILTER(CONTAINS(STR(?type), "Place") || CONTAINS(STR(?type), "Location"))
        ?place ?prop ?value .
    }
    LIMIT 50
    """
    results = query_fuseki(query)
    place_props = set()
    for result in results["results"]["bindings"]:
        prop = result["prop"]["value"].split("/")[-1].split("#")[-1]
        place_props.add(prop)
    
    for prop in sorted(place_props):
        print(f"  - {prop}")
    
    # 5. Date formats check
    print("\n5. DATE FORMATS USED")
    print("-" * 70)
    query = """
    SELECT DISTINCT ?date
    WHERE {
        ?s ?dateProp ?date .
        FILTER(CONTAINS(STR(?dateProp), "Date") || CONTAINS(STR(?dateProp), "date"))
    }
    LIMIT 20
    """
    results = query_fuseki(query)
    print("  Sample dates:")
    for result in results["results"]["bindings"]:
        date = result["date"]["value"]
        print(f"    {date}")
    
    # 6. External links (owl:sameAs)
    print("\n6. EXTERNAL LINKS (owl:sameAs)")
    print("-" * 70)
    query = """
    SELECT (COUNT(?s) as ?count)
    WHERE {
        ?s <http://www.w3.org/2002/07/owl#sameAs> ?external .
    }
    """
    results = query_fuseki(query)
    count = results["results"]["bindings"][0]["count"]["value"]
    print(f"  Total owl:sameAs links: {count}")
    
    # 7. Multilingual labels
    print("\n7. MULTILINGUAL LABELS")
    print("-" * 70)
    query = """
    SELECT ?lang (COUNT(?s) as ?count)
    WHERE {
        ?s <http://www.w3.org/2000/01/rdf-schema#label> ?label .
        BIND(LANG(?label) as ?lang)
    }
    GROUP BY ?lang
    ORDER BY DESC(?count)
    """
    results = query_fuseki(query)
    for result in results["results"]["bindings"]:
        lang = result["lang"]["value"] if result["lang"]["value"] else "(no language tag)"
        count = result["count"]["value"]
        print(f"  {lang:20} {count:>10}")
    
    # 8. Check for required properties on persons
    print("\n8. PERSON ENTITIES - PROPERTY COVERAGE")
    print("-" * 70)
    
    queries_to_check = [
        ("Total Persons", "SELECT (COUNT(?s) as ?count) WHERE { ?s a <http://schema.org/Person> . }"),
        ("Have name", "SELECT (COUNT(?s) as ?count) WHERE { ?s a <http://schema.org/Person> ; <http://schema.org/name> ?name . }"),
        ("Have birthDate", "SELECT (COUNT(?s) as ?count) WHERE { ?s a <http://schema.org/Person> ; <http://schema.org/birthDate> ?date . }"),
        ("Have image", "SELECT (COUNT(?s) as ?count) WHERE { ?s a <http://schema.org/Person> ; <http://schema.org/image> ?img . }"),
    ]
    
    for label, q in queries_to_check:
        results = query_fuseki(q)
        count = results["results"]["bindings"][0]["count"]["value"]
        print(f"  {label:20} {count:>10}")
    
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE - Use this info to write targeted SHACL shapes")
    print("=" * 70)

if __name__ == "__main__":
    main()