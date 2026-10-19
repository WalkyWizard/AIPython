import unittest
import os
import sqlite3

from graph import CityGraph, LOCATIONS, format_route
from dijkstra import dijkstra_shortest_path, find_all_routes
import database
from users import UserManager, UserProfile
from ai_module import AINavigatorAdvisor
from simulator import seed_scenario_data


class TestCityGraph(unittest.TestCase):
    def setUp(self):
        self.graph = CityGraph()

    def test_locations_exist(self):
        for code in ["A", "B", "C", "D", "E", "F", "G"]:
            self.assertIn(code, LOCATIONS)
            self.assertIn(code, self.graph.adjacency)

    def test_edge_parameters(self):
        edge = self.graph.get_edge("A", "B")
        self.assertIsNotNone(edge)
        self.assertAlmostEqual(edge.distance, 4.0)
        self.assertAlmostEqual(edge.time, 7.0)
        self.assertGreaterEqual(edge.traffic, 1.0)
        self.assertGreaterEqual(edge.difficulty, 1)


class TestDijkstraAlgorithm(unittest.TestCase):
    def setUp(self):
        self.graph = CityGraph()

    def test_dijkstra_a_to_g(self):
        res = dijkstra_shortest_path(self.graph, "A", "G", weight_mode="time")
        self.assertIsNotNone(res)
        self.assertEqual(res.nodes, ["A", "B", "E", "G"])
        self.assertEqual(res.total_distance, 18.0)
        self.assertEqual(res.total_time, 27.0)
        self.assertEqual(res.display_str, "A → B → E → G")
        self.assertEqual(res.route_str, "A,B,E,G")

    def test_dijkstra_same_node(self):
        res = dijkstra_shortest_path(self.graph, "A", "A")
        self.assertEqual(res.nodes, ["A"])
        self.assertEqual(res.total_distance, 0.0)
        self.assertEqual(res.total_time, 0.0)

    def test_find_all_routes(self):
        routes = find_all_routes(self.graph, "A", "G")
        self.assertGreater(len(routes), 2)
        route_strs = [r.route_str for r in routes]
        self.assertIn("A,B,E,G", route_strs)
        self.assertIn("A,D,F,G", route_strs)
        self.assertIn("A,B,C,G", route_strs)

        adfg = next(r for r in routes if r.route_str == "A,D,F,G")
        self.assertEqual(adfg.total_distance, 20.0)


class TestDatabaseAndHistory(unittest.TestCase):
    def setUp(self):
        database.DB_NAME = "test_navigator.db"
        database.init_db()
        database.clear_database()

    def tearDown(self):
        if os.path.exists("test_navigator.db"):
            try:
                os.remove("test_navigator.db")
            except Exception:
                pass

    def test_save_and_update_route(self):
        route_id = database.save_route(
            start_point="A",
            finish_point="G",
            route="A,B,E,G",
            distance=18.0,
            time=27.0,
            user_name="Ivan",
            user_type="driver"
        )
        self.assertGreater(route_id, 0)

        record = database.get_route_by_id(route_id)
        self.assertEqual(record["route"], "A,B,E,G")
        self.assertIsNone(record["actual_time"])

        updated = database.update_actual_trip(route_id, actual_time=31.0, actual_distance=18.2)
        self.assertTrue(updated)

        record_after = database.get_route_by_id(route_id)
        self.assertEqual(record_after["actual_time"], 31.0)
        self.assertEqual(record_after["actual_distance"], 18.2)

    def test_route_statistics_aggregation(self):
        for _ in range(3):
            database.save_route(
                "A", "G", "A,B,E,G", 18.0, 27.0,
                user_name="Ivan", user_type="driver",
                actual_time=31.0, actual_distance=18.0
            )
        for _ in range(2):
            database.save_route(
                "A", "G", "A,D,F,G", 20.0, 29.0,
                user_name="Ivan", user_type="driver",
                actual_time=27.0, actual_distance=20.0
            )

        stats = database.get_route_stats_for_pair("A", "G")
        self.assertEqual(len(stats), 2)

        abeg_stat = next(s for s in stats if s["route"] == "A,B,E,G")
        self.assertEqual(abeg_stat["total_count"], 3)
        self.assertEqual(abeg_stat["avg_actual_time"], 31.0)
        self.assertEqual(abeg_stat["avg_expected_time"], 27.0)
        self.assertEqual(abeg_stat["time_difference"], 4.0)

        adfg_stat = next(s for s in stats if s["route"] == "A,D,F,G")
        self.assertEqual(adfg_stat["total_count"], 2)
        self.assertEqual(adfg_stat["avg_actual_time"], 27.0)


class TestAIModule(unittest.TestCase):
    def setUp(self):
        database.DB_NAME = "test_navigator.db"
        database.init_db()
        database.clear_database()
        self.graph = CityGraph()
        self.advisor = AINavigatorAdvisor()

    def tearDown(self):
        if os.path.exists("test_navigator.db"):
            try:
                os.remove("test_navigator.db")
            except Exception:
                pass

    def test_ai_single_route_analysis(self):
        stats_mock = {
            "total_count": 10,
            "completed_count": 10,
            "avg_expected_time": 25.0,
            "avg_actual_time": 31.0
        }
        conclusion = self.advisor.analyze_single_route("A → B → E → G", stats_mock)
        self.assertIn("часто займає більше часу", conclusion)
        self.assertIn("31", conclusion)

    def test_ai_recommendation_logic(self):
        for _ in range(10):
            database.save_route("A", "G", "A,B,E,G", 18.0, 27.0, actual_time=31.0)
        for _ in range(6):
            database.save_route("A", "G", "A,D,F,G", 20.0, 29.0, actual_time=27.0)

        user = UserProfile("Ivan", "driver")
        rec = self.advisor.recommend_route(self.graph, "A", "G", user)

        self.assertEqual(rec["dijkstra"].route_str, "A,B,E,G")
        self.assertEqual(rec["recommended"].route_str, "A,D,F,G")
        self.assertIn("на 2.0 км довший", rec["reason"])
        self.assertIn("дозволяє досягти кінцевої точки на 4.0 хвилин швидше", rec["reason"])

    def test_user_personas(self):
        mgr = UserManager()
        u_ivan = mgr.set_current_user("Ivan", "driver")
        self.assertEqual(u_ivan.user_type, "driver")
        self.assertEqual(u_ivan.icon, "[Водій]")

        u_olena = mgr.set_current_user("Olena", "student")
        self.assertEqual(u_olena.user_type, "student")
        self.assertEqual(u_olena.icon, "[Студент]")


if __name__ == "__main__":
    unittest.main()
