"""
04_crud_operations.py – CampusBooks
=====================================
Demonstrates every required CRUD operation with real PyMongo queries.

Each function has a WHY: docstring explaining the query choice.
All output is clearly labelled so screenshots look professional.

Run AFTER 03_create_indexes.py.
"""

import datetime
import pprint
from tabulate import tabulate
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from config import get_db

_now = lambda: datetime.datetime.now(datetime.timezone.utc)

# ─────────────────────────────────────────────────────────────────────────────
# C – CREATE
# ─────────────────────────────────────────────────────────────────────────────

def demo_insert_one(db) -> ObjectId:
    """
    WHY insert_one?
    Used when a single new record is created interactively, e.g. a new student
    registering on the platform.  insert_one returns an InsertOneResult whose
    .inserted_id is the new document's _id – we use it in later CRUD demos.
    """
    print("\n--- CREATE 1: insert_one (new student) ---")
    student = {
        "name":       "Priya Nair",
        "email":      "priya.nair.demo@university.edu",
        "regNo":      "20240100",
        "department": "CSE",
        "semester":   6,
        "profile": {
            "phone":       "9812345678",
            "hostelBlock": "B",
            "roomNo":      "214",
        },
        "createdAt": _now(),
    }
    result = db["students"].insert_one(student)
    sid = result.inserted_id
    print(f"   Inserted student  _id = {sid}")
    print(f"   Name : {student['name']}")
    print(f"   Email: {student['email']}")
    return sid


def demo_insert_many(db, seller_id: ObjectId) -> list:
    """
    WHY insert_many?
    A seller lists several books at once (bulk upload scenario).
    insert_many is a single network round-trip instead of N separate inserts –
    significantly faster for batch operations.
    """
    print("\n--- CREATE 2: insert_many (3 new listings by Priya) ---")
    listings = [
        {
            "title":         "Introduction to Algorithms",
            "isbn":          "978-0262033848",
            "authors":       ["Thomas H. Cormen", "Charles E. Leiserson"],
            "courseCode":    "CSE201",
            "department":    "CSE",
            "condition":     "good",
            "originalPrice": 700,
            "price":         400,
            "tags":          ["algorithms", "programming"],
            "status":        "available",
            "sellerId":      seller_id,
            "postedAt":      _now(),
        },
        {
            "title":         "Operating System Concepts",
            "isbn":          "978-1119800330",
            "authors":       ["Abraham Silberschatz"],
            "courseCode":    "CSE302",
            "department":    "CSE",
            "condition":     "fair",
            "originalPrice": 650,
            "price":         250,
            "tags":          ["os", "systems"],
            "status":        "available",
            "sellerId":      seller_id,
            "postedAt":      _now(),
        },
        {
            "title":         "Database System Concepts",
            "isbn":          "978-0073523323",
            "authors":       ["Abraham Silberschatz"],
            "courseCode":    "CSE494",
            "department":    "CSE",
            "condition":     "new",
            "originalPrice": 800,
            "price":         700,
            "tags":          ["databases", "sql"],
            "status":        "available",
            "sellerId":      seller_id,
            "postedAt":      _now(),
        },
    ]
    result = db["listings"].insert_many(listings)
    listing_ids = result.inserted_ids
    print(f"   Inserted {len(listing_ids)} listings:")
    for i, lid in enumerate(listing_ids):
        print(f"     [{i+1}] {listings[i]['title']} – ₹{listings[i]['price']} ({listings[i]['condition']})")
    return listing_ids


# ─────────────────────────────────────────────────────────────────────────────
# R – READ
# ─────────────────────────────────────────────────────────────────────────────

def demo_find_one(db) -> None:
    """
    WHY find_one?
    Used for detail pages – fetching a single student profile by email.
    More efficient than find() when exactly one result is expected.
    """
    print("\n--- READ 1: find_one (student profile by email) ---")
    # WHY projection? Only return the fields we need; avoids sending the full
    # document over the wire when only name/dept/semester are displayed.
    doc = db["students"].find_one(
        {"email": "priya.nair.demo@university.edu"},
        projection={"_id": 0, "name": 1, "department": 1,
                    "semester": 1, "profile.hostelBlock": 1},
    )
    print(f"   Result: {doc}")


def demo_find_with_operators(db) -> None:
    """
    WHY $gte/$lte/$in/$regex?
    Real marketplace filters: price range + multiple departments + keyword search.
    These are the most common query operators in any e-commerce system.
    """
    print("\n--- READ 2: find with $gte/$lte/$in/$regex + projection + sort ---")

    # Price range + department filter + regex on title
    cursor = db["listings"].find(
        {
            "price":      {"$gte": 200, "$lte": 500},  # WHY $gte/$lte: price range filter
            "department": {"$in": ["CSE", "ECE"]},      # WHY $in: multi-value filter
            "status":     "available",
            "title":      {"$regex": "Algorithm|System|Data", "$options": "i"},  # WHY $regex: keyword search
        },
        projection={"_id": 0, "title": 1, "courseCode": 1,
                    "price": 1, "condition": 1, "department": 1},
    ).sort("price", 1).limit(8)   # WHY sort+limit: cheapest first, cap result set

    rows = list(cursor)
    if rows:
        print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no matching listings)")


def demo_text_search(db) -> None:
    """
    WHY $text search?
    Users type keywords like "algorithms textbook". $text uses the weighted text
    index (title×3, tags×1) and returns results ranked by textScore relevance –
    far superior to multiple $regex queries because it handles stemming and
    stop-words automatically.
    """
    print("\n--- READ 3: $text search (keyword: 'algorithms database') ---")
    cursor = db["listings"].find(
        {"$text": {"$search": "algorithms database"}},
        projection={"_id": 0, "title": 1, "price": 1, "condition": 1,
                    "score": {"$meta": "textScore"}},
    ).sort([("score", {"$meta": "textScore"})]).limit(5)

    rows = list(cursor)
    if rows:
        print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no text matches found)")


def demo_pagination(db) -> None:
    """
    WHY skip/limit?
    Pagination is essential in any list view. skip(n) + limit(page_size) is the
    simplest approach. (For high-traffic apps, cursor-based pagination using _id
    ranges is faster because skip() scans and discards documents.)
    """
    print("\n--- READ 4: Pagination – page 1 and page 2 of CSE listings (3 per page) ---")
    query  = {"department": "CSE", "status": "available"}
    proj   = {"_id": 0, "title": 1, "price": 1, "condition": 1, "courseCode": 1}
    page_size = 3

    for page in (1, 2):
        skip = (page - 1) * page_size
        rows = list(
            db["listings"].find(query, proj)
            .sort("price", 1)
            .skip(skip)
            .limit(page_size)
        )
        total = db["listings"].count_documents(query)   # WHY count_documents: show total
        print(f"\n   Page {page} (skip={skip}, limit={page_size}), total available: {total}")
        if rows:
            print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))


def demo_count(db) -> None:
    """
    WHY count_documents?
    Displays summary statistics on the dashboard (e.g. "142 books available").
    Uses the index on {status, department} so it's very fast.
    """
    print("\n--- READ 5: count_documents per department ---")
    rows = []
    for dept in ["CSE", "ECE", "ME", "Civil", "MBA"]:
        count = db["listings"].count_documents({"status": "available", "department": dept})
        rows.append({"Department": dept, "Available Listings": count})
    print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))


# ─────────────────────────────────────────────────────────────────────────────
# U – UPDATE
# ─────────────────────────────────────────────────────────────────────────────

def demo_update_one(db, student_id: ObjectId) -> None:
    """
    WHY update_one + $set?
    $set modifies only the specified fields; other fields are untouched.
    Using $set is safer than replacing the whole document, which would
    silently delete any fields not included in the replacement.
    """
    print("\n--- UPDATE 1: update_one with $set (move Priya to hostel block C) ---")
    before = db["students"].find_one(
        {"_id": student_id},
        projection={"_id": 0, "name": 1, "profile.hostelBlock": 1, "profile.roomNo": 1},
    )
    print(f"   Before: {before}")

    result = db["students"].update_one(
        {"_id": student_id},
        {"$set": {"profile.hostelBlock": "C", "profile.roomNo": "305"}},
    )
    print(f"   Matched: {result.matched_count}, Modified: {result.modified_count}")

    after = db["students"].find_one(
        {"_id": student_id},
        projection={"_id": 0, "name": 1, "profile.hostelBlock": 1, "profile.roomNo": 1},
    )
    print(f"   After : {after}")


def demo_update_many_mul(db) -> None:
    """
    WHY update_many + $mul?
    Apply a 10% discount to all 'poor' condition listings that are still
    available and were posted more than 60 days ago – bulk price reduction.

    WHY $mul instead of $set?
    $mul multiplies the existing value in-place without needing to know the
    current price; the server does the arithmetic, not the application.
    """
    print("\n--- UPDATE 2: update_many with $mul (10% discount on old 'poor' listings) ---")
    sixty_days_ago = _now() - datetime.timedelta(days=60)

    # Show before state (sample 3)
    sample_before = list(
        db["listings"].find(
            {"condition": "poor", "status": "available",
             "postedAt": {"$lte": sixty_days_ago}},
            {"_id": 0, "title": 1, "price": 1},
        ).limit(3)
    )
    print(f"   Sample prices before discount: {sample_before}")

    result = db["listings"].update_many(
        {
            "condition": "poor",
            "status":    "available",
            "postedAt":  {"$lte": sixty_days_ago},
        },
        # WHY pipeline update (array form)?  $mul on an int field produces a
        # double, which violates our bsonType:"int" schema.  Using an aggregation
        # pipeline update (MongoDB 4.2+) lets us chain $multiply then $toInt
        # (equivalent to floor) so the result stays a BSON int32.
        [{"$set": {"price": {
            "$toInt": {"$multiply": ["$price", 0.9]}
        }}}],
    )
    print(f"   Matched: {result.matched_count}, Modified: {result.modified_count}")

    # Show after state (same 3)
    sample_after = list(
        db["listings"].find(
            {"condition": "poor", "status": "available",
             "postedAt": {"$lte": sixty_days_ago}},
            {"_id": 0, "title": 1, "price": 1},
        ).limit(3)
    )
    print(f"   Sample prices after  discount: {sample_after}")
    print("   NOTE: We use $toInt($multiply) so price stays BSON int32 (schema-compliant).")


def demo_push_pull(db, listing_id: ObjectId) -> None:
    """
    WHY $push/$pull on tags array?
    $push appends an element to an array without fetching and re-sending the
    whole array from the client.  $pull removes matching elements by value.
    Both are atomic – safe even with concurrent writers.
    """
    print("\n--- UPDATE 3: $push and $pull on tags array ---")
    before = db["listings"].find_one(
        {"_id": listing_id}, {"_id": 0, "title": 1, "tags": 1}
    )
    print(f"   Before: {before}")

    # Add a new tag
    db["listings"].update_one(
        {"_id": listing_id},
        {"$push": {"tags": "exam-prep"}},
    )
    mid = db["listings"].find_one({"_id": listing_id}, {"_id": 0, "title": 1, "tags": 1})
    print(f"   After $push 'exam-prep': {mid}")

    # Remove it again
    db["listings"].update_one(
        {"_id": listing_id},
        {"$pull": {"tags": "exam-prep"}},
    )
    after = db["listings"].find_one({"_id": listing_id}, {"_id": 0, "title": 1, "tags": 1})
    print(f"   After $pull 'exam-prep': {after}")


def demo_inc(db, listing_id: ObjectId) -> None:
    """
    WHY $inc?
    Atomically increments a numeric field by a delta without a read-modify-write
    cycle.  Here we track how many times a listing has been viewed.
    WHY atomic? If two requests arrive simultaneously, $inc ensures neither
    view is lost; a Python read→increment→write pattern would lose one.
    """
    print("\n--- UPDATE 4: $inc (increment viewCount on a listing) ---")
    # $inc on an existing doc: adds 'viewCount' field if absent, increments if present.
    # WHY not upsert here: the listing already exists; $inc initialises missing fields to 0 then adds.
    db["listings"].update_one(
        {"_id": listing_id},
        {"$inc": {"viewCount": 1}},
    )
    doc = db["listings"].find_one({"_id": listing_id}, {"_id": 0, "title": 1, "viewCount": 1})
    print(f"   {doc}")


def demo_upsert(db) -> None:
    """
    WHY upsert=True?
    Inserts a document if no match is found, otherwise updates it.
    Useful for 'create-or-update' patterns like refreshing daily stats without
    checking for existence first – one round-trip instead of two.

    WHY use 'analytics' collection (not 'listings')?
    The listings collection has a strict $jsonSchema that requires title, isbn,
    authors, etc.  A stats/counter document doesn't fit that schema.  A separate
    unvalidated 'analytics' collection is the right place for such free-form docs.
    """
    print("\n--- UPDATE 5: upsert=True (create-or-update daily view stats in 'analytics') ---")
    today = datetime.date.today().isoformat()
    # 'analytics' collection has no schema validator – free-form stats are fine here
    for _ in range(3):   # simulate three page-view events
        db["analytics"].update_one(
            {"statsDate": today, "statType": "daily_view_counter"},
            {"$inc": {"totalViews": 1}},
            upsert=True,    # WHY upsert: creates the doc on first hit, increments on subsequent
        )
    doc = db["analytics"].find_one(
        {"statsDate": today, "statType": "daily_view_counter"},
        {"_id": 0},
    )
    print(f"   Daily stats doc: {doc}")
    # Clean up
    db["analytics"].delete_one({"statsDate": today, "statType": "daily_view_counter"})


def demo_find_one_and_update_atomic_reserve(db, listing_id: ObjectId) -> None:
    """
    WHY find_one_and_update for reservation?
    This is the critical atomic operation:
      1. Two buyers (A and B) both see listing status='available'.
      2. Without atomicity, both could 'reserve' the same book.
      3. find_one_and_update with a filter on {_id, status:'available'}
         guarantees that ONLY ONE buyer succeeds – the other gets None back
         because the status is no longer 'available' after the first update.
    This is the 'Compare-And-Swap' pattern (Unit V: concurrency).
    """
    print("\n--- UPDATE 6: find_one_and_update – atomic reserve (status: available → reserved) ---")
    result = db["listings"].find_one_and_update(
        {"_id": listing_id, "status": "available"},  # match ONLY if available
        {"$set": {"status": "reserved", "reservedAt": _now()}},
        return_document=ReturnDocument.AFTER,         # return the UPDATED doc
        projection={"_id": 0, "title": 1, "status": 1, "reservedAt": 1},
    )
    if result:
        print(f"   ✅  Reserved successfully: {result}")
    else:
        print("   ❌  Reservation failed – listing was already taken (concurrent reserve simulation)")

    # Simulate second buyer trying to reserve the same listing
    print("   Simulating second buyer attempting to reserve the same listing …")
    result2 = db["listings"].find_one_and_update(
        {"_id": listing_id, "status": "available"},  # now fails because status='reserved'
        {"$set": {"status": "reserved", "reservedAt": _now()}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0, "title": 1, "status": 1},
    )
    if result2 is None:
        print("   ✅  Second buyer correctly got None – book already reserved (atomic safety works!)")


# ─────────────────────────────────────────────────────────────────────────────
# D – DELETE
# ─────────────────────────────────────────────────────────────────────────────

def demo_delete_one(db, listing_id: ObjectId) -> None:
    """
    WHY delete_one?
    A seller withdraws a single listing.  delete_one is safer than delete_many
    when only one document should be removed.
    """
    print("\n--- DELETE 1: delete_one (seller removes a specific listing) ---")
    result = db["listings"].delete_one({"_id": listing_id})
    print(f"   Deleted count: {result.deleted_count}")


def demo_delete_many(db) -> None:
    """
    WHY delete_many?
    Housekeeping: remove cancelled transactions older than 90 days to keep the
    collection lean.  In production this would run as a scheduled cron job.
    WHY 90 days? Gives enough time to resolve disputes before purging records.
    """
    print("\n--- DELETE 2: delete_many (purge cancelled transactions older than 90 days) ---")
    ninety_days_ago = _now() - datetime.timedelta(days=90)

    # Count before
    before_count = db["transactions"].count_documents(
        {"status": "cancelled", "createdAt": {"$lte": ninety_days_ago}}
    )
    print(f"   Cancelled transactions older than 90 days: {before_count}")

    result = db["transactions"].delete_many(
        {"status": "cancelled", "createdAt": {"$lte": ninety_days_ago}}
    )
    print(f"   Deleted: {result.deleted_count} transactions")

    after_count = db["transactions"].count_documents({"status": "cancelled"})
    print(f"   Remaining cancelled transactions (< 90 days old): {after_count}")


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def _cleanup_demo_data(db) -> None:
    """Remove any leftover demo documents from a previous run so this script
    is safely re-runnable without 'duplicate key' errors."""
    student = db["students"].find_one({"email": "priya.nair.demo@university.edu"})
    if student:
        db["listings"].delete_many({"sellerId": student["_id"]})
        db["students"].delete_one({"_id": student["_id"]})
    # Also remove any stats doc left by the upsert demo
    db["listings"].delete_many({"_statType": "daily_view_counter"})


def run():
    client, db = get_db()
    try:
        print("\n" + "="*60)
        print("  04: CRUD OPERATIONS DEMO – CampusBooks")
        print("="*60)

        # Clean up any leftover demo data from prior runs
        _cleanup_demo_data(db)

        # ── CREATE ────────────────────────────────────────────────
        student_id  = demo_insert_one(db)
        listing_ids = demo_insert_many(db, student_id)

        # ── READ ──────────────────────────────────────────────────
        demo_find_one(db)
        demo_find_with_operators(db)
        demo_text_search(db)
        demo_pagination(db)
        demo_count(db)

        # ── UPDATE ────────────────────────────────────────────────
        demo_update_one(db, student_id)
        demo_update_many_mul(db)
        demo_push_pull(db, listing_ids[0])    # push/pull on first inserted listing
        demo_inc(db, listing_ids[1])
        demo_upsert(db)
        demo_find_one_and_update_atomic_reserve(db, listing_ids[2])

        # ── DELETE ────────────────────────────────────────────────
        demo_delete_one(db, listing_ids[0])   # delete first listing
        demo_delete_many(db)

        print("\n" + "="*60)
        print("  CRUD DEMO COMPLETE")
        print("="*60 + "\n")

    finally:
        client.close()


if __name__ == "__main__":
    run()
