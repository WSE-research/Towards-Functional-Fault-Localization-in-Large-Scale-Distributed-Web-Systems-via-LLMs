#!/usr/bin/env python3
"""
Script to query metadata from a SPARQL graph.
Retrieves total method calls, distinct method calls, and distinct class calls.
"""

import argparse
import requests
from typing import Tuple, Optional


def query_graph_metadata(graph_name: str, endpoint: str = "http://localhost:8890/sparql") -> Optional[Tuple[int, int, int]]:
    """
    Query a SPARQL graph for method and class metadata.
    
    Args:
        graph_name: The name of the graph to query
        endpoint: The SPARQL endpoint URL
        
    Returns:
        Tuple of (total_methods, distinct_methods, distinct_classes) or None if query fails
    """
    
    query = f"""
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbr: <http://dbpedia.org/resource/>
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX ex: <http://example.org/>

SELECT 
  ?totalMethods 
  ?distinctMethods 
  ?distinctClasses
WHERE {{
  GRAPH <{graph_name}> {{
    
    {{
      SELECT (COUNT(?method) AS ?totalMethods)
      WHERE {{
        ?s ex:method ?method .
      }}
    }}
    {{
      SELECT (COUNT(DISTINCT ?method) AS ?distinctMethods)
      WHERE {{
        ?s ex:method ?method .
      }}
    }}
    {{
      SELECT (COUNT(DISTINCT ?class) AS ?distinctClasses)
      WHERE {{
        ?s ex:method ?method .
        BIND(REPLACE(?method, "\\\\(.*\\\\)$", "") AS ?clean)
        BIND(REPLACE(?clean, "\\\\.[^.]+$", "") AS ?class)
      }}
    }}
  }}
}}
"""
    
    try:
        response = requests.post(
            endpoint,
            data={'query': query},
            headers={'Accept': 'application/sparql-results+json'}
        )
        response.raise_for_status()
        
        results = response.json()
        
        if results.get('results', {}).get('bindings'):
            binding = results['results']['bindings'][0]
            total_methods = int(binding['totalMethods']['value'])
            distinct_methods = int(binding['distinctMethods']['value'])
            distinct_classes = int(binding['distinctClasses']['value'])
            
            return (total_methods, distinct_methods, distinct_classes)
        else:
            print("No results found in the query response")
            return None
            
    except requests.RequestException as e:
        print(f"Error querying SPARQL endpoint: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error parsing query results: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Query SPARQL graph for method and class metadata'
    )
    parser.add_argument(
        'graph',
        help='The graph name to query'
    )
    parser.add_argument(
        '--endpoint',
        default='http://localhost:8890/sparql',
        help='SPARQL endpoint URL (default: http://localhost:8890/sparql)'
    )
    
    args = parser.parse_args()
    
    result = query_graph_metadata(args.graph, args.endpoint)
    
    if result:
        total_methods, distinct_methods, distinct_classes = result
        print(f"Graph: {args.graph}")
        print(f"Total method calls: {total_methods}")
        print(f"Distinct method calls: {distinct_methods}")
        print(f"Distinct class calls: {distinct_classes}")
        return 0
    else:
        print("Failed to retrieve metadata")
        return 1


if __name__ == '__main__':
    exit(main())
