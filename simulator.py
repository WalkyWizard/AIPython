import random
from datetime import datetime, timedelta
from database import save_route, clear_database, get_overall_statistics


def seed_scenario_data(clear_first: bool = True) -> int:
    if clear_first:
        clear_database()

    count = 0
    base_time = datetime.now() - timedelta(days=15)

    for i in range(10):
        trip_time = base_time + timedelta(hours=i * 24 + random.randint(1, 4))
        actual_t = round(random.uniform(29.5, 32.5), 1)
        actual_d = round(18.0 + random.uniform(-0.3, 0.5), 1)
        user = "Ivan" if i % 2 == 0 else "Maksym"
        u_type = "driver" if user == "Ivan" else "worker"

        save_route(
            start_point="A",
            finish_point="G",
            route="A,B,E,G",
            distance=18.0,
            time=27.0,
            traffic=1.5,
            user_name=user,
            user_type=u_type,
            actual_time=actual_t,
            actual_distance=actual_d,
            created_at=trip_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        count += 1

    for i in range(6):
        trip_time = base_time + timedelta(hours=i * 36 + random.randint(2, 5))
        actual_t = round(random.uniform(26.0, 28.0), 1)
        actual_d = round(20.0 + random.uniform(-0.2, 0.4), 1)
        user = "Ivan" if i < 3 else "Olena"
        u_type = "driver" if user == "Ivan" else "student"

        save_route(
            start_point="A",
            finish_point="G",
            route="A,D,F,G",
            distance=20.0,
            time=29.0,
            traffic=1.1,
            user_name=user,
            user_type=u_type,
            actual_time=actual_t,
            actual_distance=actual_d,
            created_at=trip_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        count += 1

    for i in range(30):
        trip_time = base_time + timedelta(hours=i * 10 + random.randint(1, 3))
        actual_t = round(random.uniform(39.0, 45.0), 1)
        actual_d = round(21.0 + random.uniform(0.0, 0.8), 1)
        user = "Maksym" if i % 2 == 0 else "Olena"
        u_type = "worker" if user == "Maksym" else "student"

        save_route(
            start_point="A",
            finish_point="G",
            route="A,B,C,G",
            distance=21.0,
            time=32.0,
            traffic=1.5,
            user_name=user,
            user_type=u_type,
            actual_time=actual_t,
            actual_distance=actual_d,
            created_at=trip_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        count += 1

    for i in range(5):
        save_route(
            start_point="A",
            finish_point="E",
            route="A,B,E",
            distance=10.0,
            time=16.0,
            traffic=1.4,
            user_name="Ivan",
            user_type="driver",
            actual_time=round(random.uniform(17.5, 20.0), 1),
            actual_distance=10.0,
            created_at=(base_time + timedelta(hours=i * 20)).strftime("%Y-%m-%d %H:%M:%S")
        )
        count += 1

    for i in range(4):
        save_route(
            start_point="D",
            finish_point="G",
            route="D,F,G",
            distance=15.0,
            time=21.0,
            traffic=1.1,
            user_name="Olena",
            user_type="student",
            actual_time=round(random.uniform(20.0, 22.0), 1),
            actual_distance=15.0,
            created_at=(base_time + timedelta(hours=i * 25)).strftime("%Y-%m-%d %H:%M:%S")
        )
        count += 1

    return count


def simulate_trip(
    route_nodes: list,
    expected_dist: float,
    expected_time: float,
    user_name: str,
    user_type: str
) -> tuple:
    type_factors = {
        "driver": 0.95,
        "worker": 1.05,
        "student": 1.10
    }
    factor = type_factors.get(user_type, 1.0)

    congestion = 1.0
    nodes_str = ",".join(route_nodes)
    if "B,E,G" in nodes_str or "B,E" in nodes_str:
        congestion += 0.22
    if "C,G" in nodes_str:
        congestion += 0.35
    if "D,F,G" in nodes_str:
        congestion -= 0.08

    noise = random.uniform(-0.05, 0.05)
    final_time = round(expected_time * congestion * factor * (1.0 + noise), 1)
    final_dist = round(expected_dist + random.uniform(-0.2, 0.4), 1)

    return final_time, final_dist
