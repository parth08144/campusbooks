"""
06_explain_demo.py – CampusBooks
====================================
Demonstrates the performance impact of indexes using MongoDB's explain command.

NOTE on architecture:
  Explain logic lives in services.py (run_explain, EXPLAIN_PRESETS).
  This file handles printing and is safe to run standalone.
  app.py (Streamlit Explain Viewer page) imports from services.py directly.

WHY explain()?
  explain() returns the query plan MongoDB ACTUALLY used.  By comparing a
  COLLSCAN (full collection scan, no index) vs an IXSCAN (index scan) we can
  show exactly how many documents were examined and how long it took.
  This is the standard way to prove that indexes are working.

Key metrics from executionStats:
  • stage               : COLLSCAN (bad) vs IXSCAN / FETCH (good)
  • totalDocsExamined   : fewer is better (IXSCAN reads far fewer docs)
  • totalKeysExamined   : index entries scanned
  • nReturned           : how many docs matched the query
  • executionTimeMillis : wall-clock time of the query

PyMongo 4.x note:
  cursor.explain() takes no verbosity argument.  To get executionStats we use
  db.command("explain", <find cmd>, verbosity="executionStats") which works
  across all supported MongoDB versions.

Run AFTER 03_create_indexes.py (indexes must exist for the comparison).
"""

from tabulate import tabulate
from pymongo import ASCENDING
from config import get_db


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build an explain command and return key metrics
# ─────────────────────────────────────────────────────────────────────────────

def _explain(db, collection: str, find_filter: dict,
             hint=None, projection: dict = None, sort: list = None) -> dict:
    """
    Run db.command('explain', ...) and return a flat dict of key stats.

    WHY db.command instead of cursor.explain()?
    PyMongo 4.x removed the verbosity argument from Cursor.explain().
    Using the raw 'explain' command gives full executionStats on any version.
    """
    find_cmd: dict = {"find": collection, "filter": find_filter}
    if hint       is not None: find_cmd["hint"]       = hint
    if projection is not None: find_cmd["projection"] = projection
    if sort       is not None: find_cmd["sort"]       = {k: v for k, v in sort}

    result = db.command("explain", find_cmd, verbosity="executionStats")

    es   = result.get("executionStats", {})
    plan = result.get("queryPlanner", {}).get("winningPlan", {})

    # Walk down to the innermost stage name
    def _innermost_stage(p: dict) -> str:
        if "inputStage" in p:
            return _innermost_stage(p["inputStage"])
        return p.get("stage", "UNKNOWN")

    # Collect all stage names top-to-bottom
    def _all_stages(p: dict, acc: list = None) -> list:
        if acc is None:
            acc = []
        acc.append(p.get("stage", "?"))
        if "inputStage" in p:
            _all_stages(p["inputStage"], acc)
        return acc

    return {
        "stage":               _innermost_stage(plan),
        "stageChain":          " → ".join(_all_stages(plan)),
        "totalDocsExamined":   es.get("totalDocsExamined", "—"),
        "totalKeysExamined":   es.get("totalKeysExamined", "—"),
        "nReturned":           es.get("nReturned", "—"),
        "executionTimeMillis": es.get("executionTimeMillis", "—"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Demo 1 – COLLSCAN vs IXSCAN on listings.courseCode + price
# ─────────────────────────────────────────────────────────────────────────────

def demo_collscan_vs_ixscan(db) -> None:
    """
    WHY this query? "Find all CSE494 books under ₹500" is the most common
    marketplace query.  The compound index {courseCode:1, price:1} turns a
    full collection scan into a tiny index range scan.
    """
    print("\n" + "="*60)
    print("  EXPLAIN DEMO 1: COLLSCAN vs IXSCAN")
    print("  Query: listings where courseCode=CSE494 and price < 500")
    print("="*60)

    query = {"courseCode": "CSE494", "price": {"$lt": 500}}

    # ── Step 1: force COLLSCAN by using $natural hint ─────────────────────
    # WHY $natural hint: it instructs MongoDB to iterate documents in
    # natural (insertion) order, bypassing all indexes → guaranteed COLLSCAN.
    collscan = _explain(db, "listings", query, hint={"$natural": 1})

    # ── Step 2: force IXSCAN using our named compound index ───────────────
    ixscan   = _explain(db, "listings", query, hint="idx_listings_course_price")

    # ── Print comparison table ─────────────────────────────────────────────
    rows = [
        {
            "Scan Mode":           "COLLSCAN (no index)",
            "innerStage":          collscan["stage"],
            "docsExamined":        collscan["totalDocsExamined"],
            "nReturned":           collscan["nReturned"],
            "timeMillis":          collscan["executionTimeMillis"],
        },
        {
            "Scan Mode":           "IXSCAN (compound index)",
            "innerStage":          ixscan["stage"],
            "docsExamined":        ixscan["totalDocsExamined"],
            "nReturned":           ixscan["nReturned"],
            "timeMillis":          ixscan["executionTimeMillis"],
        },
    ]
    print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    print(f"\n  📊 Docs examined: COLLSCAN={collscan['totalDocsExamined']}  vs  "
          f"IXSCAN={ixscan['totalDocsExamined']}")
    print(f"  📊 Stage chains:")
    print(f"       COLLSCAN path : {collscan['stageChain']}")
    print(f"       IXSCAN   path : {ixscan['stageChain']}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Demo 2 – Text index search explain
# ─────────────────────────────────────────────────────────────────────────────

def demo_text_index_explain(db) -> None:
    """
    WHY text index explain? Shows that $text queries use the TEXT stage.
    Without the text index, $text would throw:
      'text index required for $text query'
    proving the index is mandatory, not just a performance optimisation.
    """
    print("\n" + "="*60)
    print("  EXPLAIN DEMO 2: Text Index ($text search on 'algorithms')")
    print("="*60)

    # For $text we must use db.command directly (hint not supported with $text)
    result = db.command(
        "explain",
        {
            "find":   "listings",
            "filter": {"$text": {"$search": "algorithms"}},
        },
        verbosity="executionStats",
    )

    es   = result.get("executionStats", {})
    plan = result.get("queryPlanner", {}).get("winningPlan", {})

    def _all_stages(p, acc=None):
        if acc is None:
            acc = []
        acc.append(p.get("stage", "?"))
        if "inputStage" in p:
            _all_stages(p["inputStage"], acc)
        return acc

    stages = " → ".join(_all_stages(plan))

    rows = [{
        "Stage Chain":         stages,
        "docsExamined":        es.get("totalDocsExamined", "—"),
        "nReturned":           es.get("nReturned", "—"),
        "executionTimeMillis": es.get("executionTimeMillis", "—"),
    }]
    print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    print(f"\n  💡 The TEXT stage means MongoDB used the weighted text index "
          f"(title×3, tags×1) – not a COLLSCAN.")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Demo 3 – Covered query (index covers all projected fields – no FETCH needed)
# ─────────────────────────────────────────────────────────────────────────────

def demo_covered_query(db) -> None:
    """
    WHY covered queries?
    A covered query is answered entirely from the index without touching the
    collection data files.  MongoDB marks it with stage PROJECTION_COVERED
    (or omits a FETCH stage entirely).

    Condition for a covered query:
      • All fields in the query filter are in the index.
      • All fields in the projection are in the index.
      • _id is excluded (or is in the index).

    Our compound index is {courseCode: 1, price: 1}.  If we project only
    {courseCode, price, _id:0}, MongoDB serves the result entirely from the
    index – totalDocsExamined = 0.
    """
    print("\n" + "="*60)
    print("  EXPLAIN DEMO 3: Covered Query (no document reads needed)")
    print("  Index: {courseCode:1, price:1}")
    print("  Query: courseCode='CSE101', project only courseCode+price")
    print("="*60)

    result = db.command(
        "explain",
        {
            "find":       "listings",
            "filter":     {"courseCode": "CSE101"},
            "projection": {"_id": 0, "courseCode": 1, "price": 1},
            "hint":       "idx_listings_course_price",
        },
        verbosity="executionStats",
    )

    es   = result.get("executionStats", {})
    plan = result.get("queryPlanner", {}).get("winningPlan", {})

    def _all_stages(p, acc=None):
        if acc is None:
            acc = []
        acc.append(p.get("stage", "?"))
        if "inputStage" in p:
            _all_stages(p["inputStage"], acc)
        return acc

    stages = " → ".join(_all_stages(plan))

    rows = [{
        "Stage Chain":         stages,
        "docsExamined":        es.get("totalDocsExamined", "—"),
        "keysExamined":        es.get("totalKeysExamined", "—"),
        "nReturned":           es.get("nReturned", "—"),
        "executionTimeMillis": es.get("executionTimeMillis", "—"),
    }]
    print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    print(f"\n  Stage chain: {stages}")
    print("  💡 totalDocsExamined = 0 → query served ENTIRELY from the index "
          "(no document reads).")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Demo 4 – Buyer transaction history (compound index with sort)
# ─────────────────────────────────────────────────────────────────────────────

def demo_buyer_history_explain(db) -> None:
    """
    WHY this demo?
    "Show my purchase history, newest first" is a very common buyer query.
    The compound index {buyerId: 1, createdAt: -1} means MongoDB can:
      (a) use an IXSCAN to jump directly to the buyer's entries
      (b) return them already sorted – no in-memory SORT stage needed.
    Without this index, MongoDB would need an expensive blocking SORT.
    """
    print("\n" + "="*60)
    print("  EXPLAIN DEMO 4: Buyer History (compound index avoids in-memory sort)")
    print("="*60)

    sample_txn = db["transactions"].find_one({"status": "completed"})
    if not sample_txn:
        print("  (no completed transactions to demo)")
        return

    buyer_id = sample_txn["buyerId"]

    result = db.command(
        "explain",
        {
            "find":   "transactions",
            "filter": {"buyerId": buyer_id},
            "sort":   {"createdAt": -1},
            "hint":   "idx_txn_buyer_date",
        },
        verbosity="executionStats",
    )

    es   = result.get("executionStats", {})
    plan = result.get("queryPlanner", {}).get("winningPlan", {})

    def _all_stages(p, acc=None):
        if acc is None:
            acc = []
        acc.append(p.get("stage", "?"))
        if "inputStage" in p:
            _all_stages(p["inputStage"], acc)
        return acc

    stages = " → ".join(_all_stages(plan))

    rows = [{
        "Stage Chain":         stages,
        "docsExamined":        es.get("totalDocsExamined", "—"),
        "nReturned":           es.get("nReturned", "—"),
        "executionTimeMillis": es.get("executionTimeMillis", "—"),
    }]
    print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    print(f"\n  Stage chain: {stages}")
    has_sort = "SORT" in stages
    print(f"  💡 {'⚠ SORT stage present – index not fully covering the sort' if has_sort else 'No SORT stage → the compound index already provides the correct order.'}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def run():
    client, db = get_db()
    try:
        print("\n" + "="*60)
        print("  06: EXPLAIN DEMO – Index Performance Analysis")
        print("="*60)
        demo_collscan_vs_ixscan(db)
        demo_text_index_explain(db)
        demo_covered_query(db)
        demo_buyer_history_explain(db)
        print("=" * 60)
        print("  EXPLAIN DEMO COMPLETE")
        print("=" * 60 + "\n")
    finally:
        client.close()


if __name__ == "__main__":
    run()
