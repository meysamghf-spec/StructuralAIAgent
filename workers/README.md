# Worker Architecture (Future)

The platform uses a simple async job model:

```
API → Job → Worker → Result
```

- **API** accepts requests and enqueues jobs.
- **Job** represents a unit of background work with traceable metadata.
- **Worker** processes jobs outside the request/response cycle.
- **Result** is persisted and linked to project state (PEM).

Milestone 1 establishes this boundary only. No queue implementation yet.
