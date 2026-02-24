import argparse
import math
import os
import re

from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import floyd_warshall
from SPARQLWrapper import SPARQLWrapper, JSON


SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://localhost:8890/sparql")

QUERY_TEMPLATE = """
PREFIX ex: <http://example.org/>

SELECT DISTINCT ?u ?v (1 AS ?w)
FROM <{graph}>
WHERE {{
  # v calls u (ex:callee points to the caller)
  ?v_id ex:callee ?u_id .
  ?v_id ex:method ?v .   # name of the calling method
  ?u_id ex:method ?u .   # name of the called method
  FILTER (?u != ?v)
}}
"""


def query_kg(graph_uri: str):
    """Query the knowledge graph for the given named graph URI and return JSON results."""
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery(QUERY_TEMPLATE.format(graph=graph_uri))
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()


def build_graph(graph_uri: str):
    results = query_kg(graph_uri)["results"]["bindings"]

    nodes = set()
    edges = []

    # Build edge list from SPARQL results
    for row in results:
        u = row["u"]["value"]
        v = row["v"]["value"]
        w = float(row["w"]["value"])

        nodes.update([u, v])
        edges.append((u, v, w))

    # Map nodes to integer indices
    idx = {node: i for i, node in enumerate(nodes)}
    idx_rev = {i: node for node, i in idx.items()}

    # Build CSR sparse matrix (undirected: insert both directions)
    rows = []
    cols = []
    data = []

    seen = set()
    for u, v, w in edges:
        for a, b in ((u, v), (v, u)):
            key = (idx[a], idx[b])
            if key in seen:
                continue
            seen.add(key)
            rows.append(key[0])
            cols.append(key[1])
            data.append(w)

    n = len(idx)
    graph = csr_matrix((data, (rows, cols)), shape=(n, n))

    return graph, idx, idx_rev


def run_all_pairs(graph_uri: str):
    graph, idx, rev = build_graph(graph_uri)

    dist, pred = floyd_warshall(
        graph,
        directed=False,
        return_predecessors=True,
    )
    return dist, pred, idx, rev


def get_path(start_uri, end_uri, pred, idx, rev):
    """Reconstruct the shortest path between two nodes."""
    s = idx[start_uri]
    t = idx[end_uri]

    path = []
    cur = t

    while cur != -9999:
        path.append(rev[cur])
        if cur == s:
            break
        cur = pred[s, cur]

    return list(reversed(path))


def shortest_path(graph_uri: str, src: str, dst: str):
    """Compute shortest path between src and dst on the given graph.

    Parameters
    ----------
    graph_uri: str
        Named graph URI used in the SPARQL FROM clause.
    src: str
        Regex or substring pattern identifying the source node label.
    dst: str
        Regex or substring pattern identifying the destination node label.

    Returns
    -------
    distance: float
        Hop-distance between src and dst.
    path: list[str]
        Sequence of node labels from src to dst (inclusive).
    src_node: str
        The concrete source node that matched the src pattern.
    dst_node: str
        The concrete destination node that matched the dst pattern.
    """

    dist, pred, idx, rev = run_all_pairs(graph_uri)

    # Build regex that also matches optional inner classes like Foo$Bar.baz
    def _compile_with_innerclass_support(fragment: str):
        if "." not in fragment:
            return re.compile(fragment)
        class_part, method_part = fragment.rsplit(".", 1)
        class_regex = re.escape(class_part)
        method_regex = re.escape(method_part)
        pattern = f"{class_regex}(?:\\$[^.]*)?\\.{method_regex}"
        return re.compile(pattern)

    src_pattern = _compile_with_innerclass_support(src)
    dst_pattern = _compile_with_innerclass_support(dst)

    src_nodes = [n for n in idx if src_pattern.search(n)]
    dst_nodes = [n for n in idx if dst_pattern.search(n)]

    if not src_nodes or not dst_nodes:
        return math.inf, [], src, dst

    # Return the shortest distance across all matching node combinations
    best_result = None
    best_distance = math.inf

    for src_node in src_nodes:
        for dst_node in dst_nodes:
            distance = dist[idx[src_node], idx[dst_node]]
            if distance < best_distance:
                best_distance = distance
                path = get_path(src_node, dst_node, pred, idx, rev)
                best_result = (float(distance), path, src_node, dst_node)

    return best_result if best_result else (math.inf, [], src, dst)


def main():
    parser = argparse.ArgumentParser(
        description="Run Floyd-Warshall shortest-path on a KG-backed call graph."
    )
    parser.add_argument(
        "--graph",
        dest="graph_uri",
        required=True,
        help="Named graph URI to use in the SPARQL FROM clause.",
    )
    parser.add_argument(
        "--src",
        dest="src",
        required=True,
        help="Source method identifier (supports regex and inner-class patterns).",
    )
    parser.add_argument(
        "--dst",
        dest="dst",
        required=True,
        help="Destination method identifier (supports regex and inner-class patterns).",
    )

    args = parser.parse_args()

    distance, path, src_node, dst_node = shortest_path(
        args.graph_uri, args.src, args.dst
    )

    print("Source node:", src_node)
    print("Destination node:", dst_node)
    print("Hop distance:", distance)
    print("Path:", path)


if __name__ == "__main__":
    main()
