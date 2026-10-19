from typing import Dict, List, Tuple, Optional

LOCATIONS: Dict[str, str] = {
    "A": "Центр",
    "B": "Університет",
    "C": "Лікарня",
    "D": "Парк",
    "E": "Вокзал",
    "F": "Торговий центр",
    "G": "Аеропорт"
}


class Edge:
    def __init__(
        self,
        target: str,
        distance: float,
        time: float,
        traffic: float = 1.0,
        difficulty: int = 1,
        description: str = ""
    ):
        self.target = target
        self.distance = distance
        self.time = time
        self.traffic = traffic
        self.difficulty = difficulty
        self.description = description

    def __repr__(self) -> str:
        return (f"Edge(to={self.target}, dist={self.distance}km, "
                f"time={self.time}m, traffic={self.traffic}, diff={self.difficulty})")


class CityGraph:
    def __init__(self):
        self.adjacency: Dict[str, List[Edge]] = {node: [] for node in LOCATIONS}
        self._build_default_city_map()

    def add_edge(
        self,
        u: str,
        v: str,
        distance: float,
        time: float,
        traffic: float = 1.0,
        difficulty: int = 1,
        description: str = "",
        bidirectional: bool = True
    ):
        if u not in self.adjacency:
            self.adjacency[u] = []
        if v not in self.adjacency:
            self.adjacency[v] = []

        self.adjacency[u].append(Edge(v, distance, time, traffic, difficulty, description))
        if bidirectional:
            self.adjacency[v].append(Edge(u, distance, time, traffic, difficulty, description))

    def get_neighbors(self, node: str) -> List[Edge]:
        return self.adjacency.get(node, [])

    def get_edge(self, u: str, v: str) -> Optional[Edge]:
        for edge in self.adjacency.get(u, []):
            if edge.target == v:
                return edge
        return None

    def _build_default_city_map(self):
        self.add_edge("A", "B", distance=4.0, time=7.0, traffic=1.3, difficulty=2, description="Проспект Свободи")
        self.add_edge("A", "D", distance=5.0, time=8.0, traffic=1.1, difficulty=1, description="Паркова алея")
        self.add_edge("A", "C", distance=6.0, time=10.0, traffic=1.2, difficulty=2, description="Вулиця Медична")
        self.add_edge("B", "C", distance=3.0, time=5.0, traffic=1.1, difficulty=1, description="Студентська вулиця")
        self.add_edge("B", "E", distance=6.0, time=9.0, traffic=1.5, difficulty=2, description="Привокзальна магістраль")
        self.add_edge("B", "D", distance=4.0, time=6.0, traffic=1.0, difficulty=1, description="Зелений бульвар")
        self.add_edge("C", "E", distance=5.0, time=8.0, traffic=1.2, difficulty=2, description="Шпитальний узвіз")
        self.add_edge("C", "G", distance=14.0, time=20.0, traffic=1.5, difficulty=3, description="Старе шосе")
        self.add_edge("D", "F", distance=7.0, time=10.0, traffic=1.1, difficulty=1, description="Кільцева дорога (Захід)")
        self.add_edge("E", "F", distance=4.0, time=6.0, traffic=1.3, difficulty=2, description="Торгова вулиця")
        self.add_edge("E", "G", distance=8.0, time=11.0, traffic=1.6, difficulty=2, description="Аеропортове шосе")
        self.add_edge("F", "G", distance=8.0, time=11.0, traffic=1.1, difficulty=1, description="Новий автобан")


def get_location_name(code: str) -> str:
    return LOCATIONS.get(code.upper(), code)


def format_route(route_nodes: List[str]) -> str:
    return " → ".join(route_nodes)
