# CampusShield SaaS architecture (pre-deployment)

CampusShield keeps SQLite for local development and selects providers by environment:

```
React -> API -> service/pipeline -> repository interface -> SQLite (local)
                                           |-> DynamoDB repository (future AWS)
                    -> storage interface -> local files (local)
                                           |-> S3 (future AWS)
```

Tenant identity is derived only from the authenticated user/token.  APIs pass that server-side tenant value into every session, alert, report, detection-result, and inspection-factor query.  IDs supplied in URLs are scoped by tenant and return `404` across tenants. WebSocket connections retain the verified token tenant and receive only that tenant's alert/progress events.

The DynamoDB preparation uses a single table with `PK = TENANT#<tenantId>` and entity-specific sort keys (`USER#`, `SESSION#`, `ALERT#`, `REPORT#`). GSI1 supports tenant-independent operational indexes for user lookup, session status, and alert severity; production IAM must still constrain each request/service role to its tenant partition-key prefix.

For AWS, API Gateway invokes Lambda handlers, Cognito validates identities, DynamoDB persists metadata, and S3 stores reports/PCAPs. The current in-process WebSocket manager and FastAPI background tasks are local-development features. Production real-time delivery should use API Gateway WebSocket or EventBridge/SNS plus a connection registry; asynchronous analysis/report work should run through SQS/Step Functions/Lambda rather than in-memory background tasks.

No AWS services are provisioned by this repository or this change.
