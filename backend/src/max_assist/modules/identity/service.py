from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.errors import AppError, Forbidden, NotFound
from max_assist.modules.identity.max_init_data import parse_init_data
from max_assist.modules.identity.models import StaffProfile, User
from max_assist.utils import now

DEV_USERS = {
    "ludmila": {
        "first_name": "Людмила",
        "last_name": "Петрова",
        "username": "ludmila_p",
        "role_hint": "гражданин",
    },
    "sergey": {
        "first_name": "Сергей",
        "last_name": "Клосеп",
        "username": "sergey_k",
        "role_hint": "доверенный помощник",
    },
    "anna": {
        "first_name": "Анна",
        "last_name": "Смирнова",
        "username": "anna_s",
        "role_hint": "сотрудник МФЦ",
        "staff": {"organization": "МФЦ Фрунзенского района", "position": "Главный специалист"},
    },
    "oleg": {
        "first_name": "Олег",
        "last_name": "Нечаев",
        "username": "oleg_n",
        "role_hint": "посторонний",
    },
}


async def login_with_max(session: AsyncSession, init_data: str) -> User:
    if not settings.max_bot_token:
        raise AppError(
            "max_login_unavailable",
            "Токен бота MAX ещё не настроен, используйте dev-вход",
            503,
        )

    payload = parse_init_data(init_data, settings.max_bot_token, settings.init_data_max_age_seconds)
    profile = payload["user"]
    max_user_id = int(profile["id"])

    user = await session.scalar(select(User).where(User.max_user_id == max_user_id))
    if user is None:
        user = User(
            max_user_id=max_user_id, first_name=profile.get("first_name") or "Пользователь", staff=None
        )
        session.add(user)

    user.first_name = profile.get("first_name") or user.first_name
    user.last_name = profile.get("last_name")
    user.username = profile.get("username")
    user.photo_url = profile.get("photo_url")
    user.last_seen_at = now()

    await session.commit()
    return user


async def dev_login(session: AsyncSession, user_key: str) -> User:
    if not settings.is_dev:
        raise Forbidden("Dev-вход отключён")
    if user_key not in DEV_USERS:
        raise NotFound("Неизвестный тестовый пользователь")

    profile = DEV_USERS[user_key]
    user = await session.scalar(select(User).where(User.dev_key == user_key))
    if user is None:
        user = User(
            dev_key=user_key,
            first_name=profile["first_name"],
            last_name=profile["last_name"],
            username=profile["username"],
            staff=None,
        )
        session.add(user)

    staff = profile.get("staff")
    if staff is not None and user.staff is None:
        user.staff = StaffProfile(verified_at=now(), **staff)

    user.last_seen_at = now()
    await session.commit()
    return user


async def agree_to_recording(session: AsyncSession, user: User) -> None:
    if user.recording_consent_at is None:
        user.recording_consent_at = now()
        await session.commit()
