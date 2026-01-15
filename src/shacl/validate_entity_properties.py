"""
SHACL validation for the Tolkien Gateway Knowledge Graph
Generates statistical summary of violations
"""

from rdflib import Graph, Namespace
from pyshacl import validate
from pathlib import Path
from collections import defaultdict

DATA_FILE = "data/tolkien_complete.ttl"
SHAPES_FILE = "data/shacl_validation.ttl"
REPORT_FILE = "shacl_report/shacl_report.txt"
STATS_FILE = "shacl_report/shacl_statistics.txt"

SH = Namespace("http://www.w3.org/ns/shacl#")
SCHEMA = Namespace("http://schema.org/")


def analyze_violations(report_graph):
    """
    Analyze validation report and generate statistics
    """
    stats = defaultdict(lambda: {
        'count': 0,
        'entities': set(),
        'constraint': '',
        'message': ''
    })
    
    # Query all validation results
    query = """
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    
    SELECT ?focusNode ?path ?message ?constraint
    WHERE {
        ?result a sh:ValidationResult ;
                sh:focusNode ?focusNode .
        OPTIONAL { ?result sh:resultPath ?path }
        OPTIONAL { ?result sh:resultMessage ?message }
        OPTIONAL { ?result sh:sourceConstraintComponent ?constraint }
    }
    """
    
    results = report_graph.query(query)
    
    for row in results:
        # Extract property name
        if row.path:
            prop = str(row.path).split('/')[-1].split('#')[-1]
        else:
            prop = "unknown_property"
        
        # Extract constraint type
        if row.constraint:
            constraint = str(row.constraint).split('#')[-1].replace('ConstraintComponent', '')
        else:
            constraint = "unknown_constraint"
        
        # Extract entity name
        entity = str(row.focusNode).split('/')[-1]
        
        # Create key for grouping
        key = f"{prop} ({constraint})"
        
        # Store statistics
        stats[key]['count'] += 1
        stats[key]['entities'].add(entity)
        stats[key]['constraint'] = constraint
        if row.message:
            stats[key]['message'] = str(row.message)
    
    return stats


def generate_statistics_report(stats, conforms, total_triples):
    """
    Generate human-readable statistics report
    """
    report = []
    report.append("=" * 90)
    report.append("SHACL VALIDATION STATISTICS")
    report.append("=" * 90)
    report.append(f"\nValidation Status: {' CONFORMS' if conforms else '✗ VIOLATIONS FOUND'}")
    report.append(f"Total Triples: {total_triples:,}")
    report.append(f"\nTotal Violation Types: {len(stats)}")
    
    if stats:
        total_violations = sum(s['count'] for s in stats.values())
        total_entities = len(set().union(*[s['entities'] for s in stats.values()]))
        report.append(f"Total Violations: {total_violations:,}")
        report.append(f"Total Affected Entities: {total_entities:,}\n")
    else:
        report.append("Total Violations: 0\n")
    
    if not stats:
        report.append("\n No violations found - all data conforms to SHACL shapes!\n")
        report.append("=" * 90)
        return "\n".join(report)
    

    report.append("VIOLATIONS BY PROPERTY")
    report.append("=" * 90)
    
    # Sort by violation count (descending)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)
    
    for prop, data in sorted_stats:
        report.append(f"\n {prop}")
        report.append(f"  • Total Violations: {data['count']:,}")
        report.append(f"  • Affected Entities: {len(data['entities']):,}")
        
        if data['message']:
            # Extract first line of message
            msg = data['message'].split('\n')[0][:100]
            report.append(f"  • Issue: {msg}")
        
        # Show sample entities (first 10)
        sample = sorted(list(data['entities']))[:10]
        report.append(f"  • Sample Entities:")
        for i, entity in enumerate(sample, 1):
            report.append(f"      {i}. {entity}")
        
        if len(data['entities']) > 10:
            report.append(f"      ... and {len(data['entities']) - 10:,} more entities")
    
    # Add summary at the end
    report.append("SUMMARY - TOP ISSUES")
    
    for i, (prop, data) in enumerate(sorted_stats[:10], 1):
        percentage = (data['count'] / total_violations * 100) if total_violations > 0 else 0
        report.append(f"{i:2d}. {prop:<50} {data['count']:>8,} violations ({percentage:>5.1f}%)")
    
    report.append("\n" + "=" * 90)
    
    return "\n".join(report)


def main():
    print("=" * 70)
    print("SHACL VALIDATION WITH STATISTICS")
    print("=" * 70)
    
    print("\n[1/5] Loading RDF data graph...")
    data_graph = Graph()
    data_graph.parse(DATA_FILE, format="turtle")
    total_triples = len(data_graph)
    print(f"       Data graph loaded: {total_triples:,} triples")

    print("\n[2/5] Loading SHACL shapes graph...")
    shapes_graph = Graph()
    shapes_graph.parse(SHAPES_FILE, format="turtle")
    print(f"       Shapes graph loaded: {len(shapes_graph)} triples")

    print("\n[3/5] Running SHACL validation (this may take a few minutes)...")
    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True
    )
    print(f"       Validation complete")

    # Ensure report directory exists
    Path(REPORT_FILE).parent.mkdir(parents=True, exist_ok=True)

    print("\n[4/5] Analyzing violations and generating statistics...")
    stats = analyze_violations(report_graph)
    stats_report = generate_statistics_report(stats, conforms, total_triples)
    
    # Write statistics file
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        f.write(stats_report)
    print(f"       Statistics written to: {STATS_FILE}")

    # Write full report file
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"       Full report written to: {REPORT_FILE}")

    print("\n[5/5] Results:")
    print(f"Conforms: {conforms}")
    
    if stats:
        print(f"\nTotal Violations: {sum(s['count'] for s in stats.values()):,}")
        print(f"Violation Types: {len(stats)}")
        print(f"Affected Entities: {len(set().union(*[s['entities'] for s in stats.values()])):,}")
        
        # Show top 3 issues
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)
        print(f"\nTop 3 Issues:")
        for i, (prop, data) in enumerate(sorted_stats[:3], 1):
            print(f"  {i}. {prop}: {data['count']:,} violations")
        
        print(f"\n See {STATS_FILE} for detailed statistics")
    else:
        print("\n No violations found!")
    
    


if __name__ == "__main__":
    main()