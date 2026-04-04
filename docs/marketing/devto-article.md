---
title: The Complete Guide to Validating Indian Financial Identifiers (PAN, GST, IFSC, Aadhaar & More)
published: false
tags: india, fintech, api, webdev
cover_image: https://india-prevalidate-api-production.up.railway.app/static/img/og-image.png
---

If you've built any fintech or KYC application in India, you know the drill: users submit their PAN, GSTIN, IFSC code, or Aadhaar number, and you need to validate it. The standard approach is calling government APIs — GSTN portal, NSDL, NPCI, or RBI — which costs money per call, has rate limits, and breaks whenever the Sarkari servers go down.

But here's the thing: **most validation failures are just typos.** A mistyped PAN, a GSTIN with a wrong checksum, or a non-existent IFSC code. These can all be caught *offline* before you ever hit an external API.

In this guide, I'll walk you through how each Indian identifier works, how to validate them programmatically, and how I built a free API that does all of this offline.

## The Identifiers We'll Cover

| Identifier | Full Name | Length | Example |
|-----------|-----------|--------|---------|
| PAN | Permanent Account Number | 10 chars | `ABCDE1234F` |
| GSTIN | GST Identification Number | 15 chars | `22AAAAA0000A1Z5` |
| IFSC | Indian Financial System Code | 11 chars | `SBIN0001234` |
| Aadhaar | Unique Identification Number | 12 digits | `2234 5678 9012` |
| UPI/VPA | Virtual Payment Address | varies | `user@paytm` |
| PIN Code | Postal Index Number | 6 digits | `400001` |

---

## 1. PAN — Permanent Account Number

PAN follows a strict 10-character alphanumeric format: `AAAPL1234C`

### Format breakdown:
```
Position 1-3: Three uppercase letters (AAA)
Position 4:   Holder type category letter
              P = Individual (Person)
              C = Company
              H = HUF (Hindu Undivided Family)
              F = Firm
              A = Association of Persons (AOP)
              T = Trust
              B = Body of Individuals (BOI)
              L = Local Authority
              J = Artificial Juridical Person
              G = Government
Position 5:   First letter of holder's surname/name
Position 6-9: Four sequential digits (0001-9999)
Position 10:  Alphabetic check digit
```

### Validation regex:
```python
import re

def validate_pan(pan: str) -> bool:
    pattern = r'^[A-Z]{3}[PCFHATBJLG][A-Z][0-9]{4}[A-Z]$'
    return bool(re.match(pattern, pan.upper().strip()))
```

### What regex alone misses:
- Regex validates format but can't tell you the holder type in a structured way
- Position 4 must be one of exactly 10 letters — `PCFHATBJLG` — not any letter
- Real-world inputs often have lowercase, spaces, or special characters that need normalization

---

## 2. GSTIN — GST Identification Number

GSTIN is a 15-character identifier with a built-in **checksum** that can be mathematically verified.

### Format breakdown:
```
Position 1-2:  State code (01-37, matching Indian states/UTs)
Position 3-12: PAN of the entity (10 characters)
Position 13:   Entity number (1-9, A-Z) for same PAN
Position 14:   Default 'Z'
Position 15:   Checksum character (computed via Luhn mod-36)
```

### The checksum algorithm:
GSTIN uses a **Luhn mod-36** checksum. Here's how it works:

```python
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def compute_gstin_checksum(gstin_14: str) -> str:
    """Compute the 15th check character of a GSTIN."""
    total = 0
    for i, char in enumerate(gstin_14):
        digit = GSTIN_CHARS.index(char.upper())
        if i % 2 != 0:
            digit *= 2
        quotient, remainder = divmod(digit, 36)
        total += quotient + remainder
    check_digit = (36 - (total % 36)) % 36
    return GSTIN_CHARS[check_digit]

def validate_gstin(gstin: str) -> bool:
    if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$', gstin):
        return False
    expected = compute_gstin_checksum(gstin[:14])
    return gstin[14] == expected
```

This is powerful — you can catch transposed digits, typos, and fabricated GSTINs without ever calling the GST portal.

---

## 3. IFSC — Indian Financial System Code

IFSC is an 11-character code that uniquely identifies every bank branch in India.

### Format:
```
Position 1-4: Bank code (e.g., SBIN = State Bank of India)
Position 5:   Always '0' (reserved for future use)
Position 6-11: Branch code (alphanumeric)
```

### Validation approach:
Format validation with regex is easy: `^[A-Z]{4}0[A-Z0-9]{6}$`

But the real value is **database lookup**. With RBI's publicly available IFSC registry (178,000+ codes), you can:
- Confirm the IFSC actually exists
- Return the bank name, branch name, city, district, and state
- Detect recently merged banks (e.g., e-ABG → Baroda)

```python
# Format check
def validate_ifsc_format(ifsc: str) -> bool:
    return bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc.upper()))

# Database lookup gives you much more
# SBIN0001234 → State Bank of India, Mumbai Main Branch, Mumbai, MH
```

---

## 4. Aadhaar — Verhoeff Checksum

Aadhaar is a 12-digit number where the **last digit is a Verhoeff checksum**. The Verhoeff algorithm (1969) catches all single-digit substitutions and most transposition errors.

Without going into the full mathematical derivation, here's how to validate:

```python
# Verhoeff tables
VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9], [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6], [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8], [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2], [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4], [9,8,7,6,5,4,3,2,1,0]
]
VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9], [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2], [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0], [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5], [7,0,4,6,9,1,3,2,5,8]
]
VERHOEFF_INV = [0,4,3,2,1,5,6,7,8,9]

def validate_aadhaar(aadhaar: str) -> bool:
    digits = aadhaar.replace(" ", "")
    if not digits.isdigit() or len(digits) != 12:
        return False
    if digits[0] == '0' or digits[0] == '1':
        return False  # Aadhaar never starts with 0 or 1
    c = 0
    for i, digit in enumerate(reversed(digits)):
        c = VERHOEFF_D[c][VERHOEFF_P[i % 8][int(digit)]]
    return c == 0
```

**Key insight:** This catches 100% of single-digit errors and 100% of adjacent transposition errors. If someone types `523456789012` instead of `253456789012`, the Verhoeff check will fail.

---

## 5. UPI/VPA — Virtual Payment Address

UPI IDs follow the format `username@handle` where the handle identifies the payment service provider.

```python
KNOWN_UPI_HANDLES = {
    "paytm": "Paytm Payments Bank",
    "ybl": "PhonePe (Yes Bank)",
    "ibl": "PhonePe (ICICI Bank)",
    "axl": "PhonePe (Axis Bank)",
    "oksbi": "Google Pay (SBI)",
    "okaxis": "Google Pay (Axis Bank)",
    "okhdfcbank": "Google Pay (HDFC Bank)",
    "upi": "BHIM UPI",
    # ... and many more
}

def validate_upi(vpa: str) -> dict:
    if '@' not in vpa:
        return {"valid": False, "reason": "Missing @ separator"}
    username, handle = vpa.rsplit('@', 1)
    if not re.match(r'^[a-zA-Z0-9._-]{3,}$', username):
        return {"valid": False, "reason": "Invalid username format"}
    provider = KNOWN_UPI_HANDLES.get(handle.lower(), "Unknown")
    return {"valid": True, "handle": handle, "provider": provider}
```

---

## 6. PIN Code — Postal Index Number

India has 155,000+ post offices, each with a 6-digit PIN code. The first digit indicates the postal zone:

```
1 = Delhi, Haryana, HP, J&K, Punjab, Chandigarh
2 = UP, Uttarakhand
3 = Rajasthan, Gujarat, Daman & Diu, Dadra & Nagar Haveli
4 = Maharashtra, Goa
5 = Andhra Pradesh, Telangana, Karnataka
6 = Tamil Nadu, Kerala, Puducherry, Lakshadweep
7 = West Bengal, Odisha, Arunachal, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, Tripura, Andaman & Nicobar
8 = Bihar, Jharkhand
9 = Army Post Office (APO)
```

Format check is simple, but a database lookup against India Post's open data tells you the exact post office, district, state, and region.

---

## The Problem with DIY Validation

You *could* implement all of this yourself. Copy the regex patterns, the Verhoeff tables, download the IFSC CSV from Razorpay's GitHub, parse India Post's pincode data...

But then you need to:
- Keep the IFSC database updated (banks merge, branches open/close)
- Keep the pincode database updated
- Handle edge cases (BH-series vehicle plates, new state codes, UPI handle changes)
- Write tests for all of it
- Deploy and maintain it

That's exactly why I built **India PreValidate API**.

---

## India PreValidate API — All of This, One API Call

I packaged all of the above (and more) into a single API with 23 endpoints:

### Single validation:
```bash
# Validate a PAN
curl -X POST https://india-prevalidate-api-production.up.railway.app/v1/pan/validate \
  -H "Content-Type: application/json" \
  -d '{"identifier": "ABCPE1234F"}'
```

Response:
```json
{
  "valid": true,
  "identifier_type": "PAN",
  "details": {
    "format_valid": true,
    "holder_type": "Individual (Person)",
    "surname_initial": "E"
  },
  "disclaimer": "Format validation only..."
}
```

### Bulk validation (Pro plan):
```bash
curl -X POST https://india-prevalidate-api-production.up.railway.app/v1/pan/bulk-validate \
  -H "Content-Type: application/json" \
  -d '{"identifiers": ["ABCPE1234F", "INVALID", "ZZZZZ9999Z"]}'
```

### Reference data:
```bash
# Get all banks with IFSC prefixes
curl https://india-prevalidate-api-production.up.railway.app/v1/banks

# Get all UPI providers
curl https://india-prevalidate-api-production.up.railway.app/v1/upi-providers

# Get all RTO codes
curl https://india-prevalidate-api-production.up.railway.app/v1/rto-codes
```

### What makes it different:
- **Fully offline** — no government API calls, ever
- **Sub-100ms responses** — everything is local regex, checksums, and SQLite lookups
- **178K+ IFSC codes** from RBI's open data (Razorpay dataset, MIT licensed)
- **155K+ pincodes** from India Post (data.gov.in)
- **DPDP Act 2023 compliant** — zero logging of submitted identifiers
- **Free tier** on RapidAPI — no credit card required

### Links:
- **Try it now:** [Swagger Documentation](https://india-prevalidate-api-production.up.railway.app/docs)
- **Landing page:** [india-prevalidate-api-production.up.railway.app](https://india-prevalidate-api-production.up.railway.app/)
- **RapidAPI:** [Get API Key](https://rapidapi.com/rohitshetphoenixorg/api/india-gst-pan-ifsc-validator-bulk-single)
- **GitHub:** [rohitshet-phoenix-org/india-prevalidate-api](https://github.com/rohitshet-phoenix-org/india-prevalidate-api)

---

## When to Use Pre-Validation vs. Verification

| | Pre-Validation (this API) | Verification (government APIs) |
|---|---|---|
| **What it checks** | Format, structure, checksum | Registration status, ownership |
| **Data source** | Offline algorithms + open data | Government databases |
| **Speed** | <100ms | 500ms - 5s |
| **Cost** | Free / cheap | Per-call pricing |
| **Uptime** | 99.9%+ | Depends on gov servers |
| **Use case** | Form validation, data cleaning, pre-screening | Final KYC verification |

**The ideal workflow:**
1. User enters PAN/GST/IFSC in your form
2. **Pre-validate** with India PreValidate API (instant, free)
3. If format is invalid → show error immediately, save an API call
4. If format is valid → proceed to **verify** with NSDL/GSTN/NPCI

This approach typically reduces verification API costs by **30-50%** by catching typos and formatting errors before they reach paid endpoints.

---

*If you found this useful, consider starring the [GitHub repo](https://github.com/rohitshet-phoenix-org/india-prevalidate-api) and trying out the [free tier on RapidAPI](https://rapidapi.com/rohitshetphoenixorg/api/india-gst-pan-ifsc-validator-bulk-single). I'd love to hear what other Indian identifiers you'd want validated — drop a comment below!*
