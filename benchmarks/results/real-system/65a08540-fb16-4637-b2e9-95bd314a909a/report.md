# Local PostgreSQL/Kafka benchmark

```json
{
  "run_id": "65a08540-fb16-4637-b2e9-95bd314a909a",
  "timestamp_utc": "2026-11-11T22:46:49.193250+00:00",
  "requested": 25,
  "concurrency": 1,
  "warmup_per_worker": 1,
  "total_run_seconds_including_warmup": 15.223,
  "measurement_seconds": 9.247,
  "confirmed_effects": 25,
  "confirmed_effects_per_second": 2.704,
  "admission_ms": {
    "p50": 68.961,
    "p95": 174.987,
    "p99": 287.572
  },
  "completion_ms": {
    "p50": 378.607,
    "p95": 538.205,
    "p99": 730.854
  },
  "outcomes": {
    "SUCCEEDED": 25,
    "REJECTED": 0,
    "FAILED": 0,
    "ESCALATED": 0,
    "TIMEOUT": 0
  },
  "observed_action_count": 26,
  "authoritative_rows": [
    {
      "id": "f9b87fb1-2d30-4a93-833b-372b03965617",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "bfe5801d-5597-48c4-9c67-070377c6b5ba",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "fef866d8-65f2-4006-8aec-b0982c9f1a13",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3a63f45b-9b8b-40b1-8dcf-c902d9be3678",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "9c9c1d9c-db31-4174-8482-72c76e55bc82",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "aa3ac6f2-2ab2-4979-bb7a-48e3d88ae188",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "dd3c5453-938a-4115-b02b-d8d995df819f",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "23bd5437-4336-465a-8b2a-9b11dc21efe2",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1a03be2b-8f74-4709-bfe8-c62dd949053e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "eafcb095-22b6-42e4-8a3e-46cc7d2adb7d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7bf41264-ab94-4c98-8004-3e106a8da31d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "54138876-4e96-4458-b4c9-2190072bf6ae",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "12eb0e52-08a5-41fe-9a46-6f7fbb587b88",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "62000059-6e48-4247-8551-afe5a4b80177",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "4d3ad3c6-9882-4d6a-8a45-1d19e15a1b59",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "f5b80b7c-dd7f-4906-bdb6-1cb805ba7e2d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "301b3958-4d4b-473f-be9d-58155e3cbd1c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5a6f3113-cf05-4843-b037-a498a96238d3",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "324c163e-5a77-43de-95a5-6313a8ee8b5e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "0954f69b-e72c-4e3e-b961-241e7d6490f5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "84af08f3-8086-4935-b717-988672b5366b",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7361593c-03cc-4c83-888c-c74ca572c9b2",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7533d4f3-103a-4f01-848a-532c49cb575c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5aaa2e19-80bd-4dc7-9a1d-4bde367333aa",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "27742d4c-c876-4930-b9e1-028dd47f9f3c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "01ee86d9-00ab-4a2b-875f-9856033d765d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    }
  ],
  "environment": {
    "python": "3.12.16",
    "platform": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.41",
    "postgresql": "16.15 (Debian 16.15-1.pgdg13+2)",
    "kafka_image": "apache/kafka:3.9.0"
  },
  "unavailable": [
    "publication latency",
    "Kafka delivery latency",
    "worker execution latency",
    "consumer lag",
    "duplicate deliveries",
    "CPU and memory",
    "recovery fault injection"
  ],
  "notes": [
    "Client monotonic timing; completion includes 50ms polling.",
    "Throughput spans first measured submission to last observed terminal outcome after warmup.",
    "Dedicated local PostgreSQL and Kafka; simulator resource changes only."
  ]
}
```
