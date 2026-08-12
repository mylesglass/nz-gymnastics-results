import json
import os
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, LongScore
from app import repair_identities as ri
from app.repair_identities import (
    _build_source_consensus,
    _clean_id,
    _repair_rows,
    set_data_dir,
)


def _setup_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)
    return db_path, engine, TestSession


def _seed(session, rows: list[dict]):
    for r in rows:
        session.add(LongScore(**r))
    session.commit()


BASE = {"discipline": "WAG", "pass_number": 1, "apparatus": "VT", "event_id": 1, "event_name": "E1"}


def _write_source(tmpdir: str, participants: list[dict]):
    """Write a minimal source JSON with eventOrganizations + eventParticipants."""
    data = {
        "eventOrganizations": [{"_id": "o1", "name": "OMNI Gymnastic Centre"}],
        "eventParticipants": participants,
    }
    path = Path(tmpdir) / "evt.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class _TempSourceDir:
    """Context manager that points repair_identities at a temp source dir."""

    def __init__(self):
        self._original = ri._DATA_DIR
        self.dir = Path(tempfile.mkdtemp())

    def write(self, name: str, identifier: str, club: str = "OMNI Gymnastic Centre", tag: str = ""):
        data = {
            "eventOrganizations": [{"_id": "o1", "name": club}],
            "eventParticipants": [{"name": name, "identifier": identifier, "organizationId": "o1"}],
        }
        path = self.dir / f"{tag or name.replace(' ', '_')}_{identifier}.json"
        with open(path, "w") as f:
            json.dump(data, f)

    def write_many(self, name: str, identifier: str, n: int, club: str = "OMNI Gymnastic Centre"):
        for i in range(n):
            self.write(name, identifier, club, tag=f"{name.replace(' ', '_')}_{identifier}_{i}")

    def __enter__(self):
        set_data_dir(self.dir)
        return self

    def __exit__(self, *exc):
        set_data_dir(self._original)
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


class TestBuildSourceConsensus:
    def test_typo_loses_to_majority(self):
        # 5 files say 651229, 1 says 6511229 (a typo). Consensus must be 651229.
        with _TempSourceDir() as src:
            src.write_many("Alexandra Boys", "651229", 5)
            src.write("Alexandra Boys", "6511229")
            id_c, name_c = _build_source_consensus()
        assert id_c[("alexandra boys", "omni gymnastic centre")] == "651229"

    def test_near_tie_yields_no_consensus(self):
        # 5:3 and 3:2 splits are near-ties — winner does not reach 2x the
        # runner-up, so the key must be ABSENT from the consensus.
        with _TempSourceDir() as src:
            src.write_many("Fifty Three", "500", 5)
            src.write_many("Fifty Three", "600", 3)
            src.write_many("Three Two", "700", 3)
            src.write_many("Three Two", "800", 2)
            id_c, _ = _build_source_consensus()
        assert ("fifty three", "omni gymnastic centre") not in id_c
        assert ("three two", "omni gymnastic centre") not in id_c

    def test_clear_majority_2_to_1_applied(self):
        with _TempSourceDir() as src:
            src.write_many("Two One", "900", 2)
            src.write("Two One", "901")
            id_c, _ = _build_source_consensus()
        assert id_c[("two one", "omni gymnastic centre")] == "900"

    def test_exact_tie_no_consensus(self):
        with _TempSourceDir() as src:
            src.write("Tie Boy", "400")
            src.write("Tie Boy", "401")
            id_c, _ = _build_source_consensus()
        assert ("tie boy", "omni gymnastic centre") not in id_c

    def test_name_consensus_uses_canonical_casing(self):
        # Different source files spell the surname differently; the fixed
        # _clean_name must collapse them to one canonical spelling.
        with _TempSourceDir() as src:
            src.write_many("Amore De La Harpe", "579669", 3)
            src.write_many("Amore De la harpe", "579669", 2)
            id_c, name_c = _build_source_consensus()
        key = ("amore de la harpe", "omni gymnastic centre")
        assert name_c[key] == "Amore De La Harpe"
        assert id_c[key] == "579669"

    def test_prefix_variants_count_together(self):
        # GS-prefixed and bare identifiers are the same ID and must share votes.
        with _TempSourceDir() as src:
            src.write("Pref Boy", "GS111", tag="a")
            src.write("Pref Boy", "111", tag="b")
            src.write("Pref Boy", "222", tag="c")
            id_c, _ = _build_source_consensus()
        assert id_c[("pref boy", "omni gymnastic centre")] == "111"


class TestRepairRows:
    def test_consensus_wins_over_single_typo(self):
        # Two DB rows: one consistent across many events (651229), one source
        # typo (6511229). Consensus (5:1) must pick 651229, never the typo.
        db_path, engine, TestSession = _setup_db()
        try:
            sess = TestSession()
            _seed(sess, [
                {**BASE, "id": None, "gymnast_name": "Alexandra Boys", "gnz_id": "651229", "club_name": "Whangarei Academy of Gymnastics"},
                {**BASE, "id": None, "gymnast_name": "Alexandra Boys", "gnz_id": "6511229", "club_name": "Whangarei Academy of Gymnastics"},
            ])
            sess.close()

            id_consensus = {("alexandra boys", "whangarei academy of gymnastics"): "651229"}
            name_consensus = {("alexandra boys", "whangarei academy of gymnastics"): "Alexandra Boys"}
            sess2 = TestSession()
            stats = _repair_rows(sess2, id_consensus, name_consensus, apply=True)
            assert stats["id_fixes"] == 1  # only the typo row changes
            sess2.commit()
            sess2.close()

            sess3 = TestSession()
            rows = sess3.query(LongScore).all()
            ids = {r.gnz_id for r in rows}
            assert ids == {"651229"}  # both now the consensus ID
            sess3.close()
        finally:
            os.unlink(db_path)

    def test_splits_merged_people_by_club(self):
        # Two Madison Lynches at different clubs were merged to 249317; the
        # per-club consensus separates them.
        db_path, engine, TestSession = _setup_db()
        try:
            sess = TestSession()
            _seed(sess, [
                {**BASE, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "OMNI Gymnastic Centre"},
                {**BASE, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow Gymnastics"},
            ])
            sess.close()

            id_consensus = {
                ("madison lynch", "omni gymnastic centre"): "716561",
                ("madison lynch", "onslow gymnastics"): "249317",
            }
            sess2 = TestSession()
            stats = _repair_rows(sess2, id_consensus, {}, apply=True)
            assert stats["id_fixes"] == 1
            sess2.commit()
            sess2.close()

            sess3 = TestSession()
            rows = sess3.query(LongScore).all()
            by_club = {r.club_name: r.gnz_id for r in rows}
            assert by_club["OMNI Gymnastic Centre"] == "716561"
            assert by_club["Onslow Gymnastics"] == "249317"
            sess3.close()
        finally:
            os.unlink(db_path)

    def test_dry_run_leaves_no_trace(self):
        db_path, engine, TestSession = _setup_db()
        try:
            sess = TestSession()
            _seed(sess, [
                {**BASE, "gymnast_name": "Eva Mcewan", "gnz_id": "201094", "club_name": "HCG"},
            ])
            sess.close()

            name_consensus = {("eva mcewan", "hcg"): "Eva McEwan"}
            sess2 = TestSession()
            stats = _repair_rows(sess2, {}, name_consensus, apply=False)
            assert stats["name_fixes"] == 1
            sess2.rollback()
            sess2.close()

            sess3 = TestSession()
            row = sess3.query(LongScore).first()
            assert row.gymnast_name == "Eva Mcewan"  # unchanged
            sess3.close()
        finally:
            os.unlink(db_path)


class TestRepairIdempotency:
    def test_second_run_reports_zero(self):
        # After an apply, re-running the repair must find nothing to change.
        db_path, engine, TestSession = _setup_db()
        try:
            sess = TestSession()
            _seed(sess, [
                {**BASE, "gymnast_name": "Alexandra Boys", "gnz_id": "6511229", "club_name": "Whangarei Academy of Gymnastics"},
            ])
            sess.close()

            id_consensus = {("alexandra boys", "whangarei academy of gymnastics"): "651229"}
            sess2 = TestSession()
            first = _repair_rows(sess2, id_consensus, {}, apply=True)
            assert first["id_fixes"] == 1
            sess2.commit()
            sess2.close()

            sess3 = TestSession()
            second = _repair_rows(sess3, id_consensus, {}, apply=True)
            assert second["rows"] == 0
            assert second["id_fixes"] == 0
            sess3.rollback()
            sess3.close()
        finally:
            os.unlink(db_path)


class TestCleanId:
    def test_strips_prefixes(self):
        assert _clean_id("GS12345") == "12345"
        assert _clean_id("GNZ12345") == "12345"
        assert _clean_id("GGS12345") == "12345"

    def test_plain_numeric(self):
        assert _clean_id("12345") == "12345"

    def test_club_code_returns_empty(self):
        assert _clean_id("TRI") == ""
        assert _clean_id("ARG") == ""
