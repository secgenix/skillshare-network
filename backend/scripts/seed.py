#!/usr/bin/env python3
"""
Seed script — очищает всех пользователей и заполняет БД тестовыми данными.

Запуск внутри Docker:
    docker compose exec backend .venv/bin/python scripts/seed.py

Запуск локально (нужен запущенный Postgres):
    cd backend && uv run python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Добавляем корень backend в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Chat,
    Exchange,
    ExchangeParticipant,
    ExchangeStatus,
    Message,
    Review,
    Skill,
    SkillCategory,
    User,
    UserRole,
    UserSkillsOffered,
    UserSkillsWanted,
)

DATABASE_URL = os.getenv(
    "SSN_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/skillshare",
)

engine = create_async_engine(DATABASE_URL, echo=False)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


# ── Данные ────────────────────────────────────────────────────────────────────

CATEGORIES: dict[str, list[str]] = {
    "Программирование": [
        "Python",
        "JavaScript",
        "TypeScript",
        "Go",
        "Rust",
        "React",
        "SQL",
        "Docker",
        "Machine Learning",
        "C++",
    ],
    "Дизайн": [
        "Figma",
        "Photoshop",
        "Illustrator",
        "UI/UX Design",
        "Motion Design",
        "3D Моделирование",
        "Брендинг",
    ],
    "Языки": [
        "Английский",
        "Испанский",
        "Китайский",
        "Французский",
        "Немецкий",
        "Японский",
        "Итальянский",
    ],
    "Маркетинг": [
        "SEO",
        "SMM",
        "Контент-маркетинг",
        "Email-маркетинг",
        "Таргетированная реклама",
        "Веб-аналитика",
    ],
    "Музыка": [
        "Гитара",
        "Пианино",
        "Вокал",
        "Теория музыки",
        "Битмейкинг",
        "DJ",
        "Сведение и мастеринг",
    ],
    "Бизнес": [
        "Управление проектами",
        "Финансовый анализ",
        "Переговоры",
        "Стартапы",
        "Excel и таблицы",
    ],
    "Фото и видео": [
        "Фотография",
        "Видеомонтаж",
        "Дрон-съёмка",
        "Цветокоррекция",
        "YouTube-производство",
    ],
    "Спорт и здоровье": [
        "Йога",
        "CrossFit",
        "Плавание",
        "Бег",
        "Бокс",
        "Питание и нутрициология",
    ],
}

# Конкретные навыки (offered, wanted) — без рандома, гарантированные совпадения
ARCHETYPES_SKILLS: list[tuple[list[str], list[str]]] = [
    # Python-разработчик
    (["Python", "SQL", "Docker"], ["Figma", "UI/UX Design"]),
    # Frontend-разработчик
    (["React", "JavaScript", "TypeScript"], ["Python", "SMM"]),
    # ML-инженер
    (["Python", "Machine Learning", "SQL"], ["Английский", "Figma"]),
    # UI/UX-дизайнер
    (["Figma", "UI/UX Design", "Брендинг"], ["Python", "Контент-маркетинг"]),
    # Графический дизайнер
    (["Photoshop", "Illustrator", "Figma"], ["React", "Английский"]),
    # SEO-специалист
    (["SEO", "Веб-аналитика"], ["Figma", "Python"]),
    # SMM-менеджер
    (["SMM", "Контент-маркетинг"], ["Figma", "Python"]),
    # Преподаватель английского
    (["Английский", "Французский"], ["Python", "SEO"]),
    # Преподаватель испанского
    (["Английский", "Испанский"], ["Figma", "SMM"]),
    # Гитарист / музыкант
    (["Гитара", "Вокал", "Теория музыки"], ["SMM", "Python"]),
    # Продюсер / битмейкер
    (["Битмейкинг", "DJ"], ["Figma", "Контент-маркетинг"]),
    # Проект-менеджер
    (["Управление проектами", "Переговоры"], ["Python", "Figma"]),
    # Финансист
    (["Финансовый анализ", "Excel и таблицы"], ["Python", "SMM"]),
    # Видеограф
    (["Фотография", "Видеомонтаж", "Цветокоррекция"], ["SMM", "Python"]),
    # Тренер по йоге / нутрициолог
    (["Йога", "Питание и нутрициология"], ["Python", "Английский"]),
    # Фитнес-тренер
    (["CrossFit", "Бокс"], ["Figma", "Контент-маркетинг"]),
]

FIRST_NAMES_M = [
    "Александр",
    "Михаил",
    "Дмитрий",
    "Иван",
    "Андрей",
    "Алексей",
    "Максим",
    "Николай",
    "Сергей",
    "Артём",
    "Кирилл",
    "Роман",
    "Владимир",
    "Павел",
    "Илья",
    "Денис",
    "Евгений",
    "Антон",
    "Виктор",
    "Тимур",
    "Глеб",
    "Егор",
    "Фёдор",
    "Константин",
    "Вадим",
]
FIRST_NAMES_F = [
    "Анастасия",
    "Мария",
    "Екатерина",
    "Ольга",
    "Наталья",
    "Татьяна",
    "Анна",
    "Елена",
    "Дарья",
    "Юлия",
    "Ирина",
    "Светлана",
    "Алина",
    "Виктория",
    "Ксения",
    "Полина",
    "Валерия",
    "Марина",
    "Вероника",
    "Надежда",
]
LAST_NAMES = [
    "Иванов",
    "Смирнов",
    "Кузнецов",
    "Попов",
    "Соколов",
    "Лебедев",
    "Козлов",
    "Новиков",
    "Морозов",
    "Петров",
    "Волков",
    "Соловьёв",
    "Васильев",
    "Зайцев",
    "Павлов",
    "Семёнов",
    "Голубев",
    "Виноградов",
    "Богданов",
    "Воробьёв",
    "Фёдоров",
    "Михайлов",
    "Беляев",
    "Тарасов",
    "Белов",
    "Комаров",
    "Орлов",
    "Киселёв",
    "Макаров",
    "Андреев",
    "Ковалёв",
    "Ильин",
    "Гусев",
    "Титов",
    "Кузьмин",
    "Баранов",
    "Куликов",
    "Степанов",
    "Яковлев",
    "Борисов",
]

CHAT_MESSAGES = [
    "Привет! Предлагаю обмен навыками.",
    "Отлично, давай попробуем!",
    "Готов начать на этой неделе.",
    "У меня есть опыт в этом, расскажи подробнее.",
    "Могу уделять 2–3 часа в неделю.",
    "Когда тебе удобно начать?",
    "Договорились, жду твоего первого урока.",
    "Отправил тебе материалы.",
    "Прогресс отличный, продолжаем!",
    "Очень полезно, спасибо!",
    "Разобрались с темой, двигаемся дальше.",
    "Всё прошло как договаривались.",
]

REVIEW_POSITIVE = [
    "Всё прошло отлично, очень доволен обменом!",
    "Профессионал своего дела, рекомендую.",
    "Чётко, по делу, без воды. Спасибо!",
    "Узнал много нового, буду рад повторить.",
    "Отличный обмен, честный и ответственный.",
]
REVIEW_NEUTRAL = [
    "Нормально, в целом доволен.",
    "Хороший специалист, хотя можно глубже.",
    "Ок, базовые вещи объяснил.",
]


def _gen_name(i: int) -> str:
    if i % 3 == 0:
        first = random.choice(FIRST_NAMES_F)
        last = random.choice(LAST_NAMES)
        # феминизируем фамилию
        if last.endswith(("ов", "ев", "ёв")) or last.endswith("ин"):
            last = last + "а"
    else:
        first = random.choice(FIRST_NAMES_M)
        last = random.choice(LAST_NAMES)
    return f"{first} {last}"


async def seed(db: AsyncSession) -> None:
    # ── 1. Очистка ────────────────────────────────────────────────────────────
    print("🗑️  Очищаем базу данных…")
    await db.execute(
        text(
            "TRUNCATE TABLE reviews, messages, tasks, chats, "
            "exchange_participants, exchanges, listing_interests, listings, "
            "user_skills_offered, user_skills_wanted, "
            "skills, skill_categories, users "
            "RESTART IDENTITY CASCADE"
        )
    )
    await db.flush()
    print("   ✓ Таблицы очищены")

    # ── 2. Категории и навыки ─────────────────────────────────────────────────
    print("🏷️  Создаём категории и навыки…")
    cat_skills: dict[str, list[Skill]] = {}
    total_skills = 0

    for cat_name, skill_names in CATEGORIES.items():
        cat = SkillCategory(name=cat_name)
        db.add(cat)
        await db.flush()

        skills_in_cat: list[Skill] = []
        for sname in skill_names:
            s = Skill(name=sname, category_id=cat.id)
            db.add(s)
            await db.flush()
            skills_in_cat.append(s)
            total_skills += 1
        cat_skills[cat_name] = skills_in_cat

    print(f"   ✓ {len(CATEGORIES)} категорий, {total_skills} навыков")

    # ── 3. Администратор ──────────────────────────────────────────────────────
    print("🔑  Создаём администратора…")
    admin = User(
        email="admin@skillshare.dev",
        password_hash=_hash("admin12345"),
        full_name="Admin SkillShare",
        role=UserRole.admin,
        last_active_at=datetime.now(UTC),
    )
    db.add(admin)
    await db.flush()
    print(f"   ✓ admin@skillshare.dev / admin12345  (id={admin.id})")

    # ── 4. Пользователи ───────────────────────────────────────────────────────
    # Индекс навыков по имени для быстрого поиска
    skill_by_name: dict[str, Skill] = {}
    for skills_list in cat_skills.values():
        for sk in skills_list:
            skill_by_name[sk.name] = sk

    print("👥  Создаём 200 пользователей…")
    users: list[User] = []

    for i in range(200):
        user = User(
            email=f"user{i + 1}@test.dev",
            password_hash=_hash("testpass123"),
            full_name=_gen_name(i),
            last_active_at=datetime.now(UTC) - timedelta(days=random.randint(0, 20)),
        )
        db.add(user)
        await db.flush()

        offer_names, want_names = ARCHETYPES_SKILLS[i % len(ARCHETYPES_SKILLS)]

        for name in offer_names:
            sk = skill_by_name.get(name)
            if sk:
                db.add(
                    UserSkillsOffered(
                        user_id=user.id,
                        skill_id=sk.id,
                        level=random.randint(2, 3),
                    )
                )

        offered_ids = {skill_by_name[n].id for n in offer_names if n in skill_by_name}
        for name in want_names:
            sk = skill_by_name.get(name)
            if sk and sk.id not in offered_ids:
                db.add(
                    UserSkillsWanted(
                        user_id=user.id,
                        skill_id=sk.id,
                        desired_level=random.randint(1, 3),
                    )
                )

        users.append(user)

    await db.flush()
    print(f"   ✓ {len(users)} пользователей создано")

    # ── 5. Сделки ─────────────────────────────────────────────────────────────
    print("🤝  Создаём 120 сделок (60 завершённых, 60 активных)…")

    used_pairs: set[frozenset[int]] = set()
    pairs: list[tuple[User, User]] = []

    attempts = 0
    while len(pairs) < 120 and attempts < 5000:
        attempts += 1
        a = random.choice(users)
        b = random.choice(users)
        if a.id == b.id:
            continue
        key = frozenset([a.id, b.id])
        if key in used_pairs:
            continue
        used_pairs.add(key)
        pairs.append((a, b))

    completed = 0
    active = 0

    for idx, (ua, ub) in enumerate(pairs):
        is_done = idx < 60
        base_dt = datetime.now(UTC) - timedelta(days=random.randint(7, 90))

        started_at = base_dt + timedelta(days=random.randint(1, 4))
        completed_at = started_at + timedelta(days=random.randint(3, 20)) if is_done else None

        ex = Exchange(
            initiator_id=ua.id,
            listing_id=None,
            status=ExchangeStatus.completed if is_done else ExchangeStatus.active,
            is_chain=False,
            started_by_initiator=True,
            started_by_partner=True,
            started_at=started_at,
            completed_by_initiator=is_done,
            completed_by_partner=is_done,
            completed_at=completed_at,
        )
        db.add(ex)
        await db.flush()

        # Устанавливаем created_at задним числом
        await db.execute(
            text("UPDATE exchanges SET created_at = :dt WHERE id = :id"),
            {"dt": base_dt, "id": ex.id},
        )

        db.add(ExchangeParticipant(exchange_id=ex.id, user_id=ua.id))
        db.add(ExchangeParticipant(exchange_id=ex.id, user_id=ub.id))

        # Чат
        chat = Chat(exchange_id=ex.id)
        db.add(chat)
        await db.flush()

        # Сообщения
        for m_idx in range(random.randint(4, 10)):
            sender = ua if m_idx % 2 == 0 else ub
            db.add(
                Message(
                    chat_id=chat.id,
                    sender_id=sender.id,
                    content=random.choice(CHAT_MESSAGES),
                )
            )

        # Отзывы для завершённых
        if is_done:
            r_a = random.randint(3, 5)
            r_b = random.randint(3, 5)
            pool_a = REVIEW_POSITIVE if r_a >= 4 else REVIEW_NEUTRAL
            pool_b = REVIEW_POSITIVE if r_b >= 4 else REVIEW_NEUTRAL
            db.add(
                Review(
                    exchange_id=ex.id,
                    reviewer_id=ua.id,
                    reviewed_id=ub.id,
                    rating=r_a,
                    comment=random.choice(pool_a),
                )
            )
            db.add(
                Review(
                    exchange_id=ex.id,
                    reviewer_id=ub.id,
                    reviewed_id=ua.id,
                    rating=r_b,
                    comment=random.choice(pool_b),
                )
            )
            completed += 1
        else:
            active += 1

        await db.flush()

    print(f"   ✓ {completed} завершённых, {active} активных")

    # ── 6. Пересчёт рейтингов ─────────────────────────────────────────────────
    print("⭐  Пересчитываем рейтинги пользователей…")
    rows = list(
        await db.execute(
            select(Review.reviewed_id, func.avg(Review.rating).label("avg")).group_by(
                Review.reviewed_id
            )
        )
    )
    for row in rows:
        u = await db.get(User, row.reviewed_id)
        if u:
            u.rating = round(float(row.avg), 2)

    await db.flush()
    print(f"   ✓ Обновлено рейтингов: {len(rows)}")

    # ── Итог ──────────────────────────────────────────────────────────────────
    print()
    print("=" * 52)
    print("✅  База заполнена!")
    print()
    print("  🔑 Администратор:")
    print("     Email:   admin@skillshare.dev")
    print("     Пароль:  admin12345")
    print()
    print("  👤 Тестовые аккаунты (200 штук):")
    print("     Email:   user1@test.dev … user200@test.dev")
    print("     Пароль:  testpass123")
    print("=" * 52)


async def main() -> None:
    async with Session() as db, db.begin():
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
