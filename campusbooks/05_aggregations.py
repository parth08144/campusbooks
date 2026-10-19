"""
05_aggregations.py – CampusBooks
===================================
Five aggregation pipelines covering the full range of MongoDB aggregation
operators.  Each pipeline is fully commented stage by stage.

WHY aggregation pipelines?
  SQL-style analytics (GROUP BY, JOIN, AVG, SUM) are expressed in MongoDB
  as a sequence of stages that transform documents like a Unix pipe.
  They run inside the server, avoiding costly data transfer to the client.

NOTE on architecture:
  The actual pipeline logic lives in services.py (functions that RETURN data).
  This file keeps the print/tabulate formatting and calls services.py,
  so app.py (Streamlit) can import services.py without touching this file.

Run AFTER 03_create_indexes.py.
"""

import services
from tabulate import tabulate
from config import get_db


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 1 – Most-Traded Courses
# ─────────────────────────────────────────────────────────────────────────────

def agg_most_traded_courses(db) -> None:
    """
    GOAL: Which course codes generate the most completed sales?
    This helps the platform highlight high-demand subjects.

    Stages:
      1. $match    – keep only completed transactions (uses idx_txn_status)
      2. $lookup   – join with listings to get the courseCode
      3. $unwind   – flatten the joined array (each doc has one listing)
      4. $group    – count transactions and sum revenue per courseCode
      5. $sort     – descending by transaction count
      6. $limit    – top 8 results
      7. $project  – rename fields for clean output
    """
    print("\n" + "="*60)
    print("  AGGREGATION 1: Most-Traded Courses")
    print("="*60)

    pipeline = [
        # Stage 1 – WHY $match first: reduces the working set early; uses the
        #           idx_txn_status index so MongoDB doesn't scan all transactions.
        {"$match": {"status": "completed"}},

        # Stage 2 – WHY $lookup: we need courseCode from the listings collection.
        #           'from' is the target collection, 'localField' is the field in
        #           transactions that holds the listing's _id (item.listingId),
        #           'foreignField' is _id in listings, 'as' is the output array name.
        {"$lookup": {
            "from":         "listings",
            "localField":   "item.listingId",
            "foreignField": "_id",
            "as":           "listingInfo",
        }},

        # Stage 3 – WHY $unwind: $lookup always produces an array; $unwind
        #           deconstructs it so each transaction document has ONE listing
        #           sub-document, not an array.
        {"$unwind": "$listingInfo"},

        # Stage 4 – WHY $group: aggregate per courseCode.
        #           $sum:1 counts documents; $sum:"$item.price" totals revenue.
        {"$group": {
            "_id":         "$listingInfo.courseCode",
            "totalSales":  {"$sum": 1},
            "totalRevenue": {"$sum": "$item.price"},
        }},

        # Stage 5 – WHY $sort after $group: order by busiest course first.
        {"$sort": {"totalSales": -1}},

        # Stage 6 – WHY $limit: we only want the top 8 for display.
        {"$limit": 8},

        # Stage 7 – WHY $project: rename _id to courseCode for readable output.
        {"$project": {
            "_id":          0,
            "courseCode":   "$_id",
            "totalSales":   1,
            "totalRevenue (₹)": "$totalRevenue",
        }},
    ]

    results = list(db["transactions"].aggregate(pipeline))
    if results:
        print(tabulate(results, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no data)")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 2 – Monthly Sales Revenue
# ─────────────────────────────────────────────────────────────────────────────

def agg_monthly_revenue(db) -> None:
    """
    GOAL: How does revenue trend month by month?
    Useful for platform analytics – detect busy semester start months.

    Stages:
      1. $match   – completed transactions only
      2. $group   – group by year+month, sum prices
      3. $sort    – chronological
      4. $project – format the year-month label
    """
    print("\n" + "="*60)
    print("  AGGREGATION 2: Monthly Sales Revenue")
    print("="*60)

    pipeline = [
        # Stage 1 – filter to completed sales only
        {"$match": {"status": "completed"}},

        # Stage 2 – WHY $year/$month date operators: extract year and month
        #           from the createdAt Date field so we can group by calendar month.
        #           Using the embedded item.price (snapshot) ensures we capture the
        #           price at sale time, not the listing's current price.
        {"$group": {
            "_id": {
                "year":  {"$year":  "$createdAt"},
                "month": {"$month": "$createdAt"},
            },
            "totalRevenue":  {"$sum": "$item.price"},
            "totalSales":    {"$sum": 1},
            "avgSalePrice":  {"$avg": "$item.price"},
        }},

        # Stage 3 – WHY chronological sort: trends are only meaningful in order.
        {"$sort": {"_id.year": 1, "_id.month": 1}},

        # Stage 4 – WHY $project with $concat: combine year and month into a
        #           human-readable label like "2026-03" for the output table.
        {"$project": {
            "_id":           0,
            "Month":         {"$concat": [
                {"$toString": "$_id.year"}, "-",
                {"$cond": [
                    {"$lt": ["$_id.month", 10]},
                    {"$concat": ["0", {"$toString": "$_id.month"}]},
                    {"$toString": "$_id.month"}
                ]},
            ]},
            "Revenue (₹)":    "$totalRevenue",
            "Sales Count":    "$totalSales",
            "Avg Price (₹)":  {"$round": ["$avgSalePrice", 0]},
        }},
    ]

    results = list(db["transactions"].aggregate(pipeline))
    if results:
        print(tabulate(results, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no data)")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 3 – Seller Leaderboard
# ─────────────────────────────────────────────────────────────────────────────

def agg_seller_leaderboard(db) -> None:
    """
    GOAL: Rank sellers by average rating, only including those with ≥ 3 reviews
    (to avoid a seller with a single 5-star review topping the board).

    Stages:
      1. $group   – group reviews by sellerId, compute avg rating and count
      2. $match   – keep only sellers with ≥ 3 reviews
      3. $sort    – best rated first
      4. $limit   – top 10
      5. $lookup  – fetch seller name from students
      6. $unwind  – flatten the students array
      7. $project – clean output shape
    """
    print("\n" + "="*60)
    print("  AGGREGATION 3: Seller Leaderboard (min 3 reviews)")
    print("="*60)

    pipeline = [
        # Stage 1 – WHY group reviews by sellerId first: this is cheaper than
        #           looking up student names for every review document.
        {"$group": {
            "_id":        "$sellerId",
            "avgRating":  {"$avg": "$rating"},
            "reviewCount": {"$sum": 1},
            "ratings":    {"$push": "$rating"},  # keep raw ratings for display
        }},

        # Stage 2 – WHY $match AFTER $group: the condition (reviewCount >= 3)
        #           can only be evaluated after grouping.  This is the HAVING
        #           clause equivalent in SQL.
        {"$match": {"reviewCount": {"$gte": 3}}},

        # Stage 3 – top rated first
        {"$sort": {"avgRating": -1}},

        {"$limit": 10},

        # Stage 4 – WHY $lookup after filtering: we've already reduced the
        #           pipeline to ≤10 docs; joining all sellers first would be wasteful.
        {"$lookup": {
            "from":         "students",
            "localField":   "_id",
            "foreignField": "_id",
            "as":           "sellerInfo",
        }},

        # Stage 5 – flatten the single-element array from $lookup
        {"$unwind": {
            "path":                       "$sellerInfo",
            "preserveNullAndEmptyArrays": True,  # WHY: don't drop if student deleted
        }},

        # Stage 6 – final shape
        {"$project": {
            "_id":          0,
            "Seller":       {"$ifNull": ["$sellerInfo.name", "Unknown"]},
            "Department":   {"$ifNull": ["$sellerInfo.department", "—"]},
            "Avg Rating":   {"$round": ["$avgRating", 2]},
            "Reviews":      "$reviewCount",
        }},
    ]

    results = list(db["reviews"].aggregate(pipeline))
    if results:
        print(tabulate(results, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no sellers with >= 3 reviews yet)")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 4 – Department-wise Average Discount %
# ─────────────────────────────────────────────────────────────────────────────

def agg_department_discount(db) -> None:
    """
    GOAL: Which department's students offer the deepest discounts?
    Helps buyers know where to look for the best deals.

    Formula: discount% = (originalPrice - price) / originalPrice * 100

    Stages:
      1. $match   – only listings where originalPrice > 0 (avoid divide-by-zero)
      2. $group   – per department, compute $avg of the discount expression
      3. $project – round to 2 decimal places
      4. $sort    – deepest discount first
    """
    print("\n" + "="*60)
    print("  AGGREGATION 4: Department-wise Average Discount %")
    print("="*60)

    pipeline = [
        # Stage 1 – WHY $match: originalPrice must be > 0 to avoid division
        #           by zero in the $divide expression below.
        {"$match": {"originalPrice": {"$gt": 0}}},

        # Stage 2 – WHY $group with $avg + $divide: MongoDB evaluates the
        #           arithmetic expression per document during grouping.
        #           This is equivalent to SQL: AVG((originalPrice-price)/originalPrice*100)
        {"$group": {
            "_id": "$department",
            "avgDiscountPct": {
                "$avg": {
                    "$multiply": [
                        {"$divide": [
                            {"$subtract": ["$originalPrice", "$price"]},
                            "$originalPrice"
                        ]},
                        100
                    ]
                }
            },
            "listingCount": {"$sum": 1},
            "avgPrice":     {"$avg": "$price"},
        }},

        # Stage 3 – WHY $project + $round: display a clean 2-decimal percentage
        {"$project": {
            "_id":               0,
            "Department":        "$_id",
            "Avg Discount (%)":  {"$round": ["$avgDiscountPct", 2]},
            "Listing Count":     "$listingCount",
            "Avg Sale Price (₹)": {"$round": ["$avgPrice", 0]},
        }},

        # Stage 4 – deepest discount first
        {"$sort": {"Avg Discount (%)": -1}},
    ]

    results = list(db["listings"].aggregate(pipeline))
    if results:
        print(tabulate(results, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no data)")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 5 – Full Transaction Details ($lookup buyer + seller + listing)
# ─────────────────────────────────────────────────────────────────────────────

def agg_transaction_details(db) -> None:
    """
    GOAL: Show completed transactions in a human-readable format with buyer
    name, seller name, book title, price, and payment mode.

    WHY three $lookups?
      Transactions store only ObjectId references to keep them compact.
      At query time we enrich them with student and listing names.
      In SQL this would be three JOINs.

    Stages:
      1. $match   – completed only, limit scope
      2. $lookup  – join buyer (students)
      3. $unwind  – flatten buyer array
      4. $lookup  – join seller (students)
      5. $unwind  – flatten seller array
      6. $lookup  – join listing
      7. $unwind  – flatten listing array (preserving missing)
      8. $project – final readable shape
      9. $limit   – show 10 for demo
    """
    print("\n" + "="*60)
    print("  AGGREGATION 5: Full Transaction Details")
    print("="*60)

    pipeline = [
        # Stage 1 – completed transactions only
        {"$match": {"status": "completed"}},

        # Stages 2-3: join buyer name
        {"$lookup": {
            "from":         "students",
            "localField":   "buyerId",
            "foreignField": "_id",
            "as":           "buyer",
        }},
        # WHY $unwind immediately after $lookup: keeps the pipeline linear;
        # the next $lookup then operates on a flat document, not nested arrays.
        {"$unwind": "$buyer"},

        # Stages 4-5: join seller name
        {"$lookup": {
            "from":         "students",
            "localField":   "sellerId",
            "foreignField": "_id",
            "as":           "seller",
        }},
        {"$unwind": "$seller"},

        # Stages 6-7: join listing for courseCode
        # WHY $lookup listing even though we have item snapshot?
        # The snapshot has title + price but not courseCode.
        {"$lookup": {
            "from":         "listings",
            "localField":   "item.listingId",
            "foreignField": "_id",
            "as":           "listing",
        }},
        {"$unwind": {
            "path":                       "$listing",
            "preserveNullAndEmptyArrays": True,   # listing may have been deleted
        }},

        # Stage 8 – project only the fields needed for the output table
        {"$project": {
            "_id":           0,
            "Date":          {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}},
            "Buyer":         "$buyer.name",
            "Seller":        "$seller.name",
            "Book":          "$item.title",
            "Course":        {"$ifNull": ["$listing.courseCode", "—"]},
            "Price (₹)":     "$item.price",
            "Payment":       "$paymentMode",
        }},

        # Stage 9 – limit for demo display
        {"$limit": 10},
    ]

    results = list(db["transactions"].aggregate(pipeline))
    if results:
        print(tabulate(results, headers="keys", tablefmt="rounded_outline"))
    else:
        print("   (no completed transactions yet)")


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def run():
    client, db = get_db()
    try:
        agg_most_traded_courses(db)
        agg_monthly_revenue(db)
        agg_seller_leaderboard(db)
        agg_department_discount(db)
        agg_transaction_details(db)
        print()
    finally:
        client.close()


if __name__ == "__main__":
    run()
