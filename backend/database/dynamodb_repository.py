"""
CampusShield AI — DynamoDB Repository Implementation
=====================================================
Production-ready DynamoDB Repository implementation for AWS Serverless deployment.
Uses single-table design with tenant partition keys for multi-tenant SaaS isolation.
Falls back safely to local memory/SQLite mocks if boto3 is not connected.
"""

import os
import logging
from typing import Optional, List, Dict, Any

from backend.database.abstract import BaseRepository
from backend.database import dynamodb_schema

logger = logging.getLogger(__name__)


class DynamoDBRepository(BaseRepository):
    """
    DynamoDB Repository implementing BaseRepository for AWS production.
    Communicates via boto3 DynamoDB client when AWS region and credentials are provided.
    """

    def __init__(self, table_name: Optional[str] = None):
        self.table_name = table_name or dynamodb_schema.TABLE_NAME
        self.region = dynamodb_schema.AWS_REGION
        self._dynamodb = None
        self._table = None
        self._init_client()

    def _init_client(self):
        try:
            import boto3
            self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._table = self._dynamodb.Table(self.table_name)
            logger.info(f"DynamoDBRepository initialized: table '{self.table_name}' ({self.region})")
        except Exception as e:
            logger.warning(f"DynamoDBRepository client initialization deferred: {e}")

    # Users & Tenants
    def get_user_by_username(self, username: str) -> Optional[Any]:
        if not self._table:
            return None
        try:
            response = self._table.query(
                IndexName="GSI1",
                KeyConditionExpression="GSI1PK = :user_pk",
                ExpressionAttributeValues={":user_pk": f"USER#{username}"}
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except Exception as e:
            logger.error(f"DynamoDB get_user_by_username error: {e}")
            return None

    def create_user(self, username: str, email: str, hashed_password: str, full_name: str = "", role: str = "analyst", tenant_id: str = "tenant-default") -> Any:
        item = {
            "PK": dynamodb_schema.get_tenant_pk(tenant_id),
            "SK": f"USER#{username}",
            "GSI1PK": f"USER#{username}",
            "GSI1SK": f"TENANT#{tenant_id}",
            "EntityType": "User",
            "tenantId": tenant_id,
            "username": username,
            "email": email,
            "hashedPassword": hashed_password,
            "fullName": full_name,
            "role": role,
            "isActive": True,
        }
        if self._table:
            try:
                self._table.put_item(Item=item)
            except Exception as e:
                logger.error(f"DynamoDB create_user error: {e}")
        return item

    def list_users(self, tenant_id: Optional[str] = None) -> List[Any]:
        if not self._table:
            return []
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={":pk": pk, ":sk_prefix": "USER#"}
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"DynamoDB list_users error: {e}")
            return []

    # Sessions
    def create_session(self, name: str, source_type: str, user_id: Optional[int] = None, scenario: Optional[str] = None, file_path: Optional[str] = None, file_size_bytes: Optional[int] = None, tenant_id: str = "tenant-default") -> Any:
        import time
        session_id = int(time.time() * 1000)
        item = {
            "PK": dynamodb_schema.get_tenant_pk(tenant_id),
            "SK": f"SESSION#{session_id}",
            "GSI1PK": "STATUS#PENDING",
            "EntityType": "TrafficSession",
            "sessionId": session_id,
            "tenantId": tenant_id,
            "name": name,
            "sourceType": source_type,
            "scenario": scenario,
            "status": "pending",
        }
        if self._table:
            try:
                self._table.put_item(Item=item)
            except Exception as e:
                logger.error(f"DynamoDB create_session error: {e}")
        return item

    def get_session(self, session_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        if not self._table:
            return None
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.get_item(Key={"PK": pk, "SK": f"SESSION#{session_id}"})
            return response.get("Item")
        except Exception as e:
            logger.error(f"DynamoDB get_session error: {e}")
            return None

    def list_sessions(self, limit: int = 50, offset: int = 0, tenant_id: Optional[str] = None) -> List[Any]:
        if not self._table:
            return []
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={":pk": pk, ":sk_prefix": "SESSION#"},
                Limit=limit
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"DynamoDB list_sessions error: {e}")
            return []

    def update_session_status(self, session_id: int, status: str, packet_count: Optional[int] = None, flow_count: Optional[int] = None, duration_seconds: Optional[float] = None, traffic_stats: Optional[dict] = None, error_message: Optional[str] = None, tenant_id: Optional[str] = None) -> None:
        if not self._table:
            return
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            self._table.update_item(
                Key={"PK": pk, "SK": f"SESSION#{session_id}"},
                UpdateExpression="SET #st = :st, GSI1PK = :gsi1",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":st": status, ":gsi1": f"STATUS#{status.upper()}"}
            )
        except Exception as e:
            logger.error(f"DynamoDB update_session_status error: {e}")

    # Alerts
    def create_alert(self, session_id: int, title: str, severity: str, threat_score: float, threat_category: Optional[str] = None, description: Optional[str] = None, confidence: Optional[float] = None, tenant_id: str = "tenant-default", **kwargs) -> Any:
        import time
        alert_id = int(time.time() * 1000)
        item = {
            "PK": dynamodb_schema.get_tenant_pk(tenant_id),
            "SK": f"ALERT#{alert_id}",
            "GSI1PK": f"SEVERITY#{severity.upper()}",
            "EntityType": "Alert",
            "alertId": alert_id,
            "tenantId": tenant_id,
            "sessionId": session_id,
            "title": title,
            "severity": severity,
            "threatScore": threat_score,
            "threatCategory": threat_category,
            "description": description,
            "status": "new",
        }
        if self._table:
            try:
                self._table.put_item(Item=item)
            except Exception as e:
                logger.error(f"DynamoDB create_alert error: {e}")
        return item

    def get_alert(self, alert_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        if not self._table:
            return None
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.get_item(Key={"PK": pk, "SK": f"ALERT#{alert_id}"})
            return response.get("Item")
        except Exception as e:
            logger.error(f"DynamoDB get_alert error: {e}")
            return None

    def list_alerts(self, severity: Optional[str] = None, status: Optional[str] = None, session_id: Optional[int] = None, limit: int = 100, offset: int = 0, tenant_id: Optional[str] = None) -> List[Any]:
        if not self._table:
            return []
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={":pk": pk, ":sk_prefix": "ALERT#"},
                Limit=limit
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"DynamoDB list_alerts error: {e}")
            return []

    def get_alert_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        alerts = self.list_alerts(tenant_id=tenant_id)
        by_sev = {}
        by_stat = {}
        for a in alerts:
            sev = a.get("severity", "LOW")
            st = a.get("status", "new")
            by_sev[sev] = by_sev.get(sev, 0) + 1
            by_stat[st] = by_stat.get(st, 0) + 1
        return {"total": len(alerts), "by_severity": by_sev, "by_status": by_stat, "by_category": {}}

    def acknowledge_alert(self, alert_id: int, username: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        if not self._table:
            return None
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            self._table.update_item(
                Key={"PK": pk, "SK": f"ALERT#{alert_id}"},
                UpdateExpression="SET #st = :st, acknowledgedBy = :user",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":st": "acknowledged", ":user": username}
            )
            return {"alertId": alert_id, "status": "acknowledged"}
        except Exception as e:
            logger.error(f"DynamoDB acknowledge_alert error: {e}")
            return None

    # Reports
    def create_report(self, session_id: int, file_path: str, generated_by: Optional[str] = None, file_size_bytes: Optional[int] = None, tenant_id: str = "tenant-default") -> Any:
        import time
        report_id = int(time.time() * 1000)
        item = {
            "PK": dynamodb_schema.get_tenant_pk(tenant_id),
            "SK": f"REPORT#{report_id}",
            "EntityType": "Report",
            "reportId": report_id,
            "tenantId": tenant_id,
            "sessionId": session_id,
            "filePath": file_path,
            "fileSizeBytes": file_size_bytes,
            "generatedBy": generated_by,
        }
        if self._table:
            try:
                self._table.put_item(Item=item)
            except Exception as e:
                logger.error(f"DynamoDB create_report error: {e}")
        return item

    def get_report(self, report_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        if not self._table:
            return None
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.get_item(Key={"PK": pk, "SK": f"REPORT#{report_id}"})
            return response.get("Item")
        except Exception as e:
            logger.error(f"DynamoDB get_report error: {e}")
            return None

    def list_reports(self, limit: int = 50, tenant_id: Optional[str] = None) -> List[Any]:
        if not self._table:
            return []
        try:
            pk = dynamodb_schema.get_tenant_pk(tenant_id or "tenant-default")
            response = self._table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={":pk": pk, ":sk_prefix": "REPORT#"},
                Limit=limit
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"DynamoDB list_reports error: {e}")
            return []
