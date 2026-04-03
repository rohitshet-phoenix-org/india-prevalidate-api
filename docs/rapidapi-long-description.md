### What is India PreValidate API?

India PreValidate API validates Indian business identifiers **instantly and offline** — using algorithmic format checks, published checksum algorithms, and public-domain datasets. It does NOT connect to any government database.

![Landing Page](https://india-prevalidate-api-production.up.railway.app/static/img/screenshots/landing-page.png)

---

### Why Pre-Validate?

Every call to a paid GST verification service, PAN check, or IFSC lookup costs money. **15-30% of those calls fail** because the input was malformed in the first place — a typo, wrong length, bad checksum. India PreValidate API catches these **before** they hit your paid pipeline, saving you real money at scale.

---

### 15 Validation Endpoints

| Endpoint | What it validates |
|----------|------------------|
| **GST / GSTIN Validator** | Format, Luhn mod-36 checksum, state code, entity type |
| **PAN Validator** | Format, holder type (Individual/Company/Trust/etc.), name initial |
| **UPI ID Validator** | Handle format, 35+ provider identification (Paytm, GPay, PhonePe, etc.) |
| **IFSC Lookup** | Bank name, branch, city, MICR — from 178,670 RBI records |
| **PIN Code Lookup** | Post office, city, state, district — from 154,823 India Post records |
| **CIN Validator** | Company type, listing status, industry code, state, registration year |
| **TAN Validator** | Area code, holder type, serial number |
| **DIN Validator** | Director Identification Number format and checksum |
| **IEC Validator** | Import Export Code format validation |
| **FSSAI Validator** | License type, state identification from 14-digit format |
| **MSME / Udyam Validator** | State, district, enterprise type from registration number |
| **Vehicle Registration** | State, RTO office, format validation |
| **Driving License** | State code, format, issue year extraction |

---

### Bulk Validation — Validate 50 at Once

Stop looping through individual API calls. Our **bulk endpoints** let you validate up to **50 GSTINs or 50 PANs** in a single POST request.

![Bulk Validation](https://india-prevalidate-api-production.up.railway.app/static/img/screenshots/bulk-validation.png)

**Bulk GST Validation** (`POST /v1/gst/bulk-validate`):
- Send up to 50 GSTINs in one request
- Get per-item validation results with state name, entity type, checksum status
- Summary count of valid vs invalid

**Bulk PAN Validation** (`POST /v1/pan/bulk-validate`):
- Send up to 50 PANs in one request
- Get per-item results with holder type classification
- Summary count of valid vs invalid

**50x fewer HTTP round-trips. Under 200ms total.**

---

### Interactive API Explorer

Try every endpoint directly in our Swagger UI — no signup required for the free tier.

![Swagger UI](https://india-prevalidate-api-production.up.railway.app/static/img/screenshots/swagger-ui.png)

---

### Live Demo — Try Before You Subscribe

Our landing page includes a **live demo** where you can test GST, PAN, UPI, IFSC, and CIN validation instantly.

![Live Demo](https://india-prevalidate-api-production.up.railway.app/static/img/screenshots/live-demo.png)

---

### Key Features

- **Sub-50ms response time** — all validation runs in-memory, no external calls
- **178,670 IFSC records** — complete RBI branch directory (Razorpay open-source, MIT license)
- **154,823 PIN code records** — full India Post office directory (data.gov.in, open data)
- **DPDP Act 2023 compliant** — zero data storage, no input logging, transient processing only
- **Checksum verification** — Luhn mod-36 for GSTIN, format + structure for all others
- **Detailed breakdown** — not just valid/invalid, but state name, entity type, bank details, etc.

---

### Use Cases

- **Fintech & KYC pipelines** — pre-filter malformed identifiers before calling paid NSDL/GSP APIs
- **Form validation** — real-time format checks in onboarding forms
- **Data cleaning** — bulk validate CSV exports of GST or PAN numbers
- **ERP integrations** — validate vendor GSTIN before saving to your system
- **Compliance checks** — verify IFSC codes and PIN codes in payment workflows

---

### Data Sources

All data is from **public-domain, openly licensed sources**:

| Dataset | Source | License | Records |
|---------|--------|---------|---------|
| IFSC Branch Data | Razorpay IFSC (GitHub) | MIT License | 178,670 |
| PIN Code Data | data.gov.in (India Post) | Government Open Data License | 154,823 |
| Validation Rules | Published government specifications | Public domain | — |

---

### Privacy & Compliance

- **No data stored** — inputs are processed in memory and immediately discarded
- **No logging of identifiers** — only aggregate request counts for rate limiting
- **DPDP Act 2023 compliant** — no personal data collection, storage, or profiling
- **Stateless processing** — each request is independent, no session tracking

---

### Getting Started

1. Subscribe to a plan on RapidAPI
2. Copy your API key from the RapidAPI dashboard
3. Make your first request:

```bash
curl -X POST "https://india-prevalidate-api.p.rapidapi.com/v1/gst/validate" \
  -H "X-RapidAPI-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"gstin": "27AAPFU0939F1ZV"}'
```

**Website:** [india-prevalidate-api-production.up.railway.app](https://india-prevalidate-api-production.up.railway.app/)
