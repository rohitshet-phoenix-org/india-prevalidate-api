# India PreValidate API

**Offline Format Validation & Public-Data Enrichment for Indian Business Identifiers**

Pre-validate GSTIN, PAN, UPI IDs, IFSC codes, CIN, TAN, IEC, FSSAI, MSME/Udyam,
vehicle registration, driving license, and PIN codes using algorithmic format checks,
published checksum algorithms, and public-domain datasets — without connecting to
any government database.

---

## Privacy Notice (DPDP Act 2023 Compliance)

> **India PreValidate API does not store, log, or retain any identifiers submitted
> for validation. All processing is performed in-memory and discarded after the
> response is returned. No personal data is collected, stored, or shared. No user
> profiles are built from API usage patterns.**
>
> **This API does not store, log, or retain any identifiers submitted for
> validation. All processing is transient and in-memory only.**

This API is designed for full compliance with the Digital Personal Data Protection
Act 2023 (DPDP Act):

- **No input logging:** Submitted identifiers (PAN, GSTIN, UPI IDs, etc.) are never
  written to disk, stdout, log files, or any persistent storage
- **No user profiling:** Only aggregate request counts are tracked (e.g., "500 total
  PAN validations") — never per-user, per-IP, or per-input statistics
- **Transient processing:** All validation is in-memory. Input is discarded the
  moment the HTTP response is sent
- **No third-party data sharing:** No identifiers are transmitted to external services,
  analytics platforms, or error tracking tools
- **Suppressed framework logging:** Uvicorn/FastAPI access and error loggers are
  explicitly suppressed to prevent accidental input leakage

---

## Legal Scope & Disclaimer

### What This API Does (Legally Safe — No License Required)

This API performs **offline, client-side-equivalent structural validation** only:

- **Format validation** using publicly documented rules (regex, pattern matching)
- **Checksum verification** using published algorithms (Luhn mod-36 for GSTIN)
- **Component extraction** (state codes, entity types, name initials from format position)
- **Public-domain data enrichment** (IFSC branch data from RBI, PIN code data from India Post)
- **Known-handle mapping** (UPI provider to bank from publicly available knowledge)

### What This API Does NOT Do

- Does NOT connect to, query, or scrape **GSTN** (GST Portal) or any GSP/ASP gateway
- Does NOT query **NSDL**, **UTIITSL (Protean)**, or the Income Tax Department
- Does NOT call **NPCI's** Validate Address API or any live UPI/banking system
- Does NOT access **MCA**, **Parivahan/VAHAN**, **Sarathi**, **DGFT**, **FSSAI**, or **Udyam** portals
- Does NOT scrape any government, banking, or financial services website
- Does NOT store, log, or retain any identifiers submitted for validation
- Does NOT verify identity, KYC status, registration status, or account existence

### Regulatory Landscape

| Law/Framework | Applicability | Our Position |
|---|---|---|
| DPDP Act 2023 | Technically minimal — user voluntarily provides data for specified purpose | No storage, no logging, transient in-memory processing only |
| IT Act 2000, Section 43 | Does NOT apply — no external computer system is accessed | All processing is local: regex, checksums, dictionary lookups |
| NPCI UPI Circular OC-215 | Does NOT apply — we are not a PSP, TPAP, or bank | We parse text strings; we don't call any NPCI API |
| GST Act (GSP/ASP framework) | Does NOT apply — no GSTN system access | Algorithmic format check only |
| NSDL authorized entity rules | Does NOT apply — no PAN holder lookup | Format check only, no NSDL queries |

**This API avoids all restricted systems by design. It is in the same legal category
as a JavaScript credit card Luhn validator or an email format checker.**

### Data Sources & Licensing

| Data | Source | License |
|------|--------|---------|
| GSTIN validation | Algorithmic (documented format + Luhn mod-36) | No external data |
| PAN validation | Algorithmic (documented AAAAA9999A format) | No external data |
| UPI provider mapping | Publicly known handle-to-bank associations | Public knowledge |
| IFSC branch data | RBI published IFSC/MICR registry | **Public domain** |
| PIN code data | India Post directory on data.gov.in | **Government Open Data** |
| CIN validation | Algorithmic (Companies Act 2013 format) | No external data |
| TAN validation | Algorithmic (Income Tax Dept format) | No external data |
| IEC validation | Algorithmic (DGFT format = PAN format) | No external data |
| FSSAI validation | Algorithmic (FSSA 2006 14-digit format) | No external data |
| MSME/Udyam validation | Algorithmic (MSME Ministry 2020 format) | No external data |
| Vehicle format | Algorithmic (Motor Vehicles Act format) | No external data |
| DL format | Algorithmic (Motor Vehicles Act format) | No external data |
| DIN validation | Algorithmic (MCA 8-digit format) | No external data |
| RTO codes | State transport dept published codes | Public knowledge |

The IFSC dataset is maintained as open-source at
[github.com/razorpay/ifsc](https://github.com/razorpay/ifsc) — code under MIT license,
dataset explicitly released under **public domain**.

---

## Project Structure

```
india-prevalidate-api/
├── app/
│   ├── __init__.py
│   └── main.py              <- FastAPI app (15 endpoints, legal disclaimers in every response)
├── data/
│   ├── ifsc_sample.json     <- IFSC branch data (public-domain RBI data)
│   ├── pincode_sample.json  <- PIN code data (India Post open data, data.gov.in)
│   └── rto_codes.json       <- RTO codes (state transport dept public data)
├── tests/
│   └── test_api.py          <- 70+ test cases including legal/privacy compliance tests
├── Dockerfile                <- Production container
├── railway.json              <- Railway deployment config
├── render.yaml               <- Render deployment config
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## API Endpoints

### Core Pre-Validation (15 endpoints)

| Method | Route | What It Does | What It Does NOT Do |
|--------|-------|-------------|-------------------|
| POST | `/v1/gst/validate` | Format check, Luhn mod-36 checksum, state code, entity type | Does NOT query GSTN or confirm registration |
| POST | `/v1/pan/validate` | Format check, entity type, name initial extraction | Does NOT query NSDL or confirm issuance |
| POST | `/v1/upi/validate` | Format check, provider handle to bank/app mapping | Does NOT call NPCI or confirm VPA existence |
| POST | `/v1/ifsc/lookup` | Bank/branch/city/address from public-domain data | Uses public-domain RBI data only |
| POST | `/v1/cin/validate` | CIN format, listing status, state, company type, year | Does NOT query MCA or confirm registration |
| POST | `/v1/din/validate` | DIN 8-digit format check | Does NOT query MCA DIN database |
| POST | `/v1/tan/validate` | TAN format, area code, serial extraction | Does NOT query Income Tax Dept |
| POST | `/v1/iec/validate` | IEC (Import Export Code) format check | Does NOT query DGFT portal |
| POST | `/v1/fssai/format` | FSSAI 14-digit license format, license type, state | Does NOT query FSSAI portal |
| POST | `/v1/msme/format` | Udyam registration number format, state, district | Does NOT query Udyam portal |
| POST | `/v1/vehicle/format` | Vehicle registration format, state, RTO code | Does NOT access Parivahan/VAHAN |
| POST | `/v1/driving-license/format` | DL format, state, RTO, year of issue | Does NOT access Sarathi portal |
| POST | `/v1/pincode/lookup` | PIN code to city/state/district (public data) | Uses India Post open data only |
| POST | `/v1/gst/bulk-validate` | Batch validate up to 50 GSTINs (rate-limited) | Same offline validation, no GSTN access |
| POST | `/v1/pan/bulk-validate` | Batch validate up to 50 PANs (rate-limited) | Same offline validation, no NSDL access |

### Reference Data

| Method | Route | Description | Data Source |
|--------|-------|-------------|-------------|
| GET | `/v1/states` | GST state codes (01-38) | Published GST state code list |
| GET | `/v1/banks` | IFSC bank codes (40+) | RBI published codes (public domain) |
| GET | `/v1/upi-providers` | UPI handles with bank/app mapping (35+) | Publicly known associations |
| GET | `/v1/rto-codes` | RTO codes with city/state mapping | State transport dept (public) |
| GET | `/v1/pincode/states` | PIN code first-digit region mapping | India Post (data.gov.in) |

### Utility

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/v1/health` | Health check for uptime monitoring |
| GET | `/v1/disclaimer` | Full legal scope, privacy notice, data sources |
| GET | `/v1/stats` | Aggregate usage statistics (no per-user data) |

---

## Response Format

Every endpoint returns a consistent structure with explicit validation scope:

```json
{
    "valid": true,
    "input": "27AAPFU0939F1ZV",
    "details": {
        "format_valid": true,
        "checksum_valid": true,
        "state_code": "27",
        "state_name": "Maharashtra",
        "embedded_pan": "AAPFU0939F",
        "entity_type": "Firm / LLP",
        "entity_number": "1",
        "check_digit": "V",
        "validation_type": "offline_format_check",
        "disclaimer": "Format validation only. Does not confirm GSTN registration or active status. No data is stored or logged."
    },
    "timestamp": "2026-04-01T10:30:00+00:00"
}
```

Every response includes:
- `validation_type: "offline_format_check"` — clearly communicates this is algorithmic, not authoritative
- `disclaimer` — per-endpoint legal scope statement
- No input identifiers are stored, logged, or retained after response

---

## Rate Limiting

| Endpoint Type | Default Limit | Configurable Via |
|---|---|---|
| Single validation | 60 requests/minute per IP | `RATE_LIMIT_PER_MIN` env var |
| Bulk validation | 10 requests/minute per IP | `BULK_RATE_LIMIT_PER_MIN` env var |

Bulk endpoints (`/v1/gst/bulk-validate`, `/v1/pan/bulk-validate`) accept a maximum
of 50 items per request and are rate-limited more strictly to prevent abuse.

---

## Run Locally

```bash
cd india-prevalidate-api
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the Swagger UI. Try:

```bash
# GSTIN pre-validation
curl -X POST http://localhost:8000/v1/gst/validate \
  -H "Content-Type: application/json" \
  -d '{"gstin": "27AAPFU0939F1ZV"}'

# PAN pre-validation
curl -X POST http://localhost:8000/v1/pan/validate \
  -H "Content-Type: application/json" \
  -d '{"pan": "ABCPK1234F"}'

# UPI format check
curl -X POST http://localhost:8000/v1/upi/validate \
  -H "Content-Type: application/json" \
  -d '{"upi_id": "rohit@okaxis"}'

# IFSC lookup (public-domain data)
curl -X POST http://localhost:8000/v1/ifsc/lookup \
  -H "Content-Type: application/json" \
  -d '{"ifsc": "SBIN0001234"}'

# CIN format check
curl -X POST http://localhost:8000/v1/cin/validate \
  -H "Content-Type: application/json" \
  -d '{"cin": "U72200MH2007PTC175407"}'

# Bulk GSTIN validation (up to 50)
curl -X POST http://localhost:8000/v1/gst/bulk-validate \
  -H "Content-Type: application/json" \
  -d '{"gstins": ["27AAPFU0939F1ZV", "29ABCDE1234F1ZP"]}'

# View full legal disclaimer & privacy notice
curl http://localhost:8000/v1/disclaimer
```

Run tests: `pytest tests/ -v`

---

## Deploy to Production

### Option A: Railway (Recommended)

```bash
git init && git add . && git commit -m "India PreValidate API v2.0.0"
git remote add origin https://github.com/YOUR_USERNAME/india-prevalidate-api.git
git push -u origin main
```

Railway dashboard: New Project -> Deploy from GitHub -> auto-detects Dockerfile.
Cost: Free tier = 500 hrs/month. Hobby = $5/month always-on.

### Option B: Render

Connect GitHub repo -> Render detects Dockerfile -> set `PORT=8000` -> deploy.
Starter plan = $7/month.

### Option C: VPS ($4-6/month)

```bash
sudo apt update && sudo apt install docker.io -y
git clone https://github.com/YOUR_USERNAME/india-prevalidate-api.git
cd india-prevalidate-api
docker build -t india-prevalidate-api .
docker run -d -p 8000:8000 --restart=always --name prevalidate india-prevalidate-api
```

---

## List on RapidAPI

### API Metadata

**Name:** `India PreValidate API`

**Short Description:**
```
Pre-validate 15+ Indian identifier formats offline — GSTIN, PAN, UPI, IFSC, CIN,
TAN, IEC, FSSAI, MSME, vehicle, DL, PIN code. No government database access.
```

**Category:** Finance -> Validation

### Configure Endpoints

| Method | Route | Display Name |
|--------|-------|-------------|
| POST | `/v1/gst/validate` | Pre-Validate GSTIN Format |
| POST | `/v1/pan/validate` | Pre-Validate PAN Format |
| POST | `/v1/upi/validate` | Parse UPI ID Format |
| POST | `/v1/ifsc/lookup` | Lookup IFSC (Public Data) |
| POST | `/v1/cin/validate` | Pre-Validate CIN Format |
| POST | `/v1/din/validate` | Pre-Validate DIN Format |
| POST | `/v1/tan/validate` | Pre-Validate TAN Format |
| POST | `/v1/iec/validate` | Pre-Validate IEC Format |
| POST | `/v1/fssai/format` | Check FSSAI License Format |
| POST | `/v1/msme/format` | Check Udyam Registration Format |
| POST | `/v1/vehicle/format` | Check Vehicle Registration Format |
| POST | `/v1/driving-license/format` | Check Driving License Format |
| POST | `/v1/pincode/lookup` | Lookup PIN Code (Public Data) |
| POST | `/v1/gst/bulk-validate` | Bulk Pre-Validate GSTINs (up to 50) |
| POST | `/v1/pan/bulk-validate` | Bulk Pre-Validate PANs (up to 50) |
| GET | `/v1/disclaimer` | Legal Disclaimer & Privacy Notice |
| GET | `/v1/states` | List State Codes |
| GET | `/v1/banks` | List Bank Codes |
| GET | `/v1/upi-providers` | List UPI Providers |
| GET | `/v1/rto-codes` | List RTO Codes |
| GET | `/v1/pincode/states` | List PIN Code Regions |

### Pricing

| Plan | Price | Monthly Quota | Overage | Target |
|------|-------|---------------|---------|--------|
| **Basic** | FREE | 100 requests | -- | Testing & evaluation |
| **Pro** | $9.99/mo | 5,000 requests | $0.005/call | MVPs & small apps |
| **Ultra** | $29.99/mo | 25,000 requests | $0.003/call | Growing startups |
| **Mega** | $99.99/mo | 100,000 requests | $0.002/call | Data pipelines & fintech |

Bulk endpoints (`/v1/gst/bulk-validate`, `/v1/pan/bulk-validate`) are premium features
recommended for Pro tier and above.

---

## Production Hardening

```bash
# Redis for rate limiting (replace in-memory dict)
pip install redis

# Uptime monitoring (free tier)
# -> UptimeRobot: uptimerobot.com
```

### Load Full IFSC Dataset (High Priority — Zero Legal Risk)

The scaffold ships with sample records. Load the full ~170K branch dataset:

```bash
git clone https://github.com/razorpay/ifsc.git
# Convert their JSON/CSV to your format
# Load into SQLite or PostgreSQL for fast lookups
```

### DPDP Act Compliance — Logging Warning

Do NOT add structured logging (structlog, loguru) or error tracking (Sentry) that
captures request bodies. Input identifiers (PAN, GSTIN, UPI IDs) must NEVER be
logged, stored, or transmitted to third-party services. If you add logging, log
only aggregate metrics (e.g., "PAN validation: format=valid, entity=Company") —
never the input value itself.

Uvicorn's default access log only records request paths and status codes, which is
safe since all identifiers travel in POST bodies, not URLs. The app explicitly
suppresses uvicorn access/error loggers as an additional safeguard.

---

## What NOT To Build Without Licensing

| Feature | Authorization Required | Barrier |
|---------|----------------------|---------|
| Live GSTIN taxpayer name/status | GSP license or ASP partnership | Rs.2Cr+ capital (GSP) or Rs.50K-2L (ASP) |
| PAN-to-name verification | NSDL e-Gov authorized entity | DSC + company docs + NSDL approval |
| UPI VPA existence check | NPCI-approved PSP/TPAP | PSP bank partnership + NPCI onboarding |
| Bank account verification | Cashfree/Razorpay partnership | API agreement + per-txn cost |

---

## Marketing Positioning

Position as a **"pre-validation layer"** — the first checkpoint before expensive
authorized API calls:

> "Stop wasting money on invalid API calls. India PreValidate catches
> malformed GSTINs, invalid PANs, and bad UPI IDs BEFORE they hit your
> paid verification pipeline — saving you 15-30% on downstream API costs."

You are **not competing** with Karza, Signzy, Surepass, or AuthBridge (who offer
authorized government-database verification). You are **complementing** them by
filtering garbage inputs before they consume paid API calls.

### Where to Promote

- **Dev.to / Hashnode** — Tutorial: "How I Built a GSTIN Pre-Validation API with FastAPI"
- **r/IndianDevelopers, r/developersIndia** — Share the tool
- **IndieHackers** — Post MRR milestones
- **Twitter/X** — Thread showing API in action with code snippets
- **Product Hunt** — Launch when you have 100+ free users

---

## License

MIT — Build, sell, and scale as you like.

The IFSC dataset used is under **public domain** (sourced from RBI's published data).
PIN code data is from India Post's directory on data.gov.in (Government Open Data).
All validation logic is original algorithmic work based on publicly documented
format specifications. No government data, restricted databases, or personal
information is accessed, stored, or distributed by this API.
