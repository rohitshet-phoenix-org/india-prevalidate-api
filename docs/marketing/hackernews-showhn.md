# Hacker News — Show HN Post

**Title:** Show HN: India PreValidate – Offline validation API for PAN, GST, IFSC, Aadhaar, UPI

**URL:** https://india-prevalidate-api-production.up.railway.app/

---

**First comment (post immediately after submitting):**

Hi HN! I built an offline validation API for Indian financial identifiers.

**The problem:** Indian fintech apps doing KYC validation hit government APIs (GSTN, NSDL, NPCI) for every check. These APIs cost money per call, have rate limits, and go down frequently. Most failures are just user typos — a mistyped PAN or GSTIN that could be caught client-side.

**The solution:** India PreValidate API validates format, structure, and checksums entirely offline — no government API calls. It catches malformed identifiers before you waste money on expensive verification calls.

**What it covers:**
- PAN (format + category code)
- GSTIN (format + Luhn mod-36 checksum)
- IFSC (lookup against 178K+ codes from RBI open data)
- Aadhaar (Verhoeff algorithm)
- UPI/VPA (format + provider detection)
- Pincode (155K+ post offices from data.gov.in)
- Vehicle registration, CIN, DIN, TAN, IEC, FSSAI, MSME, Driving License

**Technical details:**
- FastAPI + SQLite (64MB database), hosted on Railway
- Sub-100ms responses (everything is local regex/checksums/DB lookups)
- 23 endpoints including bulk validation
- DPDP Act 2023 compliant — zero input logging
- Free tier on RapidAPI

Swagger docs: https://india-prevalidate-api-production.up.railway.app/docs

Happy to answer questions about the validation algorithms or the Indian identifier format specs.
