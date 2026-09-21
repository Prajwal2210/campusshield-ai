"""
CampusShield AI — DynamoDB Data Model & Schema Definition
==========================================================
Specifies single-table DynamoDB layout and entity serialization helpers.
Aligned with KIRO-SPECIFICATION.md section 9.

Key Structure:
--------------
Table Name: CampusShieldSaaS (or set via DYNAMODB_TABLE_NAME)
Partition Key (PK): String
Sort Key (SK): String

Global Secondary Indexes (GSIs):
--------------------------------
GSI1: PK=GSI1PK, SK=GSI1SK (Query entities by Status / Severity / Type)

Entity Layouts:
---------------
Tenant:   PK = TENANT#<tenant_id>,            SK = METADATA
User:     PK = TENANT#<tenant_id>,            SK = USER#<username>,   GSI1PK = USER#<username>, GSI1SK = TENANT#<tenant_id>
Session:  PK = TENANT#<tenant_id>,            SK = SESSION#<session_id>, GSI1PK = STATUS#<status>, GSI1SK = CREATED#<created_at>
Alert:    PK = TENANT#<tenant_id>,            SK = ALERT#<alert_id>,     GSI1PK = SEVERITY#<severity>, GSI1SK = CREATED#<created_at>
Report:   PK = TENANT#<tenant_id>,            SK = REPORT#<report_id>
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any

TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "CampusShieldSaaS")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def get_tenant_pk(tenant_id: str) -> str:
    return f"TENANT#{tenant_id or 'tenant-default'}"


def serialize_tenant(tenant_id: str, name: str, plan: str = "enterprise") -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "PK": get_tenant_pk(tenant_id),
        "SK": "METADATA",
        "EntityType": "Tenant",
        "tenantId": tenant_id,
        "name": name,
        "plan": plan,
        "isActive": True,
        "createdAt": now,
    }


def serialize_user(user: Any) -> Dict[str, Any]:
    now = user.created_at.isoformat() if hasattr(user.created_at, 'isoformat') else str(user.created_at)
    tenant_id = getattr(user, 'tenant_id', 'tenant-default')
    return {
        "PK": get_tenant_pk(tenant_id),
        "SK": f"USER#{user.username}",
        "GSI1PK": f"USER#{user.username}",
        "GSI1SK": f"TENANT#{tenant_id}",
        "EntityType": "User",
        "userId": user.id,
        "tenantId": tenant_id,
        "username": user.username,
        "email": user.email,
        "fullName": user.full_name,
        "role": user.role,
        "isActive": user.is_active,
        "createdAt": now,
    }


def serialize_session(session: Any) -> Dict[str, Any]:
    created_at = session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else str(session.created_at)
    tenant_id = getattr(session, 'tenant_id', 'tenant-default')
    return {
        "PK": get_tenant_pk(tenant_id),
        "SK": f"SESSION#{session.id}",
        "GSI1PK": f"STATUS#{session.status.upper()}",
        "GSI1SK": f"CREATED#{created_at}",
        "EntityType": "TrafficSession",
        "sessionId": session.id,
        "tenantId": tenant_id,
        "name": session.name,
        "sourceType": session.source_type,
        "scenario": session.scenario,
        "packetCount": session.packet_count,
        "flowCount": session.flow_count,
        "durationSeconds": session.duration_seconds,
        "status": session.status,
        "trafficStats": session.traffic_stats,
        "createdAt": created_at,
    }


def serialize_alert(alert: Any) -> Dict[str, Any]:
    created_at = alert.created_at.isoformat() if hasattr(alert.created_at, 'isoformat') else str(alert.created_at)
    tenant_id = getattr(alert, 'tenant_id', 'tenant-default')
    return {
        "PK": get_tenant_pk(tenant_id),
        "SK": f"ALERT#{alert.id}",
        "GSI1PK": f"SEVERITY#{alert.severity.upper()}",
        "GSI1SK": f"CREATED#{created_at}",
        "EntityType": "Alert",
        "alertId": alert.id,
        "tenantId": tenant_id,
        "sessionId": alert.session_id,
        "title": alert.title,
        "description": alert.description,
        "severity": alert.severity,
        "threatCategory": alert.threat_category,
        "threatScore": alert.threat_score,
        "confidence": alert.confidence,
        "status": alert.status,
        "createdAt": created_at,
    }


def serialize_report(report: Any) -> Dict[str, Any]:
    created_at = report.created_at.isoformat() if hasattr(report.created_at, 'isoformat') else str(report.created_at)
    tenant_id = getattr(report, 'tenant_id', 'tenant-default')
    return {
        "PK": get_tenant_pk(tenant_id),
        "SK": f"REPORT#{report.id}",
        "EntityType": "Report",
        "reportId": report.id,
        "tenantId": tenant_id,
        "sessionId": report.session_id,
        "filePath": report.file_path,
        "fileSizeBytes": report.file_size_bytes,
        "generatedBy": report.generated_by,
        "createdAt": created_at,
    }
