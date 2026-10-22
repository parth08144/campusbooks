"""
services.py – CampusBooks
===========================
Central service layer: every database operation is a plain function that
RETURNS data (list / dict / ObjectId).  No printing happens here.

WHY a service layer?
  Both app.py (Streamlit) and main.py (CLI) need the same queries.
  Writing the logic once here means:
    - The Streamlit UI and CLI stay thin (display only).
    - Tests can import and call service functions directly.
    - Python cannot import modules whose names start with digits, so
      04_crud_operations.py, 05_aggregations.py, 06_explain_demo.py
      now delegate to this module and only handle printing/formatting.

All functions accept `db` as the first argument so callers control
the database connection lifetime.
"""

import datetime
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import WriteError, DuplicateKeyError

_now = lambda: datetime.datetime.now(datetime.timezone.utc)

# ─────────────────────────────────────────────────────────────────────────────
# Dashboard / stats
# ─────────────────────────────────────────────────────────────────────────────

def get_collection_stats(db) -> dict:
    """Return document counts for all four collections + total revenue."""
    completed = list(db["transactions"].aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$item.price"}}},
    ]))
    return {
        "students":     db["students"].count_documents({}),
        "listings":     db["listings"].count_documents({}),
        "available":    db["listings"].count_documents({"status": "available"}),
        "sold":         db["listings"].count_documents({"status": "sold"}),
        "transactions": db["transactions"].count_documents({}),
        "reviews":      db["reviews"].count_documents({}),
        "totalRevenue": completed[0]["total"] if completed else 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Aggregations (return list-of-dicts for easy DataFrame conversion)
# ─────────────────────────────────────────────────────────────────────────────

def get_most_traded_courses(db, limit: int = 8) -> list[dict]:
    """Aggregation 1 – completed transactions grouped by courseCode."""
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$lookup": {
            "from": "listings", "localField": "item.listingId",
            "foreignField": "_id", "as": "listingInfo",
        }},
        {"$unwind": "$listingInfo"},
        {"$group": {
            "_id":          "$listingInfo.courseCode",
            "totalSales":   {"$sum": 1},
            "totalRevenue": {"$sum": "$item.price"},
        }},
        {"$sort": {"totalSales": -1}},
        {"$limit": limit},
        {"$project": {
            "_id": 0,
            "courseCode":      "$_id",
            "totalSales":      1,
            "totalRevenue":    1,
        }},
    ]
    return list(db["transactions"].aggregate(pipeline))


def get_monthly_revenue(db) -> list[dict]:
    """Aggregation 2 – revenue grouped by year-month."""
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id": {
                "year":  {"$year":  "$createdAt"},
                "month": {"$month": "$createdAt"},
            },
            "totalRevenue": {"$sum": "$item.price"},
            "totalSales":   {"$sum": 1},
            "avgPrice":     {"$avg": "$item.price"},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {"$project": {
            "_id": 0,
            "month": {"$concat": [
                {"$toString": "$_id.year"}, "-",
                {"$cond": [
                    {"$lt": ["$_id.month", 10]},
                    {"$concat": ["0", {"$toString": "$_id.month"}]},
                    {"$toString": "$_id.month"},
                ]},
            ]},
            "totalRevenue": 1,
            "totalSales":   1,
            "avgPrice":     {"$round": ["$avgPrice", 0]},
        }},
    ]
    return list(db["transactions"].aggregate(pipeline))


def get_seller_leaderboard(db, min_reviews: int = 3, limit: int = 10) -> list[dict]:
    """Aggregation 3 – top-rated sellers with at least `min_reviews` reviews."""
    pipeline = [
        {"$group": {
            "_id":        "$sellerId",
            "avgRating":  {"$avg": "$rating"},
            "reviewCount": {"$sum": 1},
        }},
        {"$match": {"reviewCount": {"$gte": min_reviews}}},
        {"$sort": {"avgRating": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "students", "localField": "_id",
            "foreignField": "_id", "as": "sellerInfo",
        }},
        {"$unwind": {"path": "$sellerInfo", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "seller":      {"$ifNull": ["$sellerInfo.name", "Unknown"]},
            "department":  {"$ifNull": ["$sellerInfo.department", "—"]},
            "avgRating":   {"$round": ["$avgRating", 2]},
            "reviewCount": 1,
        }},
    ]
    return list(db["reviews"].aggregate(pipeline))


def get_department_discount(db) -> list[dict]:
    """Aggregation 4 – average discount % per department."""
    pipeline = [
        {"$match": {"originalPrice": {"$gt": 0}}},
        {"$group": {
            "_id": "$department",
            "avgDiscountPct": {"$avg": {
                "$multiply": [
                    {"$divide": [
                        {"$subtract": ["$originalPrice", "$price"]},
                        "$originalPrice",
                    ]},
                    100,
                ]
            }},
            "listingCount": {"$sum": 1},
            "avgPrice":     {"$avg": "$price"},
        }},
        {"$project": {
            "_id": 0,
            "department":    "$_id",
            "avgDiscountPct": {"$round": ["$avgDiscountPct", 2]},
            "listingCount":  1,
            "avgPrice":      {"$round": ["$avgPrice", 0]},
        }},
        {"$sort": {"avgDiscountPct": -1}},
    ]
    return list(db["listings"].aggregate(pipeline))


def get_transaction_details(db, limit: int = 20) -> list[dict]:
    """Aggregation 5 – completed transactions with buyer/seller/listing names."""
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$lookup": {"from": "students", "localField": "buyerId",
                     "foreignField": "_id", "as": "buyer"}},
        {"$unwind": "$buyer"},
        {"$lookup": {"from": "students", "localField": "sellerId",
                     "foreignField": "_id", "as": "seller"}},
        {"$unwind": "$seller"},
        {"$lookup": {"from": "listings", "localField": "item.listingId",
                     "foreignField": "_id", "as": "listing"}},
        {"$unwind": {"path": "$listing", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "date":        {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}},
            "buyer":       "$buyer.name",
            "seller":      "$seller.name",
            "book":        "$item.title",
            "course":      {"$ifNull": ["$listing.courseCode", "—"]},
            "price":       "$item.price",
            "paymentMode": 1,
            "status":      1,
        }},
        {"$limit": limit},
    ]
    return list(db["transactions"].aggregate(pipeline))


# ─────────────────────────────────────────────────────────────────────────────
# Browse / Search listings
# ─────────────────────────────────────────────────────────────────────────────

def browse_listings(
    db,
    department:  str  = "",
    course_code: str  = "",
    condition:   str  = "",
    status:      str  = "available",
    min_price:   int  = 0,
    max_price:   int  = 10000,
    keyword:     str  = "",
    sort_field:  str  = "price",
    sort_asc:    bool = True,
    skip:        int  = 0,
    limit:       int  = 20,
) -> tuple[list[dict], int]:
    """
    Return (rows, total_count) for the listings browse page.
    WHY tuple: Streamlit pagination needs total_count to compute page count.
    """
    query: dict = {"price": {"$gte": min_price, "$lte": max_price}}
    if status:      query["status"]     = status
    if department:  query["department"] = department
    if course_code: query["courseCode"] = {"$regex": course_code.upper(), "$options": "i"}
    if condition:   query["condition"]  = condition
    if keyword:     query["$text"]      = {"$search": keyword}

    sort_dir = 1 if sort_asc else -1
    total    = db["listings"].count_documents(query)
    rows     = list(
        db["listings"]
        .find(query, {
            "_id": 0, "title": 1, "courseCode": 1, "department": 1,
            "condition": 1, "originalPrice": 1, "price": 1,
            "status": 1, "tags": 1,
        })
        .sort(sort_field, sort_dir)
        .skip(skip)
        .limit(limit)
    )
    return rows, total


# ─────────────────────────────────────────────────────────────────────────────
# Students helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_all_students(db, limit: int = 100) -> list[dict]:
    """Return basic student info for dropdowns."""
    return list(db["students"].find(
        {},
        {"_id": 1, "name": 1, "regNo": 1, "email": 1, "department": 1, "semester": 1},
    ).limit(limit))


def get_student_by_regno(db, reg_no: str) -> dict | None:
    return db["students"].find_one({"regNo": reg_no})


# ─────────────────────────────────────────────────────────────────────────────
# Post a listing (Create)
# ─────────────────────────────────────────────────────────────────────────────

def insert_listing(db, data: dict) -> ObjectId:
    """
    Insert one listing; raises WriteError / DuplicateKeyError on schema violation.
    Caller must catch and display the error.
    """
    doc = {
        "title":         data["title"],
        "isbn":          data["isbn"],
        "authors":       [a.strip() for a in data["authors"].split(",")],
        "courseCode":    data["courseCode"].strip().upper(),
        "department":    data["department"],
        "condition":     data["condition"],
        "originalPrice": int(data["originalPrice"]),
        "price":         int(data["price"]),
        "tags":          [t.strip() for t in data.get("tags", "").split(",") if t.strip()],
        "status":        "available",
        "sellerId":      ObjectId(data["sellerId"]),
        "postedAt":      _now(),
    }
    result = db["listings"].insert_one(doc)
    return result.inserted_id


def insert_student(db, data: dict) -> ObjectId:
    """Insert one student; raises on schema / duplicate violation."""
    doc = {
        "name":       data["name"],
        "email":      data["email"],
        "regNo":      data["regNo"],
        "department": data["department"],
        "semester":   int(data["semester"]),
        "profile": {
            "phone":       data["phone"],
            "hostelBlock": data["hostelBlock"],
            "roomNo":      data["roomNo"],
        },
        "createdAt": _now(),
    }
    result = db["students"].insert_one(doc)
    return result.inserted_id


# ─────────────────────────────────────────────────────────────────────────────
# Buy a book (atomic reservation + transaction creation)
# ─────────────────────────────────────────────────────────────────────────────

def get_available_listings(db, limit: int = 200) -> list[dict]:
    """Return available listings for the Buy page dropdown (newest first)."""
    return list(db["listings"].find(
        {"status": "available"},
        {"_id": 1, "title": 1, "price": 1, "courseCode": 1, "condition": 1, "sellerId": 1},
    ).sort("postedAt", -1).limit(limit))


def atomic_reserve_and_buy(
    db,
    listing_id:   ObjectId,
    buyer_id:     ObjectId,
    payment_mode: str,
) -> tuple[bool, str, ObjectId | None]:
    """
    Atomically reserve a listing and insert a transaction.
    Returns (success, message, transaction_id).

    WHY atomic: find_one_and_update with {status:'available'} filter
    ensures only one buyer wins the race.
    """
    # Step 1: attempt atomic reservation
    reserved = db["listings"].find_one_and_update(
        {"_id": listing_id, "status": "available"},
        {"$set": {"status": "reserved", "reservedAt": _now()}},
        return_document=ReturnDocument.AFTER,
    )
    if reserved is None:
        return False, "❌ Sorry — this book was just reserved by another buyer.", None

    # Step 2: insert transaction (embedded snapshot pattern)
    txn_doc = {
        "buyerId":     buyer_id,
        "sellerId":    reserved["sellerId"],
        "item": {
            "listingId": listing_id,
            "title":     reserved["title"],
            "price":     reserved["price"],
        },
        "paymentMode": payment_mode,
        "status":      "pending",
        "createdAt":   _now(),
    }
    txn_result = db["transactions"].insert_one(txn_doc)
    return (
        True,
        f"✅ Reserved '{reserved['title']}' for ₹{reserved['price']}. Transaction created.",
        txn_result.inserted_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Seller profile
# ─────────────────────────────────────────────────────────────────────────────

def get_seller_profile(db, reg_no: str) -> dict | None:
    """
    Return a dict with student info, their listings, avg rating, and reviews.
    Returns None if regNo not found.
    """
    student = db["students"].find_one({"regNo": reg_no})
    if not student:
        return None

    sid = student["_id"]

    listings = list(db["listings"].find(
        {"sellerId": sid},
        {"_id": 0, "title": 1, "courseCode": 1, "condition": 1,
         "price": 1, "originalPrice": 1, "status": 1},
    ))

    review_agg = list(db["reviews"].aggregate([
        {"$match": {"sellerId": sid}},
        {"$group": {
            "_id":        None,
            "avgRating":  {"$avg": "$rating"},
            "reviewCount": {"$sum": 1},
        }},
    ]))

    reviews = list(db["reviews"].find(
        {"sellerId": sid},
        {"_id": 0, "rating": 1, "comment": 1, "createdAt": 1},
    ).sort("createdAt", -1).limit(10))

    avg_rating   = round(review_agg[0]["avgRating"], 2)   if review_agg else None
    review_count = review_agg[0]["reviewCount"]           if review_agg else 0

    return {
        "student":      student,
        "listings":     listings,
        "avgRating":    avg_rating,
        "reviewCount":  review_count,
        "recentReviews": reviews,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation Playground
# ─────────────────────────────────────────────────────────────────────────────

INVALID_CASES = {
    "Negative price": {
        "description": "Insert a listing with price = -50 (violates minimum: 0)",
        "collection": "listings",
        "doc": lambda: {
            "title": "Test Book", "isbn": "000-0000000000",
            "authors": ["Author"], "courseCode": "CSE101",
            "department": "CSE", "condition": "good",
            "originalPrice": 500, "price": -50,
            "status": "available", "sellerId": ObjectId(), "postedAt": _now(),
        },
    },
    "Rating = 9": {
        "description": "Insert a review with rating = 9 (max is 5)",
        "collection": "reviews",
        "doc": lambda: {
            "transactionId": ObjectId(), "reviewerId": ObjectId(),
            "sellerId": ObjectId(), "rating": 9,
            "comment": "Too high!", "createdAt": _now(),
        },
    },
    "Bad condition enum": {
        "description": "Insert a listing with condition = 'mint' (not in enum)",
        "collection": "listings",
        "doc": lambda: {
            "title": "Test Book", "isbn": "000-0000000001",
            "authors": ["Author"], "courseCode": "CSE102",
            "department": "CSE", "condition": "mint",
            "originalPrice": 500, "price": 300,
            "status": "available", "sellerId": ObjectId(), "postedAt": _now(),
        },
    },
    "Semester = 10": {
        "description": "Insert a student with semester = 10 (max is 8)",
        "collection": "students",
        "doc": lambda: {
            "name": "Bad Student", "email": f"bad_{ObjectId()}@univ.edu",
            "regNo": "12345600", "department": "CSE", "semester": 10,
            "profile": {"phone": "9876543210", "hostelBlock": "A", "roomNo": "101"},
            "createdAt": _now(),
        },
    },
    "Bad regNo (ABC123)": {
        "description": "Insert a student with regNo = 'ABC123' (must be 8 digits)",
        "collection": "students",
        "doc": lambda: {
            "name": "Bad RegNo", "email": f"badreg_{ObjectId()}@univ.edu",
            "regNo": "ABC123", "department": "ECE", "semester": 3,
            "profile": {"phone": "9812345670", "hostelBlock": "B", "roomNo": "200"},
            "createdAt": _now(),
        },
    },
    "Duplicate email": {
        "description": "Insert a student with an email that already exists",
        "collection": "students",
        "doc": lambda: {
            "name": "Duplicate", "email": "arjun.sharma@university.edu",
            "regNo": "99999001", "department": "CSE", "semester": 2,
            "profile": {"phone": "9800000001", "hostelBlock": "C", "roomNo": "111"},
            "createdAt": _now(),
        },
    },
    "Missing department": {
        "description": "Insert a student missing the required 'department' field",
        "collection": "students",
        "doc": lambda: {
            "name": "Incomplete", "email": f"incomplete_{ObjectId()}@univ.edu",
            "regNo": "88888001", "semester": 2,
            "profile": {"phone": "9800000002", "hostelBlock": "D", "roomNo": "222"},
            "createdAt": _now(),
        },
    },
}


def try_invalid_insert(db, case_name: str) -> tuple[bool, str]:
    """
    Attempt a deliberately invalid insert.
    Returns (was_rejected, message).
    True = rejected as expected; False = accepted (validator broken!).
    """
    case = INVALID_CASES[case_name]
    coll = db[case["collection"]]
    try:
        coll.insert_one(case["doc"]())
        return False, "⚠️  Document was ACCEPTED — validator may not be working!"
    except DuplicateKeyError as e:
        return True, f"✅  DuplicateKeyError (E11000): {e.details.get('errmsg', str(e))}"
    except WriteError as e:
        return True, f"✅  WriteError (schema rejected): {e.details.get('errmsg', str(e))}"
    except Exception as e:
        return True, f"ℹ️  Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Explain / index analysis
# ─────────────────────────────────────────────────────────────────────────────

EXPLAIN_PRESETS = {
    "listings: courseCode + price (compound index)": {
        "collection": "listings",
        "filter":     {"courseCode": "CSE494", "price": {"$lt": 500}},
        "hint_name":  "idx_listings_course_price",
        "hint_none":  {"$natural": 1},
        "projection": None,
        "sort":       None,
    },
    "listings: covered query (PROJECTION_COVERED)": {
        "collection": "listings",
        "filter":     {"courseCode": "CSE101"},
        "hint_name":  "idx_listings_course_price",
        "hint_none":  {"$natural": 1},
        "projection": {"_id": 0, "courseCode": 1, "price": 1},
        "sort":       None,
    },
    "transactions: buyer history (sort via index)": {
        "collection": "transactions",
        "filter":     {},      # filled at runtime with a real buyerId
        "hint_name":  "idx_txn_buyer_date",
        "hint_none":  {"$natural": 1},
        "projection": None,
        "sort":       {"createdAt": -1},
    },
    "listings: status + department (compound index)": {
        "collection": "listings",
        "filter":     {"status": "available", "department": "CSE"},
        "hint_name":  "idx_listings_status_dept",
        "hint_none":  {"$natural": 1},
        "projection": None,
        "sort":       None,
    },
}


def run_explain(db, preset_name: str, use_index: bool) -> dict:
    """
    Run explain for a preset query with or without the index.
    Returns flat dict of key stats.
    """
    preset = dict(EXPLAIN_PRESETS[preset_name])

    # For buyer history, grab a real buyerId
    if "transactions" in preset["collection"] and not preset["filter"]:
        txn = db["transactions"].find_one({"status": "completed"})
        preset["filter"] = {"buyerId": txn["buyerId"]} if txn else {}

    cmd: dict = {
        "find":   preset["collection"],
        "filter": preset["filter"],
    }
    if preset.get("projection"): cmd["projection"] = preset["projection"]
    if preset.get("sort"):       cmd["sort"]       = preset["sort"]
    if use_index:
        cmd["hint"] = preset["hint_name"]
    else:
        cmd["hint"] = preset["hint_none"]

    result = db.command("explain", cmd, verbosity="executionStats")
    es   = result.get("executionStats", {})
    plan = result.get("queryPlanner", {}).get("winningPlan", {})

    def _all_stages(p, acc=None):
        if acc is None: acc = []
        acc.append(p.get("stage", "?"))
        if "inputStage" in p: _all_stages(p["inputStage"], acc)
        return acc

    return {
        "stageChain":          " → ".join(_all_stages(plan)),
        "totalDocsExamined":   es.get("totalDocsExamined", "—"),
        "totalKeysExamined":   es.get("totalKeysExamined", "—"),
        "nReturned":           es.get("nReturned", "—"),
        "executionTimeMillis": es.get("executionTimeMillis", "—"),
        "indexUsed":           use_index,
        "query":               str(preset["filter"]),
        "hint":                str(preset["hint_name"] if use_index else preset["hint_none"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Query console
# ─────────────────────────────────────────────────────────────────────────────

def query_console(db, collection: str, filter_dict: dict, limit: int = 20) -> list[dict]:
    """
    Execute a find() with the given filter on the given collection.
    Returns list of dicts (with _id converted to str for JSON-safety).
    """
    docs = list(db[collection].find(filter_dict).limit(limit))
    for doc in docs:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        # convert any nested ObjectIds to str
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                doc[k] = str(v)
    return docs
