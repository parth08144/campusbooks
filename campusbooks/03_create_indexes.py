"""
03_create_indexes.py – CampusBooks
=====================================
Creates all indexes required for efficient querying.

WHY indexes matter?
  Without indexes, MongoDB performs a COLLSCAN (full collection scan)
  for every query – reading EVERY document even if only a few match.
  Indexes create a B-tree structure that MongoDB traverses in O(log n)
  instead of O(n), giving dramatic speedups on large collections.

Index types used here:
  1. Unique   – enforces no duplicates (data integrity + fast lookups)
  2. Compound – multi-field index, supports sorting and range queries
  3. Text     – full-text search on string fields (the 'mongosearch' engine)
  4. Single   – plain index on one field

Run AFTER 02_seed_data.py so the collection already has data, which
makes explain() results in 06_explain_demo.py more realistic.
"""

from pymongo import ASCENDING, DESCENDING, TEXT
from config import get_db


def create_indexes(db) -> None:
    print("\n=== 03: Creating Indexes ===\n")

    # ── students ──────────────────────────────────────────────────────────────

    # WHY unique on email: every student must have a distinct email; the index
    # both enforces uniqueness AND makes login lookups by email O(log n).
    db["students"].create_index(
        "email",
        unique=True,
        name="unique_email",
    )
    print("   ✅  students.email          – unique index")

    # WHY unique on regNo: the university registration number is a natural
    # unique identifier; having an index enables fast student lookups by regNo.
    db["students"].create_index(
        "regNo",
        unique=True,
        name="unique_regNo",
    )
    print("   ✅  students.regNo          – unique index")

    # ── listings ─────────────────────────────────────────────────────────────

    # WHY compound {courseCode, price}?
    # The most common query pattern is "find books for CSE494 sorted by
    # price", which is exactly what this compound index supports.
    # Field order matters: equality first (courseCode), then range/sort (price).
    db["listings"].create_index(
        [("courseCode", ASCENDING), ("price", ASCENDING)],
        name="idx_listings_course_price",
    )
    print("   ✅  listings.courseCode+price – compound index")

    # WHY text on title + tags?
    # Allows students to search "algorithms textbook" and match both
    # the title and any matching tag.  MongoDB's text index handles
    # stemming, stop-words, and case-folding automatically.
    # WHY weights? title is 3× more important than a tag match.
    db["listings"].create_index(
        [("title", TEXT), ("tags", TEXT)],
        weights={"title": 3, "tags": 1},
        name="text_listings_title_tags",
    )
    print("   ✅  listings.title+tags      – text index (weighted)")

    # WHY compound {status, department}?
    # Filter available books by department: a very common marketplace query.
    db["listings"].create_index(
        [("status", ASCENDING), ("department", ASCENDING)],
        name="idx_listings_status_dept",
    )
    print("   ✅  listings.status+department – compound index")

    # WHY index on sellerId?
    # Used in $lookup during aggregation to join listings → students.
    db["listings"].create_index(
        "sellerId",
        name="idx_listings_sellerId",
    )
    print("   ✅  listings.sellerId        – single index")

    # ── transactions ──────────────────────────────────────────────────────────

    # WHY compound {buyerId, createdAt DESC}?
    # "Show my purchase history, newest first" is the primary buyer query.
    # Compound index with DESC sort matches the query order, avoiding an
    # in-memory sort step.
    db["transactions"].create_index(
        [("buyerId", ASCENDING), ("createdAt", DESCENDING)],
        name="idx_txn_buyer_date",
    )
    print("   ✅  transactions.buyerId+createdAt – compound index (desc date)")

    # WHY index on sellerId?
    # "Show my sales" is the symmetric query for sellers.
    db["transactions"].create_index(
        "sellerId",
        name="idx_txn_sellerId",
    )
    print("   ✅  transactions.sellerId    – single index")

    # WHY index on status?
    # All aggregations start with $match {status: 'completed'}.
    # Without this, MongoDB scans all 200+ transaction documents.
    db["transactions"].create_index(
        "status",
        name="idx_txn_status",
    )
    print("   ✅  transactions.status      – single index")

    # ── reviews ───────────────────────────────────────────────────────────────

    # WHY index on sellerId?
    # Seller leaderboard aggregation groups by sellerId after
    # $lookup from reviews; this index accelerates the lookup.
    db["reviews"].create_index(
        "sellerId",
        name="idx_reviews_sellerId",
    )
    print("   ✅  reviews.sellerId         – single index")

    # WHY index on transactionId (unique)?
    # One transaction → at most one review.  The unique constraint prevents
    # a buyer from reviewing the same transaction twice.
    db["reviews"].create_index(
        "transactionId",
        unique=True,
        name="unique_review_per_txn",
    )
    print("   ✅  reviews.transactionId    – unique index (1 review per txn)\n")

    # ── Print summary ─────────────────────────────────────────────────────────
    print("=== Index Summary ===")
    for coll_name in ["students", "listings", "transactions", "reviews"]:
        indexes = list(db[coll_name].index_information().keys())
        print(f"   {coll_name:<15} → {', '.join(indexes)}")
    print()


def run():
    client, db = get_db()
    try:
        create_indexes(db)
    finally:
        client.close()


if __name__ == "__main__":
    run()
