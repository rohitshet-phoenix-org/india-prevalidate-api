"""
India PreValidate API — Offline Format Validation & Public Data Enrichment
==========================================================================
This API performs CLIENT-SIDE / OFFLINE structural validation of Indian
business identifiers. It does NOT connect to, query, or scrape any
government database (GSTN, NSDL, NPCI, RBI portals, etc.).

All validation is algorithmic (regex, checksums, known-format rules).
All enrichment data (IFSC branch details, UPI provider mappings, state
codes, PIN code data) is sourced from publicly available, open-data /
public-domain datasets — not from restricted or authenticated government APIs.

PRIVACY NOTICE:
  This API does not store, log, or retain any identifiers submitted for
  validation. All processing is performed in-memory and discarded after
  the response is returned. No personal data is collected, stored, or
  shared. No user profiles are built from API usage patterns.

LEGAL SCOPE — What this API does:
  ✓ Format & structure validation using publicly documented rules
  ✓ Checksum verification using published algorithms (e.g. Luhn mod-36)
  ✓ Component extraction (state codes, entity types, name initials)
  ✓ Public-domain data enrichment (IFSC→branch from RBI open data)
  ✓ Known-handle mapping (UPI provider→bank from public knowledge)
  ✓ PIN code lookup from India Post open data (data.gov.in)

LEGAL SCOPE — What this API does NOT do:
  ✗ Connect to GSTN, GST Portal, or any GSP/ASP gateway
  ✗ Query NSDL/UTIITSL/Protean for PAN holder verification
  ✗ Call NPCI Validate Address API or any live UPI system
  ✗ Scrape any government or banking website
  ✗ Store, process, or return any personal data of third parties
  ✗ Verify identity, KYC status, registration status, or account existence
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
import re
import json
import time
import os
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

# ─── DPDP Act Compliance: Suppress ALL request body logging ─────────────────
# Uvicorn's default access logger only logs method, path, and status code —
# which is safe because all identifiers travel in POST bodies, not URLs.
# We explicitly suppress any deeper logging that frameworks or libraries
# might enable by default. No input identifiers must ever reach disk/stdout.
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)

# ─── App Setup ────────────────────────────────────────────────────────────────

PRIVACY_NOTICE = (
    "India PreValidate API does not store, log, or retain any identifiers "
    "submitted for validation. All processing is performed in-memory and "
    "discarded after the response is returned. No personal data is collected, "
    "stored, or shared."
)

app = FastAPI(
    title="India PreValidate API",
    description=(
        "Offline format validation and public-data enrichment for Indian business "
        "identifiers — GSTIN, PAN, UPI ID, IFSC, CIN, TAN, and more.\n\n"
        "**⚠️ IMPORTANT DISCLAIMER:** This API performs structural/format validation "
        "only. It uses publicly documented format rules, published checksum algorithms, "
        "and open-data / public-domain datasets. It does NOT connect to, query, or "
        "scrape any government database (GSTN, NSDL, NPCI, RBI portals). A successful "
        "format validation does NOT confirm that the identifier is registered, active, "
        "or belongs to any specific entity. For authoritative verification, use licensed "
        "GSP (GST Suvidha Provider), NSDL-authorized, or NPCI-approved services.\n\n"
        "**Privacy Notice:** " + PRIVACY_NOTICE + " "
        "This API does not store, log, or retain any identifiers submitted for "
        "validation. All processing is transient and in-memory only.\n\n"
        "**Data Sources:** IFSC branch data is sourced from RBI's publicly published "
        "IFSC/MICR registry (public domain). PIN code data is from India Post's public "
        "directory on data.gov.in. UPI provider mappings are based on publicly known "
        "handle-to-bank associations. All validation logic uses publicly documented "
        "format specifications."
    ),
    version="2.0.0",
    docs_url=None,
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static Files & Custom UI ───────────────────────────────────────────────

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_APP_DIR)
STATIC_DIR = os.path.join(_PROJECT_ROOT, "static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    """Serve the landing page at root."""
    html_path = os.path.join(STATIC_DIR, "landing.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    """Custom-themed Swagger UI with branded CSS."""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " — API Documentation",
        swagger_favicon_url="/static/img/favicon.svg",
        swagger_css_url="/static/css/swagger-custom.css",
    )

# ─── Aggregate Stats Only (no per-user tracking, no input logging) ──────────
# DPDP Act compliance: We track only aggregate counts. No user identifiers,
# IP addresses, or submitted data is recorded in stats.

stats = {
    "total_requests": 0,
    "gst_validations": 0,
    "pan_validations": 0,
    "upi_validations": 0,
    "ifsc_lookups": 0,
    "cin_validations": 0,
    "din_validations": 0,
    "tan_validations": 0,
    "iec_validations": 0,
    "fssai_validations": 0,
    "msme_validations": 0,
    "vehicle_validations": 0,
    "dl_validations": 0,
    "pincode_lookups": 0,
    "bulk_gst_validations": 0,
    "bulk_pan_validations": 0,
    "started_at": datetime.now(timezone.utc).isoformat(),
}


# ─── Rate Limiter (simple, per-IP, swap for Redis in prod) ───────────────────
# DPDP Note: rate_limits stores ONLY {ip: [timestamp_list]} in memory for
# sliding-window enforcement. No request bodies, identifiers, or usage profiles
# are stored. The dict is ephemeral (lost on restart) and never persisted to disk.

rate_limits: dict = {}
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
BULK_RATE_LIMIT = int(os.getenv("BULK_RATE_LIMIT_PER_MIN", "10"))


async def check_rate_limit(request: Request):
    """Sliding-window rate limiter. Does NOT log client IP or request data."""
    client_ip = request.client.host
    now = time.time()
    window = rate_limits.get(client_ip, [])
    window = [t for t in window if now - t < 60]
    if len(window) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Max {RATE_LIMIT} requests/minute. Upgrade your plan for higher limits.",
                "retry_after_seconds": int(60 - (now - window[0])),
            },
        )
    window.append(now)
    rate_limits[client_ip] = window


async def check_bulk_rate_limit(request: Request):
    """Stricter rate limit for bulk endpoints. Does NOT log client IP or request data."""
    client_ip = request.client.host
    now = time.time()
    key = f"bulk_{client_ip}"
    window = rate_limits.get(key, [])
    window = [t for t in window if now - t < 60]
    if len(window) >= BULK_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "bulk_rate_limit_exceeded",
                "message": f"Max {BULK_RATE_LIMIT} bulk requests/minute. Upgrade your plan for higher limits.",
                "retry_after_seconds": int(60 - (now - window[0])),
            },
        )
    window.append(now)
    rate_limits[key] = window


# ─── Load Data Files ────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


@lru_cache()
def load_ifsc_db() -> dict:
    """Load IFSC → Bank mapping from public-domain RBI dataset."""
    try:
        with open(os.path.join(DATA_DIR, "ifsc_sample.json"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@lru_cache()
def load_pincode_db() -> dict:
    """Load PIN code → location mapping from India Post open data (data.gov.in)."""
    try:
        with open(os.path.join(DATA_DIR, "pincode_sample.json"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@lru_cache()
def load_rto_db() -> dict:
    """Load RTO code → city/state mapping from public knowledge."""
    try:
        with open(os.path.join(DATA_DIR, "rto_codes.json"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ─── Request/Response Models ─────────────────────────────────────────────────

class GSTRequest(BaseModel):
    gstin: str = Field(..., min_length=15, max_length=15, examples=["27AAPFU0939F1ZV"])

class PANRequest(BaseModel):
    pan: str = Field(..., min_length=10, max_length=10, examples=["ABCDE1234F"])

class UPIRequest(BaseModel):
    upi_id: str = Field(..., examples=["rohit@okaxis"])

class IFSCRequest(BaseModel):
    ifsc: str = Field(..., min_length=11, max_length=11, examples=["SBIN0001234"])

class CINRequest(BaseModel):
    cin: str = Field(..., min_length=21, max_length=21, examples=["U72200MH2007PTC175407"])

class DINRequest(BaseModel):
    din: str = Field(..., min_length=8, max_length=8, examples=["00012345"])

class TANRequest(BaseModel):
    tan: str = Field(..., min_length=10, max_length=10, examples=["MUMB12345A"])

class IECRequest(BaseModel):
    iec: str = Field(..., min_length=10, max_length=10, examples=["ABCDE1234F"])

class FSSAIRequest(BaseModel):
    fssai: str = Field(..., min_length=14, max_length=14, examples=["10015011000123"])

class MSMERequest(BaseModel):
    udyam: str = Field(..., examples=["UDYAM-MH-01-0012345"])

class VehicleRequest(BaseModel):
    registration: str = Field(..., examples=["MH01AB1234"])

class DLRequest(BaseModel):
    dl_number: str = Field(..., examples=["MH0120190012345"])

class PincodeRequest(BaseModel):
    pincode: str = Field(..., min_length=6, max_length=6, examples=["110001"])

class BulkGSTRequest(BaseModel):
    gstins: list[str] = Field(..., min_length=1, max_length=50, examples=[["27AAPFU0939F1ZV", "29ABCDE1234F1ZP"]])

class BulkPANRequest(BaseModel):
    pans: list[str] = Field(..., min_length=1, max_length=50, examples=[["ABCPK1234F", "AAACR5678G"]])

class VerifyResponse(BaseModel):
    valid: bool
    input: str
    details: dict
    timestamp: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REFERENCE DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman & Diu", "26": "Dadra & Nagar Haveli", "27": "Maharashtra",
    "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar", "36": "Telangana",
    "37": "Andhra Pradesh (New)", "38": "Ladakh",
}

PAN_FOURTH_CHAR = {
    "A": "Association of Persons (AOP)",
    "B": "Body of Individuals (BOI)",
    "C": "Company",
    "F": "Firm / LLP",
    "G": "Government",
    "H": "Hindu Undivided Family (HUF)",
    "J": "Artificial Juridical Person",
    "L": "Local Authority",
    "P": "Individual / Person",
    "T": "Trust (AOP)",
}

GSTIN_CHECKSUM_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

UPI_PROVIDERS = {
    "okaxis": {"bank": "Axis Bank", "app": "Google Pay"},
    "oksbi": {"bank": "State Bank of India", "app": "Google Pay"},
    "okhdfcbank": {"bank": "HDFC Bank", "app": "Google Pay"},
    "okicici": {"bank": "ICICI Bank", "app": "Google Pay"},
    "ybl": {"bank": "Yes Bank", "app": "PhonePe"},
    "axl": {"bank": "Axis Bank", "app": "PhonePe"},
    "ibl": {"bank": "ICICI Bank", "app": "PhonePe"},
    "paytm": {"bank": "Paytm Payments Bank", "app": "Paytm"},
    "apl": {"bank": "Axis Bank", "app": "Amazon Pay"},
    "ratn": {"bank": "RBL Bank", "app": "Slice"},
    "jupiteraxis": {"bank": "Axis Bank", "app": "Jupiter"},
    "freecharge": {"bank": "Axis Bank", "app": "Freecharge"},
    "upi": {"bank": "Various (NPCI direct)", "app": "BHIM / Bank App"},
    "axisbank": {"bank": "Axis Bank", "app": "Axis Mobile"},
    "sbi": {"bank": "State Bank of India", "app": "SBI YONO"},
    "hdfcbank": {"bank": "HDFC Bank", "app": "HDFC MobileBanking"},
    "icici": {"bank": "ICICI Bank", "app": "iMobile Pay"},
    "kotak": {"bank": "Kotak Mahindra Bank", "app": "Kotak App"},
    "boi": {"bank": "Bank of India", "app": "BOI Mobile"},
    "pnb": {"bank": "Punjab National Bank", "app": "PNB ONE"},
    "indus": {"bank": "IndusInd Bank", "app": "IndusMobile"},
    "federal": {"bank": "Federal Bank", "app": "FedMobile"},
    "citi": {"bank": "Citibank", "app": "Citi Mobile"},
    "idbi": {"bank": "IDBI Bank", "app": "IDBI Go Mobile+"},
    "rbl": {"bank": "RBL Bank", "app": "RBL MoBank"},
    "dlb": {"bank": "Dhanlaxmi Bank", "app": "Dhanlaxmi App"},
    "kbl": {"bank": "Karnataka Bank", "app": "KBL Mobile+"},
    "cbin": {"bank": "Central Bank of India", "app": "Cent Mobile"},
    "cnrb": {"bank": "Canara Bank", "app": "Canara ai1"},
    "barodampay": {"bank": "Bank of Baroda", "app": "bob World"},
    "unionbankofindia": {"bank": "Union Bank of India", "app": "Vyom"},
    "waheed": {"bank": "Waheed (Unknown)", "app": "Unknown"},
    "nsdl": {"bank": "NSDL Payments Bank", "app": "NSDL Jiffy"},
    "airtel": {"bank": "Airtel Payments Bank", "app": "Airtel Thanks"},
    "jio": {"bank": "Jio Payments Bank", "app": "JioMoney"},
    "postbank": {"bank": "India Post Payments Bank", "app": "DakPay"},
    "fino": {"bank": "Fino Payments Bank", "app": "FinoPay"},
}

BANK_CODES = {
    "SBIN": "State Bank of India",
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank",
    "PUNB": "Punjab National Bank",
    "CNRB": "Canara Bank",
    "UBIN": "Union Bank of India",
    "BARB": "Bank of Baroda",
    "IOBA": "Indian Overseas Bank",
    "IDIB": "IDBI Bank",
    "BKID": "Bank of India",
    "CBIN": "Central Bank of India",
    "INDB": "IndusInd Bank",
    "YESB": "Yes Bank",
    "FDRL": "Federal Bank",
    "RATN": "RBL Bank",
    "KARB": "Karnataka Bank",
    "SIBL": "South Indian Bank",
    "TMBL": "Tamilnad Mercantile Bank",
    "KVBL": "Karur Vysya Bank",
    "MAHB": "Bank of Maharashtra",
    "UCBA": "UCO Bank",
    "PSIB": "Punjab & Sind Bank",
    "ALLA": "Allahabad Bank (Indian Bank)",
    "IDUK": "IDFC First Bank",
    "AIRP": "Airtel Payments Bank",
    "PYTM": "Paytm Payments Bank",
    "JIOP": "Jio Payments Bank",
    "DLXB": "Dhanlaxmi Bank",
    "CSBK": "CSB Bank",
    "AUBL": "AU Small Finance Bank",
    "ESFB": "Equitas Small Finance Bank",
    "USFB": "Ujjivan Small Finance Bank",
    "NSPB": "NSDL Payments Bank",
    "FINO": "Fino Payments Bank",
    "DBSS": "DBS Bank India",
    "SCBL": "Standard Chartered Bank",
    "CITI": "Citibank",
    "HSBC": "HSBC India",
    "DEUT": "Deutsche Bank India",
}

CIN_STATE_CODES = {
    "MH": "Maharashtra", "DL": "Delhi", "KA": "Karnataka",
    "TN": "Tamil Nadu", "KL": "Kerala", "GJ": "Gujarat",
    "RJ": "Rajasthan", "UP": "Uttar Pradesh", "WB": "West Bengal",
    "TS": "Telangana", "AP": "Andhra Pradesh", "PB": "Punjab",
    "HR": "Haryana", "MP": "Madhya Pradesh", "BR": "Bihar",
    "OD": "Odisha", "JH": "Jharkhand", "AS": "Assam",
    "GA": "Goa", "CT": "Chhattisgarh", "UK": "Uttarakhand",
    "HP": "Himachal Pradesh", "JK": "Jammu & Kashmir",
    "SK": "Sikkim", "MN": "Manipur", "ML": "Meghalaya",
    "TR": "Tripura", "MZ": "Mizoram", "NL": "Nagaland",
    "AR": "Arunachal Pradesh", "CH": "Chandigarh",
    "AN": "Andaman & Nicobar", "PY": "Puducherry",
    "LD": "Lakshadweep", "DD": "Daman & Diu",
    "DN": "Dadra & Nagar Haveli", "LA": "Ladakh",
}

CIN_COMPANY_TYPES = {
    "PTC": "Private Limited Company",
    "PLC": "Public Limited Company",
    "GAP": "Company Limited by Guarantee (with share capital)",
    "GAT": "Company Limited by Guarantee (without share capital)",
    "ULL": "Unlimited Liability Company",
    "FTC": "Foreign Company (subsidiary)",
    "GOI": "Government Company",
    "NPL": "Not-for-Profit License Company (Section 8)",
    "OPC": "One Person Company",
    "LLP": "Limited Liability Partnership",
}

FSSAI_LICENSE_TYPES = {
    "10": "Central License (large manufacturers, importers)",
    "20": "State License (medium manufacturers, storage)",
    "21": "State License (medium manufacturers)",
    "22": "State License (storage/transport)",
    "11": "Central License (100% EOU)",
    "12": "Central License (head office with central license)",
}

UDYAM_STATE_CODES = {
    "AN": "Andaman & Nicobar", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BR": "Bihar", "CG": "Chhattisgarh", "CH": "Chandigarh",
    "DD": "Daman & Diu", "DL": "Delhi", "DN": "Dadra & Nagar Haveli",
    "GA": "Goa", "GJ": "Gujarat", "HP": "Himachal Pradesh", "HR": "Haryana",
    "JH": "Jharkhand", "JK": "Jammu & Kashmir", "KA": "Karnataka",
    "KL": "Kerala", "LA": "Ladakh", "LD": "Lakshadweep", "MH": "Maharashtra",
    "ML": "Meghalaya", "MN": "Manipur", "MP": "Madhya Pradesh",
    "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha", "PB": "Punjab",
    "PY": "Puducherry", "RJ": "Rajasthan", "SK": "Sikkim",
    "TN": "Tamil Nadu", "TR": "Tripura", "TS": "Telangana",
    "UK": "Uttarakhand", "UP": "Uttar Pradesh", "WB": "West Bengal",
}

PINCODE_REGIONS = {
    "1": {"region": "Northern", "states": "Delhi, Haryana, Punjab, Himachal Pradesh, J&K, Ladakh, Chandigarh"},
    "2": {"region": "Northern", "states": "Uttar Pradesh, Uttarakhand"},
    "3": {"region": "Western", "states": "Rajasthan, Gujarat, Daman & Diu, Dadra & Nagar Haveli"},
    "4": {"region": "Western", "states": "Maharashtra, Goa"},
    "5": {"region": "Southern", "states": "Andhra Pradesh, Telangana, Karnataka"},
    "6": {"region": "Southern", "states": "Kerala, Tamil Nadu, Puducherry, Lakshadweep"},
    "7": {"region": "Eastern", "states": "West Bengal, Odisha, Andaman & Nicobar, Sikkim, NE States"},
    "8": {"region": "Eastern", "states": "Bihar, Jharkhand"},
    "9": {"region": "APS (Army Postal Service)", "states": "Military addresses"},
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_gstin_checksum(gstin: str) -> bool:
    """Validate GSTIN check digit using Luhn mod 36 variant."""
    gstin = gstin.upper()
    total = 0
    for i, ch in enumerate(gstin[:14]):
        val = GSTIN_CHECKSUM_CHARS.index(ch)
        if i % 2 != 0:
            val *= 2
        total += val // 36 + val % 36
    remainder = total % 36
    check_digit = GSTIN_CHECKSUM_CHARS[(36 - remainder) % 36]
    return check_digit == gstin[14]


def _validate_single_gstin(gstin: str) -> dict:
    """Core GSTIN validation logic. Returns details dict. No logging of input."""
    gstin = gstin.upper().strip()
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    format_valid = bool(re.match(pattern, gstin))
    state_code = gstin[:2]
    embedded_pan = gstin[2:12]
    entity_number = gstin[12]
    check_digit = gstin[14]
    state_name = STATE_CODES.get(state_code, "Unknown")
    pan_type_char = embedded_pan[3] if len(embedded_pan) >= 4 else ""
    entity_type = PAN_FOURTH_CHAR.get(pan_type_char, "Unknown")
    checksum_valid = validate_gstin_checksum(gstin) if format_valid else False
    is_valid = format_valid and state_name != "Unknown" and checksum_valid

    return {
        "valid": is_valid,
        "details": {
            "format_valid": format_valid,
            "checksum_valid": checksum_valid,
            "state_code": state_code,
            "state_name": state_name,
            "embedded_pan": embedded_pan,
            "entity_type": entity_type,
            "entity_number": entity_number,
            "check_digit": check_digit,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm GSTN registration "
                "or active status. No data is stored or logged."
            ),
        },
    }


def _validate_single_pan(pan: str) -> dict:
    """Core PAN validation logic. Returns details dict. No logging of input."""
    pan = pan.upper().strip()
    pattern = r"^[A-Z]{3}[ABCFGHJLPT][A-Z][0-9]{4}[A-Z]$"
    format_valid = bool(re.match(pattern, pan))
    entity_char = pan[3] if len(pan) >= 4 else ""
    name_initial = pan[4] if len(pan) >= 5 else ""
    entity_type = PAN_FOURTH_CHAR.get(entity_char, "Unknown")
    serial = pan[5:9] if len(pan) >= 9 else ""

    return {
        "valid": format_valid,
        "details": {
            "format_valid": format_valid,
            "entity_type": entity_type,
            "entity_type_code": entity_char,
            "name_initial": name_initial,
            "name_hint": (
                f"Surname starts with '{name_initial}'"
                if entity_char == "P"
                else f"Entity name starts with '{name_initial}'"
            ),
            "serial_number": serial,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm PAN issuance or holder "
                "identity. Name verification requires authorized NSDL access. "
                "No data is stored or logged."
            ),
        },
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 1: GST VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/gst/validate", response_model=VerifyResponse, tags=["GST Pre-Validation"])
async def validate_gst(body: GSTRequest, _=Depends(check_rate_limit)):
    """
    Pre-validate a GSTIN (Goods & Services Tax Identification Number).

    Performs OFFLINE format and structural validation only. Does NOT query
    the GSTN portal or any GSP/ASP gateway. No input data is stored or logged.

    **What this checks:**
    - 15-character format compliance (regex)
    - Luhn mod-36 checksum verification (published algorithm)
    - State code validity (codes 01-38 per published GST state code list)
    - Embedded PAN extraction and entity type classification

    **What this does NOT check:**
    - Whether the GSTIN is actually registered with GSTN
    - Taxpayer name, registration date, or active/cancelled status

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["gst_validations"] += 1

    result = _validate_single_gstin(body.gstin)
    return VerifyResponse(
        valid=result["valid"],
        input=body.gstin.upper().strip(),
        details=result["details"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 2: PAN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/pan/validate", response_model=VerifyResponse, tags=["PAN Pre-Validation"])
async def validate_pan(body: PANRequest, _=Depends(check_rate_limit)):
    """
    Pre-validate a PAN (Permanent Account Number) and extract embedded info.

    Performs OFFLINE structural analysis only. Does NOT query NSDL,
    UTIITSL (Protean), or the Income Tax Department. No input data is stored or logged.

    **What this checks:**
    - 10-character format compliance (AAAAA9999A pattern)
    - Entity type classification from 4th character
    - Name initial extraction from 5th character

    **What this does NOT check:**
    - Whether the PAN is actually issued or exists in NSDL records
    - PAN holder's name or active status

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["pan_validations"] += 1

    result = _validate_single_pan(body.pan)
    return VerifyResponse(
        valid=result["valid"],
        input=body.pan.upper().strip(),
        details=result["details"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 3: UPI FORMAT PARSING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/upi/validate", response_model=VerifyResponse, tags=["UPI Format Parsing"])
async def validate_upi(body: UPIRequest, _=Depends(check_rate_limit)):
    """
    Parse a UPI ID format and identify the likely provider/bank.

    Performs OFFLINE format parsing and provider handle matching only.
    Does NOT call NPCI's Validate Address API, any PSP system, or any
    bank's UPI infrastructure. No input data is stored or logged.

    **What this checks:**
    - UPI ID format compliance (username@provider pattern)
    - Provider handle recognition against known handles
    - Bank and app mapping based on publicly known associations

    **What this does NOT check:**
    - Whether the UPI ID (VPA) actually exists or is active
    - Account holder name or linked bank account details

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["upi_validations"] += 1

    upi_id = body.upi_id.strip().lower()
    pattern = r"^[a-zA-Z0-9.\-_]{3,}@[a-zA-Z]{2,}$"
    format_valid = bool(re.match(pattern, upi_id))

    parts = upi_id.split("@")
    username = parts[0] if len(parts) == 2 else ""
    provider_handle = parts[1] if len(parts) == 2 else ""

    provider_info = UPI_PROVIDERS.get(provider_handle, None)
    provider_recognized = provider_info is not None

    return VerifyResponse(
        valid=format_valid and provider_recognized,
        input=upi_id,
        details={
            "format_valid": format_valid,
            "username": username,
            "provider_handle": f"@{provider_handle}",
            "provider_recognized": provider_recognized,
            "bank": provider_info["bank"] if provider_info else "Unknown",
            "app": provider_info["app"] if provider_info else "Unknown",
            "validation_type": "offline_format_check",
            "note": (
                "Format and provider handle are structurally valid. This does NOT "
                "confirm the UPI ID exists or is active. Live VPA validation requires "
                "NPCI-approved PSP/TPAP access. No data is stored or logged."
                if format_valid and provider_recognized
                else "Unrecognized UPI handle or invalid format. No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 4: IFSC LOOKUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/ifsc/lookup", response_model=VerifyResponse, tags=["IFSC Lookup (Public Domain)"])
async def lookup_ifsc(body: IFSCRequest, _=Depends(check_rate_limit)):
    """
    Look up bank and branch details from an IFSC code.

    Uses PUBLIC-DOMAIN data sourced from RBI's published IFSC/MICR registry.
    IFSC codes are printed on every cheque leaf and bank passbook in India.

    **Data licensing:** Public domain — no authorization required.

    **Privacy:** IFSC codes identify bank branches, not individuals.
    No personal data is processed.
    """
    stats["total_requests"] += 1
    stats["ifsc_lookups"] += 1

    ifsc = body.ifsc.upper().strip()
    pattern = r"^[A-Z]{4}0[A-Z0-9]{6}$"
    format_valid = bool(re.match(pattern, ifsc))

    bank_code = ifsc[:4]
    branch_code = ifsc[5:] if len(ifsc) >= 11 else ""
    bank_name = BANK_CODES.get(bank_code, None)

    ifsc_db = load_ifsc_db()
    branch_info = ifsc_db.get(ifsc, None)

    return VerifyResponse(
        valid=format_valid and bank_name is not None,
        input=ifsc,
        details={
            "format_valid": format_valid,
            "bank_code": bank_code,
            "bank_name": bank_name or "Unknown bank code",
            "branch_code": branch_code,
            "branch_name": branch_info.get("branch", "Not in sample dataset — load full RBI dataset for complete coverage") if branch_info else "Not in sample dataset",
            "city": branch_info.get("city", "—") if branch_info else "—",
            "state": branch_info.get("state", "—") if branch_info else "—",
            "address": branch_info.get("address", "—") if branch_info else "—",
            "micr_code": branch_info.get("micr", "—") if branch_info else "—",
            "data_source": "RBI published IFSC/MICR registry (public domain)",
            "data_license": "Public domain — no authorization required",
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 5: CIN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/cin/validate", response_model=VerifyResponse, tags=["CIN Pre-Validation"])
async def validate_cin(body: CINRequest, _=Depends(check_rate_limit)):
    """
    Pre-validate a CIN (Company Identification Number) format.

    Performs OFFLINE structural analysis only. Does NOT query the MCA portal
    or any Registrar of Companies database.

    CIN is mandatory on all company letterheads, invoices, and MCA filings
    under the Companies Act 2013 — it is inherently public information.

    **What this checks:**
    - 21-character format compliance
    - Listing status (L=Listed, U=Unlisted)
    - Industry code, state, year, company type, registration number

    **What this does NOT check:**
    - Whether the CIN is actually registered with MCA
    - Company name, status, or director details

    **Privacy:** CIN is a corporate identifier, not personal data.
    """
    stats["total_requests"] += 1
    stats["cin_validations"] += 1

    cin = body.cin.upper().strip()
    pattern = r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$"
    format_valid = bool(re.match(pattern, cin))

    listing_status = cin[0] if len(cin) >= 1 else ""
    industry_code = cin[1:6] if len(cin) >= 6 else ""
    state_code = cin[6:8] if len(cin) >= 8 else ""
    year = cin[8:12] if len(cin) >= 12 else ""
    company_type = cin[12:15] if len(cin) >= 15 else ""
    reg_number = cin[15:21] if len(cin) >= 21 else ""

    state_name = CIN_STATE_CODES.get(state_code, "Unknown")
    company_type_name = CIN_COMPANY_TYPES.get(company_type, "Unknown")
    listing_desc = "Listed on stock exchange" if listing_status == "L" else "Unlisted (private)" if listing_status == "U" else "Unknown"

    year_valid = year.isdigit() and 1850 <= int(year) <= datetime.now().year if year.isdigit() else False
    is_valid = format_valid and state_name != "Unknown" and company_type_name != "Unknown" and year_valid

    return VerifyResponse(
        valid=is_valid,
        input=cin,
        details={
            "format_valid": format_valid,
            "listing_status": listing_desc,
            "listing_code": listing_status,
            "industry_code_nic": industry_code,
            "state_code": state_code,
            "state_name": state_name,
            "year_of_incorporation": year,
            "company_type": company_type_name,
            "company_type_code": company_type,
            "registration_number": reg_number,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm MCA registration or "
                "company active status. CIN is public information displayed on "
                "company letterheads per Companies Act 2013."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 6: DIN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/din/validate", response_model=VerifyResponse, tags=["DIN Pre-Validation"])
async def validate_din(body: DINRequest, _=Depends(check_rate_limit)):
    """
    Pre-validate a DIN (Director Identification Number) format.

    Performs OFFLINE format check only. Does NOT query MCA's DIN database.

    DIN is issued by MCA under the Companies Act 2013 and must be disclosed
    in company annual filings (public records).

    **Privacy:** DIN is a corporate governance identifier disclosed in public filings.
    """
    stats["total_requests"] += 1
    stats["din_validations"] += 1

    din = body.din.strip()
    pattern = r"^[0-9]{8}$"
    format_valid = bool(re.match(pattern, din))

    return VerifyResponse(
        valid=format_valid,
        input=din,
        details={
            "format_valid": format_valid,
            "digit_count": len(din),
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm DIN issuance or director "
                "identity. DIN is disclosed in public company filings per Companies Act 2013."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 7: TAN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/tan/validate", response_model=VerifyResponse, tags=["TAN Pre-Validation"])
async def validate_tan(body: TANRequest, _=Depends(check_rate_limit)):
    """
    Pre-validate a TAN (Tax Deduction Account Number) format.

    Performs OFFLINE format check only. Does NOT query the Income Tax
    Department or NSDL TAN database. No input data is stored or logged.

    TAN is printed on TDS certificates (Form 16/16A) — inherently public information.

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["tan_validations"] += 1

    tan = body.tan.upper().strip()
    pattern = r"^[A-Z]{4}[0-9]{5}[A-Z]$"
    format_valid = bool(re.match(pattern, tan))

    area_code = tan[:4] if len(tan) >= 4 else ""
    serial = tan[4:9] if len(tan) >= 9 else ""
    check_char = tan[9] if len(tan) >= 10 else ""

    return VerifyResponse(
        valid=format_valid,
        input=tan,
        details={
            "format_valid": format_valid,
            "area_code": area_code,
            "serial_number": serial,
            "check_character": check_char,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm TAN issuance or holder identity. "
                "TAN format is published by the Income Tax Department. "
                "No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 8: IEC VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/iec/validate", response_model=VerifyResponse, tags=["IEC Pre-Validation"])
async def validate_iec(body: IECRequest, _=Depends(check_rate_limit)):
    """
    Pre-validate an IEC (Import Export Code) format.

    Performs OFFLINE format check only. Does NOT query DGFT portal.
    No input data is stored or logged.

    IEC follows PAN format as it is essentially the PAN of the
    importing/exporting entity. DGFT provides free public IEC search.

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["iec_validations"] += 1

    iec = body.iec.upper().strip()
    pattern = r"^[A-Z]{3}[ABCFGHJLPT][A-Z][0-9]{4}[A-Z]$"
    format_valid = bool(re.match(pattern, iec))

    entity_char = iec[3] if len(iec) >= 4 else ""
    entity_type = PAN_FOURTH_CHAR.get(entity_char, "Unknown")

    return VerifyResponse(
        valid=format_valid,
        input=iec,
        details={
            "format_valid": format_valid,
            "entity_type": entity_type,
            "entity_type_code": entity_char,
            "note": "IEC follows PAN format — it is the PAN of the importing/exporting entity",
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm DGFT registration or "
                "import/export privileges. IEC format follows published PAN specification. "
                "No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 9: FSSAI FORMAT CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/fssai/format", response_model=VerifyResponse, tags=["FSSAI Format Check"])
async def validate_fssai(body: FSSAIRequest, _=Depends(check_rate_limit)):
    """
    Check FSSAI license number format.

    Performs OFFLINE format check only. Does NOT query FSSAI's portal.
    No input data is stored or logged.

    FSSAI license numbers must be printed on all food product packaging
    in India (Food Safety and Standards Act 2006).

    **Privacy:** FSSAI numbers are business identifiers printed on consumer products.
    """
    stats["total_requests"] += 1
    stats["fssai_validations"] += 1

    fssai = body.fssai.strip()
    pattern = r"^[0-9]{14}$"
    format_valid = bool(re.match(pattern, fssai))

    license_type_code = fssai[:2] if len(fssai) >= 2 else ""
    state_code = fssai[2:4] if len(fssai) >= 4 else ""
    license_type = FSSAI_LICENSE_TYPES.get(license_type_code, "Unknown license type")
    fssai_state = STATE_CODES.get(state_code, "Unknown state")

    return VerifyResponse(
        valid=format_valid,
        input=fssai,
        details={
            "format_valid": format_valid,
            "license_type_code": license_type_code,
            "license_type": license_type,
            "state_code": state_code,
            "state_name": fssai_state,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm FSSAI license issuance or "
                "active status. FSSAI numbers are printed on food packaging per FSSA 2006. "
                "No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 10: MSME / UDYAM FORMAT CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/msme/format", response_model=VerifyResponse, tags=["MSME Format Check"])
async def validate_msme(body: MSMERequest, _=Depends(check_rate_limit)):
    """
    Check Udyam registration number format.

    Performs OFFLINE format check only. Does NOT query the Udyam portal.
    No input data is stored or logged.

    Udyam format was published by the MSME Ministry (2020).

    **Privacy:** Udyam numbers are business identifiers, not personal data.
    """
    stats["total_requests"] += 1
    stats["msme_validations"] += 1

    udyam = body.udyam.upper().strip()
    pattern = r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$"
    format_valid = bool(re.match(pattern, udyam))

    state_code = ""
    district_code = ""
    serial = ""
    state_name = "Unknown"

    if format_valid:
        parts = udyam.split("-")
        state_code = parts[1]
        district_code = parts[2]
        serial = parts[3]
        state_name = UDYAM_STATE_CODES.get(state_code, "Unknown")

    return VerifyResponse(
        valid=format_valid and state_name != "Unknown",
        input=udyam,
        details={
            "format_valid": format_valid,
            "state_code": state_code,
            "state_name": state_name,
            "district_code": district_code,
            "serial_number": serial,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm Udyam registration or "
                "MSME status. Format published by MSME Ministry (2020). "
                "No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 11: VEHICLE REGISTRATION FORMAT CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/vehicle/format", response_model=VerifyResponse, tags=["Vehicle Format Check"])
async def validate_vehicle(body: VehicleRequest, _=Depends(check_rate_limit)):
    """
    Check vehicle registration number format.

    Performs OFFLINE format check only. Does NOT access Parivahan/VAHAN
    database or any RTO system. No input data is stored or logged.

    Vehicle registration numbers are printed on every vehicle's number plate.
    Format is documented under the Motor Vehicles Act.

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["vehicle_validations"] += 1

    reg = body.registration.upper().strip().replace(" ", "").replace("-", "")
    pattern = r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{1,4}$"
    format_valid = bool(re.match(pattern, reg))

    state_code = reg[:2] if len(reg) >= 2 else ""
    rto_code = reg[:4] if len(reg) >= 4 else ""

    rto_db = load_rto_db()
    rto_info = rto_db.get(rto_code, None)
    state_name = CIN_STATE_CODES.get(state_code, "Unknown")

    return VerifyResponse(
        valid=format_valid,
        input=reg,
        details={
            "format_valid": format_valid,
            "state_code": state_code,
            "state_name": state_name,
            "rto_code": rto_code,
            "rto_office": rto_info.get("city", "Not in dataset") if rto_info else "Not in dataset",
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm vehicle registration or "
                "ownership. Does not access Parivahan/VAHAN database. "
                "No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 12: DRIVING LICENSE FORMAT CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/driving-license/format", response_model=VerifyResponse, tags=["DL Format Check"])
async def validate_dl(body: DLRequest, _=Depends(check_rate_limit)):
    """
    Check driving license number format.

    Performs OFFLINE format check only. Does NOT access Sarathi/Parivahan
    portal or any RTO system. No input data is stored or logged.

    DL format is documented under the Motor Vehicles Act.

    **Privacy:** Input is processed in-memory and discarded. Not stored or logged.
    """
    stats["total_requests"] += 1
    stats["dl_validations"] += 1

    dl = body.dl_number.upper().strip().replace(" ", "").replace("-", "")
    pattern = r"^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$"
    format_valid = bool(re.match(pattern, dl))

    state_code = dl[:2] if len(dl) >= 2 else ""
    rto_code = dl[:4] if len(dl) >= 4 else ""
    year = dl[4:8] if len(dl) >= 8 else ""
    serial = dl[8:] if len(dl) >= 8 else ""

    state_name = CIN_STATE_CODES.get(state_code, "Unknown")
    year_valid = year.isdigit() and 1950 <= int(year) <= datetime.now().year if year.isdigit() else False

    return VerifyResponse(
        valid=format_valid and state_name != "Unknown" and year_valid,
        input=dl,
        details={
            "format_valid": format_valid,
            "state_code": state_code,
            "state_name": state_name,
            "rto_code": rto_code,
            "year_of_issue": year,
            "serial_number": serial,
            "validation_type": "offline_format_check",
            "disclaimer": (
                "Format validation only. Does not confirm DL issuance or validity. "
                "Does not access Sarathi/Parivahan portal. Format documented under "
                "Motor Vehicles Act. No data is stored or logged."
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 13: PIN CODE LOOKUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/pincode/lookup", response_model=VerifyResponse, tags=["PIN Code Lookup (Public Domain)"])
async def lookup_pincode(body: PincodeRequest, _=Depends(check_rate_limit)):
    """
    Look up location details from an Indian PIN code.

    Uses PUBLIC-DOMAIN data from India Post's All India Pincode Directory,
    published on data.gov.in — Government of India's Open Data platform.

    **Data licensing:** Government of India Open Data — free for public use.

    **Privacy:** PIN codes identify geographic areas, not individuals.
    """
    stats["total_requests"] += 1
    stats["pincode_lookups"] += 1

    pincode = body.pincode.strip()
    pattern = r"^[1-9][0-9]{5}$"
    format_valid = bool(re.match(pattern, pincode))

    first_digit = pincode[0] if len(pincode) >= 1 else ""
    region_info = PINCODE_REGIONS.get(first_digit, None)

    pincode_db = load_pincode_db()
    location = pincode_db.get(pincode, None)

    return VerifyResponse(
        valid=format_valid,
        input=pincode,
        details={
            "format_valid": format_valid,
            "region": region_info["region"] if region_info else "Unknown",
            "region_states": region_info["states"] if region_info else "Unknown",
            "office_name": location.get("office", "Not in sample dataset — load full India Post dataset for complete coverage") if location else "Not in sample dataset",
            "district": location.get("district", "—") if location else "—",
            "state": location.get("state", "—") if location else "—",
            "circle": location.get("circle", "—") if location else "—",
            "delivery": location.get("delivery", "—") if location else "—",
            "data_source": "India Post All India Pincode Directory (data.gov.in — public domain)",
            "data_license": "Government of India Open Data — free for public use",
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 14: BULK GSTIN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/gst/bulk-validate", tags=["GST Pre-Validation (Bulk)"])
async def bulk_validate_gst(body: BulkGSTRequest, _=Depends(check_bulk_rate_limit)):
    """
    Batch pre-validate up to 50 GSTINs in a single API call.

    Same offline algorithmic validation as /v1/gst/validate, accepting an array.
    Rate-limited to prevent abuse. Premium feature for paid plans.

    No input data is stored or logged. All processing is in-memory.
    """
    stats["total_requests"] += 1
    stats["bulk_gst_validations"] += 1

    results = []
    for gstin in body.gstins:
        if len(gstin) != 15:
            results.append({
                "input": gstin.upper().strip(),
                "valid": False,
                "details": {"error": "Must be exactly 15 characters", "validation_type": "offline_format_check"},
            })
        else:
            r = _validate_single_gstin(gstin)
            results.append({
                "input": gstin.upper().strip(),
                "valid": r["valid"],
                "details": r["details"],
            })

    valid_count = sum(1 for r in results if r["valid"])
    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "results": results,
        "validation_type": "offline_format_check",
        "disclaimer": (
            "Batch format validation only. Does not confirm GSTN registration. "
            "No input data is stored, logged, or retained."
        ),
        "privacy_notice": PRIVACY_NOTICE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT 15: BULK PAN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/v1/pan/bulk-validate", tags=["PAN Pre-Validation (Bulk)"])
async def bulk_validate_pan(body: BulkPANRequest, _=Depends(check_bulk_rate_limit)):
    """
    Batch pre-validate up to 50 PANs in a single API call.

    Same offline algorithmic validation as /v1/pan/validate, accepting an array.
    Rate-limited to prevent abuse. Premium feature for paid plans.

    No input data is stored or logged. All processing is in-memory.
    """
    stats["total_requests"] += 1
    stats["bulk_pan_validations"] += 1

    results = []
    for pan in body.pans:
        if len(pan) != 10:
            results.append({
                "input": pan.upper().strip(),
                "valid": False,
                "details": {"error": "Must be exactly 10 characters", "validation_type": "offline_format_check"},
            })
        else:
            r = _validate_single_pan(pan)
            results.append({
                "input": pan.upper().strip(),
                "valid": r["valid"],
                "details": r["details"],
            })

    valid_count = sum(1 for r in results if r["valid"])
    return {
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "results": results,
        "validation_type": "offline_format_check",
        "disclaimer": (
            "Batch format validation only. Does not confirm PAN issuance. "
            "No input data is stored, logged, or retained."
        ),
        "privacy_notice": PRIVACY_NOTICE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTILITY ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/v1/health", tags=["Utility"])
async def health_check():
    """Health check for uptime monitoring."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "India PreValidate API",
        "validation_type": "offline_format_check",
        "privacy": "No data is stored, logged, or retained",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/v1/disclaimer", tags=["Utility"])
async def get_disclaimer():
    """
    Legal disclaimer, privacy notice, and scope of this API.
    Consumers of this API should review this before integrating.
    """
    return {
        "service": "India PreValidate API",
        "version": "2.0.0",
        "privacy_notice": PRIVACY_NOTICE,
        "privacy_notice_short": (
            "This API does not store, log, or retain any identifiers submitted "
            "for validation. All processing is transient and in-memory only."
        ),
        "legal_scope": {
            "what_this_api_does": [
                "Offline format and structure validation using publicly documented rules",
                "Checksum verification using published algorithms (e.g. Luhn mod-36 for GSTIN)",
                "Component extraction (state codes, entity types, name initials)",
                "Public-domain data enrichment (IFSC branch data from RBI open publications)",
                "Public-domain data enrichment (PIN code data from India Post / data.gov.in)",
                "Known-handle mapping (UPI provider-to-bank from publicly available information)",
            ],
            "what_this_api_does_NOT_do": [
                "Connect to, query, or scrape GSTN, GST Portal, or any GSP/ASP gateway",
                "Query NSDL, UTIITSL (Protean), or Income Tax Department systems",
                "Call NPCI Validate Address API or any live UPI/banking system",
                "Access MCA portal, Parivahan/VAHAN, Sarathi, or any RTO system",
                "Access DGFT, FSSAI, or Udyam registration portals",
                "Scrape any government, banking, or financial services website",
                "Store, log, or retain any identifiers submitted for validation",
                "Build user profiles from API usage patterns",
                "Collect, process, or share any personal data",
                "Verify identity, KYC status, registration status, or account existence",
            ],
        },
        "data_handling": {
            "input_retention": "NONE — all inputs are processed in-memory and discarded after response",
            "logging_policy": "No input identifiers are logged. Only aggregate request counts are tracked.",
            "user_profiling": "NONE — no per-user or per-IP usage profiles are built",
            "data_sharing": "NONE — no data is shared with any third party",
        },
        "data_sources": {
            "gstin_validation": "Algorithmic — publicly documented format rules and Luhn mod-36 checksum",
            "pan_validation": "Algorithmic — publicly documented AAAAA9999A format specification",
            "upi_provider_mapping": "Curated from publicly known handle-to-bank associations",
            "ifsc_branch_data": "RBI published IFSC/MICR registry (public domain)",
            "pincode_data": "India Post All India Pincode Directory (data.gov.in — public domain)",
            "cin_validation": "Algorithmic — Companies Act 2013 published format",
            "din_validation": "Algorithmic — MCA published 8-digit format",
            "tan_validation": "Algorithmic — Income Tax Department published format",
            "iec_validation": "Algorithmic — DGFT published format (same as PAN)",
            "fssai_validation": "Algorithmic — FSSA 2006 published 14-digit format",
            "msme_validation": "Algorithmic — MSME Ministry published Udyam format (2020)",
            "vehicle_validation": "Algorithmic — Motor Vehicles Act published format",
            "dl_validation": "Algorithmic — Motor Vehicles Act published format",
            "state_codes": "Published GST state code list (public knowledge)",
            "rto_codes": "State transport department published RTO codes (public knowledge)",
        },
        "important_notice": (
            "A successful format validation confirms structural correctness only. "
            "It does NOT confirm that the identifier is registered, active, or belongs "
            "to any specific entity. For authoritative verification, consumers must use "
            "licensed/authorized services as applicable."
        ),
        "applicable_regulations_acknowledged": [
            "Information Technology Act, 2000 (Section 43 — unauthorized access)",
            "Digital Personal Data Protection Act, 2023 (DPDP Act)",
            "NPCI UPI Procedural Guidelines and API Usage Circulars",
            "GSTN GSP/ASP Framework for GST data access",
            "NSDL/Protean authorized entity requirements for PAN verification",
            "Companies Act 2013 (CIN/DIN format and disclosure requirements)",
            "Motor Vehicles Act (vehicle registration and DL formats)",
            "Food Safety and Standards Act 2006 (FSSAI license display requirements)",
        ],
        "compliance_statement": (
            "This API does not access any restricted, authenticated, or licensed "
            "government/financial system. All data used is either algorithmically "
            "derived from publicly documented format specifications or sourced from "
            "explicitly public-domain datasets. No personal data of any individual "
            "is stored, logged, processed beyond transient in-memory validation, "
            "or returned by this API."
        ),
    }


@app.get("/v1/stats", tags=["Utility"])
async def get_stats():
    """
    Aggregate usage statistics. No per-user or per-IP data is tracked.
    Protect this endpoint with admin auth in production.
    """
    return {
        **stats,
        "note": "Aggregate counts only. No per-user, per-IP, or per-input data is tracked.",
    }


@app.get("/v1/states", tags=["Reference Data"])
async def list_state_codes():
    """
    List all valid Indian state codes used in GSTIN (first 2 digits).
    Source: Published GST state code list (public knowledge).
    """
    return {"states": STATE_CODES, "data_source": "Published GST state code list"}


@app.get("/v1/banks", tags=["Reference Data"])
async def list_bank_codes():
    """
    List all recognized IFSC bank codes (first 4 characters).
    Source: RBI published bank code assignments (public domain).
    """
    return {"banks": BANK_CODES, "data_source": "RBI published bank codes (public domain)"}


@app.get("/v1/upi-providers", tags=["Reference Data"])
async def list_upi_providers():
    """
    List all recognized UPI provider handles with bank/app mapping.
    Source: Publicly known UPI handle-to-bank associations.
    """
    return {
        "providers": {f"@{k}": v for k, v in UPI_PROVIDERS.items()},
        "data_source": "Publicly known UPI handle-to-bank associations",
        "note": "Provider list may not be exhaustive. New handles are added periodically.",
    }


@app.get("/v1/rto-codes", tags=["Reference Data"])
async def list_rto_codes():
    """
    List all recognized RTO codes with city/state mapping.
    Source: State transport department published RTO codes (public knowledge).
    """
    rto_db = load_rto_db()
    return {
        "rto_codes": rto_db,
        "total": len(rto_db),
        "data_source": "State transport department published RTO codes (public knowledge)",
    }


@app.get("/v1/pincode/states", tags=["Reference Data"])
async def list_pincode_states():
    """
    List PIN code first-digit region mapping (India Post system).
    Source: India Post published PIN code documentation (data.gov.in — public domain).
    """
    return {
        "regions": PINCODE_REGIONS,
        "data_source": "India Post PIN code system documentation (data.gov.in — public domain)",
        "data_license": "Government of India Open Data — free for public use",
    }


# ─── Validation Error Handler ─────────────────────────────────────────────────
# DPDP Act compliance: FastAPI's default 422 response includes submitted input
# values in the error body. We override this to strip all input data from error
# responses, returning only field names and error types — never the actual values.

from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return validation errors WITHOUT echoing back submitted input values."""
    sanitized_errors = []
    for err in exc.errors():
        sanitized_errors.append({
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "type": err.get("type", "unknown"),
            "message": err.get("msg", "Validation error"),
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "details": sanitized_errors,
            "privacy": "No submitted data is included in error responses, stored, or logged.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ─── Global Error Handler ────────────────────────────────────────────────────
# Error responses intentionally do NOT include request details, input data,
# stack traces, or any information that could constitute logging of user input.

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Something went wrong. Please try again.",
            "privacy": "No request data has been stored or logged.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ─── Static File Mount (MUST be last — acts as catch-all) ──────────────────
# Placed after all route definitions so it doesn't shadow API endpoints.

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
