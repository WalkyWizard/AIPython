import heapq
from typing import Dict, List, Tuple, Optional
from graph import CityGraph, Edge, LOCATIONS


class RouteResult:
    def __init__(
        self,
        nodes: List[str],
        total_distance: float,
        total_time: float,
        avg_traffic: float,
        edge_details: List[Tuple[str, str, Edge]]
    ):
        self.nodes = nodes
        self.total_distance = round(total_distance, 2)
        self.total_time = round(total_time, 2)
        self.avg_traffic = round(avg_traffic, 2)
        self.edge_details = edge_details

    @property
    def route_str(self) -> str:
        return ",".join(self.nodes)

    @property
    def display_str(self) -> str:
        return " → ".join(self.nodes)

    def __repr__(self) -> str:
        return f"<RouteResult {self.display_str}: {self.total_distance} km, {self.total_time} min>"


def dijkstra_shortest_path(
    graph: CityGraph,
    start: str,
    finish: str,
    weight_mode: str = "time"
) -> Optional[RouteResult]:
    start = start.upper().strip()
    finish = finish.upper().strip()

    if start not in LOCATIONS or finish not in LOCATIONS:
        return None

    if start == finish:
        return RouteResult([start], 0.0, 0.0, 1.0, [])

    costs: Dict[str, float] = {node: float("inf") for node in LOCATIONS}
    costs[start] = 0.0

    previous: Dict[str, Optional[Tuple[str, Edge]]] = {node: None for node in LOCATIONS}

    pq: List[Tuple[float, str]] = [(0.0, start)]
    visited = set()

    while pq:
        current_cost, current_node = heapq.heappop(pq)

        if current_node in visited:
            continue
        visited.add(current_node)

        if current_node == finish:
            break

        for edge in graph.get_neighbors(current_node):
            neighbor = edge.target
            if neighbor in visited:
                continue

            weight = edge.time if weight_mode == "time" else edge.distance
            new_cost = current_cost + weight

            if new_cost < costs[neighbor]:
                costs[neighbor] = new_cost
                previous[neighbor] = (current_node, edge)
                heapq.heappush(pq, (new_cost, neighbor))

    if costs[finish] == float("inf"):
        return None

    curr = finish
    path_nodes: List[str] = []
    edge_details: List[Tuple[str, str, Edge]] = []

    while curr is not None:
        path_nodes.append(curr)
        prev_data = previous[curr]
        if prev_data is not None:
            prev_node, edge_obj = prev_data
            edge_details.append((prev_node, curr, edge_obj))
            curr = prev_node
        else:
            curr = None

    path_nodes.reverse()
    edge_details.reverse()

    total_distance = sum(edge.distance for _, _, edge in edge_details)
    total_time = sum(edge.time for _, _, edge in edge_details)
    avg_traffic = (
        sum(edge.traffic for _, _, edge in edge_details) / len(edge_details)
        if edge_details else 1.0
    )

    return RouteResult(
        nodes=path_nodes,
        total_distance=total_distance,
        total_time=total_time,
        avg_traffic=avg_traffic,
        edge_details=edge_details
    )


def find_all_routes(
    graph: CityGraph,
    start: str,
    finish: str,
    max_depth: int = 6
) -> List[RouteResult]:
    start = start.upper().strip()
    finish = finish.upper().strip()

    if start not in LOCATIONS or finish not in LOCATIONS:
        return []

    results: List[RouteResult] = []

    def dfs(current: str, visited: List[str], current_edges: List[Tuple[str, str, Edge]]):
        if len(visited) > max_depth:
            return
        if current == finish:
            total_dist = sum(e.distance for _, _, e in current_edges)
            total_time = sum(e.time for _, _, e in current_edges)
            avg_traffic = sum(e.traffic for _, _, e in current_edges) / len(current_edges) if current_edges else 1.0
            results.append(RouteResult(
                nodes=list(visited),
                total_distance=total_dist,
                total_time=total_time,
                avg_traffic=avg_traffic,
                edge_details=list(current_edges)
            ))
            return

        for edge in graph.get_neighbors(current):
            nxt = edge.target
            if nxt not in visited:
                visited.append(nxt)
                current_edges.append((current, nxt, edge))
                dfs(nxt, visited, current_edges)
                current_edges.pop()
                visited.pop()

    dfs(start, [start], [])

    results.sort(key=lambda r: (r.total_time, r.total_distance))
    return results
