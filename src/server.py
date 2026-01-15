from __future__ import annotations
import urllib.parse
import re
from urllib.parse import unquote, quote
import hashlib
from typing import List, Tuple, Dict, Any

from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS

import requests
from flask import Flask, request, render_template, redirect, Response, jsonify

KG_BASE = "http://localhost:5000"
FUSEKI_SPARQL = "http://localhost:3030/tolkien/sparql"
FUSEKI_QUERY = "http://localhost:3030/tolkien/sparql"
FUSEKI_UPDATE = "http://localhost:3030/tolkien/update"

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SCHEMA = "http://schema.org/"

app = Flask(__name__)


# ---------------------------
# Content negotiation
# ---------------------------
def wants_turtle() -> bool:
    accept = (request.headers.get("Accept") or "").lower()
    return ("text/turtle" in accept) or ("application/rdf+xml" in accept) or ("application/n-triples" in accept)


# ---------------------------
# SPARQL helpers
# ---------------------------
def _post_construct(query: str, timeout: int = 20) -> Graph:
    resp = requests.post(
        FUSEKI_SPARQL,
        data={"query": query},
        headers={"Accept": "text/turtle"},
        timeout=timeout,
    )
    resp.raise_for_status()
    g = Graph()
    g.parse(data=resp.content, format="turtle")
    return g


def construct_resource(subject_iri: str) -> Graph:
    q1 = f"""
    PREFIX rdf:  <{RDF}>
    PREFIX rdfs: <{RDFS}>
    PREFIX owl:  <{OWL}>
    PREFIX schema: <http://schema.org/>
    CONSTRUCT {{
      <{subject_iri}> ?p ?o .
      <{subject_iri}> rdf:type ?type .
      ?type rdfs:subClassOf ?super .
      <{subject_iri}> owl:sameAs ?same .
      ?same owl:sameAs <{subject_iri}> .
    }}
    WHERE {{
      <{subject_iri}> ?p ?o .
      FILTER (?p != schema:relatedTo)
      OPTIONAL {{
        <{subject_iri}> rdf:type ?type .
        OPTIONAL {{ ?type rdfs:subClassOf ?super . }}
      }}
      OPTIONAL {{ <{subject_iri}> owl:sameAs ?same . }}
      OPTIONAL {{ ?same owl:sameAs <{subject_iri}> . }}
    }}
    """
    
    q2 = f"""
    PREFIX schema: <http://schema.org/>
    CONSTRUCT {{
      <{subject_iri}> schema:relatedTo ?o .
    }}
    WHERE {{
      <{subject_iri}> schema:relatedTo ?o .
    }}
    LIMIT 500
    """
    
    g = _post_construct(q1, timeout=30)
    g2 = _post_construct(q2, timeout=10)
    for triple in g2:
        g.add(triple)
    return g


def get_kg_statistics() -> Dict[str, Any]:
    """Query Fuseki for comprehensive KG statistics"""
    # Initialize all stats with defaults first
    stats = {
        'total_triples': 'N/A',
        'unique_entities': 'N/A',
        'characters': 'N/A',
        'locations': 'N/A',
        'works': 'N/A',
        'cards': 'N/A',
        'with_birth': 'N/A',
        'with_images': 'N/A',
        'external_links': 'N/A',
        'types': [],
        'languages': []
    }
    
    try:
        # Total triples
        q_triples = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_triples}, timeout=10)
        if resp.status_code == 200:
            stats['total_triples'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Unique entities
        q_entities = f"""
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE {{ 
            ?s a ?type . 
            FILTER(STRSTARTS(STR(?s), "{KG_BASE}/resource/"))
        }}
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_entities}, timeout=10)
        if resp.status_code == 200:
            stats['unique_entities'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Characters count
        q_characters = f"""
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE {{ 
            ?s a <{KG_BASE}/vocab/Character> .
        }}
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_characters}, timeout=10)
        if resp.status_code == 200:
            stats['characters'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Locations count
        q_locations = f"""
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE {{ 
            ?s a <{KG_BASE}/vocab/Location> .
        }}
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_locations}, timeout=10)
        if resp.status_code == 200:
            stats['locations'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Works count
        q_works = f"""
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE {{ 
            ?s a <{KG_BASE}/vocab/Work> .
        }}
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_works}, timeout=10)
        if resp.status_code == 200:
            stats['works'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Cards count
        q_cards = f"""
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE {{ 
            ?s a <{KG_BASE}/vocab/Card> .
        }}
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_cards}, timeout=10)
        if resp.status_code == 200:
            stats['cards'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Entities with birth dates
        q_birth = """
        PREFIX schema: <http://schema.org/>
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE { 
            ?s schema:birthDate ?date .
        }
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_birth}, timeout=10)
        if resp.status_code == 200:
            stats['with_birth'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Entities with images
        q_images = """
        PREFIX schema: <http://schema.org/>
        SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE { 
            ?s schema:image ?img .
        }
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_images}, timeout=10)
        if resp.status_code == 200:
            stats['with_images'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # External links count
        q_external = """
        PREFIX schema: <http://schema.org/>
        SELECT (COUNT(?url) AS ?count) WHERE { 
            ?s schema:url ?url .
            FILTER(STRSTARTS(STR(?url), "http"))
        }
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_external}, timeout=10)
        if resp.status_code == 200:
            stats['external_links'] = resp.json()['results']['bindings'][0]['count']['value']
    except: pass
    
    try:
        # Entity types (top 10)
        q_types = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?type (COUNT(?s) AS ?count) WHERE {
            ?s rdf:type ?type .
            FILTER(STRSTARTS(STR(?type), "http://localhost:5000/vocab/"))
        }
        GROUP BY ?type
        ORDER BY DESC(?count)
        LIMIT 10
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_types}, timeout=10)
        if resp.status_code == 200:
            stats['types'] = [(b['type']['value'].split('/')[-1], b['count']['value']) 
                              for b in resp.json()['results']['bindings']]
    except: pass
    
    try:
        # Languages available - FIXED QUERY
        q_langs = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?lang (COUNT(?label) AS ?count) 
        WHERE {
            ?s rdfs:label ?label .
            BIND(LANG(?label) AS ?lang)
            FILTER(?lang != "")
        }
        GROUP BY ?lang
        ORDER BY DESC(?count)
        """
        resp = requests.post(FUSEKI_SPARQL, data={"query": q_langs}, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            stats['languages'] = [(b['lang']['value'], b['count']['value']) 
                                for b in result['results']['bindings']]
            print(f"Found {len(stats['languages'])} languages")
    except Exception as e:
        print(f"Languages query error: {e}")
    
    return stats


# ---------------------------
# Data extraction helpers
# ---------------------------
def wiki_file_to_image_url(wiki_url: str) -> str:
    if "/wiki/File:" not in wiki_url:
        return wiki_url
    filename_encoded = wiki_url.split("/wiki/File:")[-1]
    filename_decoded = urllib.parse.unquote(filename_encoded)
    md5 = hashlib.md5(filename_decoded.encode()).hexdigest()
    filename_for_url = urllib.parse.quote(filename_decoded)
    return f"https://tolkiengateway.net/w/images/{md5[0]}/{md5[:2]}/{filename_for_url}"


def clean_wiki_text(text: str) -> str:
    text = re.sub(r'\{\{TA\|(\d+)\}\}', r'T.A. \1', text)
    text = re.sub(r'\{\{SA\|(\d+)\}\}', r'S.A. \1', text)
    text = re.sub(r'\{\{FA\|(\d+)\}\}', r'F.A. \1', text)
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    return text.strip()


def extract_entity_data(subject_iri):
    """Extract all data for an entity from the triplestore"""
    
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <http://schema.org/>
    
    CONSTRUCT {{
        <{subject_iri}> ?p ?o .
    }}
    WHERE {{
        <{subject_iri}> ?p ?o .
    }}
    """
    
    try:
        resp = requests.post(
            FUSEKI_QUERY,
            data={"query": query},
            headers={"Accept": "text/turtle"},
            timeout=30
        )
        
        if resp.status_code != 200:
            return None
        
        g = Graph()
        g.parse(data=resp.content, format="turtle")
        
        if len(g) == 0:
            return None
        
        print(f"Found {len(g)} triples for {subject_iri}")
        
        subject = URIRef(subject_iri)
        label_uri = URIRef('http://www.w3.org/2000/01/rdf-schema#label')
        type_uri = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
        
        # Labels
        labels = []
        for s, p, o in g.triples((subject, label_uri, None)):
            if isinstance(o, Literal):
                labels.append((o.language or 'en', str(o)))
        
        # Title
        title = None
        for lang, text in labels:
            if lang == 'en':
                title = text
                break
        if not title and labels:
            title = labels[0][1]
        if not title:
            title = unquote(subject_iri.split('/')[-1]).replace('_', ' ')
        
        # Types
        types = []
        for s, p, o in g.triples((subject, type_uri, None)):
            type_name = str(o).split('/')[-1].split('#')[-1]
            if type_name not in ['Resource', 'Thing']:
                types.append(type_name)
        
        # Core facts
        core_facts = {}
        core_props = {
            'http://schema.org/birthDate': 'Birth',
            'http://schema.org/deathDate': 'Death',
            'http://schema.org/gender': 'Gender',
            'http://localhost:5000/vocab/race': 'Race',
            'http://localhost:5000/vocab/culture': 'Culture',
        }
        
        for prop_uri_str, label_text in core_props.items():
            for s, p, o in g.triples((subject, URIRef(prop_uri_str), None)):
                if isinstance(o, Literal):
                    core_facts[label_text] = str(o)
        
        # Description
        description = None
        for s, p, o in g.triples((subject, URIRef('http://schema.org/description'), None)):
            if isinstance(o, Literal):
                description = str(o)
                break
        
        # Image
        image_url = None
        for s, p, o in g.triples((subject, URIRef('http://schema.org/image'), None)):
            image_url = str(o)
            break
        
        # TRANSFORM wiki File: URLs to actual image URLs
        if image_url:
            image_url = wiki_file_to_image_url(image_url) 
            
        
        # Properties
        literal_props = []
        uri_props = []
        
        skip_props = [
            'http://www.w3.org/2000/01/rdf-schema#label',
            'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
            'http://schema.org/description',
            'http://schema.org/image'
        ] + list(core_props.keys())
        
        for s, p, o in g:
            if str(p) in skip_props:
                continue
            
            prop_name = str(p).split('/')[-1].split('#')[-1]
            
            if isinstance(o, Literal):
                obj_str = str(o).strip()
                if obj_str.lower() in ['and', '&', 'or', ',', '(', ')', '-', '–', '—'] or len(obj_str) <= 1:
                    continue
                literal_props.append((prop_name, str(p), str(o)))
            else:
                uri_props.append((prop_name, str(p), str(o)))
        
        return {
            'title': title,
            'types': types,
            'labels': labels,
            'core_facts': core_facts,
            'description': description,
            'image_url': image_url,
            'literal_props': literal_props,
            'uri_props': uri_props
        }
        
    except Exception as e:
        print(f"Error extracting entity data: {e}")
        import traceback
        traceback.print_exc()
        return None


def wiki_file_to_image_url(wiki_url: str) -> str:
    """Transform wiki File: page URL to actual image URL"""
    if not wiki_url or "/wiki/File:" not in wiki_url:
        return wiki_url
    
    filename_encoded = wiki_url.split("/wiki/File:")[-1]
    filename_decoded = urllib.parse.unquote(filename_encoded)
    
    md5 = hashlib.md5(filename_decoded.encode('utf-8')).hexdigest()
    filename_for_url = urllib.parse.quote(filename_decoded)
    
    return f"https://tolkiengateway.net/w/images/{md5[0]}/{md5[:2]}/{filename_for_url}"


def get_featured_characters():
    """Fetch 5 famous characters with images for home page"""
    
    # List of famous character URIs
    character_uris = [
        "http://localhost:5000/resource/Gandalf",
        "http://localhost:5000/resource/Frodo_Baggins",
        "http://localhost:5000/resource/Aragorn",
        "http://localhost:5000/resource/Galadriel",
        "http://localhost:5000/resource/Sauron"
    ]
    
    featured = []
    
    for uri in character_uris:
        # Construct SPARQL query to get character info
        query = f"""
        PREFIX schema: <http://schema.org/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?name ?image ?description ?birthDate ?deathDate ?spouse ?race
        WHERE {{
            <{uri}> rdfs:label ?name .
            OPTIONAL {{ <{uri}> schema:image ?image }}
            OPTIONAL {{ <{uri}> schema:description ?description }}
            OPTIONAL {{ <{uri}> schema:birthDate ?birthDate }}
            OPTIONAL {{ <{uri}> schema:deathDate ?deathDate }}
            OPTIONAL {{ <{uri}> schema:spouse ?spouse }}
            OPTIONAL {{ <{uri}> rdf:type ?race }}
            FILTER(LANG(?name) = "en" || LANG(?name) = "")
        }}
        LIMIT 1
        """
        
        try:
            response = requests.post(
                FUSEKI_SPARQL,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                if results['results']['bindings']:
                    result = results['results']['bindings'][0]
                    
                    # Extract data
                    name = result.get('name', {}).get('value', uri.split('/')[-1].replace('_', ' '))
                    image_url = result.get('image', {}).get('value', '')
                    description = result.get('description', {}).get('value', '')
                    
                    # Transform wiki File: URLs to actual image URLs
                    if image_url:
                        image_url = wiki_file_to_image_url(image_url)
                    
                    # Build metadata dictionary
                    meta = {}
                    
                    # Extract race from rdf:type
                    if 'race' in result:
                        race_uri = result['race']['value']
                        race_name = race_uri.split('/')[-1].replace('_', ' ')
                        meta['Race'] = race_name
                    
                    # Add birth date if available
                    if 'birthDate' in result:
                        meta['Born'] = result['birthDate']['value']
                    
                    # Add spouse if available
                    if 'spouse' in result:
                        spouse_uri = result['spouse']['value']
                        spouse_name = spouse_uri.split('/')[-1].replace('_', ' ')
                        meta['Spouse'] = spouse_name
                    
                    # Truncate description to 200 characters
                    if description:
                        description = description[:200] + '...' if len(description) > 200 else description
                    else:
                        description = f"One of the most renowned figures in Middle-earth's history."
                    
                    featured.append({
                        'name': name,
                        'uri': uri.replace('http://localhost:5000', ''),  # Make relative
                        'image': image_url,
                        'description': description,
                        'meta': meta
                    })
        
        except Exception as e:
            print(f"Error fetching character {uri}: {e}")
            continue
    
    return featured

@app.route("/api/stats")
def api_stats():
    """API endpoint to get statistics as JSON"""
    stats = get_kg_statistics()
    return jsonify(stats)

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def home():
    """Home page with dashboard - loads fast with placeholder stats"""
    
    # Get featured characters (usually fast)
    try:
        featured_characters = get_featured_characters()
    except Exception as e:
        print(f"Warning: Could not fetch featured characters: {e}")
        featured_characters = []
    
    # Quick placeholder stats - will be loaded via AJAX
    stats = {
        'total_triples': None,  # Will show "Loading..."
        'unique_entities': None,
        'languages': [],
        'external_links': None
    }
    
    return render_template('home.html', 
                         featured_characters=featured_characters,
                         stats=stats)

@app.route("/search")
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return render_template('search.html', query=query, results=[])
    
    sparql_query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?entity ?label WHERE {{
        ?entity rdfs:label ?label .
        FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{query}")))
        FILTER(LANG(?label) = "en" || LANG(?label) = "")
    }} LIMIT 50
    """
    
    try:
        resp = requests.post(FUSEKI_SPARQL, data={"query": sparql_query}, timeout=10)
        bindings = resp.json()['results']['bindings']
        results = [{'entity': b['entity']['value'], 'label': b['label']['value']} for b in bindings]
    except:
        results = []
    
    return render_template('search.html', query=query, results=results)

# Add the custom filter
@app.template_filter('urldecode')
def urldecode_filter(s):
    return unquote(s)

@app.route("/resource/<path:entity>")
def resource_uri(entity):
    """
    Resource URI - represents the actual entity (non-information resource).
    Implements proper content negotiation:
    - HTML requests → 303 redirect to /page/
    - RDF requests → serve RDF directly
    """
    accept = request.headers.get('Accept', '')
    
    # Check what format is requested
    wants_rdf = (
        'text/turtle' in accept or 
        'application/rdf+xml' in accept or
        'application/n-triples' in accept or
        'application/ld+json' in accept
    )
    
    if wants_rdf or request.args.get('format') == 'turtle':
        # Serve RDF directly for RDF requests
        return serve_rdf(entity)
    else:
        # 303 redirect to page URI for HTML/browser requests
        return redirect(f"/page/{entity}", code=303)


@app.route("/page/<path:entity>")
def page_uri(entity):
    """
    Page URI - represents the HTML document about the entity.
    Always serves HTML.
    """
    return serve_html(entity)
@app.template_filter('urldecode')
def urldecode_filter(s):
    return unquote(s)
@app.route("/sparql", methods=['GET', 'POST'])
def sparql_interface():
    """SPARQL query interface"""
    query = request.form.get('query', '') or request.args.get('query', '')
    results = None
    error = None
    execution_time = 0
    
    if query:
        try:
            import time
            start_time = time.time()
            
            resp = requests.post(
                FUSEKI_SPARQL,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=30
            )
            
            execution_time = round((time.time() - start_time) * 1000, 2)
            
            if resp.status_code == 200:
                results = resp.json()
            else:
                error = f"Query failed with status {resp.status_code}: {resp.text}"
        except Exception as e:
            error = str(e)
    
    # Example queries
    examples = [
        {
            "name": "Find All Persons",
            "query": """PREFIX schema: <http://schema.org/>
SELECT ?person ?name WHERE {
  ?person a schema:Person ;
          schema:name ?name .
} LIMIT 20"""
        },
        {
            "name": "Family Relationships",
            "query": """PREFIX schema: <http://schema.org/>
SELECT ?person ?name ?parent ?parentName WHERE {
  ?person schema:name ?name ;
          schema:parent ?parent .
  ?parent schema:name ?parentName .
} LIMIT 20"""
        },
        {
            "name": "Places in Middle-earth",
            "query": """PREFIX schema: <http://schema.org/>
SELECT ?place ?name ?container WHERE {
  ?place a schema:Place ;
         schema:name ?name ;
         schema:containedInPlace ?container .
} LIMIT 20"""
        },
        {
            "name": "External Alignments",
            "query": """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX schema: <http://schema.org/>
SELECT ?entity ?name ?external WHERE {
  ?entity a schema:Person ;
          schema:name ?name ;
          owl:sameAs ?external .
} LIMIT 20"""
        },
        {
            "name": "Count Entities by Type",
            "query": """PREFIX schema: <http://schema.org/>
SELECT ?type (COUNT(?entity) as ?count) WHERE {
  ?entity a ?type .
} GROUP BY ?type ORDER BY DESC(?count)"""
        }
    ]
    
    return render_template('sparql.html', 
                         query=query, 
                         results=results, 
                         error=error,
                         execution_time=execution_time,
                         examples=examples)


def serve_rdf(entity):
    """Serve RDF representation (Turtle)"""
    base_uri = request.host_url.rstrip('/')
    
    # Flask decodes the URL, but Fuseki has encoded URIs
    # So we need to re-encode to match what's in the database
    subject_iri = f"{base_uri}/resource/{quote(entity)}"
    
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <http://schema.org/>
    
    CONSTRUCT {{
        <{subject_iri}> ?p ?o .
    }}
    WHERE {{
        <{subject_iri}> ?p ?o .
    }}
    """
    
    try:
        resp = requests.post(
            FUSEKI_QUERY,
            data={"query": query},
            headers={"Accept": "text/turtle"},
            timeout=30
        )
        
        if resp.status_code == 200:
            return Response(resp.content, mimetype='text/turtle')
        else:
            return f"Error querying triplestore: {resp.status_code}", 500
            
    except Exception as e:
        return f"Error: {str(e)}", 500
    
def serve_html(entity):
    """Serve HTML representation"""
    base_uri = request.host_url.rstrip('/')
    
    # Flask decodes the URL, but Fuseki has encoded URIs
    subject_iri = f"{base_uri}/resource/{quote(entity)}"
    
    # Extract entity data
    entity_data = extract_entity_data(subject_iri)
    
    if not entity_data:
        return f"Entity not found: {entity}", 404
    
    # Render template
    return render_template(
        'entity.html',
        title=entity_data['title'],
        subject_iri=subject_iri,
        entity_types=entity_data['types'],
        labels=entity_data['labels'],
        core_facts=entity_data['core_facts'],
        description=entity_data['description'],
        image_url=entity_data['image_url'],
        literal_props=entity_data['literal_props'],
        uri_props=entity_data['uri_props']
    )
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)