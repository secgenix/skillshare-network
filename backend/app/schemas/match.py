from pydantic import BaseModel, ConfigDict


class SkillMatch(BaseModel):
    skill_id: int
    skill_name: str
    offered_level: int
    desired_level: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ScoreBreakdown(BaseModel):
    s_skills: float
    s_level: float
    s_activity: float
    s_reputation: float
    core_score: float
    final_score: float


class MatchResult(BaseModel):
    user_id: int
    full_name: str | None = None
    avatar_url: str | None = None
    score: ScoreBreakdown
    skills_i_get: list[SkillMatch]
    skills_i_give: list[SkillMatch]

    model_config = ConfigDict(from_attributes=True)


class MatchResponse(BaseModel):
    results: list[MatchResult]
    total: int
