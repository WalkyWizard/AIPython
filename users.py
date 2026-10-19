from typing import Dict, List, Optional

USER_TYPES_INFO: Dict[str, Dict[str, str]] = {
    "student": {
        "title": "Студент",
        "description": "Пріоритет: менша дистанція та спокійний темп. Можливе пересування пішки/громадським транспортом.",
        "icon": "[Студент]"
    },
    "worker": {
        "title": "Працівник",
        "description": "Пріоритет: передбачуваність та пунктуальність. Чутливий до затримок у ранкові та вечірні години пік.",
        "icon": "[Працівник]"
    },
    "driver": {
        "title": "Водій",
        "description": "Пріоритет: широкі магістралі та об'їзд заторів. Здатний рухатися швидше на автобанах.",
        "icon": "[Водій]"
    }
}


class UserProfile:
    def __init__(self, name: str, user_type: str = "driver"):
        self.name = name.strip()
        self.user_type = user_type.lower().strip()
        if self.user_type not in USER_TYPES_INFO:
            self.user_type = "worker"

    @property
    def type_title(self) -> str:
        return USER_TYPES_INFO[self.user_type]["title"]

    @property
    def icon(self) -> str:
        return USER_TYPES_INFO[self.user_type]["icon"]

    @property
    def description(self) -> str:
        return USER_TYPES_INFO[self.user_type]["description"]

    def __repr__(self) -> str:
        return f"{self.name} ({self.type_title})"


class UserManager:
    DEFAULT_PROFILES = [
        UserProfile("Ivan", "driver"),
        UserProfile("Olena", "student"),
        UserProfile("Maksym", "worker"),
        UserProfile("Anna", "driver"),
    ]

    def __init__(self):
        self.profiles: Dict[str, UserProfile] = {
            p.name.lower(): p for p in self.DEFAULT_PROFILES
        }
        self.current_user: UserProfile = self.profiles["ivan"]

    def set_current_user(self, name: str, user_type: Optional[str] = None) -> UserProfile:
        key = name.lower().strip()
        if key in self.profiles:
            if user_type:
                self.profiles[key].user_type = user_type
            self.current_user = self.profiles[key]
        else:
            new_profile = UserProfile(name, user_type or "worker")
            self.profiles[key] = new_profile
            self.current_user = new_profile
        return self.current_user

    def get_all_profiles(self) -> List[UserProfile]:
        return list(self.profiles.values())
