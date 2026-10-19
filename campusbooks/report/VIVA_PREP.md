# CampusBooks – Viva Preparation Pack
### CSE494 | Intelligent NoSQL Databases

---

## PART A: Slide-by-Slide Presentation Outline (9 Slides)

---

### Slide 1 – Title & Motivation
**Heading:** CampusBooks – A MongoDB-Powered Second-Hand Textbook Marketplace  
**Sub-heading:** CSE494 Individual Project | [Your Name] | [Roll No]

**Visuals:** A simple graphic — stack of books + ₹ discount badge

**Speaker notes:**
> "Good [morning/afternoon]. My project is CampusBooks — a marketplace where senior students can list their used textbooks for juniors to buy at a discount. The core problem is that students spend thousands of rupees on new textbooks every semester, use them once, and then they collect dust. CampusBooks solves this with a NoSQL database that I'll walk you through today."

---

### Slide 2 – Problem Statement & Why NoSQL
**Content (two columns):**

Left — The Problem:
- Students spend ₹5,000–₹15,000 per semester on textbooks
- Books are used for 1 semester, then abandoned
- No organised campus second-hand market exists

Right — Why MongoDB:
- Flexible schema (books have variable numbers of authors)
- Embedded documents (profile always fetched with student)
- Built-in text search for title/tag keyword queries
- `$jsonSchema` for database-level validation
- Aggregation pipeline for analytics

**Speaker notes:**
> "I chose MongoDB because the data is naturally document-shaped. A book listing has embedded authors, a student has an embedded profile, and a transaction has an embedded price snapshot. These patterns are awkward in a relational table but natural in a document store."

---

### Slide 3 – Data Model & Design Decisions
**Heading:** 4 Collections, 3 Design Patterns

**Content (table):**

| Collection | Key Design Decision | Why |
|---|---|---|
| `students` | Profile **embedded** (1-to-1) | Always fetched together; avoids extra round-trip |
| `listings` | Authors **embedded array** | Read-only; never queried independently |
| `transactions` | Item **snapshot embedded** | History stays correct if listing is later changed |
| `reviews` | **Referenced** (separate collection) | Unbounded growth → 16 MB doc limit risk |

**Visuals:** Mini ER diagram (can paste from REPORT.md Mermaid)

**Speaker notes:**
> "The most important design decision is the transaction item snapshot. If I simply referenced the listing, and the seller later changed the price or deleted the listing, the transaction history would show the wrong amount. By embedding a snapshot at purchase time — just like a printed receipt — the history is always accurate."

---

### Slide 4 – Schema Validation (Unit III)
**Heading:** $jsonSchema – Database-Level Data Integrity

**Content:**
- `validationLevel: "strict"` — validates every insert AND update
- `validationAction: "error"` — rejects invalid documents outright
- 7 validation rules demonstrated live

**Code snippet:**
```json
"semester": {
  "bsonType": "int",
  "minimum": 1,
  "maximum": 8
},
"regNo": {
  "bsonType": "string",
  "pattern": "^[0-9]{8}$"
}
```

**[Screenshot 1: Invalid-insert demo — 7 rejected documents]**

**Speaker notes:**
> "Validation in Python alone can be bypassed by anyone connecting via mongosh or Compass. Putting it in the database means it cannot be bypassed regardless of how data enters the system. I'll show this live: I deliberately insert a listing with price = -50 and MongoDB rejects it with a WriteError."

---

### Slide 5 – Indexes (Unit IV)
**Heading:** 11 Indexes Across 4 Collections

**Content (table):**

| Index | Type | Benefit |
|---|---|---|
| `students.email` | Unique | Integrity + fast login |
| `listings.{courseCode, price}` | Compound | Most-common query: books by course under budget |
| `listings.{title, tags}` | Text (weighted) | Full-text search with relevance scoring |
| `listings.{status, department}` | Compound | Available-by-dept filter |
| `transactions.{buyerId, createdAt DESC}` | Compound | Buyer history — no in-memory sort needed |
| `reviews.transactionId` | Unique | Max 1 review per transaction |

**[Screenshot 10: COLLSCAN 302 docs vs IXSCAN 6 docs]**

**Speaker notes:**
> "The compound index on courseCode+price reduced document examination from 302 to just 6 — a 50× improvement. I also have a covered query where totalDocsExamined = 0, meaning the result came entirely from the index with zero document reads. I'll show this with explain() output."

---

### Slide 6 – CRUD Operations
**Heading:** All Required CRUD Operations Demonstrated

**Content (3-column grid):**

| CREATE | READ | UPDATE | DELETE |
|---|---|---|---|
| `insert_one` — new student | `find_one` + projection | `update_one` + `$set` | `delete_one` |
| `insert_many` — bulk listings | `find` + `$gte/$lte/$in/$regex` | `update_many` + `$toInt($multiply)` | `delete_many` (90-day purge) |
| | `$text` search | `$push`/`$pull` on tags | |
| | Pagination (skip/limit) | `$inc` viewCount | |
| | `count_documents` | `upsert=True` | |
| | | `find_one_and_update` (atomic CAS) | |

**[Screenshot 4: Atomic reservation — second buyer gets None]**

**Speaker notes:**
> "The most interesting operation is the atomic reservation using find_one_and_update. The filter includes {status: 'available'} so it only matches and updates if the book hasn't been taken yet. This is the Compare-And-Swap pattern — it prevents two buyers from reserving the same book simultaneously."

---

### Slide 7 – Aggregation Pipelines
**Heading:** 5 Aggregation Pipelines for Analytics

**Content:**

1. **Most-Traded Courses** — `$match → $lookup → $unwind → $group → $sort → $limit`
2. **Monthly Revenue** — `$year/$month → $group → $sort`
3. **Seller Leaderboard** — `$group → $match (≥3 reviews) → $lookup → $project`
4. **Department Discount %** — `$avg of $divide expression → $round`
5. **Transaction Details** — 3× `$lookup` (buyer + seller + listing)

**[Screenshot 5: Most-Traded Courses]**  
**[Screenshot 7: Seller Leaderboard]**

**Speaker notes:**
> "In pipeline 3, I do the $group and $match BEFORE the $lookup. This is equivalent to SQL's HAVING clause — I filter sellers with at least 3 reviews first, then join student names only for those ≤10 qualifying sellers. Joining all sellers first would be expensive and wasteful."

---

### Slide 8 – PyMongo Integration
**Heading:** Python + PyMongo 4.7 Integration Details

**Content:**
- `python-dotenv` for secret-free configuration
- `MongoClient` connection pool (automatic)
- `ReturnDocument.AFTER` for post-update documents
- `db.command("explain", ..., verbosity="executionStats")` — correct PyMongo 4.x API
- Pipeline updates `[{$set: ...}]` for schema-compliant `$multiply`
- `tabulate` for professional table output in CLI

**Code snippet:**
```python
# Atomic price discount — keeps bsonType: int
db["listings"].update_many(
    {"condition": "poor", "status": "available"},
    [{"$set": {"price": {
        "$toInt": {"$multiply": ["$price", 0.9]}
    }}}],
)
```

**Speaker notes:**
> "One gotcha I hit: MongoDB's $mul operator on an int field returns a double, which violated my $jsonSchema validator. Using an aggregation pipeline update with $toInt fixes this — the result stays as int32. This is a good example of why strict schema enforcement leads to better code."

---

### Slide 9 – Demo & Conclusion
**Heading:** Live Demo + Key Takeaways

**Content (two columns):**

Left — Demo menu (`python main.py`):
1. Validation errors
2. CRUD operations
3. Aggregation pipelines
4. Explain: COLLSCAN → IXSCAN
5. Live custom query by regNo / courseCode

Right — Key Takeaways:
- MongoDB excels at **variable-schema, document-centric** data
- `$jsonSchema` + strict validation = DB-level data integrity
- Indexes can reduce doc reads by **50×**
- Aggregation pipeline = server-side analytics with zero data transfer
- Embedding vs. referencing is the **most important design decision**

**Speaker notes:**
> "To summarise: CampusBooks shows that MongoDB is an excellent fit for marketplace applications where schema flexibility, text search, and analytics are all needed simultaneously. The key skill is knowing when to embed and when to reference — and always enforcing validation at the database layer."

---
---

## PART B: Screenshot Checklist

Take screenshots in this exact order, naming them as shown.

| # | Script / Action | What to Capture | Filename |
|---|----------------|-----------------|----------|
| 1 | `python 01_setup_validation.py` | The 7 "✅ WriteError/DuplicateKeyError caught" messages | `ss01_validation_errors.png` |
| 2 | `python 02_seed_data.py` | "✅ Inserted X students/listings/transactions/reviews" + counts table | `ss02_seed_data.png` |
| 3 | `python 03_create_indexes.py` | All 11 "✅ index" lines + the Index Summary table | `ss03_indexes.png` |
| 4 | `python 04_crud_operations.py` – CREATE section | insert_one output + insert_many output (3 books) | `ss04a_crud_create.png` |
| 5 | `python 04_crud_operations.py` – READ section | READ 2 (find with operators table) | `ss04b_crud_read_filter.png` |
| 6 | `python 04_crud_operations.py` – READ section | READ 3 ($text search with score column) | `ss04c_crud_text_search.png` |
| 7 | `python 04_crud_operations.py` – READ section | READ 4 (two pagination tables) | `ss04d_crud_pagination.png` |
| 8 | `python 04_crud_operations.py` – UPDATE section | UPDATE 1 (before/after $set) + UPDATE 2 ($mul discount) | `ss04e_crud_update.png` |
| 9 | `python 04_crud_operations.py` – UPDATE section | UPDATE 6 (atomic reserve — second buyer gets None) | `ss04f_crud_atomic.png` |
| 10 | `python 04_crud_operations.py` – DELETE section | DELETE 2 (cancelled transactions purge count) | `ss04g_crud_delete.png` |
| 11 | `python 05_aggregations.py` | Aggregation 1 – Most-Traded Courses table | `ss05a_agg_courses.png` |
| 12 | `python 05_aggregations.py` | Aggregation 2 – Monthly Revenue table | `ss05b_agg_monthly.png` |
| 13 | `python 05_aggregations.py` | Aggregation 3 – Seller Leaderboard table | `ss05c_agg_leaderboard.png` |
| 14 | `python 05_aggregations.py` | Aggregation 4 – Department Discount table | `ss05d_agg_discount.png` |
| 15 | `python 05_aggregations.py` | Aggregation 5 – Transaction Details table | `ss05e_agg_txn.png` |
| 16 | `python 06_explain_demo.py` | Demo 1 – COLLSCAN vs IXSCAN comparison table | `ss06a_explain_collscan.png` |
| 17 | `python 06_explain_demo.py` | Demo 3 – Covered query (docsExamined = 0) | `ss06b_explain_covered.png` |
| 18 | `python main.py` → option 8 → option 2 | Live courseCode query result | `ss07_live_query.png` |
| 19 | MongoDB Compass | Collection list (4 collections) + students schema view | `ss08_compass_overview.png` |
| 20 | MongoDB Compass | Any document expanded (e.g., a transaction with item snapshot) | `ss09_compass_document.png` |

> **Tip:** Run `python 01_setup_validation.py && python 02_seed_data.py && python 03_create_indexes.py` before screenshots 4–18 to have a clean, reproducible state.

---
---

## PART C: 24 Likely Viva Questions & Answers

### Section 1 – Document Design & Embedding vs. Referencing

**Q1. Why did you embed the student profile instead of storing it in a separate collection?**

> The profile (phone, hostelBlock, roomNo) is accessed in every student query — always together, never independently. Embedding it means one document read fetches everything. Referencing would require a second round-trip (`$lookup`) on every profile view. The 1-to-1 relationship and always-together access pattern make embedding the correct choice here.

---

**Q2. Why are reviews referenced (separate collection) rather than embedded in the student document?**

> Reviews grow without bound. A popular seller could accumulate thousands of reviews over time. If reviews were embedded in the student document, that document would grow indefinitely and eventually hit MongoDB's 16 MB document size limit. Referencing keeps each document small, and indexing `sellerId` in the reviews collection makes the leaderboard aggregation efficient.

---

**Q3. What is the "snapshot pattern" and where did you use it?**

> The snapshot pattern copies a subset of a referenced document into the referencing document at the time of the operation. I used it in `transactions.item`: when a transaction is created, I copy the listing's `_id`, `title`, and `price` into the transaction document. If the seller later changes the price or deletes the listing, the transaction history still shows the correct price at purchase time — just like a printed receipt.

---

**Q4. When would you use `$lookup` instead of embedding?**

> Use `$lookup` (referencing) when:
> - The sub-document can grow unboundedly (e.g., reviews)
> - The data is shared by many parent documents (e.g., a student referenced by 50 listings)
> - The sub-document needs its own independent indexes and queries
> - You need to avoid update anomalies (e.g., if student name changes, updating one `students` document is enough — you don't need to update every listing)
>
> Use embedding when the data is always accessed together, has a 1-to-1 or 1-to-few relationship, and will not grow unboundedly.

---

**Q5. What is the difference between `bsonType: "int"` and `bsonType: "double"` in a schema?**

> BSON (Binary JSON) has explicit type distinctions. `int` is a 32-bit signed integer (exact); `double` is a 64-bit IEEE 754 floating-point (may have rounding errors). For prices in rupees I used `int` — all values are whole numbers, arithmetic is exact, and the `$jsonSchema` validator enforces this. In production, financial values requiring decimal precision (like ₹99.99) would use `Decimal128`, a 128-bit decimal type that avoids floating-point errors.

---

### Section 2 – Validation

**Q6. Why does validation live in the database rather than only in Python?**

> Application-layer validation (Python) can be bypassed by anyone who connects to MongoDB directly — via `mongosh`, MongoDB Compass, or a different application. Database-level validation via `$jsonSchema` is the last line of defence: it is enforced by the MongoDB server itself, regardless of the client. This is analogous to database constraints (NOT NULL, CHECK) in a relational database.

---

**Q7. What is the difference between `validationLevel: "strict"` and `"moderate"`?**

> - `"strict"`: validates **every** insert and every update, on all documents.
> - `"moderate"`: only validates updates to documents that **already satisfy** the current schema. Documents that existed before the validator was added and were invalid can still be updated without being rejected. This is weaker and allows schema drift.
>
> I chose `"strict"` for the strongest enforcement.

---

**Q8. What is the difference between `validationAction: "error"` and `"warn"`?**

> - `"error"`: rejects the write operation outright. The client receives a `WriteError`.
> - `"warn"`: allows the invalid write to proceed but logs a warning in the MongoDB server log. The client never knows.
>
> `"warn"` is useful during schema migration when you want to see what existing queries would fail without breaking production. `"error"` is used when you want strict enforcement.

---

### Section 3 – Indexes

**Q9. What is a compound index and when is it more efficient than two separate single-field indexes?**

> A compound index indexes multiple fields in a defined order, e.g., `{courseCode: 1, price: 1}`. It supports:
> 1. Queries that filter on `courseCode` alone (uses the leading key)
> 2. Queries that filter on `courseCode` AND `price` (both keys)
> 3. Sort on `price` after equality on `courseCode` — without an in-memory sort
>
> Two separate indexes on `courseCode` and `price` would require MongoDB to either scan one index and re-filter, or use an index intersection (more expensive). The compound index is the efficient choice for the pattern "books in this course under this price".

---

**Q10. What is a covered query? How did you achieve it in this project?**

> A covered query is one where the index contains all the fields needed — both for filtering and for the projection — so MongoDB can answer the query **without reading any documents from the collection**. `totalDocsExamined = 0`.
>
> In my project: `find({courseCode: "CSE101"}, {_id:0, courseCode:1, price:1})` with hint `idx_listings_course_price` produces stage `PROJECTION_COVERED → IXSCAN` because the compound index `{courseCode, price}` contains exactly the two projected fields (plus _id is excluded).

---

**Q11. What does the explain() output tell you, and what are the key fields?**

> `explain("executionStats")` shows:
> - `stage`: the query plan stage — `COLLSCAN` (no index), `IXSCAN` (index scan), `FETCH` (load full doc), `SORT` (in-memory sort needed), `TEXT_MATCH`, `PROJECTION_COVERED`
> - `totalDocsExamined`: documents read from disk — fewer is better
> - `totalKeysExamined`: index entries scanned
> - `nReturned`: documents matching the query
> - `executionTimeMillis`: wall-clock time
>
> A high `totalDocsExamined` relative to `nReturned` signals a missing or ineffective index.

---

**Q12. Why does the compound index `{buyerId: 1, createdAt: -1}` avoid an in-memory sort?**

> The index stores entries sorted by `buyerId` ascending, then `createdAt` descending. When the query is `{buyerId: X}` with `.sort({createdAt: -1})`, MongoDB can enter the index at `buyerId = X` and scan backwards through the `createdAt` entries — they are already in the correct sort order. No separate `SORT` stage is needed, avoiding a blocking in-memory sort that could use significant memory for large result sets.

---

### Section 4 – Aggregation

**Q13. In pipeline 3 (Seller Leaderboard), why do you do `$group` and `$match` BEFORE `$lookup`?**

> Because `$match` (filter reviewCount ≥ 3) can only be evaluated AFTER `$group` calculates the counts. This is the SQL `HAVING` clause equivalent. By filtering before `$lookup`, we reduce the pipeline to at most 10 documents before joining with the students collection. If we did `$lookup` first, we would join every review document with its seller — thousands of lookups — then discard most of them. Pipeline ordering directly impacts performance.

---

**Q14. What is the purpose of `$unwind` after `$lookup`?**

> `$lookup` always produces an **array** in the output field (`as`), even if there is only one matching document. `$unwind` deconstructs this array so each output document has a single embedded sub-document instead of a single-element array. Without `$unwind`, accessing `sellerInfo.name` would fail because `sellerInfo` is an array, not an object.

---

**Q15. What does `preserveNullAndEmptyArrays: true` do in `$unwind`?**

> By default, `$unwind` drops documents where the array is missing or empty. `preserveNullAndEmptyArrays: true` preserves those documents (outputting `null` for the unwound field). I use it on the listing `$unwind` in pipeline 5 because a listing may have been deleted after the transaction was created. Without this option, those transactions would silently disappear from the results.

---

### Section 5 – PyMongo & Concurrency

**Q16. What is `find_one_and_update` and why is it needed for reservation?**

> `find_one_and_update` atomically finds a document matching the filter and applies an update, returning the document before or after the update in a single server operation.
>
> For reservation: the filter includes `{status: "available"}`. If two buyers request simultaneously, MongoDB's server-side atomicity guarantees only one will find a matching document. The other receives `None` — the book is already `"reserved"`. A Python read→check→write sequence would not be atomic: between the read and the write, another buyer could change the status, creating a race condition where two buyers get the same book.

---

**Q17. What is `upsert=True` and when would you use it?**

> `upsert=True` means: if a document matching the filter exists, update it; if not, **insert** a new document combining the filter and the update. It saves a check-then-insert round-trip (two operations) and is atomic.
>
> Use cases: create-or-update counters (e.g., daily page view stats), user preferences (first visit creates, subsequent visits update), idempotent operations where you don't know if a document exists.

---

**Q18. Why did you use `db.command("explain", ..., verbosity="executionStats")` instead of `cursor.explain()`?**

> In PyMongo 4.x, `Cursor.explain()` no longer accepts a verbosity argument — it only returns the basic query plan without execution statistics. To get `executionStats` (which includes `totalDocsExamined`, `executionTimeMillis`, etc.), you must use `db.command("explain", {find:..., filter:...}, verbosity="executionStats")`. This is the correct PyMongo 4.x API and works across all MongoDB versions.

---

**Q19. How does the text index work, and what are its limitations?**

> MongoDB's text index tokenises string fields into stemmed words (e.g., "algorithms" → "algorithm"), removes stop-words (e.g., "the", "and"), and builds an inverted index. A `$text` query searches this index and returns a relevance score (`textScore`) based on term frequency and field weights.
>
> Limitations:
> - Only one text index per collection
> - Cannot combine `$text` with arbitrary sort (must sort by `textScore` or no sort)
> - Does not support fuzzy matching or synonyms (unlike Elasticsearch)
> - The index itself can be large (one entry per unique stem per document)

---

**Q20. If the data grew to 10 million listings, what changes would you make?**

> 1. **Sharding**: shard the `listings` collection on `department` (or `courseCode`) so each shard holds one department's data, distributing read load.
> 2. **Atlas Search** (Lucene-based): replace the MongoDB text index with Atlas Search for fuzzy matching, synonyms, and faceted filtering.
> 3. **`$facet` aggregation**: for the marketplace filter sidebar (count by department, condition, price range) in a single pipeline.
> 4. **TTL index** on transactions: automatically delete cancelled transactions after 90 days without a cron job — `db.transactions.createIndex({"createdAt": 1}, {expireAfterSeconds: 7776000, partialFilterExpression: {status: "cancelled"}})`.
> 5. **Read replicas**: route aggregation queries to a secondary replica to isolate analytics load from transactional queries.
> 6. **Decimal128**: migrate price fields from `int` to `Decimal128` for accurate financial arithmetic.

---

**Q21. Why does COLLSCAN sometimes show 2ms while IXSCAN takes 25ms on a 300-document collection?**

> In a development environment with only ~300 documents, the entire collection fits into MongoDB's WiredTiger RAM buffer cache.
>
> 1. **COLLSCAN overhead on tiny datasets:** A sequential sweep through 300 memory-resident documents takes negligible CPU cycles (~1–2 ms).
> 2. **IXSCAN overhead:** An index scan requires:
>    - Traversing the B-tree index structure in RAM.
>    - Reading index keys matching the condition.
>    - Performing a separate `FETCH` step to load each document from the collection by its RecordId / `_id`.
>    - At small scale, the B-tree traversal and FETCH stages introduce fixed engine overhead that can exceed a raw memory sweep.
> 3. **The deterministic metric is `totalDocsExamined`:**
>    - `COLLSCAN`: examines **302 documents** (100% of collection).
>    - `IXSCAN`: examines **6 documents** (98% reduction).
>    - At 100,000 documents, `IXSCAN` still examines only 6 documents, while `COLLSCAN` must examine 100,000 documents (costing seconds or disk I/O). In production databases, `totalDocsExamined` is the true performance indicator, not small-sample wall-clock fluctuations.

---

**Q22. What does the "Validation Playground" in your Streamlit app demonstrate?**

> The Validation Playground provides live interactive proof of **server-side schema enforcement**:
> - Each button triggers an `insert_one()` with a document crafted to violate a specific rule (e.g., negative price, review rating = 9, semester = 10, invalid condition enum like 'mint').
> - When clicked, MongoDB's `$jsonSchema` engine intercepts the write and aborts it with a `WriteError: Document failed validation`.
> - The green success alert in the UI confirms MongoDB caught and rejected the malformed data.
> - **Significance for viva:** This proves validation is enforced by MongoDB itself, not by client-side Python `if` statements. Even if an attacker or buggy script used `mongosh` or Compass directly, the database would reject the write.

---

**Q23. How is your project architecturally structured between the Streamlit UI and PyMongo?**

> We strictly adhere to the **Separation of Concerns** principle with a three-tier modular architecture:
> 1. **Data Layer (`services.py`):** Pure PyMongo functions implementing every CRUD query, transaction, aggregation pipeline, and explain runner. Functions accept database handles and parameters and return clean Python dictionaries/lists.
> 2. **Presentation Layer (`app.py`):** A 9-page Streamlit web application that contains zero database queries or business logic. It imports functions from `services.py` and renders them with modern UI components, animated cards, and responsive charts.
> 3. **CLI Layer (`main.py` & numbered scripts):** Terminal interfaces that import the same `services.py` functions for CLI testing and demonstration.
>
> Writing DB logic once in `services.py` ensures consistency and testability across both web and CLI interfaces.

---

**Q24. How does the "Register as Seller" feature enforce schema rules on insertion?**

> When a student registers on the web UI:
> 1. The input form collects personal details and embedded hostel contact information.
> 2. `services.insert_student()` calls `db.students.insert_one()`.
> 3. MongoDB's `$jsonSchema` engine immediately validates:
>    - `regNo` must match the 8-digit regex `^[0-9]{8}$`.
>    - `semester` must be an integer between 1 and 8.
>    - `phone` must match a 10-digit mobile number pattern.
>    - `department` must match one of the allowed enum values (`CSE`, `ECE`, `ME`, `Civil`, `MBA`).
> 4. MongoDB's unique indexes on `email` and `regNo` prevent duplicate registrations, throwing `DuplicateKeyError` (E11000) if violated.

---
---

## PART D: 8 "Modify This Query" Practice Exercises

Work through each exercise before your viva. Solutions are provided below each question.

---

### Exercise 1
**Task:** The seller leaderboard (Aggregation 3) currently requires at least 3 reviews. Change it to require at least 5 reviews, and show only the top 5 sellers (not 10).

**Which file / lines to change:** `05_aggregations.py` → `agg_seller_leaderboard`

**Solution:**
```python
# Change:
{"$match": {"reviewCount": {"$gte": 3}}},
{"$limit": 10},

# To:
{"$match": {"reviewCount": {"$gte": 5}}},
{"$limit": 5},
```

---

### Exercise 2
**Task:** The monthly revenue pipeline (Aggregation 2) groups by month. Change it to group by **week of the year** instead (weekly revenue).

**Solution:**
```python
# Replace $month with $week:
{"$group": {
    "_id": {
        "year": {"$year":  "$createdAt"},
        "week": {"$week":  "$createdAt"},   # ← changed from $month
    },
    "totalRevenue": {"$sum": "$item.price"},
    "totalSales":   {"$sum": 1},
}},
# And update the $project label:
"Week": {"$concat": [
    {"$toString": "$_id.year"}, "-W",
    {"$toString": "$_id.week"}
]},
```

---

### Exercise 3
**Task:** Show only sellers from **hostel block B** in the seller leaderboard (Aggregation 3). (Hint: add a `$match` on `sellerInfo.profile.hostelBlock` after the `$lookup`.)

**Solution:**
```python
# Add this stage AFTER the $unwind of sellerInfo:
{"$match": {"sellerInfo.profile.hostelBlock": "B"}},
```

---

### Exercise 4
**Task:** The pagination demo in CRUD currently shows CSE listings sorted by price ascending. Change it to show **ECE listings** sorted by **originalPrice descending** with **5 items per page**.

**Which file / lines to change:** `04_crud_operations.py` → `demo_pagination`

**Solution:**
```python
query     = {"department": "ECE", "status": "available"}   # ECE, not CSE
proj      = {"_id": 0, "title": 1, "price": 1,
             "originalPrice": 1, "condition": 1}
page_size = 5                                               # 5, not 3

# Inside the loop:
.sort("originalPrice", -1)                                  # DESC, not ASC
```

---

### Exercise 5
**Task:** Write a new aggregation that finds the **average number of days** a listing stays `"available"` before being sold. (Hint: `$match {status: "sold"}`, then `$subtract` `postedAt` from a computed soldAt, then `$avg`.)

**Solution:**
```python
pipeline = [
    {"$match": {"status": "sold"}},
    # $subtract two dates gives milliseconds; divide by ms-per-day
    {"$addFields": {
        "daysListed": {
            "$divide": [
                {"$subtract": [
                    datetime.datetime.now(datetime.timezone.utc),
                    "$postedAt"
                ]},
                1000 * 60 * 60 * 24   # ms → days
            ]
        }
    }},
    {"$group": {
        "_id":        "$department",
        "avgDaysListed": {"$avg": "$daysListed"},
        "soldCount":     {"$sum": 1},
    }},
    {"$project": {
        "_id": 0,
        "department":    "$_id",
        "avgDaysListed": {"$round": ["$avgDaysListed", 1]},
        "soldCount":     1,
    }},
    {"$sort": {"avgDaysListed": 1}},
]
```

---

### Exercise 6
**Task:** Add a `$match` stage to Aggregation 1 (Most-Traded Courses) to only count transactions where `paymentMode = "upi"`. Where exactly should this `$match` go and why?

**Solution:**
```python
# Add to the BEGINNING of the pipeline (before $lookup):
{"$match": {"status": "completed", "paymentMode": "upi"}},

# WHY at the beginning: $match early reduces the working set before the
# expensive $lookup. Adding it after $lookup would join all listings
# before filtering — wasteful.
```

---

### Exercise 7
**Task:** The find-with-operators query currently filters by `department: {$in: ["CSE", "ECE"]}`. Change it to find listings where the **price is between ₹100 and ₹300** AND **condition is NOT "poor"** (use `$ne` or `$nin`).

**Which file / lines to change:** `04_crud_operations.py` → `demo_find_with_operators`

**Solution:**
```python
cursor = db["listings"].find(
    {
        "price":     {"$gte": 100, "$lte": 300},
        "condition": {"$nin": ["poor"]},    # $nin: not in list
        "status":    "available",
    },
    projection={"_id": 0, "title": 1, "courseCode": 1,
                "price": 1, "condition": 1, "department": 1},
).sort("price", 1).limit(8)
```

---

### Exercise 8
**Task:** Add a **new aggregation** that answers: "How many listings are in each condition (`new`, `good`, `fair`, `poor`) per department?" Output should have columns: Department, Condition, Count, Avg Price.

**Solution:**
```python
pipeline = [
    {"$group": {
        "_id": {
            "department": "$department",
            "condition":  "$condition",
        },
        "count":    {"$sum": 1},
        "avgPrice": {"$avg": "$price"},
    }},
    {"$project": {
        "_id":        0,
        "Department": "$_id.department",
        "Condition":  "$_id.condition",
        "Count":      "$count",
        "Avg Price (₹)": {"$round": ["$avgPrice", 0]},
    }},
    {"$sort": {"Department": 1, "Condition": 1}},
]
results = list(db["listings"].aggregate(pipeline))
print(tabulate(results, headers="keys", tablefmt="rounded_outline"))
```

---
