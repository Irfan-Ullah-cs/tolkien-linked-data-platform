import csv
import urllib.parse

def normalize_name(name):
    """Convert name to URI format (same as your existing URIs)"""
    return name.strip().replace(' ', '_')

def create_resource_uri(name):
    """Create resource URI matching your existing pattern"""
    encoded = urllib.parse.quote(normalize_name(name))
    return f"http://localhost:5000/resource/{encoded}"

def escape_literal(text):
    """Escape special characters in RDF literals"""
    if not text:
        return text
    # Escape backslashes first, then quotes, then newlines
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', ' ')
    text = text.replace('\r', '')
    return text.strip()

def generate_csv_enrichment(csv_file, output_file):
    """
    Read LOTR characters CSV and generate RDF triples.
    """
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        characters = list(reader)
    
    with open(output_file, 'w', encoding='utf-8') as out:
        # Write prefixes
        out.write("@prefix schema: <http://schema.org/> .\n")
        out.write("@prefix tolkien: <http://localhost:5000/vocab/> .\n")
        out.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n")
        
        stats = {
            'total': 0,
            'with_birth': 0,
            'with_death': 0,
            'with_gender': 0,
            'with_race': 0,
            'with_realm': 0,
            'with_spouse': 0,
            'with_hair': 0,
            'with_height': 0
        }
        
        for row in characters:
            name = row.get('name', '').strip()
            if not name:
                continue
            
            stats['total'] += 1
            resource_uri = create_resource_uri(name)
            
            triples = []
            
            # Birth date
            birth = row.get('birth', '').strip()
            if birth:
                birth_clean = escape_literal(birth)
                triples.append(f'    schema:birthDate "{birth_clean}"')
                stats['with_birth'] += 1
            
            # Death date
            death = row.get('death', '').strip()
            if death:
                death_clean = escape_literal(death)
                triples.append(f'    schema:deathDate "{death_clean}"')
                stats['with_death'] += 1
            
            # Gender
            gender = row.get('gender', '').strip()
            if gender:
                gender_clean = escape_literal(gender)
                triples.append(f'    schema:gender "{gender_clean}"')
                stats['with_gender'] += 1
            
            # Hair color
            hair = row.get('hair', '').strip()
            if hair:
                hair_clean = escape_literal(hair)
                triples.append(f'    tolkien:hairColor "{hair_clean}"')
                stats['with_hair'] += 1
            
            # Height
            height = row.get('height', '').strip()
            if height:
                height_clean = escape_literal(height)
                triples.append(f'    tolkien:height "{height_clean}"')
                stats['with_height'] += 1
            
            # Race
            race = row.get('race', '').strip()
            if race:
                race_clean = escape_literal(race)
                triples.append(f'    tolkien:race "{race_clean}"')
                stats['with_race'] += 1
            
            # Realm
            realm = row.get('realm', '').strip()
            if realm:
                realm_clean = escape_literal(realm)
                triples.append(f'    tolkien:realm "{realm_clean}"')
                stats['with_realm'] += 1
            
            # Spouse (create link to spouse entity)
            spouse = row.get('spouse', '').strip()
            if spouse and spouse.lower() not in ['none', 'unnamed wife', 'unnamed husband', '']:
                spouse_uri = create_resource_uri(spouse)
                triples.append(f'    schema:spouse <{spouse_uri}>')
                stats['with_spouse'] += 1
            
            # Write to file if we have any triples
            if triples:
                out.write(f"<{resource_uri}>\n")
                for i, triple in enumerate(triples):
                    if i == len(triples) - 1:  # Last triple
                        out.write(f"{triple} .\n\n")
                    else:
                        out.write(f"{triple} ;\n")
        
        # Print statistics
        print(f"LOTR CSV Integration Complete")
        print(f"Total characters processed: {stats['total']}")
        print(f"  - With birth date:  {stats['with_birth']}")
        print(f"  - With death date:  {stats['with_death']}")
        print(f"  - With gender:      {stats['with_gender']}")
        print(f"  - With race:        {stats['with_race']}")
        print(f"  - With realm:       {stats['with_realm']}")
        print(f"  - With spouse:      {stats['with_spouse']}")
        print(f"  - With hair:        {stats['with_hair']}")
        print(f"  - With height:      {stats['with_height']}")
        print(f"\n Generated: {output_file}")

if __name__ == "__main__":
    generate_csv_enrichment('data/external/lotr_characters.csv', 'data/kg/lotr_csv_enrichment.ttl')