import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from graph import CityGraph, format_route, get_location_name
from dijkstra import RouteResult, dijkstra_shortest_path, find_all_routes
from database import get_route_stats_for_pair, get_user_stats_for_pair
from users import UserProfile


class AINavigatorAdvisor:
    def __init__(self, api_key: Optional[str] = None, provider: str = "auto"):
        self.provider = provider
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")

    def set_api_key(self, key: str, provider: str = "gemini"):
        self.api_key = key.strip() if key else None
        self.provider = provider

    def _call_gemini_api(self, prompt: str) -> Optional[str]:
        if not self.api_key:
            return None

        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 1000
                }
            }
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    text = (
                        res_json.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if text:
                        return text.strip()
            except Exception:
                continue

        return None

    def _call_openai_api(self, prompt: str) -> Optional[str]:
        if not self.api_key:
            return None

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Ти експертний AI-диспетчер міського навігатора. Відповідай українською мовою структуровано, лаконічно і переконливо."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                return res_json["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    def analyze_single_route(self, route_str: str, stats: Dict[str, Any]) -> str:
        total = stats.get("total_count", 0)
        completed = stats.get("completed_count", 0)
        exp_time = stats.get("avg_expected_time", 0.0)
        act_time = stats.get("avg_actual_time")

        if not act_time or completed == 0:
            return f"Маршрут {route_str}: зафіксовано {total} розрахунків, але фактичних поїздок ще немає. Необхідно накопичити дані."

        delay = round(act_time - exp_time, 1)
        delay_pct = round(((act_time - exp_time) / exp_time) * 100, 1) if exp_time else 0.0

        prompt = f"""
Проаналізуй історію проходження маршруту:
Маршрут: {route_str}
Кількість завершених поїздок: {completed}
Середній фактичний час: {act_time} хв.
Очікуваний час за алгоритмом: {exp_time} хв.
Різниця: {delay} хв ({delay_pct:+}%).

Сформулюй стислий професійний висновок AI-аналітика (1-2 речення) про надійність маршруту та необхідність коригування часу.
"""
        llm_reply = None
        if self.api_key:
            llm_reply = self._call_gemini_api(prompt) or self._call_openai_api(prompt)

        if llm_reply:
            return llm_reply

        if delay > 2.0:
            return (
                f"Маршрут {route_str} за {completed} проходженнями часто займає більше часу, "
                f"ніж прогнозує стандартний алгоритм (фактично {act_time} хв проти {exp_time} хв). "
                f"Рекомендується враховувати додаткові {max(15, int(delay_pct))}% часу через регулярні затримки."
            )
        elif delay < -1.5:
            return (
                f"Маршрут {route_str} демонструє високу пропускну здатність: фактичний час ({act_time} хв) "
                f"в середньому на {abs(delay)} хв швидший за розрахунковий ({exp_time} хв). "
                f"Маршрут надійний та має низький трафік."
            )
        else:
            return (
                f"Маршрут {route_str} має стабільний графік: середній фактичний час {act_time} хв "
                f"майже повністю відповідає очікуваному {exp_time} хв (відхилення лише {delay:+} хв)."
            )

    def recommend_route(
        self,
        graph: CityGraph,
        start: str,
        finish: str,
        current_user: UserProfile
    ) -> Dict[str, Any]:
        start = start.upper().strip()
        finish = finish.upper().strip()

        dijkstra_res = dijkstra_shortest_path(graph, start, finish, weight_mode="time")
        if not dijkstra_res:
            return {"error": f"Маршрут між {start} та {finish} не знайдено."}

        all_routes = find_all_routes(graph, start, finish)

        global_history = get_route_stats_for_pair(start, finish)
        user_history = get_user_stats_for_pair(current_user.name, start, finish)

        history_map: Dict[str, Dict[str, Any]] = {
            item["route"]: item for item in global_history
        }
        user_hist_map: Dict[str, Dict[str, Any]] = {
            item["route"]: item for item in user_history
        }

        total_pair_trips = sum(item.get("completed_count", 0) for item in global_history)

        if total_pair_trips == 0:
            memory_level = "Порожня історія (0 поїздок)"
            confidence_badge = "[0%]"
            memory_comment = "AI ще не має накопичених даних для цього напрямку. Рекомендація базується суто на математичному розрахунку Дейкстри."
        elif total_pair_trips < 5:
            memory_level = f"Початкова пам'ять ({total_pair_trips} поїздок)"
            confidence_badge = "[!]"
            memory_comment = f"AI ще не має достатньо інформації ({total_pair_trips} < 5 поїздок). Рекомендація є попередньою."
        elif total_pair_trips < 15:
            memory_level = f"Сформована пам'ять ({total_pair_trips} поїздок)"
            confidence_badge = "[+]"
            memory_comment = f"AI володіє достатньою вибіркою ({total_pair_trips} поїздок) для виявлення стійких патернів заторів."
        else:
            memory_level = f"Висока точність пам'яті ({total_pair_trips} поїздок)"
            confidence_badge = "[++]"
            memory_comment = f"Система глибоко натренована на {total_pair_trips} реальних проходженнях. Рекомендація має найвищу достовірність."

        candidates = []
        dijkstra_key = dijkstra_res.route_str

        d_hist = history_map.get(dijkstra_key, {})
        d_user = user_hist_map.get(dijkstra_key, {})
        candidates.append({
            "route_obj": dijkstra_res,
            "route_str": dijkstra_key,
            "is_dijkstra": True,
            "history": d_hist,
            "user_history": d_user
        })

        for r in all_routes:
            r_key = r.route_str
            if r_key != dijkstra_key:
                candidates.append({
                    "route_obj": r,
                    "route_str": r_key,
                    "is_dijkstra": False,
                    "history": history_map.get(r_key, {}),
                    "user_history": user_hist_map.get(r_key, {})
                })
            if len(candidates) >= 4:
                break

        scored_candidates = []
        for cand in candidates:
            r_obj: RouteResult = cand["route_obj"]
            hist = cand["history"]
            u_hist = cand["user_history"]

            completed = hist.get("completed_count", 0)
            avg_act = hist.get("avg_actual_time")
            u_act = u_hist.get("avg_actual_time")

            if completed >= 3 and avg_act:
                effective_time = avg_act
            else:
                effective_time = r_obj.total_time

            personal_note = ""
            if u_act and u_hist.get("completed_count", 0) >= 2:
                effective_time = round(u_act * 0.65 + effective_time * 0.35, 1)
                personal_note = f"Особистий темп {current_user.name}: {u_act} хв (за {u_hist['completed_count']} поїздками)."

            if current_user.user_type == "student":
                penalty_for_extra_km = (r_obj.total_distance - dijkstra_res.total_distance) * 0.5
                score = effective_time + max(0, penalty_for_extra_km)
            elif current_user.user_type == "driver":
                score = effective_time
            else:
                variance = (hist.get("max_actual_time", effective_time) - hist.get("min_actual_time", effective_time)) * 0.3
                score = effective_time + variance

            scored_candidates.append({
                **cand,
                "effective_time": round(effective_time, 1),
                "score": score,
                "personal_note": personal_note
            })

        scored_candidates.sort(key=lambda x: x["score"])
        recommended = scored_candidates[0]
        rec_obj: RouteResult = recommended["route_obj"]

        dist_diff = round(rec_obj.total_distance - dijkstra_res.total_distance, 1)
        time_diff = round(dijkstra_res.total_time - recommended["effective_time"], 1)

        is_dijkstra_chosen = (recommended["route_str"] == dijkstra_key)

        llm_analysis = None
        if self.api_key:
            prompt_context = f"""
Ти AI-навігатор міста. Проаналізуй ситуацію та надай обґрунтовану рекомендацію користувачу.

Користувач: {current_user.name} (тип: {current_user.user_type} - {current_user.type_title})
Маршрут: {get_location_name(start)} ({start}) -> {get_location_name(finish)} ({finish})

Стандартний розрахунок Dijkstra:
- Маршрут: {dijkstra_res.display_str}
- Відстань: {dijkstra_res.total_distance} км
- Прогнозований час: {dijkstra_res.total_time} хв

Історія проходжень у базі даних SQLite:
"""
            for sc in scored_candidates:
                h = sc["history"]
                cnt = h.get("completed_count", 0)
                act = h.get("avg_actual_time", "немає даних")
                prompt_context += f"- Маршрут {sc['route_obj'].display_str}: {cnt} проходжень, сер. факт. час: {act} хв (прогноз: {sc['route_obj'].total_time} хв)\n"

            if recommended["personal_note"]:
                prompt_context += f"\nПерсональні дані користувача: {recommended['personal_note']}\n"

            prompt_context += f"""
Рекомендований AI маршрут: {rec_obj.display_str}

Надай чітку, структуровану відповідь українською:
1. Рекомендований маршрут
2. Причина вибору (порівняй відстань і реальний історичний час)
3. Висновок щодо надійності вибірки та порада для типу користувача ({current_user.type_title})
"""
            llm_analysis = self._call_gemini_api(prompt_context) or self._call_openai_api(prompt_context)

        if not llm_analysis:
            if is_dijkstra_chosen:
                if total_pair_trips == 0:
                    reason = (
                        f"Маршрут Дейкстри {dijkstra_res.display_str} є оптимальним "
                        f"за розрахунковими параметрами ({dijkstra_res.total_distance} км, {dijkstra_res.total_time} хв). "
                        f"Історичні затримки на ньому ще не зафіксовані."
                    )
                else:
                    reason = (
                        f"Маршрут Дейкстри {dijkstra_res.display_str} підтвердив свою ефективність "
                        f"в історії поїздок (середній реальний час {recommended['effective_time']} хв). "
                        f"Альтернативи не мають переваг у часі."
                    )
            else:
                d_eff = next(c["effective_time"] for c in scored_candidates if c["is_dijkstra"])
                saved_time = round(d_eff - recommended["effective_time"], 1)
                dist_txt = f"на {abs(dist_diff)} км довший" if dist_diff > 0 else f"на {abs(dist_diff)} км коротший"
                reason = (
                    f"Цей маршрут {dist_txt}, але за історичними даними в середньому "
                    f"дозволяє досягти кінцевої точки на {saved_time} хвилин швидше "
                    f"(реальний час {recommended['effective_time']} хв проти {d_eff} хв на маршруті Дейкстри, де зафіксовано затори)."
                )

            if recommended["personal_note"]:
                reason += f"\nВраховано персональну історію водія {current_user.name}."

        return {
            "start": start,
            "finish": finish,
            "start_name": get_location_name(start),
            "finish_name": get_location_name(finish),
            "current_user": current_user,
            "dijkstra": dijkstra_res,
            "recommended": rec_obj,
            "is_dijkstra_chosen": is_dijkstra_chosen,
            "memory_level": memory_level,
            "confidence_badge": confidence_badge,
            "memory_comment": memory_comment,
            "reason": reason if not llm_analysis else None,
            "llm_analysis": llm_analysis,
            "scored_candidates": scored_candidates
        }
