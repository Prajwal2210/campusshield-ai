"""
Preservation Property Tests (Task 2 / Property 2).

These tests verify that non-config module behaviors are unchanged before
and after the fix is applied. They use only modules that do NOT have a
hard dependency on backend.config at collection time.

Property 2a: Feature extraction completeness
  For all non-empty lists of packet dicts, extract_features_from_window
  returns a dict with exactly len(FEATURE_NAMES) float values and never raises.

Property 2b: Tenant isolation universality
  For any pair of distinct tenant IDs, CRUD queries for one tenant never
  return rows belonging to the other.

These tests pass on UNFIXED code (no .env required) because the modules
under test do not import backend.config.
After the fix, they must continue to pass — confirming zero regressions.
"""

import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.features.extractor import extract_features_from_window, FEATURE_NAMES
from backend.database import crud
from backend.database.models import Base, Tenant, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_packet(timestamp=None, size=200, protocol="TCP", dst_port=80,
                 src_ip="10.0.0.1", dst_ip="192.168.1.1"):
    return {
        "index": 0,
        "timestamp": timestamp or time.time(),
        "size": size,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": 12345,
        "dst_port": dst_port,
        "protocol": protocol,
        "ip_len": size - 14,
        "ttl": 64,
        "tcp_flags": "PA" if protocol == "TCP" else None,
        "payload_size": max(0, size - 40),
        "payload_bytes": b"Hello World " * 10,
    }


def _make_in_memory_db():
    """Create a fresh in-memory SQLite database for isolation tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session()


# ---------------------------------------------------------------------------
# Property 2a: Feature extraction completeness
# ---------------------------------------------------------------------------

class TestFeatureExtractionPreservation:
    """
    Feature extraction must return exactly len(FEATURE_NAMES) float values
    for any non-empty packet list, and never raise an exception.
    """

    def test_single_packet_returns_all_feature_names(self):
        pkt = _make_packet()
        features = extract_features_from_window([pkt])
        assert set(features.keys()) == set(FEATURE_NAMES)
        assert len(features) == len(FEATURE_NAMES)

    def test_all_values_are_floats(self):
        packets = [_make_packet(timestamp=time.time() + i * 0.01) for i in range(10)]
        features = extract_features_from_window(packets)
        for name, value in features.items():
            assert isinstance(value, float), f"Feature {name!r} is not float: {type(value)}"

    def test_never_raises_for_various_packet_counts(self):
        for n in [1, 2, 5, 10, 50, 100]:
            packets = [_make_packet(timestamp=time.time() + i * 0.01) for i in range(n)]
            # Must not raise
            features = extract_features_from_window(packets)
            assert len(features) == len(FEATURE_NAMES)

    def test_empty_packet_list_returns_zeros(self):
        features = extract_features_from_window([])
        assert set(features.keys()) == set(FEATURE_NAMES)
        assert all(v == 0.0 for v in features.values())

    def test_mixed_protocols_produce_valid_features(self):
        base = time.time()
        packets = []
        for i in range(30):
            proto = ["TCP", "UDP", "ICMP"][i % 3]
            port = 80 if proto != "ICMP" else None
            packets.append(_make_packet(timestamp=base + i * 0.01, protocol=proto, dst_port=port))
        features = extract_features_from_window(packets)
        assert set(features.keys()) == set(FEATURE_NAMES)
        assert features["protocol_entropy"] > 0  # mixed protocols have nonzero entropy

    @pytest.mark.parametrize("size", [64, 128, 512, 1024, 1500])
    def test_various_packet_sizes_do_not_raise(self, size):
        pkt = _make_packet(size=size)
        features = extract_features_from_window([pkt])
        assert len(features) == len(FEATURE_NAMES)


# ---------------------------------------------------------------------------
# Property 2b: Tenant isolation universality
# ---------------------------------------------------------------------------

class TestTenantIsolationPreservation:
    """
    CRUD queries for one tenant must never return rows belonging to another.
    Extends test_tenant_isolation.py with additional cross-tenant combinations.
    """

    @pytest.mark.parametrize("tid_a,tid_b", [
        ("tenant-alpha", "tenant-beta"),
        ("org-university", "org-hospital"),
        ("t1", "t2"),
        ("tenant-00000000", "tenant-11111111"),
    ])
    def test_sessions_are_isolated_between_tenant_pairs(self, tid_a, tid_b):
        engine, db = _make_in_memory_db()
        try:
            db.add_all([
                Tenant(id=tid_a, name=f"Tenant {tid_a}"),
                Tenant(id=tid_b, name=f"Tenant {tid_b}"),
                User(tenant_id=tid_a, username=f"user-{tid_a}", email=f"{tid_a}@test.local", hashed_password="x"),
                User(tenant_id=tid_b, username=f"user-{tid_b}", email=f"{tid_b}@test.local", hashed_password="x"),
            ])
            db.commit()

            session_a = crud.create_session(db, "Analysis A", "simulation", tenant_id=tid_a)
            session_b = crud.create_session(db, "Analysis B", "simulation", tenant_id=tid_b)

            # A cannot see B's session
            assert crud.get_session(db, session_b.id, tenant_id=tid_a) is None
            # B cannot see A's session
            assert crud.get_session(db, session_a.id, tenant_id=tid_b) is None
            # A's list does not contain B's session
            a_sessions = [s.id for s in crud.list_sessions(db, tenant_id=tid_a)]
            assert session_b.id not in a_sessions
            assert session_a.id in a_sessions
        finally:
            db.close()
            engine.dispose()

    @pytest.mark.parametrize("tid_a,tid_b", [
        ("tenant-alpha", "tenant-beta"),
        ("org-university", "org-hospital"),
    ])
    def test_alerts_are_isolated_between_tenant_pairs(self, tid_a, tid_b):
        engine, db = _make_in_memory_db()
        try:
            db.add_all([
                Tenant(id=tid_a, name=f"Tenant {tid_a}"),
                Tenant(id=tid_b, name=f"Tenant {tid_b}"),
            ])
            db.commit()

            session_a = crud.create_session(db, "Analysis A", "simulation", tenant_id=tid_a)
            session_b = crud.create_session(db, "Analysis B", "simulation", tenant_id=tid_b)
            alert_a = crud.create_alert(db, session_id=session_a.id, tenant_id=tid_a,
                                        title="Alert A", severity="HIGH", threat_score=85.0)
            alert_b = crud.create_alert(db, session_id=session_b.id, tenant_id=tid_b,
                                        title="Alert B", severity="LOW", threat_score=20.0)

            # A cannot see B's alert
            assert crud.get_alert(db, alert_b.id, tenant_id=tid_a) is None
            # B cannot see A's alert
            assert crud.get_alert(db, alert_a.id, tenant_id=tid_b) is None
            # List isolation
            assert crud.list_alerts(db, tenant_id=tid_a) != []
            b_alert_ids = [a.id for a in crud.list_alerts(db, tenant_id=tid_b)]
            assert alert_a.id not in b_alert_ids

        finally:
            db.close()
            engine.dispose()

    def test_reports_are_isolated_between_tenants(self):
        tid_a, tid_b = "tenant-x", "tenant-y"
        engine, db = _make_in_memory_db()
        try:
            db.add_all([
                Tenant(id=tid_a, name="Tenant X"),
                Tenant(id=tid_b, name="Tenant Y"),
            ])
            db.commit()

            session_a = crud.create_session(db, "Analysis A", "simulation", tenant_id=tid_a)
            report_a = crud.create_report(db, session_id=session_a.id, tenant_id=tid_a, file_path="a.pdf")

            # B cannot see A's report
            assert crud.get_report(db, report_a.id, tenant_id=tid_b) is None
        finally:
            db.close()
            engine.dispose()


# ---------------------------------------------------------------------------
# Property: Schema idempotency (no live DB required)
# ---------------------------------------------------------------------------

class TestSchemaIdempotency:
    """
    Calling Base.metadata.create_all() multiple times on the same engine
    must not raise an exception or destroy existing data.
    """

    def test_create_all_is_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        # First call creates tables
        Base.metadata.create_all(engine)
        # Second call must be a no-op (not raise, not drop tables)
        Base.metadata.create_all(engine)
        engine.dispose()

    def test_data_survives_second_create_all(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            db.add(Tenant(id="tenant-persist", name="Persistent Tenant"))
            db.commit()
            # Second create_all
            Base.metadata.create_all(engine)
            # Data must still be there
            found = db.query(Tenant).filter_by(id="tenant-persist").first()
            assert found is not None
            assert found.name == "Persistent Tenant"
        finally:
            db.close()
            engine.dispose()
