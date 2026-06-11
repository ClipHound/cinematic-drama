from drama_agent.memory.embeddings import stable_embedding
from drama_agent.memory.schemas import Character
from drama_agent.memory.vectors import VectorStore, character_vector_text, point_uuid


def test_stable_embedding_is_deterministic_and_normalized() -> None:
    first = stable_embedding("主角 隐藏高手", 16)
    second = stable_embedding("主角 隐藏高手", 16)

    assert first == second
    assert len(first) == 16
    assert abs(sum(value * value for value in first) - 1.0) < 0.000001


def test_character_vector_text_and_point_uuid_are_stable() -> None:
    character = Character(
        id="char-1",
        name="主角A",
        aliases=["公子A"],
        description="隐藏高手",
        first_seen=1,
    )

    assert "公子A" in character_vector_text(character)
    assert point_uuid("char-1") == point_uuid("char-1")


def test_vector_store_local_qdrant_searches_character(tmp_path) -> None:
    vectors = VectorStore(
        project_id="demo",
        qdrant_path=tmp_path / "qdrant",
        embed_endpoint="",
        vector_size=64,
    )
    character = Character(
        id="char-example",
        name="主角B",
        aliases=["侯府公子"],
        description="隐藏高手 纨绔",
        first_seen=1,
    )

    vectors.sync_character(character)
    hits = vectors.search_characters("侯府 公子", limit=3)
    vectors.close()

    assert hits
    assert hits[0].payload["id"] == "char-example"
