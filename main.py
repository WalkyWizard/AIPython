import sys
import os

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

from graph import CityGraph, LOCATIONS, get_location_name, format_route
from dijkstra import dijkstra_shortest_path, find_all_routes, RouteResult
from database import (
    init_db,
    save_route,
    update_actual_trip,
    get_recent_routes,
    get_pending_routes,
    get_route_stats_for_pair,
    get_user_stats_for_pair,
    get_overall_statistics,
    clear_database
)
from users import UserManager, USER_TYPES_INFO
from ai_module import AINavigatorAdvisor
from simulator import seed_scenario_data, simulate_trip


def print_banner(user_manager: UserManager):
    u = user_manager.current_user
    print("=" * 60)
    print("                 ===== AI NAVIGATOR =====")
    print("         Міська адаптивна навігаційна система")
    print(f"  Активний користувач: {u.name} ({u.type_title})")
    print("=" * 60)


def print_locations():
    print("\nДоступні локації карти:")
    for code, name in LOCATIONS.items():
        print(f"  [{code}] — {name}")


def prompt_location(prompt_text: str, default: str = "") -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{prompt_text}{suffix}: ").strip().upper()
        if not raw and default:
            return default
        if raw in LOCATIONS:
            return raw
        print(f"Помилка: локація '{raw}' не існує. Введіть одну з: {', '.join(LOCATIONS.keys())}")


def menu_find_route(graph: CityGraph, user_manager: UserManager):
    print("\n--- 1. Пошук оптимального маршруту (Dijkstra) ---")
    print_locations()

    start = prompt_location("\nПочаткова точка", default="A")
    finish = prompt_location("Кінцева точка", default="G")

    if start == finish:
        print("\nПочаткова та кінцева точки однакові! Ви вже на місці.")
        return

    result = dijkstra_shortest_path(graph, start, finish, weight_mode="time")
    if not result:
        print(f"\nШлях між {start} та {finish} не знайдено.")
        return

    print("\n" + "=" * 50)
    print(f"Маршрут: {result.display_str}")
    print(f"Відстань: {result.total_distance} км")
    print(f"Час: {result.total_time} хв.")
    print("=" * 50)

    print("\nПосегментний план поїздки:")
    for u, v, edge in result.edge_details:
        print(f"  • {u} ({get_location_name(u)}) → {v} ({get_location_name(v)}): "
              f"{edge.distance} км, {edge.time} хв | "
              f"Затори: x{edge.traffic} | {edge.description}")

    u = user_manager.current_user
    route_id = save_route(
        start_point=start,
        finish_point=finish,
        route=result.route_str,
        distance=result.total_distance,
        time=result.total_time,
        traffic=result.avg_traffic,
        user_name=u.name,
        user_type=u.user_type
    )
    print(f"\n[OK] Маршрут автоматично записано до бази даних (ID запису: #{route_id}).")

    print("\nБажаєте зафіксувати фактичний результат поїздки?")
    print("1. Ввести фактичний час вручну")
    print("2. Змоделювати поїздку автоматично (з урахуванням трафіку)")
    print("0. Пропустити (зберегти тільки прогноз)")
    choice = input("Ваш вибір [0/1/2]: ").strip()

    if choice == "1":
        try:
            act_time = float(input(f"Фактичний час у хвилинах (очікувалось {result.total_time} хв): "))
            act_dist_str = input(f"Фактична відстань у км [Enter={result.total_distance}]: ").strip()
            act_dist = float(act_dist_str) if act_dist_str else result.total_distance
            update_actual_trip(route_id, act_time, act_dist)
            print(f"[OK] Фактичні дані збережено: {act_time} хв, {act_dist} км.")
        except ValueError:
            print("Некоректний формат числа. Запис збережено без фактичного часу.")
    elif choice == "2":
        sim_time, sim_dist = simulate_trip(
            result.nodes, result.total_distance, result.total_time, u.name, u.user_type
        )
        update_actual_trip(route_id, sim_time, sim_dist)
        diff = round(sim_time - result.total_time, 1)
        diff_str = f"+{diff}" if diff > 0 else f"{diff}"
        print(f"\n[Симуляція завершена]:")
        print(f"  Фактичний час: {sim_time} хв ({diff_str} хв від прогнозу)")
        print(f"  Фактична відстань: {sim_dist} км")
        print("[OK] Дані поїздки збережено в БД.")


def menu_add_actual_result(user_manager: UserManager):
    print("\n--- 2. Додати результат проходження маршруту ---")
    pending = get_pending_routes(limit=10)

    if pending:
        print("\nОстанні маршрути, які очікують внесення фактичного часу:")
        print(f"{'ID':<5} | {'Користувач':<10} | {'Маршрут':<15} | {'Очік. час':<10} | {'Очік. відст.':<12}")
        print("-" * 60)
        for r in pending:
            route_disp = r['route'].replace(',', ' → ')
            print(f"#{r['id']:<4} | {r['user_name']:<10} | {route_disp:<15} | {r['time']:<10} | {r['distance']:<12}")

        print("\nОберіть ID зі списку вище або натисніть Enter для ручного введення нового маршруту:")
        choice = input("ID маршруту: ").strip()
        if choice and choice.isdigit():
            r_id = int(choice)
            try:
                act_time = float(input("Введіть фактичний час (хв): "))
                act_dist_str = input("Введіть фактичну відстань (км, Enter щоб пропустити): ").strip()
                act_dist = float(act_dist_str) if act_dist_str else None
                success = update_actual_trip(r_id, act_time, act_dist)
                if success:
                    print(f"[OK] Маршрут #{r_id} успішно оновлено фактичними даними!")
                    return
                else:
                    print(f"Помилка: маршрут з ID #{r_id} не знайдено.")
            except ValueError:
                print("Помилка: некоректне числове значення.")
                return

    print("\nВнесення нового завершеного маршруту вручну:")
    print_locations()
    start = prompt_location("Початкова точка", default="A")
    finish = prompt_location("Кінцева точка", default="G")
    route_input = input("Маршрут через кому (наприклад, A,B,E,G): ").strip().upper()
    if not route_input:
        print("Маршрут не вказано.")
        return

    try:
        exp_time = float(input("Очікуваний час за алгоритмом (хв): "))
        exp_dist = float(input("Очікувана відстань (км): "))
        act_time = float(input("Фактичний час (хв): "))
        act_dist_str = input(f"Фактична відстань (км) [Enter={exp_dist}]: ").strip()
        act_dist = float(act_dist_str) if act_dist_str else exp_dist

        u = user_manager.current_user
        save_route(
            start_point=start,
            finish_point=finish,
            route=route_input,
            distance=exp_dist,
            time=exp_time,
            user_name=u.name,
            user_type=u.user_type,
            actual_time=act_time,
            actual_distance=act_dist
        )
        print("[OK] Новий результат поїздки успішно додано до БД!")
    except ValueError:
        print("Помилка при введенні чисел.")


def menu_history(advisor: AINavigatorAdvisor):
    print("\n--- 3. Історія маршрутів ---")
    recent = get_recent_routes(limit=15)

    if not recent:
        print("Історія поїздок у базі даних порожня. Виконайте розрахунок маршруту або згенеруйте тестові дані (пункт 7).")
        return

    print("\nОстанні збережені записи:")
    header = f"{'ID':<4} | {'Дата':<19} | {'Користувач':<10} | {'Маршрут':<18} | {'Очік.':<8} | {'Факт.':<8} | {'Різниця':<8}"
    print(header)
    print("-" * len(header))
    for r in recent:
        route_disp = r['route'].replace(',', ' → ')
        act_str = f"{r['actual_time']} хв" if r['actual_time'] is not None else "---"
        exp_str = f"{r['time']} хв"
        if r['actual_time'] is not None:
            diff = round(r['actual_time'] - r['time'], 1)
            diff_str = f"{diff:+0.1f} хв"
        else:
            diff_str = "в дорозі"
        u_info = f"{r['user_name']} ({r['user_type'][0]})"
        print(f"#{r['id']:<3} | {r['created_at']:<19} | {u_info:<10} | {route_disp:<18} | {exp_str:<8} | {act_str:<8} | {diff_str:<8}")

    print("\nБажаєте переглянути детальний AI-аналіз конкретного напрямку? (наприклад, A -> G)")
    check = input("Введіть 'y' для перегляду аналізу напрямку або Enter для повернення: ").strip().lower()
    if check == 'y':
        start = prompt_location("Початкова точка", default="A")
        finish = prompt_location("Кінцева точка", default="G")
        stats = get_route_stats_for_pair(start, finish)
        if not stats:
            print(f"Немає даних для напрямку {start} → {finish}.")
            return
        print(f"\n--- Накопичена статистика для напрямку {start} → {finish} ---")
        for s in stats:
            route_disp = s['route'].replace(',', ' → ')
            print(f"\nМаршрут: {route_disp}")
            print(f"  Всього поїздок: {s['total_count']} (завершених: {s['completed_count']})")
            if s['avg_actual_time']:
                print(f"  Середній очікуваний час: {s['avg_expected_time']} хв | Середній фактичний час: {s['avg_actual_time']} хв")
                print(f"  Різниця: {s['time_difference']:+0.1f} хв ({s['delay_percent']:+0.1f}%)")
            analysis = advisor.analyze_single_route(route_disp, s)
            print(f"  Висновок AI: {analysis}")


def menu_statistics():
    print("\n--- 4. Загальна статистика системи ---")
    stats = get_overall_statistics()
    totals = stats["totals"]

    total_records = totals.get("total_records") or 0
    completed_trips = totals.get("completed_trips") or 0

    if total_records == 0:
        print("База даних ще не містить записів. Запустіть пошук маршрутів або наповніть базу тестовими даними (пункт 7).")
        return

    avg_time = round(totals.get("avg_actual_time") or 0.0, 1)
    avg_dist = round(totals.get("avg_actual_distance") or totals.get("avg_distance") or 0.0, 1)
    avg_diff = round(totals.get("avg_time_diff") or 0.0, 1)

    print("=" * 60)
    print(f"  Всього розраховано маршрутів: {total_records}")
    print(f"  Завершених поїздок з фактичним часом: {completed_trips}")
    print(f"  Середній фактичний час поїздки: {avg_time} хв")
    print(f"  Середня відстань: {avg_dist} км")
    diff_sign = "+" if avg_diff > 0 else ""
    print(f"  Середня різниця (прогноз vs факт): {diff_sign}{avg_diff} хв")
    print("=" * 60)

    print("\nНайпопулярніші маршрути:")
    pop = stats.get("popular_routes", [])
    if pop:
        for idx, p in enumerate(pop, 1):
            route_disp = p['route'].replace(',', ' → ')
            act_avg = f"{round(p['avg_actual_time'], 1)} хв" if p['avg_actual_time'] else "немає факт. даних"
            print(f"  {idx}. {route_disp}")
            print(f"     Використано: {p['usage_count']} раз(ів) | Середній час: {act_avg} (прогноз: {p['avg_predicted_time']} хв)")
    else:
        print("  Немає даних.")

    fastest = stats.get("fastest_route")
    slowest = stats.get("slowest_route")

    print("\nРекорди швидкості:")
    if fastest:
        f_disp = fastest['route'].replace(',', ' → ')
        print(f"  Найшвидший маршрут: {f_disp} (середній час: {round(fastest['avg_act'], 1)} хв)")
    if slowest:
        s_disp = slowest['route'].replace(',', ' → ')
        print(f"  Найповільніший маршрут: {s_disp} (середній час: {round(slowest['avg_act'], 1)} хв)")

    u_stats = stats.get("user_types_stats", [])
    if u_stats:
        print("\nСтатистика за типами користувачів:")
        for us in u_stats:
            t_name = USER_TYPES_INFO.get(us['user_type'], {}).get('title', us['user_type'])
            print(f"  • {t_name} ({us['user_type']}): "
                  f"{us['trip_count']} поїздок, "
                  f"сер. час: {round(us['avg_time'], 1)} хв, "
                  f"сер. дистанція: {round(us['avg_dist'], 1)} км")


def menu_ai_recommendation(graph: CityGraph, user_manager: UserManager, advisor: AINavigatorAdvisor):
    print("\n--- 5. AI-рекомендація оптимального маршруту ---")
    print_locations()

    start = prompt_location("\nПочаткова точка", default="A")
    finish = prompt_location("Кінцева точка", default="G")

    if start == finish:
        print("\nПочаткова та кінцева точки однакові!")
        return

    curr_user = user_manager.current_user
    print(f"\n[AI] Аналізуємо мережу доріг та базу даних для користувача {curr_user.name} ({curr_user.type_title})...")

    rec = advisor.recommend_route(graph, start, finish, curr_user)
    if "error" in rec:
        print(f"\nПомилка: {rec['error']}")
        return

    dijkstra_res: RouteResult = rec["dijkstra"]
    recommended_res: RouteResult = rec["recommended"]

    print("\n" + "=" * 65)
    print("                ЗВІТ AI-НАВІГАТОРА")
    print("=" * 65)

    print(f"\n1. Розрахунок за стандартним алгоритмом (Dijkstra):")
    print(f"   Маршрут: {dijkstra_res.display_str}")
    print(f"   Відстань: {dijkstra_res.total_distance} км")
    print(f"   Прогнозований час: {dijkstra_res.total_time} хв.")

    print(f"\n2. Статус навчання системи «пам’яті»:")
    print(f"   {rec['confidence_badge']} Рівень пам'яті: {rec['memory_level']}")
    print(f"   Примітка: {rec['memory_comment']}")

    print("\n3. Порівняльний аналіз альтернативних варіантів:")
    print(f"{'Маршрут':<20} | {'Прогноз':<10} | {'Історія (факт)':<16} | {'Поїздок':<8}")
    print("-" * 62)

    for cand in rec["scored_candidates"]:
        r_obj: RouteResult = cand["route_obj"]
        hist = cand["history"]
        completed = hist.get("completed_count", 0)
        avg_act = f"{hist.get('avg_actual_time')} хв" if hist.get('avg_actual_time') else "немає"
        is_d = " (Dijkstra)" if cand["is_dijkstra"] else ""
        disp = f"{r_obj.display_str}{is_d}"
        print(f"{disp:<20} | {r_obj.total_time:<8} хв | {avg_act:<16} | {completed:<8}")

    print("\n" + "=" * 65)
    print(f"РЕКОМЕНДОВАНИЙ МАРШРУТ ВІД AI:")
    print(f"   -> {recommended_res.display_str}")
    print(f"   Відстань: {recommended_res.total_distance} км")
    print(f"   Очікуваний реальний час: {rec['scored_candidates'][0]['effective_time']} хв.")
    print("=" * 65)

    if rec.get("llm_analysis"):
        print("\nДетальний висновок AI (LLM):")
        print(rec["llm_analysis"])
    else:
        print("\nПричина вибору:")
        print(f"   {rec['reason']}")

    route_id = save_route(
        start_point=start,
        finish_point=finish,
        route=recommended_res.route_str,
        distance=recommended_res.total_distance,
        time=recommended_res.total_time,
        traffic=recommended_res.avg_traffic,
        user_name=curr_user.name,
        user_type=curr_user.user_type
    )
    print(f"\n[OK] Рекомендацію збережено до журналу (ID: #{route_id}).")

    print("\nБажаєте зафіксувати проходження рекомендованого маршруту?")
    print("1. Змоделювати поїздку автоматично")
    print("2. Ввести фактичний час вручну")
    print("0. Пропустити")
    c = input("Ваш вибір [0/1/2]: ").strip()
    if c == "1":
        sim_time, sim_dist = simulate_trip(
            recommended_res.nodes, recommended_res.total_distance, recommended_res.total_time,
            curr_user.name, curr_user.user_type
        )
        update_actual_trip(route_id, sim_time, sim_dist)
        print(f"[OK] Поїздку завершено: факт. час {sim_time} хв, факт. дистанція {sim_dist} км. Історію в БД оновлено!")
    elif c == "2":
        try:
            act_time = float(input("Фактичний час (хв): "))
            update_actual_trip(route_id, act_time)
            print("[OK] Дані збережено!")
        except ValueError:
            print("Некоректний формат числа.")


def menu_switch_user(user_manager: UserManager):
    print("\n--- 6. Керування користувачами та профілями ---")
    profiles = user_manager.get_all_profiles()
    print("Наявні профілі:")
    for idx, p in enumerate(profiles, 1):
        is_active = " [АКТИВНИЙ]" if p.name.lower() == user_manager.current_user.name.lower() else ""
        print(f"  {idx}. {p.name} — {p.type_title} ({p.user_type}){is_active}")
        print(f"     {p.description}")

    print("\nОберіть номер профілю або введіть ім'я для створення нового:")
    choice = input("Номер або нове ім'я: ").strip()
    if not choice:
        return

    if choice.isdigit() and 1 <= int(choice) <= len(profiles):
        selected = profiles[int(choice) - 1]
        user_manager.set_current_user(selected.name, selected.user_type)
        print(f"\n[OK] Активний профіль змінено на: {user_manager.current_user}")
    else:
        new_name = choice
        print("Оберіть тип користувача:")
        print("1. driver (водій — швидкість по шосе, об'їзд заторів)")
        print("2. student (студент — коротша дистанція, економний темп)")
        print("3. worker (працівник — регулярність та пунктуальність)")
        t_choice = input("Тип [1/2/3, Enter=3]: ").strip()
        type_map = {"1": "driver", "2": "student", "3": "worker"}
        u_type = type_map.get(t_choice, "worker")
        user_manager.set_current_user(new_name, u_type)
        print(f"\n[OK] Створено та активовано профіль: {user_manager.current_user}")


def menu_seed_data():
    print("\n--- 7. Генерація тестових даних (Демо-сценарій ТЗ) ---")
    print("Буде згенеровано історичний набір поїздок:")
    print("  • Маршрут A → B → E → G: 10 поїздок (середній фактичний час ~31 хв проти 27 хв прогнозу)")
    print("  • Маршрут A → D → F → G: 6 поїздок (середній фактичний час ~27 хв проти 29 хв прогнозу)")
    print("  • Маршрут A → B → C → G: 30 поїздок (середній фактичний час ~42 хв проти 32 хв прогнозу)")
    print("  • Персональні дані водія Ivan (сер. час ~29 хв проти 35 хв в інших)")
    confirm = input("\nОчистити поточну історію та згенерувати еталонний датасет? (y/n): ").strip().lower()
    if confirm == "y":
        count = seed_scenario_data(clear_first=True)
        print(f"\n[OK] Успішно згенеровано {count} поїздок! База даних наповнена.")
        print("Тепер перейдіть до пунктів '4. Статистика' або '5. AI-рекомендація', щоб перевірити роботу системи.")


def menu_configure_ai(advisor: AINavigatorAdvisor):
    print("\n--- 8. Налаштування AI API ---")
    status = "Підключено" if advisor.api_key else "Використовується вбудований Heuristic AI Engine"
    print(f"Поточний статус AI: {status}")
    if advisor.api_key:
        masked_key = advisor.api_key[:4] + "..." + advisor.api_key[-4:] if len(advisor.api_key) > 8 else "***"
        print(f"Активний API ключ: {masked_key}")

    print("\nОпції:")
    print("1. Ввести API ключ Google Gemini")
    print("2. Ввести API ключ OpenAI")
    print("3. Очистити ключ (використовувати локальний розумний AI рушій)")
    print("0. Повернутися")

    c = input("Вибір: ").strip()
    if c == "1":
        key = input("Введіть Google Gemini API Key: ").strip()
        if key:
            advisor.set_api_key(key, provider="gemini")
            print("[OK] Google Gemini API ключ збережено.")
    elif c == "2":
        key = input("Введіть OpenAI API Key: ").strip()
        if key:
            advisor.set_api_key(key, provider="openai")
            print("[OK] OpenAI API ключ збережено.")
    elif c == "3":
        advisor.set_api_key("", provider="auto")
        print("[OK] Ключ очищено. Увімкнено автономний AI-рушій.")


def main():
    init_db()
    graph = CityGraph()
    user_manager = UserManager()
    advisor = AINavigatorAdvisor()

    while True:
        print_banner(user_manager)
        print("1. Знайти маршрут")
        print("2. Додати результат проходження")
        print("3. Історія маршрутів")
        print("4. Статистика")
        print("5. AI-рекомендація")
        print("6. Змінити користувача / Профіль")
        print("7. Згенерувати тестові дані (Демо-сценарій ТЗ)")
        print("8. Налаштувати AI API")
        print("0. Вихід")
        print("=" * 60)

        choice = input("Оберіть пункт меню [0-8]: ").strip()

        if choice == "1":
            menu_find_route(graph, user_manager)
        elif choice == "2":
            menu_add_actual_result(user_manager)
        elif choice == "3":
            menu_history(advisor)
        elif choice == "4":
            menu_statistics()
        elif choice == "5":
            menu_ai_recommendation(graph, user_manager, advisor)
        elif choice == "6":
            menu_switch_user(user_manager)
        elif choice == "7":
            menu_seed_data()
        elif choice == "8":
            menu_configure_ai(advisor)
        elif choice == "0":
            print("\nДякуємо за використання AI-навігатора! До побачення.")
            break
        else:
            print("\nНевідомий пункт меню. Будь ласка, введіть число від 0 до 8.")

        input("\nНатисніть Enter для продовження...")


if __name__ == "__main__":
    main()
