# Reddit Post — r/developersIndia

**Flair:** `I Made This`

**Title:** I built a free offline validation API for Indian PAN, GST, IFSC, Aadhaar, UPI & more — no government API calls, sub-100ms responses

**Body:**

Hey r/developersIndia!

I built **India PreValidate API** — an offline validation API for Indian financial identifiers. It validates format and structure without ever hitting government servers (GSTN, NSDL, NPCI, etc.).

### What it validates (15 identifier types):
- **PAN** — format + category code validation
- **GSTIN** — format + checksum verification
- **IFSC** — lookup against 178,000+ codes (RBI open data)
- **Aadhaar** — Verhoeff checksum algorithm
- **UPI/VPA** — format + provider detection
- **Pincode** — lookup against 155,000+ post offices (data.gov.in)
- **Vehicle Registration** — format + RTO code mapping
- **CIN, DIN, TAN, IEC, FSSAI, MSME, Driving License** — format validation

### Why I built it:
Every fintech app doing KYC hits government APIs to validate identifiers. But most of the time, users just mistype their PAN or GSTIN. You're burning API credits on typos.

Pre-validating format *before* calling expensive verification APIs saves real money. And since it's all offline (regex, checksums, local databases), responses are under 100ms with 99.9%+ uptime regardless of whether Sarkari servers are down.

### Tech stack:
- **FastAPI** (Python)
- **SQLite** — 64MB database with IFSC + Pincode data
- **Hosted on Railway**
- **Free tier on RapidAPI** (no credit card needed)

### Links:
- Landing page: https://india-prevalidate-api-production.up.railway.app/
- Swagger docs: https://india-prevalidate-api-production.up.railway.app/docs
- RapidAPI: https://rapidapi.com/rohitshetphoenixorg/api/india-gst-pan-ifsc-validator-bulk-single
- GitHub: https://github.com/rohitshet-phoenix-org/india-prevalidate-api

### Privacy:
DPDP Act 2023 compliant — zero logging of submitted identifiers. All processing is in-memory and discarded after response.

Would love feedback from the community! What other Indian identifiers would you want validated? Any edge cases I'm missing?
