from pathlib import Path

import pytest

from app.recommender import RecommendationEngine


@pytest.fixture
def engine(tmp_path: Path):
    return RecommendationEngine("book1-100k.csv", str(tmp_path / "state.json"))


def test_loads_dataset(engine):
    assert len(engine.items) > 1000


def test_create_user_and_update_preferences(engine):
    user = engine.add_user("u1", "Ana", {"1": 5.0})
    assert user["name"] == "Ana"
    updated = engine.update_preferences("u1", {"2": 4.0})
    assert updated["preferences"] == {"1": 5.0, "2": 4.0}


def test_recommendations_return_unique_unrated_items(engine):
    engine.add_user("u2", "Bruno", {"1": 5.0, "2": 4.0})
    recommendations = engine.recommend("u2", 5)
    assert len(recommendations) == 5
    assert "1" not in {item["id"] for item in recommendations}
    assert len({item["id"] for item in recommendations}) == 5


def test_invalid_rating_is_rejected(engine):
    engine.add_user("u3", "Carla")
    with pytest.raises(ValueError):
        engine.update_preferences("u3", {"1": 8.0})
