"""
main.py – CampusBooks
========================
Menu-driven CLI for the live viva demo.
Lets the examiner navigate through all major operations interactively.

Usage: python main.py
"""

import sys
import datetime
import importlib
from tabulate import tabulate
from config import get_db

# Import all demo modules
import importlib

_MODULES: dict = {}


def _load_modules():
    """Lazy-import the demo modules so startup is fast."""
    global _MODULES
    for name in ["setup_val", "seed", "indexes", "crud", "agg", "explain"]:
        pass  # we import inline below to avoid circular issues


def _banner(title: str) -> None:
    width = 60
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)


def _pause():
    input("\n  Press ENTER to return to the main menu …\n")


# ─────────────────────────────────────────────────────────────────────────────
# Menu handlers
# ─────────────────────────────────────────────────────────────────────────────

def menu_setup(db, client):
    _banner("OPTION 1 – Setup: Drop + Recreate Collections & Validators")
    import importlib, sys
    mod = importlib.import_module("01_setup_validation")
    mod.setup_collections(db)
    mod.create_email_index(db)
    print("\n  ⚠  Collections recreated. Run 'Seed Data' next.")
    _pause()


def menu_seed(db, client):
    _banner("OPTION 2 – Seed Data (50 students / 300 listings / 200 txns / 150 reviews)")
    mod = importlib.import_module("02_seed_data")
    mod.run()
    _pause()


def menu_indexes(db, client):
    _banner("OPTION 3 – Create Indexes")
    mod = importlib.import_module("03_create_indexes")
    mod.create_indexes(db)
    _pause()


def menu_validation_demo(db, client):
    _banner("OPTION 4 – Validation Demo (invalid inserts)")
    mod = importlib.import_module("01_setup_validation")
    mod.demo_invalid_inserts(db)
    _pause()


def menu_crud(db, client):
    _banner("OPTION 5 – CRUD Operations Demo")
    mod = importlib.import_module("04_crud_operations")
    mod.run()
    _pause()


def menu_aggregations(db, client):
    """Sub-menu: run individual aggregations."""
    agg_mod = importlib.import_module("05_aggregations")

    options = [
        ("1", "Most-Traded Courses",          agg_mod.agg_most_traded_courses),
        ("2", "Monthly Revenue",              agg_mod.agg_monthly_revenue),
        ("3", "Seller Leaderboard",           agg_mod.agg_seller_leaderboard),
        ("4", "Department Discount %",        agg_mod.agg_department_discount),
        ("5", "Full Transaction Details",     agg_mod.agg_transaction_details),
        ("A", "Run ALL 5 Aggregations",       None),
        ("B", "Back to main menu",            None),
    ]

    while True:
        _banner("OPTION 6 – Aggregation Pipelines")
        for code, label, _ in options:
            print(f"    [{code}] {label}")
        choice = input("\n  Enter choice: ").strip().upper()

        if choice == "B":
            break
        elif choice == "A":
            for code, label, fn in options:
                if fn:
                    fn(db)
            _pause()
        else:
            for code, label, fn in options:
                if code == choice and fn:
                    fn(db)
                    _pause()
                    break


def menu_explain(db, client):
    _banner("OPTION 7 – Explain Demo (COLLSCAN vs IXSCAN)")
    mod = importlib.import_module("06_explain_demo")
    mod.run()
    _pause()


def menu_custom_query(db, client):
    _banner("OPTION 8 – Custom Live Query")
    print("  Sub-options:")
    print("    [1] Find student by regNo")
    print("    [2] Find available listings by courseCode")
    print("    [3] Find listings by department + max price")
    print("    [4] Show seller stats (by email)")
    print("    [B] Back")
    choice = input("\n  Enter choice: ").strip().upper()

    if choice == "1":
        regno = input("  Enter 8-digit regNo: ").strip()
        doc = db["students"].find_one(
            {"regNo": regno},
            {"_id": 0, "name": 1, "email": 1, "department": 1,
             "semester": 1, "profile": 1},
        )
        if doc:
            print(f"\n  Found: {doc}")
        else:
            print("  No student found with that regNo.")

    elif choice == "2":
        code = input("  Enter courseCode (e.g. CSE494): ").strip().upper()
        rows = list(
            db["listings"].find(
                {"courseCode": code, "status": "available"},
                {"_id": 0, "title": 1, "condition": 1, "price": 1,
                 "originalPrice": 1, "courseCode": 1},
            ).sort("price", 1).limit(10)
        )
        if rows:
            print()
            print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
        else:
            print(f"  No available listings for {code}.")

    elif choice == "3":
        dept = input("  Department [CSE/ECE/ME/Civil/MBA]: ").strip().upper()
        try:
            max_price = int(input("  Max price (₹): ").strip())
        except ValueError:
            print("  Invalid price.")
            _pause()
            return
        rows = list(
            db["listings"].find(
                {"department": dept, "status": "available",
                 "price": {"$lte": max_price}},
                {"_id": 0, "title": 1, "condition": 1, "price": 1, "courseCode": 1},
            ).sort("price", 1).limit(10)
        )
        if rows:
            print()
            print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
        else:
            print(f"  No listings found for {dept} under ₹{max_price}.")

    elif choice == "4":
        email = input("  Enter seller's email: ").strip()
        seller = db["students"].find_one({"email": email}, {"_id": 1, "name": 1})
        if not seller:
            print("  Student not found.")
            _pause()
            return
        sid = seller["_id"]
        listings_count = db["listings"].count_documents({"sellerId": sid})
        sold_count     = db["listings"].count_documents({"sellerId": sid, "status": "sold"})
        review_agg     = list(db["reviews"].aggregate([
            {"$match":  {"sellerId": sid}},
            {"$group":  {"_id": None, "avgRating": {"$avg": "$rating"}, "count": {"$sum": 1}}},
        ]))
        avg  = round(review_agg[0]["avgRating"], 2) if review_agg else "—"
        rcnt = review_agg[0]["count"]               if review_agg else 0
        print(f"\n  Seller     : {seller['name']}")
        print(f"  Listings   : {listings_count} (sold: {sold_count})")
        print(f"  Avg Rating : {avg} ({rcnt} reviews)")

    _pause()


def menu_collection_stats(db, client):
    _banner("OPTION 9 – Collection Statistics")
    rows = []
    for coll in ["students", "listings", "transactions", "reviews"]:
        count  = db[coll].count_documents({})
        idx_ct = len(list(db[coll].list_indexes()))
        rows.append({"Collection": coll, "Documents": count, "Indexes": idx_ct})
    print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
    _pause()


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

MENU = [
    ("1", "Setup – Create/Reset Collections & Validators", menu_setup),
    ("2", "Seed Data",                                     menu_seed),
    ("3", "Create Indexes",                                menu_indexes),
    ("4", "Validation Demo (invalid inserts)",             menu_validation_demo),
    ("5", "CRUD Operations Demo",                          menu_crud),
    ("6", "Aggregation Pipelines",                         menu_aggregations),
    ("7", "Explain Demo (COLLSCAN vs IXSCAN)",             menu_explain),
    ("8", "Custom Live Query",                             menu_custom_query),
    ("9", "Collection Statistics",                         menu_collection_stats),
    ("Q", "Quit",                                          None),
]


def main():
    client, db = get_db()
    try:
        while True:
            print("\n" + "╔" + "═"*58 + "╗")
            print("║" + "  📚  CampusBooks – CSE494 Demo CLI".center(58) + "║")
            print("╠" + "═"*58 + "╣")
            for code, label, _ in MENU:
                print(f"║  [{code}] {label:<53}║")
            print("╚" + "═"*58 + "╝")

            choice = input("\n  Enter option: ").strip().upper()

            if choice == "Q":
                print("\n  Goodbye! 👋\n")
                break

            matched = False
            for code, label, handler in MENU:
                if code == choice and handler:
                    try:
                        handler(db, client)
                    except Exception as exc:
                        print(f"\n  ❌ Error: {exc}")
                        _pause()
                    matched = True
                    break

            if not matched:
                print("  Invalid option. Try again.")

    finally:
        client.close()


if __name__ == "__main__":
    # Fix Windows console encoding
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")   # type: ignore
    main()
