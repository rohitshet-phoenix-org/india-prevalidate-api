"""
Tests for India PreValidate API
Run: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─── Health Check ─────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ─── GST Validation ──────────────────────────────────────────────────────────

class TestGST:
    def test_valid_gstin_format(self):
        """27AAPFU0939F1ZV is a well-formed Maharashtra GSTIN."""
        r = client.post("/v1/gst/validate", json={"gstin": "27AAPFU0939F1ZV"})
        data = r.json()
        assert r.status_code == 200
        assert data["details"]["state_name"] == "Maharashtra"
        assert data["details"]["format_valid"] is True
        assert data["details"]["entity_type"] == "Firm / LLP"

    def test_invalid_gstin_too_short(self):
        r = client.post("/v1/gst/validate", json={"gstin": "27AAP"})
        assert r.status_code == 422  # Pydantic validation error

    def test_invalid_gstin_bad_state(self):
        r = client.post("/v1/gst/validate", json={"gstin": "99AAPFU0939F1ZV"})
        data = r.json()
        assert data["details"]["state_name"] == "Unknown"
        assert data["valid"] is False

    def test_gstin_delhi(self):
        r = client.post("/v1/gst/validate", json={"gstin": "07AAPFU0939F1ZV"})
        data = r.json()
        assert data["details"]["state_code"] == "07"
        assert data["details"]["state_name"] == "Delhi"

    def test_gstin_extracts_pan(self):
        r = client.post("/v1/gst/validate", json={"gstin": "29ABCDE1234F1ZP"})
        data = r.json()
        assert data["details"]["embedded_pan"] == "ABCDE1234F"


# ─── PAN Validation ──────────────────────────────────────────────────────────

class TestPAN:
    def test_valid_individual_pan(self):
        r = client.post("/v1/pan/validate", json={"pan": "ABCPK1234F"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["entity_type"] == "Individual / Person"
        assert data["details"]["name_initial"] == "K"

    def test_valid_company_pan(self):
        r = client.post("/v1/pan/validate", json={"pan": "AAACR5678G"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["entity_type"] == "Company"

    def test_invalid_pan_wrong_4th_char(self):
        r = client.post("/v1/pan/validate", json={"pan": "ABCXK1234F"})
        data = r.json()
        assert data["valid"] is False

    def test_invalid_pan_too_short(self):
        r = client.post("/v1/pan/validate", json={"pan": "ABC"})
        assert r.status_code == 422


# ─── UPI Validation ──────────────────────────────────────────────────────────

class TestUPI:
    def test_valid_gpay_upi(self):
        r = client.post("/v1/upi/validate", json={"upi_id": "rohit@okaxis"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["bank"] == "Axis Bank"
        assert data["details"]["app"] == "Google Pay"

    def test_valid_phonepe_upi(self):
        r = client.post("/v1/upi/validate", json={"upi_id": "testuser@ybl"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["app"] == "PhonePe"

    def test_valid_paytm_upi(self):
        r = client.post("/v1/upi/validate", json={"upi_id": "9876543210@paytm"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["bank"] == "Paytm Payments Bank"

    def test_unknown_provider(self):
        r = client.post("/v1/upi/validate", json={"upi_id": "test@xyzunknown"})
        data = r.json()
        assert data["valid"] is False
        assert data["details"]["provider_recognized"] is False

    def test_invalid_format(self):
        r = client.post("/v1/upi/validate", json={"upi_id": "nope"})
        data = r.json()
        assert data["valid"] is False


# ─── IFSC Lookup ──────────────────────────────────────────────────────────────

class TestIFSC:
    def test_valid_sbi_ifsc(self):
        r = client.post("/v1/ifsc/lookup", json={"ifsc": "SBIN0001234"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["bank_name"] == "State Bank of India"
        assert data["details"]["branch_name"] == "Andheri West"

    def test_valid_hdfc_ifsc(self):
        r = client.post("/v1/ifsc/lookup", json={"ifsc": "HDFC0000001"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["bank_name"] == "HDFC Bank"

    def test_unknown_bank_code(self):
        r = client.post("/v1/ifsc/lookup", json={"ifsc": "ZZZZ0000001"})
        data = r.json()
        assert data["valid"] is False
        assert data["details"]["bank_name"] == "Unknown bank code"

    def test_invalid_format(self):
        r = client.post("/v1/ifsc/lookup", json={"ifsc": "SBI123"})
        assert r.status_code == 422


# ─── Utility Endpoints ───────────────────────────────────────────────────────

def test_list_states():
    r = client.get("/v1/states")
    assert r.status_code == 200
    assert "07" in r.json()["states"]  # Delhi

def test_list_banks():
    r = client.get("/v1/banks")
    assert r.status_code == 200
    assert "SBIN" in r.json()["banks"]

def test_list_upi_providers():
    r = client.get("/v1/upi-providers")
    assert r.status_code == 200
    assert "@paytm" in r.json()["providers"]

def test_stats():
    r = client.get("/v1/stats")
    assert r.status_code == 200
    assert "total_requests" in r.json()


# ─── Legal Framing Tests ─────────────────────────────────────────────────────

def test_disclaimer_endpoint():
    """The /v1/disclaimer endpoint must exist and return full legal scope."""
    r = client.get("/v1/disclaimer")
    assert r.status_code == 200
    data = r.json()
    assert "legal_scope" in data
    assert "what_this_api_does" in data["legal_scope"]
    assert "what_this_api_does_NOT_do" in data["legal_scope"]
    assert "data_sources" in data
    assert "compliance_statement" in data
    assert "applicable_regulations_acknowledged" in data


def test_gst_response_includes_disclaimer():
    """GST response must include validation_type and disclaimer fields."""
    r = client.post("/v1/gst/validate", json={"gstin": "27AAPFU0939F1ZV"})
    data = r.json()
    assert data["details"]["validation_type"] == "offline_format_check"
    assert "disclaimer" in data["details"]
    assert "does not confirm" in data["details"]["disclaimer"].lower()


def test_pan_response_includes_disclaimer():
    """PAN response must include validation_type and disclaimer fields."""
    r = client.post("/v1/pan/validate", json={"pan": "ABCPK1234F"})
    data = r.json()
    assert data["details"]["validation_type"] == "offline_format_check"
    assert "disclaimer" in data["details"]
    assert "does not confirm" in data["details"]["disclaimer"].lower()


def test_upi_response_includes_validation_type():
    """UPI response must include validation_type field."""
    r = client.post("/v1/upi/validate", json={"upi_id": "rohit@okaxis"})
    data = r.json()
    assert data["details"]["validation_type"] == "offline_format_check"
    assert "does NOT confirm" in data["details"]["note"]


def test_ifsc_response_includes_public_domain_source():
    """IFSC response must cite public-domain data source."""
    r = client.post("/v1/ifsc/lookup", json={"ifsc": "SBIN0001234"})
    data = r.json()
    assert "public domain" in data["details"]["data_source"].lower()
    assert "data_license" in data["details"]


def test_health_includes_service_name():
    """Health check must include service name and validation type."""
    r = client.get("/v1/health")
    data = r.json()
    assert data["service"] == "India PreValidate API"
    assert data["validation_type"] == "offline_format_check"


def test_states_includes_data_source():
    """States endpoint must cite its data source."""
    r = client.get("/v1/states")
    data = r.json()
    assert "data_source" in data


def test_banks_includes_data_source():
    """Banks endpoint must cite its data source."""
    r = client.get("/v1/banks")
    data = r.json()
    assert "data_source" in data


def test_upi_providers_includes_data_source():
    """UPI providers endpoint must cite its data source."""
    r = client.get("/v1/upi-providers")
    data = r.json()
    assert "data_source" in data


# ─── CIN Validation ─────────────────────────────────────────────────────────

class TestCIN:
    def test_valid_cin(self):
        """U72200MH2007PTC175407 is a well-formed CIN."""
        r = client.post("/v1/cin/validate", json={"cin": "U72200MH2007PTC175407"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["listing_code"] == "U"
        assert data["details"]["state_name"] == "Maharashtra"
        assert data["details"]["company_type"] == "Private Limited Company"
        assert data["details"]["year_of_incorporation"] == "2007"

    def test_listed_cin(self):
        r = client.post("/v1/cin/validate", json={"cin": "L72200DL2010PLC200001"})
        data = r.json()
        assert data["details"]["listing_code"] == "L"
        assert data["details"]["state_name"] == "Delhi"
        assert data["details"]["company_type"] == "Public Limited Company"

    def test_invalid_cin_bad_state(self):
        r = client.post("/v1/cin/validate", json={"cin": "U72200ZZ2007PTC175407"})
        data = r.json()
        assert data["valid"] is False

    def test_cin_too_short(self):
        r = client.post("/v1/cin/validate", json={"cin": "U72200MH"})
        assert r.status_code == 422

    def test_cin_response_includes_disclaimer(self):
        r = client.post("/v1/cin/validate", json={"cin": "U72200MH2007PTC175407"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]
        assert "does not confirm" in data["details"]["disclaimer"].lower()


# ─── DIN Validation ─────────────────────────────────────────────────────────

class TestDIN:
    def test_valid_din(self):
        r = client.post("/v1/din/validate", json={"din": "00012345"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["format_valid"] is True

    def test_invalid_din_alpha(self):
        r = client.post("/v1/din/validate", json={"din": "0001234A"})
        data = r.json()
        assert data["valid"] is False

    def test_din_too_short(self):
        r = client.post("/v1/din/validate", json={"din": "1234"})
        assert r.status_code == 422

    def test_din_response_includes_disclaimer(self):
        r = client.post("/v1/din/validate", json={"din": "00012345"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]


# ─── TAN Validation ─────────────────────────────────────────────────────────

class TestTAN:
    def test_valid_tan(self):
        r = client.post("/v1/tan/validate", json={"tan": "MUMB12345A"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["area_code"] == "MUMB"

    def test_invalid_tan_format(self):
        r = client.post("/v1/tan/validate", json={"tan": "1234567890"})
        data = r.json()
        assert data["valid"] is False

    def test_tan_response_includes_disclaimer(self):
        r = client.post("/v1/tan/validate", json={"tan": "MUMB12345A"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]
        assert "does not confirm" in data["details"]["disclaimer"].lower()


# ─── IEC Validation ─────────────────────────────────────────────────────────

class TestIEC:
    def test_valid_iec(self):
        """IEC follows PAN format — 4th char must be a valid entity type (C=Company)."""
        r = client.post("/v1/iec/validate", json={"iec": "ABCCE1234F"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["entity_type"] == "Company"

    def test_invalid_iec_wrong_4th_char(self):
        r = client.post("/v1/iec/validate", json={"iec": "ABCXE1234F"})
        data = r.json()
        assert data["valid"] is False

    def test_iec_response_includes_disclaimer(self):
        r = client.post("/v1/iec/validate", json={"iec": "ABCCE1234F"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]


# ─── FSSAI Validation ───────────────────────────────────────────────────────

class TestFSSAI:
    def test_valid_fssai(self):
        r = client.post("/v1/fssai/format", json={"fssai": "10015011000123"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["format_valid"] is True

    def test_invalid_fssai_alpha(self):
        r = client.post("/v1/fssai/format", json={"fssai": "1001501100012A"})
        data = r.json()
        assert data["valid"] is False

    def test_fssai_too_short(self):
        r = client.post("/v1/fssai/format", json={"fssai": "123"})
        assert r.status_code == 422

    def test_fssai_response_includes_disclaimer(self):
        r = client.post("/v1/fssai/format", json={"fssai": "10015011000123"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]
        assert "does not confirm" in data["details"]["disclaimer"].lower()


# ─── MSME / Udyam Validation ───────────────────────────────────────────────

class TestMSME:
    def test_valid_udyam(self):
        r = client.post("/v1/msme/format", json={"udyam": "UDYAM-MH-01-0012345"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["state_name"] == "Maharashtra"

    def test_invalid_udyam_bad_state(self):
        r = client.post("/v1/msme/format", json={"udyam": "UDYAM-ZZ-01-0012345"})
        data = r.json()
        assert data["valid"] is False

    def test_invalid_udyam_format(self):
        r = client.post("/v1/msme/format", json={"udyam": "NOTUDYAM12345"})
        data = r.json()
        assert data["valid"] is False

    def test_msme_response_includes_disclaimer(self):
        r = client.post("/v1/msme/format", json={"udyam": "UDYAM-MH-01-0012345"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]


# ─── Vehicle Registration Validation ────────────────────────────────────────

class TestVehicle:
    def test_valid_vehicle(self):
        r = client.post("/v1/vehicle/format", json={"registration": "MH01AB1234"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["state_code"] == "MH"
        assert data["details"]["state_name"] == "Maharashtra"

    def test_vehicle_with_spaces(self):
        r = client.post("/v1/vehicle/format", json={"registration": "MH 01 AB 1234"})
        data = r.json()
        assert data["valid"] is True

    def test_invalid_vehicle_format(self):
        r = client.post("/v1/vehicle/format", json={"registration": "123456"})
        data = r.json()
        assert data["valid"] is False

    def test_vehicle_response_includes_disclaimer(self):
        r = client.post("/v1/vehicle/format", json={"registration": "MH01AB1234"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]
        assert "does not confirm" in data["details"]["disclaimer"].lower()


# ─── Driving License Validation ─────────────────────────────────────────────

class TestDL:
    def test_valid_dl(self):
        r = client.post("/v1/driving-license/format", json={"dl_number": "MH0120190012345"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["state_name"] == "Maharashtra"
        assert data["details"]["year_of_issue"] == "2019"

    def test_invalid_dl_bad_year(self):
        r = client.post("/v1/driving-license/format", json={"dl_number": "MH0118000012345"})
        data = r.json()
        assert data["valid"] is False

    def test_dl_response_includes_disclaimer(self):
        r = client.post("/v1/driving-license/format", json={"dl_number": "MH0120190012345"})
        data = r.json()
        assert data["details"]["validation_type"] == "offline_format_check"
        assert "disclaimer" in data["details"]
        assert "does not confirm" in data["details"]["disclaimer"].lower()


# ─── PIN Code Lookup ────────────────────────────────────────────────────────

class TestPincode:
    def test_valid_pincode_delhi(self):
        r = client.post("/v1/pincode/lookup", json={"pincode": "110001"})
        data = r.json()
        assert r.status_code == 200
        assert data["valid"] is True
        assert data["details"]["region"] == "Northern"
        assert data["details"]["office_name"] == "Connaught Place"

    def test_valid_pincode_mumbai(self):
        r = client.post("/v1/pincode/lookup", json={"pincode": "400001"})
        data = r.json()
        assert data["valid"] is True
        assert data["details"]["state"] == "Maharashtra"

    def test_invalid_pincode_starts_with_zero(self):
        r = client.post("/v1/pincode/lookup", json={"pincode": "012345"})
        data = r.json()
        assert data["valid"] is False

    def test_pincode_too_short(self):
        r = client.post("/v1/pincode/lookup", json={"pincode": "110"})
        assert r.status_code == 422

    def test_pincode_response_includes_data_source(self):
        r = client.post("/v1/pincode/lookup", json={"pincode": "110001"})
        data = r.json()
        assert "public domain" in data["details"]["data_source"].lower()
        assert "data_license" in data["details"]


# ─── Bulk GST Validation ────────────────────────────────────────────────────

class TestBulkGST:
    def test_bulk_gst_multiple(self):
        r = client.post("/v1/gst/bulk-validate", json={"gstins": ["27AAPFU0939F1ZV", "29ABCDE1234F1ZP"]})
        data = r.json()
        assert r.status_code == 200
        assert data["total"] == 2
        assert "results" in data
        assert data["valid_count"] + data["invalid_count"] == 2

    def test_bulk_gst_includes_disclaimer(self):
        r = client.post("/v1/gst/bulk-validate", json={"gstins": ["27AAPFU0939F1ZV"]})
        data = r.json()
        assert "disclaimer" in data
        assert "does not confirm" in data["disclaimer"].lower()
        assert "privacy_notice" in data

    def test_bulk_gst_bad_length(self):
        r = client.post("/v1/gst/bulk-validate", json={"gstins": ["SHORT", "27AAPFU0939F1ZV"]})
        data = r.json()
        assert data["results"][0]["valid"] is False
        assert "error" in data["results"][0]["details"]

    def test_bulk_gst_max_50(self):
        """Reject batches larger than 50."""
        gstins = ["27AAPFU0939F1ZV"] * 51
        r = client.post("/v1/gst/bulk-validate", json={"gstins": gstins})
        assert r.status_code == 422


# ─── Bulk PAN Validation ────────────────────────────────────────────────────

class TestBulkPAN:
    def test_bulk_pan_multiple(self):
        r = client.post("/v1/pan/bulk-validate", json={"pans": ["ABCPK1234F", "AAACR5678G"]})
        data = r.json()
        assert r.status_code == 200
        assert data["total"] == 2
        assert data["valid_count"] + data["invalid_count"] == 2

    def test_bulk_pan_includes_disclaimer(self):
        r = client.post("/v1/pan/bulk-validate", json={"pans": ["ABCPK1234F"]})
        data = r.json()
        assert "disclaimer" in data
        assert "does not confirm" in data["disclaimer"].lower()
        assert "privacy_notice" in data

    def test_bulk_pan_bad_length(self):
        r = client.post("/v1/pan/bulk-validate", json={"pans": ["SHORT", "ABCPK1234F"]})
        data = r.json()
        assert data["results"][0]["valid"] is False

    def test_bulk_pan_max_50(self):
        """Reject batches larger than 50."""
        pans = ["ABCPK1234F"] * 51
        r = client.post("/v1/pan/bulk-validate", json={"pans": pans})
        assert r.status_code == 422


# ─── RTO Codes Reference ────────────────────────────────────────────────────

def test_rto_codes():
    r = client.get("/v1/rto-codes")
    assert r.status_code == 200
    data = r.json()
    assert "rto_codes" in data
    assert "data_source" in data


def test_pincode_states():
    r = client.get("/v1/pincode/states")
    assert r.status_code == 200
    data = r.json()
    assert "regions" in data
    assert "data_source" in data
    assert "data_license" in data


# ─── Privacy Compliance Tests ───────────────────────────────────────────────

def test_disclaimer_includes_privacy_notice():
    """The /v1/disclaimer endpoint must include DPDP-compliant privacy info."""
    r = client.get("/v1/disclaimer")
    data = r.json()
    assert "privacy_notice" in data
    assert "does not store" in data["privacy_notice"].lower()
    assert "data_handling" in data
    assert data["data_handling"]["input_retention"] == "NONE — all inputs are processed in-memory and discarded after response"
    assert data["data_handling"]["user_profiling"] == "NONE — no per-user or per-IP usage profiles are built"


def test_no_prohibited_identifier_endpoints():
    """Endpoints for legally restricted identifiers must NOT exist."""
    prohibited_paths = [
        "/v1/restricted-1/format",
        "/v1/restricted-2/format",
        "/v1/restricted-3/format",
    ]
    for path in prohibited_paths:
        r = client.post(path, json={})
        assert r.status_code in (404, 405), f"{path} should not exist but returned {r.status_code}"
