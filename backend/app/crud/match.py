from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exchange, ExchangeStatus, ListingInterest, ListingInterestStatus
from app.models.review import Review
from app.models.skill import Skill, UserSkillsOffered, UserSkillsWanted
from app.models.user import User
from app.schemas.match import MatchResult, ScoreBreakdown, SkillMatch

# Максимальное количество обменов для нормализации репутации
MAX_EXCHANGES_FOR_REPUTATION = 200


async def find_matches(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> list[MatchResult]:
    # Навыки текущего пользователя
    my_offered_rows = list(
        await db.execute(
            select(UserSkillsOffered.skill_id, UserSkillsOffered.level).where(
                UserSkillsOffered.user_id == user_id
            )
        )
    )
    my_offered: dict[int, int] = {r.skill_id: r.level for r in my_offered_rows}

    my_wanted_rows = list(
        await db.execute(
            select(UserSkillsWanted.skill_id, UserSkillsWanted.desired_level).where(
                UserSkillsWanted.user_id == user_id
            )
        )
    )
    my_wanted: dict[int, int] = {r.skill_id: r.desired_level for r in my_wanted_rows}

    if not my_wanted:
        return []

    my_wanted_ids = list(my_wanted.keys())
    my_offered_ids = list(my_offered.keys())

    # Поиск кандидатов

    # предлагает ли этот кандидат навыки которые я хочу?
    offers_what_i_want = (
        select(UserSkillsOffered.user_id)
        .where(
            UserSkillsOffered.user_id == User.id,
            UserSkillsOffered.skill_id.in_(my_wanted_ids),
        )
        .correlate(User)
        .exists()
    )

    # Условия попадания в кандидаты
    conditions = [
        User.id != user_id,
        User.is_deleted.is_(False),
        offers_what_i_want,
    ]

    # хочет ли этот кандидат навыки которые я предлагаю?
    if my_offered_ids:
        wants_what_i_offer = (
            select(UserSkillsWanted.user_id)
            .where(
                UserSkillsWanted.user_id == User.id,
                UserSkillsWanted.skill_id.in_(my_offered_ids),
            )
            .correlate(User)
            .exists()
        )
        conditions.append(wants_what_i_offer)

    # Берём кандидатов прошедших SQL-фильтры; 500 — защита от взрыва при большой БД.
    # Финальный limit применяем в конце после score-фильтрации и дедупа по категориям.
    candidates: list[User] = list(await db.scalars(select(User).where(*conditions).limit(500)))
    if not candidates:
        return []

    candidate_ids = [c.id for c in candidates]

    # Пакетная загрузка навыков кандидатов
    c_offered_rows = list(
        await db.execute(
            select(
                UserSkillsOffered.user_id,
                UserSkillsOffered.skill_id,
                UserSkillsOffered.level,
            ).where(UserSkillsOffered.user_id.in_(candidate_ids))
        )
    )
    candidate_offers: dict[int, dict[int, int]] = {}
    for r in c_offered_rows:
        if r.user_id not in candidate_offers:
            candidate_offers[r.user_id] = {}
        candidate_offers[r.user_id][r.skill_id] = r.level

    c_wanted_rows = list(
        await db.execute(
            select(
                UserSkillsWanted.user_id,
                UserSkillsWanted.skill_id,
                UserSkillsWanted.desired_level,
            ).where(UserSkillsWanted.user_id.in_(candidate_ids))
        )
    )
    candidate_wanted: dict[int, dict[int, int]] = {}
    for r in c_wanted_rows:
        if r.user_id not in candidate_wanted:
            candidate_wanted[r.user_id] = {}
        candidate_wanted[r.user_id][r.skill_id] = r.desired_level

    # Загружаем имена всех задействованных навыков одним запросом
    all_skill_ids = (
        set(my_wanted_ids)
        | set(my_offered_ids)
        | {r.skill_id for r in c_offered_rows}
        | {r.skill_id for r in c_wanted_rows}
    )
    skill_name_rows = list(
        await db.execute(
            select(Skill.id, Skill.name, Skill.category_id).where(Skill.id.in_(all_skill_ids))
        )
    )
    skill_names: dict[int, str] = {r.id: r.name for r in skill_name_rows}
    skill_categories_id: dict[int, int] = {r.id: r.category_id for r in skill_name_rows}

    # Отзывы кандидатов
    review_rows = list(
        await db.execute(
            select(Review.reviewed_id, Review.rating).where(
                Review.reviewed_id.in_(candidate_ids),
                Review.is_deleted.is_(False),
                Review.is_hidden.is_(False),
            )
        )
    )
    candidate_reviews: dict[int, list[int]] = {}
    for r in review_rows:
        if r.reviewed_id not in candidate_reviews:
            candidate_reviews[r.reviewed_id] = []
        candidate_reviews[r.reviewed_id].append(r.rating)

    # Количество завершённых обменов (инициатор + участник)
    initiator_rows = list(
        await db.execute(
            select(Exchange.initiator_id, func.count().label("cnt"))
            .where(
                Exchange.initiator_id.in_(candidate_ids),
                Exchange.status == ExchangeStatus.completed,
                Exchange.is_deleted.is_(False),
            )
            .group_by(Exchange.initiator_id)
        )
    )
    exchange_counts: dict[int, int] = {r.initiator_id: r.cnt for r in initiator_rows}

    participant_rows = list(
        await db.execute(
            select(ListingInterest.responder_id, func.count().label("cnt"))
            .join(Exchange, Exchange.listing_id == ListingInterest.listing_id)
            .where(
                ListingInterest.responder_id.in_(candidate_ids),
                ListingInterest.status == ListingInterestStatus.accepted,
                Exchange.status == ExchangeStatus.completed,
                Exchange.is_deleted.is_(False),
            )
            .group_by(ListingInterest.responder_id)
        )
    )
    for r in participant_rows:
        exchange_counts[r.responder_id] = exchange_counts.get(r.responder_id, 0) + r.cnt

    # Антифрод: получаем список фродовых пользователей
    fraudulent_rows = list(
        await db.scalars(
            select(User.id).where(
                User.id.in_(candidate_ids),
                User.is_fraudulent.is_(True),
            )
        )
    )
    fraudulent_user_ids: frozenset[int] = frozenset(fraudulent_rows)

    scored: list[tuple[float, int, MatchResult]] = []

    for candidate in candidates:
        cid = candidate.id
        if cid in fraudulent_user_ids:
            continue

        c_offered = candidate_offers.get(cid, {})
        c_wanted = candidate_wanted.get(cid, {})

        # Жёсткий фильтр: кандидат должен покрывать ≥50% моих желаемых навыков
        matched_for_me = set(c_offered.keys()) & set(my_wanted.keys())
        coverage = len(matched_for_me) / len(my_wanted)
        if coverage < 0.5:
            continue

        # S_навыки
        A = coverage
        matched_for_him = set(my_offered.keys()) & set(c_wanted.keys())
        B = len(matched_for_him) / len(c_wanted) if c_wanted else 0.0
        s_skills = A * 0.6 + B * 0.4

        # S_уровень
        level_scores: list[float] = []
        for skill_id in matched_for_me:
            level_scores.append(1.0 - abs(c_offered[skill_id] - my_wanted[skill_id]) / 3.0)
        s_level = sum(level_scores) / len(level_scores) if level_scores else 0.0

        # S_активность
        last_active = candidate.last_active_at
        if last_active is None:
            s_activity = 0.5
        else:
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=UTC)
            days_passed = (datetime.now(UTC) - last_active).days
            s_activity = math.exp(-days_passed / 30)

        # S_репутация
        reviews = candidate_reviews.get(cid, [])
        if not reviews:
            s_reputation = 0.5
        else:
            n = len(reviews)
            avg_rating = sum(reviews) / n
            rating_norm = avg_rating / 5.0
            if n < 5:
                rating_norm -= (5 - n) / 5 * 0.2
                rating_norm = max(0.0, rating_norm)

            exp_count = exchange_counts.get(cid, 0)
            exp_norm = math.log(1 + exp_count) / math.log(MAX_EXCHANGES_FOR_REPUTATION + 1)

            positive = sum(1 for r in reviews if r >= 4)
            pos_share = positive / n
            if n < 10:
                pos_share = pos_share * 0.8 + 0.18

            s_reputation = 0.4 * rating_norm + 0.3 * exp_norm + 0.3 * pos_share

        core_score = s_skills**1.4 * s_level**0.9 * s_activity**0.5 * s_reputation**0.8

        exp_count = exchange_counts.get(cid, 0)
        final_score = core_score
        if exp_count < 3:
            created = candidate.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            days_since_reg = (datetime.now(UTC) - created).days
            bonus = 0.1 * max(0.0, 1.0 - days_since_reg / 30.0)
            final_score *= 1.0 + bonus

        completeness = [
            bool(candidate.full_name),
            bool(candidate.avatar_url),
            bool(c_offered),
            bool(c_wanted),
        ]
        if sum(completeness) / 4 < 0.5:
            final_score *= 0.85

        final_score = min(final_score, 1.0)

        # Формируем списки навыков для схемы
        skills_i_get: list[SkillMatch] = [
            SkillMatch(
                skill_id=sid,
                skill_name=skill_names.get(sid, ""),
                offered_level=c_offered[sid],
                desired_level=my_wanted.get(sid),
            )
            for sid in sorted(matched_for_me)
        ]
        skills_i_give: list[SkillMatch] = [
            SkillMatch(
                skill_id=sid,
                skill_name=skill_names.get(sid, ""),
                offered_level=my_offered[sid],
                desired_level=c_wanted.get(sid),
            )
            for sid in sorted(matched_for_him)
        ]

        score_breakdown = ScoreBreakdown(
            s_skills=round(s_skills, 4),
            s_level=round(s_level, 4),
            s_activity=round(s_activity, 4),
            s_reputation=round(s_reputation, 4),
            core_score=round(core_score, 4),
            final_score=round(final_score, 4),
        )

        primary_skill_id = next(iter(matched_for_me))
        category_id = skill_categories_id.get(primary_skill_id)

        result = MatchResult(
            user_id=cid,
            full_name=candidate.full_name,
            avatar_url=candidate.avatar_url,
            score=score_breakdown,
            skills_i_get=skills_i_get,
            skills_i_give=skills_i_give,
        )
        scored.append((final_score, category_id, result))

    def sort_key(item: tuple[float, int | None, MatchResult]) -> float:
        return item[0]

    # Фильтр по минимальному порогу и сортировка
    scored = [(s, cat, r) for s, cat, r in scored if s >= 0.2]
    scored.sort(key=sort_key, reverse=True)

    # Дедупликация по категориям: не более 5 кандидатов из одной категории
    category_counts: dict[int | None, int] = {}
    final: list[MatchResult] = []

    for _final_score, category_id, result in scored:
        cnt = category_counts.get(category_id, 0)
        if cnt < 5:
            final.append(result)
            category_counts[category_id] = cnt + 1

    return final[:limit]
