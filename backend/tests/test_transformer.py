import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.main import app

HERE = Path(__file__).resolve().parent
DATA_DIR_2025 = HERE.parent.parent / "data-collection" / "2025" / "json"
DATA_DIR_2026 = HERE.parent.parent / "data-collection" / "2026"

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)

    import app.database as db_mod

    old_engine = db_mod.engine
    old_session = db_mod.SessionLocal
    db_mod.engine = engine
    db_mod.SessionLocal = TestSession

    yield

    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


class TestApparatusFinalsAA:
    def test_csg_classic_apparatus_finals_aa_is_sum_of_round_scores(self):
        path = DATA_DIR_2025 / "csg-classic_2025.json"
        if not path.exists():
            pytest.skip("csg-classic_2025.json not found")

        with open(path, "rb") as f:
            upload_resp = client.post("/api/upload?allow_unknown=1", files={"file": ("csg-classic_2025.json", f, "application/json")})
        assert upload_resp.status_code == 200, upload_resp.text
        event_id = upload_resp.json()["id"]

        resp = client.get(f"/api/events/{event_id}/results/wide")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "wag" in data

        # Find Abby Downes in apparatus finals
        wag = data["wag"]
        finals_row = None
        for row in wag["rows"]:
            if row.get("name") == "Abby Downes" and row.get("round-type") == "Apparatus Finals":
                finals_row = row
                break

        assert finals_row is not None, "Abby Downes apparatus finals row not found"
        # She only did Floor final (12.133) — that should be her AA
        assert finals_row.get("aa-score") is not None, "aa-score should be set for apparatus finals"
        assert float(finals_row["aa-score"]) == pytest.approx(12.133, abs=0.001)
        assert finals_row.get("aa-rank") is None, "aa-rank should be null for apparatus finals"


class TestDNSPassFirst:
    """A DNS pass that sorts as pass 1 must not blank out a real pass-2 score."""

    def test_multi_day_dns_pass_does_not_hide_real_scores(self):
        path = DATA_DIR_2026 / "centrals-2026.json"
        if not path.exists():
            pytest.skip("centrals-2026.json not found")

        with open(path, "rb") as f:
            upload_resp = client.post("/api/upload?allow_unknown=1", files={"file": ("centrals-2026.json", f, "application/json")})
        assert upload_resp.status_code == 200, upload_resp.text
        event_id = upload_resp.json()["id"]

        resp = client.get(f"/api/events/{event_id}/results/wide")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "wag" in data

        row = None
        for r in data["wag"]["rows"]:
            if r.get("name") == "Cleo Bell" and r.get("round-type") == "All Around":
                row = r
                break
        assert row is not None, "Cleo Bell All Around row not found"

        # Day 2 scores must survive even though each apparatus has a DNS pass 1
        assert float(row["vt-total"]) == pytest.approx(10.9, abs=0.001)
        assert float(row["ub-total"]) == pytest.approx(10.9, abs=0.001)
        assert float(row["bb-total"]) == pytest.approx(10.65, abs=0.001)
        assert float(row["fx-total"]) == pytest.approx(11.75, abs=0.001)
        assert float(row["aa-score"]) == pytest.approx(44.2, abs=0.001)
