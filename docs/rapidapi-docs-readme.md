## Quick Start Guide

### 1. Get Your API Key
Subscribe to any plan on this page. Your RapidAPI key is available in the **Code Snippets** section on any endpoint.

### 2. Make Your First Request

**Validate a GSTIN:**
```bash
curl -X POST "https://india-prevalidate-api.p.rapidapi.com/v1/gst/validate" \
  -H "X-RapidAPI-Key: YOUR_API_KEY" \
  -H "X-RapidAPI-Host: india-prevalidate-api.p.rapidapi.com" \
  -H "Content-Type: application/json" \
  -d '{"gstin": "27AAPFU0939F1ZV"}'
```

**Response:**
```json
{
  "valid": true,
  "details": {
    "format_valid": true,
    "checksum_valid": true,
    "state_code": "27",
    "state_name": "Maharashtra",
    "entity_type": "Firm / LLP",
    "pan_component": "AAPFU0939F",
    "validation_type": "offline_format_check"
  }
}
```

---

## All Endpoints

### Single Validation Endpoints (POST)

| Endpoint | Input Field | Example Value |
|----------|------------|---------------|
| `/v1/gst/validate` | `gstin` | `27AAPFU0939F1ZV` |
| `/v1/pan/validate` | `pan` | `ABCPK1234F` |
| `/v1/upi/validate` | `upi_id` | `rohit@okaxis` |
| `/v1/ifsc/lookup` | `ifsc` | `SBIN0001234` |
| `/v1/pincode/lookup` | `pincode` | `400001` |
| `/v1/cin/validate` | `cin` | `U72200MH2007PTC175407` |
| `/v1/tan/validate` | `tan` | `MUMA12345B` |
| `/v1/din/validate` | `din` | `00012345` |
| `/v1/iec/validate` | `iec` | `0304000246` |
| `/v1/fssai/format` | `fssai` | `10016011000123` |
| `/v1/msme/format` | `udyam` | `UDYAM-MH-02-0012345` |
| `/v1/vehicle/format` | `registration` | `MH02AB1234` |
| `/v1/dl/format` | `dl_number` | `MH0220190012345` |

### Bulk Validation Endpoints (POST) — Pro Plan & Above

| Endpoint | Input Field | Max Items |
|----------|------------|-----------|
| `/v1/gst/bulk-validate` | `gstins` (array) | 50 |
| `/v1/pan/bulk-validate` | `pans` (array) | 50 |

**Bulk example:**
```bash
curl -X POST "https://india-prevalidate-api.p.rapidapi.com/v1/gst/bulk-validate" \
  -H "X-RapidAPI-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"gstins": ["27AAPFU0939F1ZV", "29ABCDE1234F1Z5", "06INVALID"]}'
```

### Reference Endpoints (GET)

| Endpoint | Description |
|----------|-------------|
| `/v1/states` | All Indian state codes and names |
| `/v1/ifsc/banks` | List of all banks in the IFSC database |
| `/v1/stats` | Database statistics (record counts) |
| `/v1/health` | Service health check |
| `/v1/disclaimer` | Legal disclaimer and data source information |

---

## Rate Limits

| Endpoint Type | Limit |
|--------------|-------|
| Single validation | 60 requests/min |
| Bulk validation | 10 requests/min |

Rate limits are per API key. Upgrade your plan for higher limits.

---

## Error Handling

All errors return standard HTTP status codes with JSON bodies:

| Status | Meaning |
|--------|---------|
| `200` | Success — check the `valid` field in response |
| `422` | Invalid request body (missing or malformed field) |
| `429` | Rate limit exceeded — retry after `retry_after_seconds` |
| `500` | Server error |

---

## Important Notes

- This API performs **offline format validation only** — it does NOT connect to government databases
- A "valid" result means the identifier is **structurally correct**, not that it is registered or active
- For authoritative verification, use licensed GSP, NSDL, or NPCI services after pre-validation
- IFSC and PIN code lookups return real data from public-domain datasets (RBI/India Post)
- No input data is stored or logged — fully DPDP Act 2023 compliant

---

## Support

- **Website:** [india-prevalidate-api-production.up.railway.app](https://india-prevalidate-api-production.up.railway.app/)
- **Full Swagger Docs:** [india-prevalidate-api-production.up.railway.app/docs](https://india-prevalidate-api-production.up.railway.app/docs)
- **ReDoc:** [india-prevalidate-api-production.up.railway.app/redoc](https://india-prevalidate-api-production.up.railway.app/redoc)
