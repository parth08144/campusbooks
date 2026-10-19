"""
01_setup_validation.py – CampusBooks
=====================================
Creates the four collections with $jsonSchema validators and then
deliberately inserts INVALID documents to demonstrate error-handling.

WHY $jsonSchema at the DB level?
  Validation in the application layer (Python) can be bypassed by anyone
  who connects directly via mongosh or Compass. Putting the schema in the
  DB guarantees data integrity regardless of how data enters the system.
  This is a core concept in Unit III of CSE494.

WHY validationLevel "strict" + validationAction "error"?
  - "strict"  → validates ALL writes (insert AND update), not just inserts.
  - "error"   → rejects the document instead of just logging a warning.
  Together they give the strongest possible enforcement.

Run order: always run this BEFORE 02_seed_data.py.
"""

import datetime
import pymongo
from pymongo import MongoClient
from pymongo.errors import WriteError, DuplicateKeyError, CollectionInvalid
from config import get_db

# Timezone-aware UTC helper – replaces the deprecated datetime.utcnow()
def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)

# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────

def _drop_if_exists(db, name: str) -> None:
    """Drop a collection if it already exists so we can re-run this script
    without 'collection already exists' errors during development."""
    if name in db.list_collection_names():
        db.drop_collection(name)
        print(f"   Dropped existing collection '{name}'")


# ──────────────────────────────────────────────────────────────────────────────
# $jsonSchema definitions
# ──────────────────────────────────────────────────────────────────────────────

# WHY: schema is defined as a plain dict so it can be reused in
#      create_collection and in collMod without duplication.

STUDENTS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "title": "Student",
        # WHY 'required': MongoDB only enforces presence of listed fields;
        # other fields are silently allowed (open schema by default).
        "required": ["name", "email", "regNo", "department",
                     "semester", "profile", "createdAt"],
        "additionalProperties": True,   # allow _id and any future fields
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "Full name of the student – must be a string"
            },
            "email": {
                "bsonType": "string",
                # WHY pattern: basic format guard; uniqueness is enforced by an index
                "pattern": "^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$",
                "description": "University email – must match email pattern"
            },
            "regNo": {
                "bsonType": "string",
                # WHY exactly 8 digits: matches the university registration format
                "pattern": "^[0-9]{8}$",
                "description": "8-digit registration number"
            },
            "department": {
                "bsonType": "string",
                "enum": ["CSE", "ECE", "ME", "Civil", "MBA"],
                "description": "Must be one of the five recognised departments"
            },
            "semester": {
                "bsonType": "int",
                # WHY minimum/maximum: semesters only go from 1 to 8 in a 4-year programme
                "minimum": 1,
                "maximum": 8,
                "description": "Current semester (1–8)"
            },
            "profile": {
                # WHY EMBEDDED (1-to-1): profile data is always fetched with the
                # student; embedding avoids an extra round-trip.
                "bsonType": "object",
                "required": ["phone", "hostelBlock", "roomNo"],
                "properties": {
                    "phone": {
                        "bsonType": "string",
                        "pattern": "^[6-9][0-9]{9}$",
                        "description": "10-digit Indian mobile number"
                    },
                    "hostelBlock": {
                        "bsonType": "string",
                        "description": "Hostel block label, e.g. 'A', 'B', 'C'"
                    },
                    "roomNo": {
                        "bsonType": "string",
                        "description": "Room number, e.g. '204'"
                    }
                }
            },
            "createdAt": {
                "bsonType": "date",
                "description": "Account creation timestamp – stored as BSON Date"
            }
        }
    }
}

LISTINGS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "title": "Listing",
        "required": ["title", "isbn", "authors", "courseCode", "department",
                     "condition", "originalPrice", "price", "status",
                     "sellerId", "postedAt"],
        "properties": {
            "title": {"bsonType": "string"},
            "isbn":  {"bsonType": "string"},
            "authors": {
                # WHY array of strings: a book can have multiple authors;
                # embedding them avoids a separate authors collection for a
                # read-mostly field that never needs its own queries.
                "bsonType": "array",
                "items": {"bsonType": "string"},
                "minItems": 1
            },
            "courseCode": {
                "bsonType": "string",
                "pattern": "^[A-Z]{2,5}[0-9]{3}$",
                "description": "e.g. CSE494, ECE301"
            },
            "department": {
                "bsonType": "string",
                "enum": ["CSE", "ECE", "ME", "Civil", "MBA"]
            },
            "condition": {
                "bsonType": "string",
                # WHY enum: prevents typos like 'Good' vs 'good'; consistent
                # values make filtering and aggregation reliable.
                "enum": ["new", "good", "fair", "poor"],
                "description": "Physical condition of the book"
            },
            "originalPrice": {
                "bsonType": "int",
                # WHY int, not Decimal128: keeps aggregation arithmetic
                # simple (no BSON decimal128 handling needed). Note: for
                # financial production systems use Decimal128 to avoid
                # floating-point rounding.
                "minimum": 0,
                "description": "MRP in INR – must be a non-negative integer"
            },
            "price": {
                "bsonType": "int",
                "minimum": 0,
                "description": "Asking price in INR"
            },
            "tags": {
                "bsonType": "array",
                "items": {"bsonType": "string"}
            },
            "status": {
                "bsonType": "string",
                "enum": ["available", "reserved", "sold"]
            },
            "sellerId": {
                # WHY ObjectId reference (not embedded): a student record is
                # shared across many listings; duplicating it would waste space
                # and create update anomalies.
                "bsonType": "objectId",
                "description": "Reference to students._id"
            },
            "postedAt": {"bsonType": "date"}
        }
    }
}

TRANSACTIONS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "title": "Transaction",
        "required": ["buyerId", "sellerId", "item",
                     "paymentMode", "status", "createdAt"],
        "properties": {
            "buyerId":  {"bsonType": "objectId"},
            "sellerId": {"bsonType": "objectId"},
            "item": {
                # WHY EMBEDDED SNAPSHOT: if the listing is later edited or
                # deleted, transaction history still shows the price and title
                # at the time of purchase.  This is the 'snapshot pattern'.
                "bsonType": "object",
                "required": ["listingId", "title", "price"],
                "properties": {
                    "listingId": {"bsonType": "objectId"},
                    "title":     {"bsonType": "string"},
                    "price":     {"bsonType": "int", "minimum": 0}
                }
            },
            "paymentMode": {
                "bsonType": "string",
                "enum": ["cash", "upi"]
            },
            "status": {
                "bsonType": "string",
                "enum": ["pending", "completed", "cancelled"]
            },
            "createdAt": {"bsonType": "date"}
        }
    }
}

REVIEWS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "title": "Review",
        "required": ["transactionId", "reviewerId", "sellerId",
                     "rating", "comment", "createdAt"],
        "properties": {
            "transactionId": {"bsonType": "objectId"},
            "reviewerId":    {"bsonType": "objectId"},
            "sellerId":      {"bsonType": "objectId"},
            "rating": {
                "bsonType": "int",
                # WHY minimum 1, maximum 5: standard 5-star scale
                "minimum": 1,
                "maximum": 5
            },
            "comment":   {"bsonType": "string"},
            "createdAt": {"bsonType": "date"}
        }
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# Setup function
# ──────────────────────────────────────────────────────────────────────────────

def setup_collections(db) -> None:
    """
    Drop and re-create all four collections with $jsonSchema validators.

    WHY create_collection with 'validator'? This is the MongoDB way to attach
    a schema at collection-creation time.  Using 'collMod' afterwards would
    work too, but creating with the validator is cleaner for a fresh setup.
    """
    print("\n=== STEP 1: Creating Collections with $jsonSchema Validators ===\n")

    specs = [
        ("students",     STUDENTS_SCHEMA),
        ("listings",     LISTINGS_SCHEMA),
        ("transactions", TRANSACTIONS_SCHEMA),
        ("reviews",      REVIEWS_SCHEMA),
    ]

    for coll_name, schema in specs:
        _drop_if_exists(db, coll_name)
        db.create_collection(
            coll_name,
            validator=schema,
            validationLevel="strict",   # enforce on ALL writes
            validationAction="error",   # reject, don't warn
        )
        print(f"   ✅  Collection '{coll_name}' created with strict $jsonSchema validator")

    print("\n   All collections ready.\n")


# ──────────────────────────────────────────────────────────────────────────────
# Unique index on email (needed before the duplicate-email demo)
# ──────────────────────────────────────────────────────────────────────────────

def create_email_index(db) -> None:
    """Create just the unique email index so the duplicate-email demo works.
    The full index set is built in 03_create_indexes.py."""
    db["students"].create_index("email", unique=True, name="unique_email")
    db["students"].create_index("regNo", unique=True, name="unique_regNo")
    print("   ✅  Unique indexes on students.email and students.regNo created\n")


# ──────────────────────────────────────────────────────────────────────────────
# Invalid-insert demonstration (screenshot material)
# ──────────────────────────────────────────────────────────────────────────────

def demo_invalid_inserts(db) -> None:
    """
    WHY run invalid inserts?
    The examiner needs to see that the validator ACTUALLY rejects bad data.
    Each case tests a different validation rule, making the demo comprehensive.
    """
    print("=== STEP 2: Invalid-Insert Demo (expect errors below) ===\n")

    students  = db["students"]
    listings  = db["listings"]
    reviews   = db["reviews"]

    # ── Case 1: Negative price ─────────────────────────────────────────────────
    print("── Case 1: Listing with negative price (should be rejected) ──")
    try:
        listings.insert_one({
            "title":         "Data Structures",
            "isbn":          "978-0132576277",
            "authors":       ["Mark Allen Weiss"],
            "courseCode":    "CSE201",
            "department":    "CSE",
            "condition":     "good",
            "originalPrice": 450,
            "price":         -50,        # ❌ violates minimum: 0
            "tags":          ["algorithms"],
            "status":        "available",
            "sellerId":      __import__("bson").ObjectId(),
            "postedAt":      _now(),
        })
        print("   ❌  ERROR: document was accepted – validator is not working!")
    except WriteError as e:
        print(f"   ✅  WriteError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    # ── Case 2: Rating out of range ────────────────────────────────────────────
    print("── Case 2: Review with rating = 9 (max is 5) ──")
    try:
        reviews.insert_one({
            "transactionId": __import__("bson").ObjectId(),
            "reviewerId":    __import__("bson").ObjectId(),
            "sellerId":      __import__("bson").ObjectId(),
            "rating":        9,          # ❌ violates maximum: 5
            "comment":       "Great seller!",
            "createdAt":     _now(),
        })
        print("   ❌  ERROR: document was accepted – validator is not working!")
    except WriteError as e:
        print(f"   ✅  WriteError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    # ── Case 3: Invalid enum value ─────────────────────────────────────────────
    print("── Case 3: Listing with condition = 'mint' (not in enum) ──")
    try:
        listings.insert_one({
            "title":         "Operating Systems",
            "isbn":          "978-0133805727",
            "authors":       ["Abraham Silberschatz"],
            "courseCode":    "CSE303",
            "department":    "CSE",
            "condition":     "mint",     # ❌ not in ["new","good","fair","poor"]
            "originalPrice": 600,
            "price":         300,
            "status":        "available",
            "sellerId":      __import__("bson").ObjectId(),
            "postedAt":      _now(),
        })
        print("   ❌  ERROR: document was accepted – validator is not working!")
    except WriteError as e:
        print(f"   ✅  WriteError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    # ── Case 4: Semester out of range ──────────────────────────────────────────
    print("── Case 4: Student with semester = 10 (max is 8) ──")
    try:
        students.insert_one({
            "name":       "Test Student",
            "email":      "test.semester@university.edu",
            "regNo":      "12345678",
            "department": "CSE",
            "semester":   10,            # ❌ violates maximum: 8
            "profile": {
                "phone":       "9876543210",
                "hostelBlock": "A",
                "roomNo":      "101",
            },
            "createdAt": _now(),
        })
        print("   ❌  ERROR: document was accepted – validator is not working!")
    except WriteError as e:
        print(f"   ✅  WriteError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    # ── Case 5: Bad regNo format ───────────────────────────────────────────────
    print("── Case 5: Student with regNo = 'ABC123' (must be 8 digits) ──")
    try:
        students.insert_one({
            "name":       "Bad RegNo",
            "email":      "bad.regno@university.edu",
            "regNo":      "ABC123",      # ❌ violates pattern ^[0-9]{8}$
            "department": "ECE",
            "semester":   3,
            "profile": {
                "phone":       "9876543211",
                "hostelBlock": "B",
                "roomNo":      "202",
            },
            "createdAt": _now(),
        })
        print("   ❌  ERROR: document was accepted – validator is not working!")
    except WriteError as e:
        print(f"   ✅  WriteError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    # ── Case 6: Duplicate email ────────────────────────────────────────────────
    print("── Case 6: Duplicate email (unique index should reject) ──")
    # First insert (valid – should succeed)
    VALID_STUDENT = {
        "name":       "Arjun Sharma",
        "email":      "arjun.sharma@university.edu",
        "regNo":      "20240001",
        "department": "CSE",
        "semester":   5,
        "profile": {
            "phone":       "9876543210",
            "hostelBlock": "A",
            "roomNo":      "101",
        },
        "createdAt": _now(),
    }
    students.insert_one(VALID_STUDENT)
    print("   Inserted first student (arjun.sharma@university.edu) – OK")

    # Second insert with same email (should fail)
    try:
        VALID_STUDENT.pop("_id")         # remove _id so insert_one generates a new one
        VALID_STUDENT["regNo"] = "20240002"  # different regNo but same email
        students.insert_one(VALID_STUDENT)
        print("   ❌  ERROR: duplicate email was accepted!")
    except DuplicateKeyError as e:
        print(f"   ✅  DuplicateKeyError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    # ── Case 7: Missing required field ────────────────────────────────────────
    print("── Case 7: Student document missing 'department' field ──")
    try:
        students.insert_one({
            "name":       "Incomplete Student",
            "email":      "incomplete@university.edu",
            "regNo":      "20240099",
            # "department" is missing ❌
            "semester":   2,
            "profile": {
                "phone":       "9876500000",
                "hostelBlock": "C",
                "roomNo":      "301",
            },
            "createdAt": _now(),
        })
        print("   ❌  ERROR: document was accepted – validator is not working!")
    except WriteError as e:
        print(f"   ✅  WriteError caught (as expected): {e.details.get('errmsg', str(e))}\n")

    print("=== Invalid-Insert Demo Complete ===\n")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def run():
    client, db = get_db()
    try:
        setup_collections(db)
        create_email_index(db)
        demo_invalid_inserts(db)
    finally:
        client.close()


if __name__ == "__main__":
    run()
