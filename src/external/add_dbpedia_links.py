import requests
import time
from urllib.parse import quote

FUSEKI_SPARQL = "http://localhost:3030/tolkien/sparql"
DBPEDIA_SPARQL = "https://dbpedia.org/sparql"
KG_BASE = "http://localhost:5000"

def get_important_entities():
    """Get well-connected, important entities from our KG"""
    
    # Strategy 1: Get entities that already have Wikipedia links
    query_with_wiki = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX schema: <http://schema.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT DISTINCT ?entity ?label ?wikipedia
    WHERE {{
        ?entity rdfs:label ?label .
        ?entity owl:sameAs ?wikipedia .
        FILTER(LANG(?label) = "en")
        FILTER(STRSTARTS(STR(?entity), "{KG_BASE}/resource/"))
        FILTER(CONTAINS(STR(?wikipedia), "wikipedia.org"))
    }}
    LIMIT 1000
    """
    
    print("Strategy 1: Getting entities with Wikipedia links...")
    resp = requests.post(FUSEKI_SPARQL, data={"query": query_with_wiki}, timeout=30)
    
    entities = []
    if resp.status_code == 200:
        results = resp.json()['results']['bindings']
        for r in results:
            wiki_url = r['wikipedia']['value']
            # Convert Wikipedia URL to DBpedia URI
            # https://en.wikipedia.org/wiki/Gandalf → http://dbpedia.org/resource/Gandalf
            if '/wiki/' in wiki_url:
                page_name = wiki_url.split('/wiki/')[-1]
                dbpedia_uri = f"http://dbpedia.org/resource/{page_name}"
                
                entities.append({
                    'uri': r['entity']['value'],
                    'label': r['label']['value'],
                    'dbpedia_uri': dbpedia_uri,
                    'source': 'wikipedia_link'
                })
    
    print(f"  Found {len(entities)} entities with Wikipedia links")
    
    # Strategy 2: Get well-connected entities (most properties)
    query_connected = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?entity ?label (COUNT(?p) AS ?propCount)
    WHERE {{
        ?entity rdfs:label ?label .
        ?entity rdf:type <{KG_BASE}/vocab/Character> .
        ?entity ?p ?o .
        FILTER(LANG(?label) = "en")
        FILTER(STRSTARTS(STR(?entity), "{KG_BASE}/resource/"))
    }}
    GROUP BY ?entity ?label
    ORDER BY DESC(?propCount)
    LIMIT 300
    """
    
    print("Strategy 2: Getting most well-connected characters...")
    resp = requests.post(FUSEKI_SPARQL, data={"query": query_connected}, timeout=30)
    
    if resp.status_code == 200:
        results = resp.json()['results']['bindings']
        existing_uris = {e['uri'] for e in entities}
        
        for r in results:
            uri = r['entity']['value']
            if uri not in existing_uris:
                entities.append({
                    'uri': uri,
                    'label': r['label']['value'],
                    'dbpedia_uri': None,  # Will search for this
                    'source': 'well_connected',
                    'properties': r['propCount']['value']
                })
    
    print(f"  Added {len(entities) - len([e for e in entities if e['source'] == 'wikipedia_link'])} well-connected entities")
    
    # Strategy 3: Add famous locations
    query_locations = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT DISTINCT ?entity ?label
    WHERE {{
        ?entity rdfs:label ?label .
        ?entity rdf:type <{KG_BASE}/vocab/Location> .
        FILTER(LANG(?label) = "en")
        FILTER(STRSTARTS(STR(?entity), "{KG_BASE}/resource/"))
        FILTER(
            CONTAINS(LCASE(?label), "rivendell") ||
            CONTAINS(LCASE(?label), "gondor") ||
            CONTAINS(LCASE(?label), "rohan") ||
            CONTAINS(LCASE(?label), "shire") ||
            CONTAINS(LCASE(?label), "mordor") ||
            CONTAINS(LCASE(?label), "moria") ||
            CONTAINS(LCASE(?label), "lothlorien") ||
            CONTAINS(LCASE(?label), "minas") ||
            CONTAINS(LCASE(?label), "isengard")
        )
    }}
    LIMIT 50
    """
    
    print("Strategy 3: Getting famous locations...")
    resp = requests.post(FUSEKI_SPARQL, data={"query": query_locations}, timeout=30)
    
    if resp.status_code == 200:
        results = resp.json()['results']['bindings']
        existing_uris = {e['uri'] for e in entities}
        
        for r in results:
            uri = r['entity']['value']
            if uri not in existing_uris:
                entities.append({
                    'uri': uri,
                    'label': r['label']['value'],
                    'dbpedia_uri': None,
                    'source': 'famous_location'
                })
    
    print(f"  Added {len([e for e in entities if e['source'] == 'famous_location'])} famous locations")
    
    print(f"\nTotal entities to process: {len(entities)}")
    return entities


def search_dbpedia(label):
    """Search DBpedia for matching resource"""
    # Try direct lookup first
    dbpedia_uri = f"http://dbpedia.org/resource/{quote(label.replace(' ', '_'))}"
    
    check_query = f"""
    ASK {{
        <{dbpedia_uri}> ?p ?o .
    }}
    """
    
    try:
        resp = requests.post(
            DBPEDIA_SPARQL,
            data={"query": check_query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=10
        )
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get('boolean', False):
                return dbpedia_uri
    except:
        pass
    
    return None


def main():
    print("=" * 70)
    print("Smart DBpedia owl:sameAs Link Generator")
    print("=" * 70)
    print()
    
    # Get important entities
    entities = get_important_entities()
    
    if not entities:
        print("No entities found!")
        return
    
    # Process entities
    matches = []
    needs_search = []
    
    # Separate entities that already have DBpedia URIs from those that need searching
    for entity in entities:
        if entity['dbpedia_uri']:
            matches.append({
                'our_uri': entity['uri'],
                'label': entity['label'],
                'dbpedia_uri': entity['dbpedia_uri']
            })
        else:
            needs_search.append(entity)
    
    print(f"\n {len(matches)} entities already have DBpedia URIs (from Wikipedia links)")
    print(f" {len(needs_search)} entities need DBpedia search")
    
    # Search DBpedia for remaining entities
    if needs_search:
        print(f"\nSearching DBpedia for {len(needs_search)} entities...")
        
        for i, entity in enumerate(needs_search):
            print(f"\r  [{i+1}/{len(needs_search)}] Searching: {entity['label'][:50]}...", end="")
            
            dbpedia_uri = search_dbpedia(entity['label'])
            
            if dbpedia_uri:
                matches.append({
                    'our_uri': entity['uri'],
                    'label': entity['label'],
                    'dbpedia_uri': dbpedia_uri
                })
            
            time.sleep(0.5)  # Be polite to DBpedia
        
        print()  # New line after progress
    
    print(f"\n{'='*70}")
    print(f" Total matches found: {len(matches)}")
    print(f"{'='*70}")
    
    if not matches:
        print("\nNo matches found!")
        return
    
    # Show sample matches
    print("\nSample matches:")
    for match in matches[:15]:
        print(f"  • {match['label']}")
        print(f"    {match['our_uri']}")
        print(f"    → {match['dbpedia_uri']}")
    
    if len(matches) > 15:
        print(f"  ... and {len(matches) - 15} more")
    
    # Generate Turtle file
    triples = ["@prefix owl: <http://www.w3.org/2002/07/owl#> .", ""]
    for match in matches:
        triples.append(f"<{match['our_uri']}> owl:sameAs <{match['dbpedia_uri']}> .")
    
    turtle_content = "\n".join(triples)
    output_file = "data/kg/dbpedia_sameas_smart.ttl"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(turtle_content)
    
    print(f"\n Saved {len(matches)} owl:sameAs links to {output_file}")
    
    # Upload to Fuseki
    print("\n" + "="*70)
    response = input("Upload to Fuseki? (y/n): ")
    
    if response.lower() == 'y':
        print("\nUploading to Fuseki...")
        
        resp = requests.post(
            'http://localhost:3030/tolkien/data',
            data=turtle_content.encode('utf-8'),
            headers={'Content-Type': 'text/turtle; charset=utf-8'}
        )
        
        if resp.status_code == 200:
            result = resp.json()
            print(f" Successfully uploaded {result.get('tripleCount', len(matches))} triples!")
        else:
            print(f" Upload failed: {resp.status_code}")


if __name__ == "__main__":
    main()