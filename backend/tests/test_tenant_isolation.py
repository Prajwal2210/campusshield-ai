"""Repository-level regression tests for server-enforced tenant isolation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import crud
from backend.database.models import Base, Tenant, User


def test_tenant_scoped_records_are_not_returned_to_another_tenant():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([
            Tenant(id="tenant-a", name="Tenant A"),
            Tenant(id="tenant-b", name="Tenant B"),
            User(tenant_id="tenant-a", username="a-user", email="a@example.test", hashed_password="x"),
            User(tenant_id="tenant-b", username="b-user", email="b@example.test", hashed_password="x"),
        ])
        db.commit()

        session_a = crud.create_session(db, "A analysis", "simulation", tenant_id="tenant-a")
        session_b = crud.create_session(db, "B analysis", "simulation", tenant_id="tenant-b")
        alert_a = crud.create_alert(db, session_id=session_a.id, tenant_id="tenant-a", title="A", severity="HIGH", threat_score=80)
        report_a = crud.create_report(db, session_id=session_a.id, tenant_id="tenant-a", file_path="a.pdf")

        assert crud.get_session(db, session_a.id, tenant_id="tenant-b") is None
        assert [s.id for s in crud.list_sessions(db, tenant_id="tenant-a")] == [session_a.id]
        assert crud.get_alert(db, alert_a.id, tenant_id="tenant-b") is None
        assert crud.list_alerts(db, tenant_id="tenant-b") == []
        assert crud.get_report(db, report_a.id, tenant_id="tenant-b") is None
        assert session_b.id not in [s.id for s in crud.list_sessions(db, tenant_id="tenant-a")]
    finally:
        db.close()
        engine.dispose()
