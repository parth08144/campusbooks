"""
02_seed_data.py – CampusBooks
===============================
Generates and inserts realistic seed data:
  • 50 students
  • 300 listings
  • 200 transactions
  • 150 reviews

WHY realistic data?
  Aggregation results become meaningful (e.g., monthly revenue trends,
  top-selling departments) only when the data is realistic.  Generic
  'lorem ipsum' data hides bugs in queries.

WHY fixed random seed (SEED = 42)?
  Screenshots taken on different machines or at different times will show
  the same documents, making the viva reproducible.  The examiner can
  verify your output matches your report.

Run AFTER 01_setup_validation.py (collections must exist).
"""

import random
import datetime
from bson import ObjectId
from faker import Faker
from config import get_db

# ── Reproducible randomness ────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
fake = Faker("en_IN")       # Indian locale for names, phones, cities
Faker.seed(SEED)

# ──────────────────────────────────────────────────────────────────────────────
# Reference data (written by hand – realistic Indian university context)
# ──────────────────────────────────────────────────────────────────────────────

DEPARTMENTS = ["CSE", "ECE", "ME", "Civil", "MBA"]

# WHY course codes per department: listings must map to real courses so
# aggregation-by-courseCode is meaningful.
COURSE_CODES: dict[str, list[str]] = {
    "CSE":   ["CSE101", "CSE201", "CSE301", "CSE401", "CSE494",
               "CSE302", "CSE402", "CSE501"],
    "ECE":   ["ECE101", "ECE201", "ECE301", "ECE401", "ECE402"],
    "ME":    ["ME101",  "ME201",  "ME301",  "ME401",  "ME402"],
    "Civil": ["CV101",  "CV201",  "CV301",  "CV401",  "CV402"],
    "MBA":   ["MBA101", "MBA201", "MBA301", "MBA401", "MBA501"],
}

# WHY real book titles: query results look credible in screenshots.
BOOKS: list[dict] = [
    # CSE books
    {"title": "Introduction to Algorithms",          "isbn": "978-0262033848", "authors": ["Thomas H. Cormen", "Charles E. Leiserson"],      "dept": "CSE", "courses": ["CSE201", "CSE301"]},
    {"title": "Computer Networks",                   "isbn": "978-0132126953", "authors": ["Andrew S. Tanenbaum"],                           "dept": "CSE", "courses": ["CSE301", "CSE401"]},
    {"title": "Operating System Concepts",           "isbn": "978-1119800330", "authors": ["Abraham Silberschatz", "Peter B. Galvin"],       "dept": "CSE", "courses": ["CSE302", "CSE303"]},
    {"title": "Database System Concepts",            "isbn": "978-0073523323", "authors": ["Abraham Silberschatz"],                          "dept": "CSE", "courses": ["CSE401", "CSE494"]},
    {"title": "Artificial Intelligence: A Modern Approach","isbn": "978-0136042594","authors": ["Stuart Russell", "Peter Norvig"],            "dept": "CSE", "courses": ["CSE494", "CSE501"]},
    {"title": "Clean Code",                          "isbn": "978-0132350884", "authors": ["Robert C. Martin"],                              "dept": "CSE", "courses": ["CSE101", "CSE201"]},
    {"title": "The Pragmatic Programmer",            "isbn": "978-0135957059", "authors": ["David Thomas", "Andrew Hunt"],                   "dept": "CSE", "courses": ["CSE101"]},
    {"title": "Design Patterns",                     "isbn": "978-0201633610", "authors": ["Gang of Four"],                                  "dept": "CSE", "courses": ["CSE402"]},
    {"title": "Data Structures and Algorithms in Python","isbn": "978-1118290279","authors": ["Michael T. Goodrich"],                        "dept": "CSE", "courses": ["CSE201", "CSE301"]},
    {"title": "Computer Organization and Architecture","isbn": "978-0134101613","authors": ["William Stallings"],                            "dept": "CSE", "courses": ["CSE302"]},
    # ECE books
    {"title": "Electronic Devices and Circuit Theory","isbn": "978-0134561547", "authors": ["Robert L. Boylestad"],                          "dept": "ECE", "courses": ["ECE101", "ECE201"]},
    {"title": "Signals and Systems",                 "isbn": "978-0138147570", "authors": ["Alan V. Oppenheim"],                             "dept": "ECE", "courses": ["ECE201", "ECE301"]},
    {"title": "Digital Signal Processing",           "isbn": "978-0131873742", "authors": ["John G. Proakis"],                               "dept": "ECE", "courses": ["ECE301", "ECE401"]},
    {"title": "Microprocessors and Microcontrollers","isbn": "978-8131710142", "authors": ["N. Senthil Kumar"],                              "dept": "ECE", "courses": ["ECE401", "ECE402"]},
    {"title": "Electromagnetic Field Theory",        "isbn": "978-0195693leware", "authors": ["K.A. Gangadhar"],                             "dept": "ECE", "courses": ["ECE201"]},
    # ME books
    {"title": "Engineering Thermodynamics",          "isbn": "978-0073398174", "authors": ["Michael J. Moran"],                              "dept": "ME",  "courses": ["ME101", "ME201"]},
    {"title": "Mechanics of Materials",              "isbn": "978-0134319650", "authors": ["Russell C. Hibbeler"],                           "dept": "ME",  "courses": ["ME201", "ME301"]},
    {"title": "Machine Design",                      "isbn": "978-9332518353", "authors": ["V.B. Bhandari"],                                 "dept": "ME",  "courses": ["ME301", "ME401"]},
    {"title": "Fluid Mechanics",                     "isbn": "978-0073398273", "authors": ["Frank M. White"],                                "dept": "ME",  "courses": ["ME201", "ME401"]},
    {"title": "Manufacturing Engineering and Technology","isbn": "978-0133586251","authors": ["Serope Kalpakjian"],                          "dept": "ME",  "courses": ["ME401", "ME402"]},
    # Civil books
    {"title": "Structural Analysis",                 "isbn": "978-9332518452", "authors": ["R.C. Hibbeler"],                                 "dept": "Civil","courses": ["CV201", "CV301"]},
    {"title": "Geotechnical Engineering",            "isbn": "978-0070700901", "authors": ["C. Venkatramaiah"],                              "dept": "Civil","courses": ["CV301", "CV401"]},
    {"title": "Concrete Technology",                 "isbn": "978-8121925891", "authors": ["M.S. Shetty"],                                   "dept": "Civil","courses": ["CV201", "CV302"]},
    {"title": "Highway Engineering",                 "isbn": "978-8121902120", "authors": ["S.K. Khanna", "C.E.G. Justo"],                  "dept": "Civil","courses": ["CV401", "CV402"]},
    {"title": "Environmental Engineering",           "isbn": "978-9352535453", "authors": ["S.K. Garg"],                                     "dept": "Civil","courses": ["CV101", "CV401"]},
    # MBA books
    {"title": "Principles of Marketing",             "isbn": "978-0135768501", "authors": ["Philip Kotler", "Gary Armstrong"],               "dept": "MBA", "courses": ["MBA101", "MBA201"]},
    {"title": "Financial Management",                "isbn": "978-9385965975", "authors": ["Prasanna Chandra"],                              "dept": "MBA", "courses": ["MBA201", "MBA301"]},
    {"title": "Organizational Behavior",             "isbn": "978-0133809299", "authors": ["Stephen P. Robbins"],                            "dept": "MBA", "courses": ["MBA101", "MBA401"]},
    {"title": "Business Statistics",                 "isbn": "978-9332540538", "authors": ["J.K. Sharma"],                                   "dept": "MBA", "courses": ["MBA101", "MBA301"]},
    {"title": "Strategic Management",                "isbn": "978-1259924880", "authors": ["Arthur A. Thompson"],                            "dept": "MBA", "courses": ["MBA501", "MBA401"]},
]

TAGS_POOL = [
    "algorithms", "programming", "circuits", "thermodynamics",
    "structures", "marketing", "finance", "signals", "databases",
    "networking", "os", "machine-design", "concrete", "roads",
    "geotechnical", "ai", "ml", "clean-code", "statistics", "strategy"
]

HOSTEL_BLOCKS = ["A", "B", "C", "D", "E"]
CONDITIONS     = ["new", "good", "fair", "poor"]
PAYMENT_MODES  = ["cash", "upi"]

# WHY weights on condition: most second-hand books are 'good' or 'fair';
# 'new' and 'poor' are rarer, making the data realistic.
CONDITION_WEIGHTS = [0.10, 0.45, 0.35, 0.10]

# Price discount factor per condition (applied to originalPrice)
DISCOUNT: dict[str, tuple[float, float]] = {
    "new":  (0.85, 0.95),
    "good": (0.55, 0.75),
    "fair": (0.35, 0.55),
    "poor": (0.15, 0.35),
}

# ──────────────────────────────────────────────────────────────────────────────
# Generators
# ──────────────────────────────────────────────────────────────────────────────

def _rand_date(days_back: int = 365) -> datetime.datetime:
    """Return a random UTC datetime within the past `days_back` days."""
    delta = datetime.timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return datetime.datetime.now(datetime.timezone.utc) - delta


def generate_students(n: int = 50) -> list[dict]:
    """
    WHY: Generate students first; their _id values are referenced by
    listings, transactions, and reviews.
    """
    used_emails = set()
    used_regnos = set()
    students    = []

    for i in range(n):
        while True:
            email = fake.email()
            if email not in used_emails:
                used_emails.add(email)
                break

        while True:
            regno = str(random.randint(10000000, 99999999))
            if regno not in used_regnos:
                used_regnos.add(regno)
                break

        dept = random.choice(DEPARTMENTS)
        # Indian mobile numbers start with 6-9 and are 10 digits
        phone = str(random.choice([6, 7, 8, 9])) + "".join(
            [str(random.randint(0, 9)) for _ in range(9)]
        )

        students.append({
            "_id":        ObjectId(),
            "name":       fake.name(),
            "email":      email,
            "regNo":      regno,
            "department": dept,
            "semester":   random.randint(1, 8),
            "profile": {
                "phone":       phone,
                "hostelBlock": random.choice(HOSTEL_BLOCKS),
                "roomNo":      str(random.randint(100, 500)),
            },
            "createdAt": _rand_date(days_back=730),
        })
    return students


def generate_listings(students: list[dict], n: int = 300) -> list[dict]:
    """
    WHY: Each listing references a seller (student._id).
    The price is a realistic fraction of originalPrice based on condition.
    """
    listings = []
    for _ in range(n):
        book      = random.choice(BOOKS)
        dept      = book["dept"]
        condition = random.choices(CONDITIONS, weights=CONDITION_WEIGHTS, k=1)[0]
        orig_price = random.choice([300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800])
        lo, hi    = DISCOUNT[condition]
        price     = int(orig_price * random.uniform(lo, hi))

        # WHY price is int: keeps aggregation ($sum, $avg) simple and exact.
        # In production, Decimal128 would prevent floating-point errors.
        seller    = random.choice(students)
        num_tags  = random.randint(1, 3)
        tags      = random.sample(TAGS_POOL, k=num_tags)

        # Pick a course from the book's eligible courses, or fallback to dept
        course = random.choice(book["courses"]) if book["courses"] else random.choice(COURSE_CODES[dept])

        listings.append({
            "_id":           ObjectId(),
            "title":         book["title"],
            "isbn":          book["isbn"],
            "authors":       book["authors"],
            "courseCode":    course,
            "department":    dept,
            "condition":     condition,
            "originalPrice": orig_price,
            "price":         price,
            "tags":          tags,
            "status":        random.choices(
                                 ["available", "reserved", "sold"],
                                 weights=[0.40, 0.10, 0.50],
                                 k=1
                             )[0],
            "sellerId":      seller["_id"],
            "postedAt":      _rand_date(days_back=300),
        })
    return listings


def generate_transactions(
    students:  list[dict],
    listings:  list[dict],
    n:         int = 200,
) -> list[dict]:
    """
    WHY: Transactions link a buyer and seller with an embedded item snapshot.
    We only create transactions for 'sold' or 'reserved' listings so the
    data is internally consistent.
    """
    eligible  = [l for l in listings if l["status"] in ("sold", "reserved")]
    if len(eligible) < n:
        n = len(eligible)       # avoid repeating if not enough eligible listings

    sampled   = random.sample(eligible, k=n)
    txns      = []
    for listing in sampled:
        buyer = random.choice(students)
        # ensure buyer ≠ seller (can't buy your own book)
        while buyer["_id"] == listing["sellerId"]:
            buyer = random.choice(students)

        txns.append({
            "_id":      ObjectId(),
            "buyerId":  buyer["_id"],
            "sellerId": listing["sellerId"],
            # WHY snapshot: title and price at transaction time
            "item": {
                "listingId": listing["_id"],
                "title":     listing["title"],
                "price":     listing["price"],
            },
            "paymentMode": random.choice(PAYMENT_MODES),
            "status":      random.choices(
                               ["pending", "completed", "cancelled"],
                               weights=[0.10, 0.80, 0.10],
                               k=1
                           )[0],
            "createdAt":   _rand_date(days_back=180),
        })
    return txns


def generate_reviews(
    transactions: list[dict],
    n:            int = 150,
) -> list[dict]:
    """
    WHY REFERENCED (not embedded): reviews grow without bound as more buyers
    leave feedback.  Embedding all reviews in the seller document would make
    it grow indefinitely, eventually hitting MongoDB's 16 MB document limit.
    Referencing keeps each document small.

    Only completed transactions can have reviews.
    """
    completed = [t for t in transactions if t["status"] == "completed"]
    if len(completed) < n:
        n = len(completed)

    sampled = random.sample(completed, k=n)
    reviews = []
    for txn in sampled:
        reviews.append({
            "_id":           ObjectId(),
            "transactionId": txn["_id"],
            "reviewerId":    txn["buyerId"],
            "sellerId":      txn["sellerId"],
            "rating":        random.choices(
                                 [1, 2, 3, 4, 5],
                                 # WHY skewed: most buyers who complete leave
                                 # positive reviews; negative reviews are rarer.
                                 weights=[0.03, 0.07, 0.15, 0.35, 0.40],
                                 k=1
                             )[0],
            "comment":       random.choice([
                "Book was in great condition, as described.",
                "Seller was very prompt and helpful.",
                "Good deal, saved a lot of money!",
                "Slight wear but pages are clean.",
                "Fast handover, no issues.",
                "Highly recommended seller.",
                "Book had a few highlights but still useful.",
                "Would buy from this seller again.",
                "Price was fair for the condition.",
                "The seller was courteous and punctual.",
            ]),
            "createdAt": _rand_date(days_back=150),
        })
    return reviews


# ──────────────────────────────────────────────────────────────────────────────
# Main seed function
# ──────────────────────────────────────────────────────────────────────────────

def run():
    client, db = get_db()
    try:
        print("\n=== 02: Seeding CampusBooks Database ===\n")

        # ── Students ──────────────────────────────────────────────────────────
        print("  Generating 50 students …")
        students = generate_students(50)
        result   = db["students"].insert_many(students)
        print(f"  ✅  Inserted {len(result.inserted_ids)} students\n")

        # ── Listings ──────────────────────────────────────────────────────────
        print("  Generating 300 listings …")
        listings = generate_listings(students, 300)
        result   = db["listings"].insert_many(listings)
        print(f"  ✅  Inserted {len(result.inserted_ids)} listings\n")

        # ── Transactions ──────────────────────────────────────────────────────
        print("  Generating 200 transactions …")
        transactions = generate_transactions(students, listings, 200)
        result       = db["transactions"].insert_many(transactions)
        print(f"  ✅  Inserted {len(result.inserted_ids)} transactions\n")

        # ── Reviews ───────────────────────────────────────────────────────────
        print("  Generating 150 reviews …")
        reviews = generate_reviews(transactions, 150)
        result  = db["reviews"].insert_many(reviews)
        print(f"  ✅  Inserted {len(result.inserted_ids)} reviews\n")

        # ── Summary ───────────────────────────────────────────────────────────
        print("=== Seed Complete – Collection Counts ===")
        for coll in ["students", "listings", "transactions", "reviews"]:
            count = db[coll].count_documents({})
            print(f"   {coll:<15} {count:>4} documents")
        print()

    finally:
        client.close()


if __name__ == "__main__":
    run()
