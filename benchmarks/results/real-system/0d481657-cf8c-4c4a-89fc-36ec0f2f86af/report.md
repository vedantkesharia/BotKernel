# Local PostgreSQL/Kafka benchmark

```json
{
  "run_id": "0d481657-cf8c-4c4a-89fc-36ec0f2f86af",
  "timestamp_utc": "2026-11-11T22:52:52.326251+00:00",
  "requested": 50,
  "concurrency": 5,
  "warmup_per_worker": 1,
  "total_run_seconds_including_warmup": 21.83,
  "measurement_seconds": 13.945,
  "confirmed_effects": 50,
  "confirmed_effects_per_second": 3.585,
  "admission_ms": {
    "p50": 269.282,
    "p95": 665.516,
    "p99": 892.288
  },
  "completion_ms": {
    "p50": 1312.721,
    "p95": 2212.026,
    "p99": 2379.237
  },
  "outcomes": {
    "SUCCEEDED": 50,
    "REJECTED": 0,
    "FAILED": 0,
    "ESCALATED": 0,
    "TIMEOUT": 0
  },
  "observed_action_count": 55,
  "authoritative_rows": [
    {
      "id": "29953d29-e09b-4529-b494-408902b09bd4",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "86ce9974-58e2-4b44-98df-55529be4dafa",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "075e6eb6-070a-4789-8ba8-eef2de065b80",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5df35369-3773-4714-9d4c-346be6565ac3",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "b987a3ea-3497-4b46-b2c6-f8fc2015461e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7c398543-23b7-430a-af37-7a2471ac4ace",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "b1176583-b91f-42b5-bc56-d4d03802b310",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5e9d1ad2-be1e-47ec-96fe-76aab6af26a8",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "780c4fad-5849-44cb-acb7-14ca915481ec",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "46d6a83a-4fe2-4810-9e45-c42b6149bd13",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "4e747fb4-54c1-448d-aac3-f5afd4c7a053",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "53f3a795-eccc-4261-8db6-8b5eb46dc42d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e62f8102-40fb-42c9-92a2-4947c32165bf",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1b1cb723-902d-401f-bf87-48543f3e8685",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "ec8a6884-f965-49b7-8661-d54acb68174a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "0360ea28-3b30-466b-b977-5bffcf21d7b3",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "ef04f9b6-451b-456a-b329-b919578266b9",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "54da1e54-8160-4fff-96ab-0519527fdece",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "0246e091-d434-40eb-b6fb-6fa94ca06733",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3d04f387-21f7-40e0-9b2a-0ea1ca5d95f2",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "cd2d1fc6-f3b3-42f1-aa61-d9cbab4b82b6",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "bd8d9acc-2df0-48ff-925a-8d67a5949001",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1102267c-e03b-4e93-be60-baaf71f14f39",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "41ac1e39-af0a-4b05-b02e-dd0c79933701",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "805c05c8-c98f-4683-869a-1c1ca320b46b",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "72b0f1d4-6197-45f9-a8f8-23f2a54e832d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7b18103e-1fdf-4ba8-90c7-e8e40b03930d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e8dbe19b-aeb2-4ed2-acb5-fb4d1fe34606",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a8825ae8-a206-4752-96ec-724f29416cb3",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "8124f0a5-8a01-46a4-9bfd-ae0f7d77b90c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "f4478ae1-d6af-4819-a009-ff4bfa58e6f5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "80d9d2b4-b6f8-41d5-9dc7-e91cbf8de9a8",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1aa77b30-c725-4e54-8986-6ed769af18f5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "f3db56b1-ffdf-46da-ba93-46c679736276",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3607cb15-bdba-49c0-b278-0783a88056a7",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a78574e3-eca0-4676-9e92-94a05d1de6b3",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7ea37460-cc82-477d-8bcb-94b4d414e249",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "2e4e10d3-ce87-492f-b9af-3cdee2f11088",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "f6e07a8b-d1f6-47c1-9c05-5e4f253e6ea2",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "dc9d3e59-87b4-490e-933e-f4c8fb4657be",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "b5e1bdb9-1a8d-4927-a0f5-c04fd91f8d5a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "71b8e068-ce55-4d2e-b97a-55992ddcb3ce",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "bbfd948b-9b4b-44d4-96cb-a52af71e4bdd",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e81cd01f-be14-4ca4-a417-d8603facbf0a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7ef120dc-9984-4d52-ade4-acee5ee52207",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "aedf4c7f-5ebc-4acd-ba80-ccd19e645178",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3b5d5c88-2979-40ee-bdd9-9e0a81e71c45",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e70a087e-7162-4156-93c2-5b20f34640f5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "beb9fa6b-1a78-4229-8e84-fc96ef7d9523",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "2bd47c62-1af5-45c4-841d-62a948ed03ef",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "c7b9db66-98a4-4983-80d9-20cf3c9f5d44",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "52bf7446-c5bf-4b5a-b101-fe1eeacd7410",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "54979403-11ff-4779-b80f-cf79517569a2",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e07c11ec-3427-493f-94be-04e92823cae0",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a3707231-6250-4c25-a5c8-757fdebc544c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    }
  ],
  "resource_versions": [
    {
      "id": "benchmark-0d481657-cf8c-4c4a-89fc-36ec0f2f86af-0",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-0d481657-cf8c-4c4a-89fc-36ec0f2f86af-1",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-0d481657-cf8c-4c4a-89fc-36ec0f2f86af-2",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-0d481657-cf8c-4c4a-89fc-36ec0f2f86af-3",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-0d481657-cf8c-4c4a-89fc-36ec0f2f86af-4",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
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
