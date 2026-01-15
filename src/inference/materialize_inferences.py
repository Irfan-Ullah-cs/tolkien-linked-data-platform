import requests
import time

FUSEKI_SPARQL = "http://localhost:3030/tolkien/sparql"
FUSEKI_UPDATE = "http://localhost:3030/tolkien/update"

def count_triples():
    """Count total triples in KG"""
    query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
    resp = requests.post(FUSEKI_SPARQL, data={"query": query}, timeout=30)
    if resp.status_code == 200:
        return int(resp.json()['results']['bindings'][0]['count']['value'])
    return 0

def materialize_symmetric_spouse():
    """Infer symmetric spouse relationships"""
    query = """
    PREFIX schema: <http://schema.org/>
    INSERT {
        ?spouse2 schema:spouse ?spouse1 .
    }
    WHERE {
        ?spouse1 schema:spouse ?spouse2 .
        FILTER NOT EXISTS { ?spouse2 schema:spouse ?spouse1 }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=60)
    return resp.status_code in [200, 204]

def materialize_inverse_parent_children():
    """Infer parent from children and vice versa"""
    query = """
    PREFIX schema: <http://schema.org/>
    INSERT {
        ?child schema:parent ?parent .
    }
    WHERE {
        ?parent schema:children ?child .
        FILTER NOT EXISTS { ?child schema:parent ?parent }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=60)
    return resp.status_code in [200, 204]

def materialize_inverse_depicts_depictedIn():
    """Infer depictedIn from depicts"""
    query = """
    PREFIX tolkien: <http://localhost:5000/vocab/>
    INSERT {
        ?character tolkien:depictedIn ?card .
    }
    WHERE {
        ?card tolkien:depicts ?character .
        FILTER NOT EXISTS { ?character tolkien:depictedIn ?card }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=60)
    return resp.status_code in [200, 204]

def materialize_symmetric_relatedTo():
    """Infer symmetric relatedTo relationships"""
    query = """
    PREFIX schema: <http://schema.org/>
    INSERT {
        ?entity2 schema:relatedTo ?entity1 .
    }
    WHERE {
        ?entity1 schema:relatedTo ?entity2 .
        FILTER NOT EXISTS { ?entity2 schema:relatedTo ?entity1 }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=120)
    return resp.status_code in [200, 204]

def materialize_rdfs_subclass():
    """Infer types from subClassOf"""
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX schema: <http://schema.org/>
    PREFIX tolkien: <http://localhost:5000/vocab/>
    
    INSERT {
        ?entity rdf:type schema:Person .
    }
    WHERE {
        ?entity rdf:type tolkien:Character .
        FILTER NOT EXISTS { ?entity rdf:type schema:Person }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=60)
    return resp.status_code in [200, 204]

def materialize_symmetric_sameas():
    """Infer symmetric owl:sameAs relationships"""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    INSERT {
        ?entity2 owl:sameAs ?entity1 .
    }
    WHERE {
        ?entity1 owl:sameAs ?entity2 .
        FILTER NOT EXISTS { ?entity2 owl:sameAs ?entity1 }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=60)
    return resp.status_code in [200, 204]

def materialize_transitive_sameas():
    """Infer transitive owl:sameAs relationships"""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    INSERT {
        ?entity1 owl:sameAs ?entity3 .
    }
    WHERE {
        ?entity1 owl:sameAs ?entity2 .
        ?entity2 owl:sameAs ?entity3 .
        FILTER (?entity1 != ?entity3)
        FILTER NOT EXISTS { ?entity1 owl:sameAs ?entity3 }
    }
    """
    resp = requests.post(FUSEKI_UPDATE, data={"update": query}, timeout=120)
    return resp.status_code in [200, 204]

def main():
    print("=" * 70)
    print("Materializing OWL/RDFS Inferences")
    print("=" * 70)
    
    # Get baseline
    print("\n[Baseline]")
    initial_count = count_triples()
    print(f"  Current triples: {initial_count:,}")
    
    inferences = []
    
    # Rule 1: Symmetric spouse
    print("\n[Rule 1: Symmetric spouse]")
    print("  IF ?a spouse ?b THEN ?b spouse ?a")
    before = count_triples()
    if materialize_symmetric_spouse():
        after = count_triples()
        added = after - before
        inferences.append(("Symmetric spouse", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    time.sleep(1)
    
    # Rule 2: Inverse parent/children
    print("\n[Rule 2: Inverse parent/children]")
    print("  IF ?p children ?c THEN ?c parent ?p")
    before = count_triples()
    if materialize_inverse_parent_children():
        after = count_triples()
        added = after - before
        inferences.append(("Inverse parent/children", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    time.sleep(1)

    print("\n[Rule 2b: Inverse depicts/depictedIn]")
    print("  IF ?card depicts ?char THEN ?char depictedIn ?card")
    before = count_triples()
    if materialize_inverse_depicts_depictedIn():
        after = count_triples()
        added = after - before
        inferences.append(("Inverse depicts/depictedIn", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    time.sleep(1)
    
    # Rule 3: Symmetric relatedTo (BIG ONE - will take time)
    print("\n[Rule 3: Symmetric relatedTo]")
    print("  IF ?a relatedTo ?b THEN ?b relatedTo ?a")
    print("  (This may take 30-60 seconds due to high volume...)")
    before = count_triples()
    if materialize_symmetric_relatedTo():
        after = count_triples()
        added = after - before
        inferences.append(("Symmetric relatedTo", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    time.sleep(1)
    
    # Rule 4: RDFS subClassOf
    print("\n[Rule 4: RDFS subClassOf]")
    print("  IF ?x type Character AND Character subClassOf Person THEN ?x type Person")
    before = count_triples()
    if materialize_rdfs_subclass():
        after = count_triples()
        added = after - before
        inferences.append(("RDFS subClassOf", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    time.sleep(1)
    
    # Rule 5: Symmetric owl:sameAs
    print("\n[Rule 5: Symmetric owl:sameAs]")
    print("  IF ?a sameAs ?b THEN ?b sameAs ?a")
    before = count_triples()
    if materialize_symmetric_sameas():
        after = count_triples()
        added = after - before
        inferences.append(("Symmetric owl:sameAs", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    time.sleep(1)
    
    # Rule 6: Transitive owl:sameAs
    print("\n[Rule 6: Transitive owl:sameAs]")
    print("  IF ?a sameAs ?b AND ?b sameAs ?c THEN ?a sameAs ?c")
    print("  (This may take time if there are long sameAs chains...)")
    before = count_triples()
    if materialize_transitive_sameas():
        after = count_triples()
        added = after - before
        inferences.append(("Transitive owl:sameAs", added))
        print(f"  [OK] Added {added:,} triples")
    else:
        print("  [FAIL] Failed")
    
    # Final count
    print("Summary")
    
    final_count = count_triples()
    total_added = final_count - initial_count
    
    print(f"\n  Initial triples:  {initial_count:,}")
    print(f"  Final triples:    {final_count:,}")
    print(f"  Inferred triples: {total_added:,}")
    print(f"  Increase:         {(total_added/initial_count*100):.1f}%")
    
    print("\n  Breakdown:")
    for rule, count in inferences:
        print(f"    - {rule}: {count:,}")
    

    print("Materialization complete!")

if __name__ == "__main__":
    main()