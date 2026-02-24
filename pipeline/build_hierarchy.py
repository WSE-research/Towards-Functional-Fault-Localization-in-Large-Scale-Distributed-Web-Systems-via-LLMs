from SPARQLWrapper import SPARQLWrapper, JSON, TURTLE
import xml.etree.ElementTree as ET
import json
import argparse

# --- Konfiguration ---
SPARQL_ENDPOINT = "http://localhost:8890/sparql"  # anpassen
# default graph (keeps previous behaviour when no CLI arg is given)
DEFAULT_GRAPH = "urn:graph:07399ab8-e64f-463f-bff6-692c8473e19c"

# CLI: optional positional argument for graph URI
parser = argparse.ArgumentParser(description="Build method hierarchy from a SPARQL graph")
parser.add_argument('graph', nargs='?', default=DEFAULT_GRAPH,
                    help='Graph URI to query (default: %(default)s)')
parser.add_argument('--format', choices=['xml', 'ttl', 'json'], default='xml',
                    help='Output format: xml, ttl, or json (default: xml)')
parser.add_argument('--output', '-o', 
                    help='Output filename (default: methods_hierarchy.xml or methods_hierarchy.ttl)')
args = parser.parse_args()
GRAPH_URI = args.graph

sparql = SPARQLWrapper(SPARQL_ENDPOINT)
sparql.setReturnFormat(JSON)

# --- SPARQL: Traversal der RDF-List für args, single result ---
sparql.setQuery(f"""
PREFIX ex: <http://example.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?method ?name ?callee ?argType ?argValue ?resType ?resValue
FROM <{GRAPH_URI}>
WHERE {{
    ?method ex:method ?name ;
            ex:callee ?callee .

    OPTIONAL {{
        ?method ex:args ?argList .
        ?argList rdf:rest*/rdf:first ?argNode .
        ?argNode rdf:type ?argType ;
                 rdf:value ?argValue .
    }}

    OPTIONAL {{
        ?method ex:result ?resNode .
        ?resNode rdf:type ?resType ;
                 rdf:value ?resValue .
    }}
}}
""")

results = sparql.query().convert()

# --- Methoden-Dict aufbauen (aggregiert args und single result) ---
methods = {}
for row in results["results"]["bindings"]:
    method_id = row["method"]["value"]
    # Name und callee könnten in manchen DBs fehlen – defensiv behandeln
    name = row["name"]["value"] if "name" in row else ""
    callee = row["callee"]["value"] if "callee" in row else method_id

    if method_id not in methods:
        methods[method_id] = {
            "id": method_id,
            "name": name,
            "callee": callee,
            "args": [],        # list of {"type":..., "value":...}
            "result": None,    # single {"type":..., "value":...} or None
            "children": []     # list of method ids called by this method
        }
    else:
        # Falls Name/Callee in späteren Zeilen nicht gesetzt waren, aktualisieren
        if not methods[method_id]["name"] and name:
            methods[method_id]["name"] = name
        if not methods[method_id]["callee"] and callee:
            methods[method_id]["callee"] = callee

    # args (können mehrere Zeilen erzeugen)
    if "argType" in row and "argValue" in row:
        methods[method_id]["args"].append({
            "type": row["argType"]["value"],
            "value": row["argValue"]["value"]
        })

    # result (falls mehrfach wegen SPARQL-Duplikaten auftaucht, überschreiben wir nicht - behalten erstes)
    if methods[method_id]["result"] is None and "resType" in row and "resValue" in row:
        methods[method_id]["result"] = {
            "type": row["resType"]["value"],
            "value": row["resValue"]["value"]
        }

# --- Kinder (aufgerufene Methoden) zuweisen ---
for m in methods.values():
    if m["id"] != m["callee"]:  # selbstaufruf ignorieren bei Zuordnung
        if m["callee"] in methods:
            methods[m["callee"]]["children"].append(m["id"])

# --- Root finden (callee == id) ---
root = next((m for m in methods.values() if m["id"] == m["callee"]), None)
if root is None:
    raise ValueError("Kein Root gefunden (keine Methode mit ex:callee == id)")

# --- XML Builder mit Zyklus-Schutz ---
def build_xml_node(method_id, visited=None):
    if visited is None:
        visited = set()
    if method_id in visited:
        # Zyklus erkannt: um Endlosschleife zu vermeiden, referenzieren wir kurz und beenden
        ref = ET.Element("methodRef", attrib={"id": method_id})
        return ref

    visited.add(method_id)
    m = methods[method_id]
    elem = ET.Element("method", attrib={"id": m["id"]})
    if m["name"]:
        elem.set("name", m["name"])

    # args einbetten
    if m["args"]:
        args_elem = ET.SubElement(elem, "args")
        for arg in m["args"]:
            arg_elem = ET.SubElement(args_elem, "arg", attrib={"type": arg["type"]})
            arg_elem.text = arg["value"]

    # result (einzelnes Element, falls vorhanden)
    if m["result"]:
        res = m["result"]
        res_elem = ET.SubElement(elem, "result", attrib={"type": res["type"]})
        res_elem.text = res["value"]

    # methods (aufgerufene Methoden)
    methods_elem = ET.SubElement(elem, "called")
    for child_id in m["children"]:
        child_node = build_xml_node(child_id, visited.copy())  # copy visited für getrennte Pfade
        methods_elem.append(child_node)

    return elem

# Function to pretty-print XML (optional)
def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
    return elem

# Function that returns the XML content instead of writing to file (optional), s.t. I can call the method from elsewhere with the graph and get the XML string
def get_hierarchy_xml_string(graph_uri: str) -> str:
    sparql.setQuery(f"""
    PREFIX ex: <http://example.org/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?method ?name ?callee ?argType ?argValue ?resType ?resValue
    FROM <{graph_uri}>
    WHERE {{
        ?method ex:method ?name ;
                ex:callee ?callee .

        OPTIONAL {{
            ?method ex:args ?argList .
            ?argList rdf:rest*/rdf:first ?argNode .
            ?argNode rdf:type ?argType ;
                     rdf:value ?argValue .
        }}

        OPTIONAL {{
            ?method ex:result ?resNode .
            ?resNode rdf:type ?resType ;
                     rdf:value ?resValue .
        }}
    }}
    """)

    results = sparql.query().convert()

    # --- Methoden-Dict aufbauen (aggregiert args und single result) ---
    methods = {}
    for row in results["results"]["bindings"]:
        method_id = row["method"]["value"]
        # Name und callee könnten in manchen DBs fehlen – defensiv behandeln
        name = row["name"]["value"] if "name" in row else ""
        callee = row["callee"]["value"] if "callee" in row else method_id

        if method_id not in methods:
            methods[method_id] = {
                "id": method_id,
                "name": name,
                "callee": callee,
                "args": [],        # list of {"type":..., "value":...}
                "result": None,    # single {"type":..., "value":...} or None
                "children": []     # list of method ids called by this method
            }
        else:
            # Falls Name/Callee in späteren Zeilen nicht gesetzt waren, aktualisieren
            if not methods[method_id]["name"] and name:
                methods[method_id]["name"] = name
            if not methods[method_id]["callee"] and callee:
                methods[method_id]["callee"] = callee

        # args (können mehrere Zeilen erzeugen)
        if "argType" in row and "argValue" in row:
            methods[method_id]["args"].append({
                "type": row["argType"]["value"],
                "value": row["argValue"]["value"]
            })
        # result (falls mehrfach wegen SPARQL-Duplikaten auftaucht, überschreiben wir nicht - behalten erstes)
        if methods[method_id]["result"] is None and "resType" in row and "resValue" in row:
            methods[method_id]["result"] = {
                "type": row["resType"]["value"],
                "value": row["resValue"]["value"]
            }
    # --- Kinder (aufgerufene Methoden) zuweisen ---
    for m in methods.values():
        if m["id"] != m["callee"]:  # selbstaufruf ignorieren bei Zuordnung
            if m["callee"] in methods:
                methods[m["callee"]]["children"].append(m["id"])
    # --- Root finden (callee == id) ---
    root = next((m for m in methods.values() if m["id"] == m["callee"]), None)
    if root is None:
        raise ValueError("Kein Root gefunden (keine Methode mit ex:callee == id)")
    # --- XML Builder mit Zyklus-Schutz ---
    def build_xml_node(method_id, visited=None):
        if visited is None:
            visited = set()
        if method_id in visited:
            # Zyklus erkannt: um Endlosschleife zu vermeiden, referenzieren wir kurz und beenden
            ref = ET.Element("methodRef", attrib={"id": method_id})
            return ref

        visited.add(method_id)
        m = methods[method_id]
        elem = ET.Element("method", attrib={"id": m["id"]})
        if m["name"]:
            elem.set("name", m["name"])

        # args einbetten
        if m["args"]:
            args_elem = ET.SubElement(elem, "args")
            for arg in m["args"]:
                arg_elem = ET.SubElement(args_elem, "arg", attrib={"type": arg["type"]})
                arg_elem.text = arg["value"]

        # result (einzelnes Element, falls vorhanden)
        if m["result"]:
            res = m["result"]
            res_elem = ET.SubElement(elem, "result", attrib={"type": res["type"]})
            res_elem.text = res["value"]

        # methods (aufgerufene Methoden)
        methods_elem = ET.SubElement(elem, "methods")
        for child_id in m["children"]:
            child_node = build_xml_node(child_id, visited.copy())  # copy visited für getrennte Pfade
            methods_elem.append(child_node)

        return elem
    # --- XML-Dokument erstellen und als String zurückgeben ---
    root_elem = build_xml_node(root["id"])
    indent(root_elem)  # optional: schön formatieren
    xml_string = ET.tostring(root_elem, encoding="utf-8", method="xml").decode("utf-8")
    return xml_string


# Function to create TTL (Turtle) representation of the hierarchy
def get_hierarchy_ttl_string(graph_uri: str) -> str:
    """Generate Turtle/TTL representation of the method hierarchy from a SPARQL graph."""
    sparql.setReturnFormat("n3")
    query = f"""
    PREFIX ex: <http://example.org/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?method ?name ?callee ?argType ?argValue ?resType ?resValue
    FROM <{graph_uri}>
    WHERE {{
        ?method ex:method ?name ;
                ex:callee ?callee .

        OPTIONAL {{
            ?method ex:args ?argList .
            ?argList rdf:rest*/rdf:first ?argNode .
            ?argNode rdf:type ?argType ;
                     rdf:value ?argValue .
        }}

        OPTIONAL {{
            ?method ex:result ?resNode .
            ?resNode rdf:type ?resType ;
                     rdf:value ?resValue .
        }}
    }}
    """
    sparql.setQuery(query)
    print(query)

    return str(sparql.queryAndConvert())


# Function to create JSON representation of the hierarchy
def get_hierarchy_json_string(graph_uri: str) -> str:
    """Generate JSON representation of the method hierarchy from a SPARQL graph."""
    sparql.setReturnFormat(JSON)
    sparql.setQuery(f"""
    PREFIX ex: <http://example.org/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?method ?name ?callee ?argType ?argValue ?resType ?resValue
    FROM <{graph_uri}>
    WHERE {{
        ?method ex:method ?name ;
                ex:callee ?callee .

        OPTIONAL {{
            ?method ex:args ?argList .
            ?argList rdf:rest*/rdf:first ?argNode .
            ?argNode rdf:type ?argType ;
                     rdf:value ?argValue .
        }}

        OPTIONAL {{
            ?method ex:result ?resNode .
            ?resNode rdf:type ?resType ;
                     rdf:value ?resValue .
        }}
    }}
    """)

    results = sparql.query().convert()

    # --- Methoden-Dict aufbauen ---
    methods = {}
    for row in results["results"]["bindings"]:
        method_id = row["method"]["value"]
        name = row["name"]["value"] if "name" in row else ""
        callee = row["callee"]["value"] if "callee" in row else method_id

        if method_id not in methods:
            methods[method_id] = {
                "id": method_id,
                "name": name,
                "callee": callee,
                "args": [],
                "result": None,
                "children": []
            }
        else:
            if not methods[method_id]["name"] and name:
                methods[method_id]["name"] = name
            if not methods[method_id]["callee"] and callee:
                methods[method_id]["callee"] = callee

        # args
        if "argType" in row and "argValue" in row:
            methods[method_id]["args"].append({
                "type": row["argType"]["value"],
                "value": row["argValue"]["value"]
            })
        # result
        if methods[method_id]["result"] is None and "resType" in row and "resValue" in row:
            methods[method_id]["result"] = {
                "type": row["resType"]["value"],
                "value": row["resValue"]["value"]
            }

    # --- Kinder zuweisen ---
    for m in methods.values():
        if m["id"] != m["callee"]:
            if m["callee"] in methods:
                methods[m["callee"]]["children"].append(m["id"])

    # --- Root finden ---
    root = next((m for m in methods.values() if m["id"] == m["callee"]), None)
    if root is None:
        raise ValueError("Kein Root gefunden (keine Methode mit ex:callee == id)")

    # --- JSON Builder mit Zyklus-Schutz ---
    def build_json_node(method_id, visited=None):
        """Recursively build JSON structure with cycle protection."""
        if visited is None:
            visited = set()

        if method_id in visited:
            # Zyklus erkannt - nur Referenz zurückgeben
            return {"id": method_id, "ref": True}

        visited.add(method_id)
        m = methods[method_id]

        node = {
            "id": m["id"],
            "name": m["name"],
            "callee": m["callee"]
        }

        # Add args if present
        if m["args"]:
            node["args"] = [
                {"type": arg["type"], "value": arg["value"]}
                for arg in m["args"]
            ]

        # Add result if present
        if m["result"]:
            node["result"] = {
                "type": m["result"]["type"],
                "value": m["result"]["value"]
            }

        # Add methods (children calls)
        if m["children"]:
            node["methods"] = [
                build_json_node(child_id, visited.copy())
                for child_id in m["children"]
            ]

        return node

    # --- JSON-Dokument erstellen ---
    json_data = build_json_node(root["id"])
    return json.dumps(json_data, indent=2, ensure_ascii=False)

# --- Dokument erstellen und speichern, nur wenn als Script ausgeführt ---
if __name__ == "__main__":
    if args.format == 'ttl':
        # Generate TTL output
        ttl_content = get_hierarchy_ttl_string(GRAPH_URI)
        output_file = args.output or "methods_hierarchy.ttl"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(ttl_content)
        print(f"TTL hierarchy written to {output_file} (graph: {GRAPH_URI})")
    elif args.format == 'json':
        # Generate JSON output
        json_content = get_hierarchy_json_string(GRAPH_URI)
        output_file = args.output or "methods_hierarchy.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_content)
        print(f"JSON hierarchy written to {output_file} (graph: {GRAPH_URI})")
    else:
        # Generate XML output
        root_elem = build_xml_node(root["id"])
        tree = ET.ElementTree(root_elem)
        output_file = args.output or "methods_hierarchy.xml"
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        print(f"XML hierarchy written to {output_file} (graph: {GRAPH_URI})")