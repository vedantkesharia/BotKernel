# Local PostgreSQL/Kafka benchmark

```json
{
  "run_id": "ad2c84bc-3c6a-4dae-bc5d-4072e9367038",
  "timestamp_utc": "2026-11-11T22:56:12.641817+00:00",
  "requested": 100,
  "concurrency": 10,
  "warmup_per_worker": 1,
  "total_run_seconds_including_warmup": 40.223,
  "measurement_seconds": 32.359,
  "confirmed_effects": 100,
  "confirmed_effects_per_second": 3.09,
  "admission_ms": {
    "p50": 568.209,
    "p95": 1914.957,
    "p99": 3033.013
  },
  "completion_ms": {
    "p50": 3067.288,
    "p95": 4382.264,
    "p99": 5429.639
  },
  "outcomes": {
    "SUCCEEDED": 100,
    "REJECTED": 0,
    "FAILED": 0,
    "ESCALATED": 0,
    "TIMEOUT": 0
  },
  "observed_action_count": 110,
  "authoritative_rows": [
    {
      "id": "61c31b93-f194-46c7-baaa-9457493def08",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "bf593be6-45fa-4f85-b670-ec3089c55802",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5fe444e2-0759-49ba-92cf-8c41312eedb1",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5171c021-8e4d-4e13-8022-f2c73e11de5c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7bf0872a-7985-40ec-8cc1-f0f94cb5758f",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "89d03b9e-cdd2-4ee5-8e7f-e093d8ade635",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "783efcf3-05bc-498b-bf9b-2e55e3faea83",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "06f99fb5-391a-4b5c-8bca-ed5ad1eb2f40",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "6b392d26-9a99-40bb-ba7f-bf55eb8d9c4a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "894767bd-abfc-4be6-80a3-c9a07ccd0456",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "64cec8e7-e430-4ec2-af43-29e5340889e7",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e86cd421-de18-4a66-b78e-ddc9a3af7922",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "cd5daa04-8e5b-45f3-b543-aab80807eb56",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "8c1c1c66-1118-46f3-9d1f-5a20b0a8a6a9",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "dd5b7a35-6336-4e56-ab16-bb22d4a23ac4",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "78aa50aa-88f7-43f6-a97c-282952aa2fb2",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "704d5a29-e4f7-45d7-91ab-d8ea636a49cc",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "0b3b9819-402f-433b-8d4e-638e0cdaac7d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a03a34db-0d10-4fd9-b38f-47bac34a5565",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "25d7b914-7bee-44a3-9b74-bfad94d02202",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "09703286-e8fc-4ca2-b963-3d5786212d9f",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5fd8ea9d-6883-4f10-bd1e-e79aa66c8af8",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "0f500c63-bf03-42e0-b7e8-b1f49a8c8e3a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "9c03e91f-7927-4343-8b00-6a43f565538c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e3c2c9c8-8be2-4710-9f8c-5d249778f868",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e2c7222f-3a06-4ccc-b5c3-dede9888ca8c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "c4d3cdf4-de2b-4fe6-adbb-8dcef4f81507",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "64c551aa-14ee-47d0-92dc-20ded8f74a38",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "8badeae2-ca3c-4cf3-bd68-7981cdd6fdb3",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e8f22ee1-7ad2-4193-b9ad-5dfb73a4df0e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1f284fa9-b5ac-43e7-9c75-d70db31de825",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1c6dea9d-70b0-4b60-a564-b43a95a2eb59",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "74703c22-aee0-4757-b3ad-4c4070152d2a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "c128819b-f4bf-46f4-afc2-9c5c777a48bd",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e120f5e9-f4ce-45a9-ab91-84d60b09cc14",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3923f197-5700-460a-b8f9-8c33096d8001",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3de93210-8297-4c94-ab0d-3f1aedcbf6f5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3ad03d22-94dc-47d4-99dc-330314c27f76",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7a0fe4db-2eb7-4f24-be3d-ab326d6f1667",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7873d1b8-c9f1-4420-9dc3-5083e9edc08d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "11810e60-23cb-4621-b2e3-c85920a0e1e5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "387ae21e-7b44-4257-ae42-cb32365e6222",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a874c8c1-4180-45a8-bb36-9c386f3dc553",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3cd49895-caf8-4e13-9e15-52eed74f0567",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "c3d7acce-097b-4570-a8eb-ce96e236a4ea",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "fe67b90e-8702-4b1c-b0df-2d63bc6435ca",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "c6d7a026-6f70-44f3-9aca-12e2f1726b1a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1499eeeb-3d62-4a5c-8502-16605943bfcc",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "67b136ad-39e5-47c5-a9fc-6f3b30cfc8f1",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "10bac494-ccb8-4a51-8302-020014352dde",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "1de0daa6-8213-48d7-84fa-5bad84d80d89",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3235523a-7760-4bcb-a994-7d250c13e727",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "fde60e84-e4af-499a-a309-4786ce6e4bf1",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "9f4c97fc-a387-4d5e-9625-7f87ffb43ab5",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "70ff2b57-2e44-4802-871a-5f0859d4f824",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "900b65d3-1099-4212-81b7-f92757e8c36a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "df570f32-351c-4e5f-af84-314bc3601622",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "42e0cc2d-03f1-4007-9fd3-e624a7d5d3de",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "29533466-fa87-4c0d-8e6f-90d1b36609a8",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "aa1cc3d5-9d1f-4297-8478-f7c4e868b672",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "eb162b29-8b87-460c-b3e4-9b6bc0f5637c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a69100f4-c9e6-478d-bb88-150a351fa8ec",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "ba585175-21c1-41d8-8e50-a21d09955416",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5d1b1e14-87f2-405d-909d-9408ac52ad79",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "8d90208f-ee89-403d-8bdd-5c900623dc94",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "9ab5c338-4e54-4aef-90d1-e092d9f12a83",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "7a296daf-22aa-4c90-a813-adf11c4c33d0",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "012102b4-3ce4-4550-a55a-d677e5b982d4",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "155e3557-1d9b-4f0b-9e5e-4a980c4f9e78",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "435b2648-77b0-4731-8d84-57f0a229bc99",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "fa165c12-4d97-4935-8ca0-185736b29209",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "fb9a802d-e157-4b78-90b2-83eb6fba9b0e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3655e7c9-b495-42a6-8869-2c8f25bc7b3e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "69532a85-b965-4b92-aef2-e7650853da19",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "797bf696-5432-44c2-ba15-63c12e46f158",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "06930843-e7d2-46b6-912c-d6bdbbcdd236",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5fae7ee0-1815-4e42-8d38-d14345a31fab",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "cdc90dd4-9bea-4fd8-8b21-cf01484c2f8c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "f826b846-2904-4f60-9d3b-d75a8b06083e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "2561b312-ecd3-47a5-82f1-86c0bb4d0b05",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "ae9ce43c-31c9-4730-98f8-7555a5b95141",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e54bae8e-c2f6-4a21-bcc2-c37650332960",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "05227d71-c74b-4a97-a388-3c48821b44ea",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5141d4fe-6579-4171-915a-7ede2aa93a5a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "902cda52-0754-4738-ae68-b02637238f2d",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "78881f04-c6b8-4097-a20c-de9a7eb574d4",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "a5cb4fee-9ee7-454f-8642-54d14a9aacd9",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "bdbe8d55-baa0-472d-b458-4a955194030e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5f90ffb5-3725-4932-b2bf-97c49aaf2ae7",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "95f6147f-c355-4036-8e61-cd9f15b145ca",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "faa73409-29d5-4c86-8c1c-e6873f5c2485",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "8ff2774f-5064-49b7-8c2f-ee21be36578b",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "944585fa-acc1-4976-a779-46950f76badd",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "5fbd08d8-37c2-43b0-a7c1-9c87abd5f274",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3df58a18-5a13-4c66-9728-7060a0881aec",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e227f781-ed8c-4ee0-be75-156e6f53c279",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "911cb5a0-5901-44af-9e13-2dccc80fe22f",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "206913be-2494-44da-8c46-40136e1eaaaf",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "cacad255-8bf5-49e3-8f9b-d3e6c9e2ec04",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "b7d36cd5-4207-4e73-ad42-c9e60f5e6f42",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "f537cff0-b821-40e9-b32a-c8048115f85e",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "314fcf39-e1be-4614-a004-74447862370c",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "c2a76385-84b1-4bd9-8ea8-f638e362d574",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "e2f137f2-5927-411e-81eb-05b29ad85e12",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "b91bafdd-a180-497c-85ac-7d42efeaad2b",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "fec99d18-a118-4c20-96e3-85413a1058c6",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "794c55eb-44c6-4bc4-8444-423dc770b0b8",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "3145eda0-dd07-4e35-b826-ac24e47ebb4f",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "568ca7cf-29a0-43a0-9983-1878dab19c17",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    },
    {
      "id": "44b4b64a-65f0-4ec2-bd8d-bc5f5e14fd1a",
      "state": "SUCCEEDED",
      "published": true,
      "receipts": 1,
      "effects": 1
    }
  ],
  "resource_versions": [
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-0",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-1",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-2",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-3",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-4",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-5",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-6",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-7",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-8",
      "version": 11,
      "effect_count": 11,
      "max_effect_version": 11
    },
    {
      "id": "benchmark-ad2c84bc-3c6a-4dae-bc5d-4072e9367038-9",
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
