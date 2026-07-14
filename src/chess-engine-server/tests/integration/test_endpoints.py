"""Integration tests for the engine service HTTP endpoints.

Requires the chess-engine-server to be running at ENGINE_SERVICE_URL
(set via env var; defaults to http://localhost:8001).
"""

import pytest
import httpx

pytestmark = pytest.mark.asyncio


class TestHealthz:
    async def test_returns_200(self, async_client: httpx.AsyncClient):
        r = await async_client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAnalyzeGame:
    async def test_returns_plies_list(
        self, async_client: httpx.AsyncClient, scholars_mate_pgn: str
    ):
        r = await async_client.post(
            "/analyze/game",
            json={"pgn": scholars_mate_pgn, "student_color": "white"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "plies" in body
        assert isinstance(body["plies"], list)
        assert len(body["plies"]) == 4  # Scholar's Mate = 4 plies

    async def test_ply_schema(
        self, async_client: httpx.AsyncClient, scholars_mate_pgn: str
    ):
        r = await async_client.post(
            "/analyze/game",
            json={"pgn": scholars_mate_pgn, "student_color": "white"},
        )
        ply = r.json()["plies"][0]
        required = {"ply", "san", "uci", "fen_before", "fen_after", "eval_before_cp", "eval_after_cp"}
        assert required.issubset(ply.keys())

    async def test_cp_loss_sign_white(
        self, async_client: httpx.AsyncClient, scholars_mate_pgn: str
    ):
        """Student=white → cp_loss set on odd plies, always >= 0."""
        r = await async_client.post(
            "/analyze/game",
            json={"pgn": scholars_mate_pgn, "student_color": "white"},
        )
        plies = r.json()["plies"]
        for p in plies:
            if p["cp_loss"] is not None:
                assert p["cp_loss"] >= 0
                assert p["ply"] % 2 == 1

    async def test_cp_loss_sign_black(
        self, async_client: httpx.AsyncClient, scholars_mate_pgn: str
    ):
        """Student=black → cp_loss set on even plies, always >= 0."""
        r = await async_client.post(
            "/analyze/game",
            json={"pgn": scholars_mate_pgn, "student_color": "black"},
        )
        plies = r.json()["plies"]
        for p in plies:
            if p["cp_loss"] is not None:
                assert p["cp_loss"] >= 0
                assert p["ply"] % 2 == 0

    async def test_maia_null_when_disabled(
        self, async_client: httpx.AsyncClient, scholars_mate_pgn: str
    ):
        """When ENABLE_MAIA=false (default in docker-compose.test.yml), maia is null."""
        r = await async_client.post(
            "/analyze/game",
            json={"pgn": scholars_mate_pgn, "student_color": "white"},
        )
        plies = r.json()["plies"]
        for p in plies:
            assert p["maia"] is None

    async def test_invalid_pgn_returns_422(self, async_client: httpx.AsyncClient):
        r = await async_client.post(
            "/analyze/game",
            json={"pgn": "not a pgn", "student_color": "white"},
        )
        assert r.status_code == 422


class TestAnalyzePosition:
    START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    async def test_returns_expected_schema(self, async_client: httpx.AsyncClient):
        r = await async_client.post(
            "/analyze/position",
            json={"fen": self.START_FEN},
        )
        assert r.status_code == 200
        body = r.json()
        assert "eval_cp" in body
        assert "best_move_san" in body
        assert "best_line_san" in body
        assert "maia" in body

    async def test_start_position_eval_near_zero(self, async_client: httpx.AsyncClient):
        r = await async_client.post(
            "/analyze/position",
            json={"fen": self.START_FEN},
        )
        assert abs(r.json()["eval_cp"]) < 100
