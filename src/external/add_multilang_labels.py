import requests
import time
import csv

def get_language_links(entity_name):
    """
    Query lotr.fandom.com API to get ALL language links for an entity.
    Returns dict: {lang_code: page_title}
    """
    url = "https://lotr.fandom.com/api.php"
    params = {
        'action': 'query',
        'titles': entity_name,
        'prop': 'langlinks',
        'lllimit': 'max',  # Get all available languages
        'format': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        pages = data.get('query', {}).get('pages', {})
        
        lang_links = {}
        for page_id, page_data in pages.items():
            if 'langlinks' in page_data:
                for link in page_data['langlinks']:
                    lang = link['lang']
                    title = link['*']
                    lang_links[lang] = title
        
        return lang_links
    
    except Exception as e:
        print(f"Error fetching {entity_name}: {e}")
        return {}

def generate_multilang_ttl(entities_csv, output_file):
    """
    Read entities from CSV and generate TTL with multi-language labels.
    """
    with open(entities_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        entities = list(reader)
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n")
        
        total_enriched = 0
        total_labels = 0
        all_languages = set()
        
        for i, row in enumerate(entities):
            resource_uri = row['resource']
            en_label = row['label']
            
            print(f"[{i+1}/{len(entities)}] {en_label}", end="")
            
            # Get ALL language links from lotr.fandom.com
            lang_links = get_language_links(en_label)
            
            if lang_links:
                out.write(f"<{resource_uri}>\n")
                
                items = list(lang_links.items())
                for j, (lang, title) in enumerate(items):
                    # Escape quotes in title
                    title_clean = title.replace('\\', '\\\\').replace('"', '\\"')
                    
                    if j == len(items) - 1:  # Last item
                        out.write(f'    rdfs:label "{title_clean}"@{lang} .\n\n')
                    else:
                        out.write(f'    rdfs:label "{title_clean}"@{lang} ;\n')
                
                total_enriched += 1
                total_labels += len(lang_links)
                all_languages.update(lang_links.keys())
                print(f" → {len(lang_links)} languages: {', '.join(sorted(lang_links.keys()))}")
            else:
                print(" → no links")
            
            # Be polite to API
            time.sleep(0.5)
    

    print(f" Enriched: {total_enriched}/{len(entities)} entities")
    print(f" Total labels added: {total_labels}")
    print(f" Languages found: {len(all_languages)}")
    print(f" Languages: {', '.join(sorted(all_languages))}")
    print(f" Generated: {output_file}")


if __name__ == "__main__":
    generate_multilang_ttl('src/queryResults.csv', 'data/kg/multilang_labels.ttl')