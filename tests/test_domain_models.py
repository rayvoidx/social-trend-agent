from datetime import datetime, timedelta

from backend.domain import (
    Creator,
    CreatorPlatform,
    Insight,
    InsightRepository,
    InsightSource,
    Mission,
    MissionRepository,
    MissionStatus,
    Reward,
    RewardRepository,
    RewardStatus,
)


def test_mission_date_validation():
    start = datetime.utcnow()
    end = start + timedelta(days=1)
    mission = Mission(
        id="m1",
        title="Test Mission",
        description="Desc",
        expected_start=start,
        expected_end=end,
    )
    assert mission.expected_end >= mission.expected_start  # type: ignore[operator]


def test_mission_is_active():
    now = datetime.utcnow()
    mission = Mission(
        id="m2",
        title="Active Mission",
        description="Desc",
        status=MissionStatus.ACTIVE,
        expected_start=now - timedelta(hours=1),
        expected_end=now + timedelta(hours=1),
    )
    assert mission.is_active(now) is True


def test_creator_repository_platform_filter():
    from backend.domain import CreatorRepository

    repo = CreatorRepository()
    c1 = Creator(
        id="c1",
        name="Creator 1",
        primary_platform=CreatorPlatform.YOUTUBE,
        platforms=[CreatorPlatform.YOUTUBE],
    )
    c2 = Creator(
        id="c2",
        name="Creator 2",
        primary_platform=CreatorPlatform.INSTAGRAM,
        platforms=[CreatorPlatform.INSTAGRAM],
    )
    repo.create(c1)
    repo.create(c2)

    youtube_creators = repo.list_by_platform(CreatorPlatform.YOUTUBE)
    assert len(youtube_creators) == 1
    assert youtube_creators[0].id == "c1"


def test_insight_repository_basic_crud():
    repo = InsightRepository()
    ins = Insight(
        id="i1",
        source=InsightSource.NEWS_TREND,
        query="AI",
    )
    repo.create(ins)

    fetched = repo.get("i1")
    assert fetched is not None
    assert isinstance(fetched, Insight)
    assert fetched.id == "i1"

    items = repo.list_by_source(InsightSource.NEWS_TREND)
    assert len(items) == 1
    assert items[0].id == "i1"


def test_reward_mark_paid_and_repository_filter():
    repo = RewardRepository()
    reward = Reward(
        id="r1",
        mission_id="m1",
        creator_id="c1",
        amount=100.0,
        currency="KRW",
    )
    repo.create(reward)
    rewards_for_mission = repo.list_by_mission("m1")
    assert len(rewards_for_mission) == 1
    assert rewards_for_mission[0].status == RewardStatus.PENDING

    reward.mark_paid()
    assert reward.status == RewardStatus.PAID


