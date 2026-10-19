# CampusBooks – Second-Hand Textbook Marketplace
### CSE494 | Intelligent NoSQL Databases | Individual Project

---

## Project Overview
CampusBooks is a MongoDB-backed marketplace where senior students list
used textbooks by course code and junior students purchase them at a
discount. The system demonstrates document design, schema validation,
indexes, CRUD operations, and aggregation pipelines.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| MongoDB Community | 7.x (local) |
| mongosh | any recent |

---

## Setup Instructions (run in this exact order)

### 1. Install Python dependencies
```bash
cd campusbooks
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env if you want to use Atlas instead of localhost
```

### 3. Start MongoDB (if not already running)
```bash
# macOS (Homebrew)
brew services start mongodb-community

# Linux (systemd)
sudo systemctl start mongod

# Windows
net start MongoDB
```

### 4. Verify connection
```bash
python config.py
# Expected: ✅  Connected to MongoDB | URI: mongodb://localhost:27017 | DB: campusbooks
```

### 5. Create collections + validators + invalid-insert demo
```bash
python 01_setup_validation.py
```
**Screenshot now:** capture the 7 validation error messages.

### 6. Seed realistic data
```bash
python 02_seed_data.py
```
**Expected output:**
```
✅  Inserted 50 students
✅  Inserted 300 listings
✅  Inserted 200 transactions
✅  Inserted 150 reviews
```

### 7. Create indexes
```bash
python 03_create_indexes.py
```
**Screenshot now:** capture the index summary table.

### 8. Run CRUD operations demo
```bash
python 04_crud_operations.py
```

### 9. Run aggregation pipelines
```bash
python 05_aggregations.py
```
**Screenshot each of the 5 aggregation outputs.**

### 10. Run explain() demo
```bash
python 06_explain_demo.py
```
**Screenshot:** the COLLSCAN vs IXSCAN comparison table.

### 11. Interactive Web Application (Streamlit)
```bash
streamlit run app.py
```
Open `http://localhost:8502` to access the production-grade Web UI:
- **📊 Dashboard:** Aggregation analytics, animated stat cards, bar & line charts
- **🔍 Browse Listings:** Multi-field filtering (department, condition, price range) + `$text` search
- **📝 Post a Listing:** Interactive listing creation validated server-side
- **🧑‍💼 Register as Seller:** Student account onboarding with live `$jsonSchema` validation checks
- **🛒 Buy a Book:** Atomic CAS purchase demonstration (`find_one_and_update`)
- **👤 Seller Profile:** Active listings, sold inventory, customer reviews & rating
- **🧪 Validation Playground:** Interactive server-side `$jsonSchema` rejection trigger buttons
- **⚡ Explain Viewer:** Visual side-by-side comparison of COLLSCAN vs IXSCAN with docsExamined reduction
- **🖥️ Query Console:** Ad-hoc JSON query runner with schema presets

### 12. CLI Menu-Driven Demo
```bash
python main.py
```

### 13. mongosh queries (run in MongoDB shell)
```bash
mongosh < mongosh_queries.js
# Or paste individual sections into mongosh interactively
```

---

## File Structure
```
campusbooks/
├── config.py                 # DB connection helper & client pooling
├── services.py               # Reusable PyMongo service layer (Single Source of Truth)
├── app.py                    # Production-grade 9-page Streamlit web app
├── 01_setup_validation.py    # Collections, $jsonSchema, invalid-insert demo
├── 02_seed_data.py           # 50/300/200/150 realistic seed documents
├── 03_create_indexes.py      # All 11 indexes (compound, unique, text)
├── 04_crud_operations.py     # 12 CRUD demos with WHY comments
├── 05_aggregations.py        # 5 aggregation pipelines
├── 06_explain_demo.py        # COLLSCAN vs IXSCAN explain demo
├── main.py                   # Menu-driven CLI for terminal demo
├── mongosh_queries.js        # Same queries in mongosh syntax
├── requirements.txt
├── .env.example
├── .env                      # (not committed to git)
└── report/
    ├── REPORT.md             # Full project report (CSE494 grading criteria)
    └── VIVA_PREP.md          # 9-slide outline + 25 viva Q&As + live query cheatsheet
```

---

## Re-running from scratch
Each run of `01_setup_validation.py` **drops and re-creates** all collections,
so you can reset the database at any time:
```bash
python 01_setup_validation.py && python 02_seed_data.py && python 03_create_indexes.py
```

---

## Notes for viva
- **Separation of Concerns:** `services.py` contains all database operations (pure PyMongo returning Python dicts/lists). Both `main.py` (CLI) and `app.py` (Streamlit) consume this layer.
- **Validation in DB:** Validation is not just frontend JavaScript or Python if-statements — it is enforced at the MongoDB server level via `$jsonSchema`.
- **Deterministic Index Metric:** Focus on `totalDocsExamined` (302 vs 6) rather than milliseconds for small datasets, as in-memory RAM caching makes scans fast on small collections while index B-tree traversal has fixed overhead.
- All query functions have `WHY:` docstrings explaining design decisions.
- `mongosh_queries.js` contains the same queries in shell syntax for examiner demonstration.
