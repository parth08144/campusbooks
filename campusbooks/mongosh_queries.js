/**
 * mongosh_queries.js – CampusBooks
 * ====================================
 * All key queries in MongoDB Shell (mongosh) syntax.
 * Run in mongosh: mongosh campusbooks mongosh_queries.js
 * Or paste individual sections interactively.
 *
 * Sections:
 *   A. Validation & Schema
 *   B. CRUD operations
 *   C. Aggregation pipelines
 *   D. Index management
 *   E. Explain / query analysis
 */

// ─────────────────────────────────────────────────────────────────
// Setup: select the database
// ─────────────────────────────────────────────────────────────────
use("campusbooks");
print("\n✅  Switched to campusbooks database\n");

// ══════════════════════════════════════════════════════════════════
// A. VALIDATION & SCHEMA
// ══════════════════════════════════════════════════════════════════

print("═".repeat(60));
print("  A. VALIDATION DEMO");
print("═".repeat(60));

// A1. Show collection validator for students
print("\n── A1: students collection validator ──");
const studentsInfo = db.getCollectionInfos({ name: "students" });
printjson(studentsInfo[0].options.validator);

// A2. Attempt to insert a student with semester = 10 (should fail)
print("\n── A2: Invalid insert – semester = 10 (max is 8) ──");
try {
  db.students.insertOne({
    name:       "Bad Student",
    email:      "bad@univ.edu",
    regNo:      "12345678",
    department: "CSE",
    semester:   10,          // ❌ violates maximum: 8
    profile: { phone: "9876543210", hostelBlock: "A", roomNo: "101" },
    createdAt:  new Date(),
  });
  print("❌ Accepted – validator not working!");
} catch (e) {
  print("✅  Rejected as expected: " + e.message);
}

// A3. Attempt duplicate email (unique index)
print("\n── A3: Duplicate email (should fail with E11000) ──");
try {
  db.students.insertOne({
    name:       "Clone",
    email:      "arjun.sharma@university.edu",   // already in DB from 01_setup
    regNo:      "99999999",
    department: "ECE",
    semester:   3,
    profile: { phone: "9812345679", hostelBlock: "B", roomNo: "200" },
    createdAt:  new Date(),
  });
  print("❌ Accepted – unique index not working!");
} catch (e) {
  print("✅  DuplicateKeyError: " + e.message);
}

// ══════════════════════════════════════════════════════════════════
// B. CRUD OPERATIONS
// ══════════════════════════════════════════════════════════════════

print("\n" + "═".repeat(60));
print("  B. CRUD OPERATIONS");
print("═".repeat(60));

// ── B1. CREATE ─────────────────────────────────────────────────────

// WHY insert_one: new student registration
print("\n── B1: insertOne (new student) ──");
const newStudent = {
  name:       "Ravi Kumar (mongosh demo)",
  email:      "ravi.mongosh@university.edu",
  regNo:      "20240200",
  department: "ECE",
  semester:   4,
  profile: { phone: "9876500001", hostelBlock: "D", roomNo: "401" },
  createdAt:  new Date(),
};
const insertResult = db.students.insertOne(newStudent);
print("Inserted _id: " + insertResult.insertedId);
const RAVI_ID = insertResult.insertedId;

// WHY insert_many: bulk listing upload
print("\n── B2: insertMany (2 listings) ──");
const listingResult = db.listings.insertMany([
  {
    title:         "Signals and Systems",
    isbn:          "978-0138147570",
    authors:       ["Alan Oppenheim"],
    courseCode:    "ECE201",
    department:    "ECE",
    condition:     "good",
    originalPrice: 600,
    price:         350,
    tags:          ["signals", "systems"],
    status:        "available",
    sellerId:      RAVI_ID,
    postedAt:      new Date(),
  },
  {
    title:         "Digital Signal Processing",
    isbn:          "978-0131873742",
    authors:       ["John G. Proakis"],
    courseCode:    "ECE301",
    department:    "ECE",
    condition:     "fair",
    originalPrice: 500,
    price:         200,
    tags:          ["dsp", "signals"],
    status:        "available",
    sellerId:      RAVI_ID,
    postedAt:      new Date(),
  },
]);
print("Inserted " + listingResult.insertedIds.length + " listings");
const LISTING_ID = listingResult.insertedIds[0];

// ── B2. READ ───────────────────────────────────────────────────────

// WHY find_one with projection: fetch only needed fields
print("\n── B3: findOne (student by email, projection) ──");
printjson(
  db.students.findOne(
    { email: "ravi.mongosh@university.edu" },
    { _id: 0, name: 1, department: 1, semester: 1, "profile.hostelBlock": 1 }
  )
);

// WHY $gte/$lte/$in/$regex: common marketplace filter
print("\n── B4: find with $gte/$lte/$in/$regex + sort + limit ──");
db.listings.find(
  {
    price:      { $gte: 200, $lte: 500 },
    department: { $in: ["CSE", "ECE"] },
    status:     "available",
    title:      { $regex: "Algorithm|System|Data", $options: "i" },
  },
  { _id: 0, title: 1, courseCode: 1, price: 1, condition: 1 }
).sort({ price: 1 }).limit(5).forEach(printjson);

// WHY $text: full-text search on title+tags
print("\n── B5: $text search ('algorithms database') ──");
db.listings.find(
  { $text: { $search: "algorithms database" } },
  { _id: 0, title: 1, price: 1, score: { $meta: "textScore" } }
).sort({ score: { $meta: "textScore" } }).limit(5).forEach(printjson);

// WHY count_documents: dashboard stats
print("\n── B6: count_documents per department ──");
["CSE", "ECE", "ME", "Civil", "MBA"].forEach((dept) => {
  const n = db.listings.countDocuments({ department: dept, status: "available" });
  print("  " + dept + ": " + n + " available");
});

// WHY skip/limit: pagination
print("\n── B7: Pagination – Page 1 and Page 2 of CSE listings ──");
[0, 3].forEach((skip, i) => {
  print("  Page " + (i + 1) + ":");
  db.listings.find(
    { department: "CSE", status: "available" },
    { _id: 0, title: 1, price: 1, condition: 1 }
  ).sort({ price: 1 }).skip(skip).limit(3).forEach(printjson);
});

// ── B3. UPDATE ─────────────────────────────────────────────────────

// WHY $set: update only specified fields, leave others untouched
print("\n── B8: updateOne with $set (move Ravi to block E) ──");
db.students.updateOne(
  { _id: RAVI_ID },
  { $set: { "profile.hostelBlock": "E", "profile.roomNo": "501" } }
);
printjson(
  db.students.findOne({ _id: RAVI_ID }, { _id: 0, name: 1, profile: 1 })
);

// WHY pipeline update instead of $mul: $mul produces a double which violates
// the bsonType:int validator. Pipeline update with $toInt keeps price as int32.
print("\n── B9: updateMany pipeline update (10% off poor listings > 60 days old) ──");
const sixtyDaysAgo = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000);
const mulResult = db.listings.updateMany(
  { condition: "poor", status: "available", postedAt: { $lte: sixtyDaysAgo } },
  [{ $set: { price: { $toInt: { $multiply: ["$price", 0.9] } } } }]
);
print("Modified: " + mulResult.modifiedCount);


// WHY $push/$pull: atomic array manipulation
print("\n── B10: $push and $pull on tags array ──");
db.listings.updateOne({ _id: LISTING_ID }, { $push: { tags: "exam-prep" } });
printjson(db.listings.findOne({ _id: LISTING_ID }, { _id: 0, title: 1, tags: 1 }));
db.listings.updateOne({ _id: LISTING_ID }, { $pull: { tags: "exam-prep" } });
printjson(db.listings.findOne({ _id: LISTING_ID }, { _id: 0, title: 1, tags: 1 }));

// WHY $inc: atomic counter increment
print("\n── B11: $inc (increment viewCount) ──");
db.listings.updateOne(
  { _id: LISTING_ID },
  { $inc: { viewCount: 1 } },
  { upsert: true }
);
printjson(db.listings.findOne({ _id: LISTING_ID }, { _id: 0, title: 1, viewCount: 1 }));

// WHY findOneAndUpdate for reservation: atomic compare-and-swap
print("\n── B12: findOneAndUpdate – atomic reservation ──");
const reserved = db.listings.findOneAndUpdate(
  { _id: LISTING_ID, status: "available" },   // filter: must be available
  { $set: { status: "reserved", reservedAt: new Date() } },
  { returnDocument: "after", projection: { _id: 0, title: 1, status: 1 } }
);
printjson(reserved);

// Try to reserve again – should return null
const reservedAgain = db.listings.findOneAndUpdate(
  { _id: LISTING_ID, status: "available" },   // already reserved → no match
  { $set: { status: "reserved" } },
  { returnDocument: "after" }
);
print("Second reservation attempt result: " + reservedAgain);   // null

// ── B4. DELETE ─────────────────────────────────────────────────────

// WHY deleteOne: seller removes a single listing
print("\n── B13: deleteOne (Ravi's first listing) ──");
const delOne = db.listings.deleteOne({ _id: LISTING_ID });
print("Deleted: " + delOne.deletedCount);

// WHY deleteMany: purge old cancelled transactions (scheduled cleanup)
print("\n── B14: deleteMany (cancelled transactions older than 90 days) ──");
const ninetyDaysAgo = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);
const delMany = db.transactions.deleteMany({
  status:    "cancelled",
  createdAt: { $lte: ninetyDaysAgo },
});
print("Deleted: " + delMany.deletedCount + " old cancelled transactions");

// ══════════════════════════════════════════════════════════════════
// C. AGGREGATION PIPELINES
// ══════════════════════════════════════════════════════════════════

print("\n" + "═".repeat(60));
print("  C. AGGREGATION PIPELINES");
print("═".repeat(60));

// C1. Most-Traded Courses
print("\n── C1: Most-Traded Courses ──");
db.transactions.aggregate([
  { $match:  { status: "completed" } },
  { $lookup: { from: "listings", localField: "item.listingId",
               foreignField: "_id", as: "listingInfo" } },
  { $unwind: "$listingInfo" },
  { $group:  { _id: "$listingInfo.courseCode",
               totalSales: { $sum: 1 },
               totalRevenue: { $sum: "$item.price" } } },
  { $sort:   { totalSales: -1 } },
  { $limit:  8 },
  { $project: { _id: 0, courseCode: "$_id", totalSales: 1, totalRevenue: 1 } },
]).forEach(printjson);

// C2. Monthly Revenue
print("\n── C2: Monthly Revenue ──");
db.transactions.aggregate([
  { $match: { status: "completed" } },
  { $group: {
      _id: { year: { $year: "$createdAt" }, month: { $month: "$createdAt" } },
      totalRevenue: { $sum: "$item.price" },
      totalSales:   { $sum: 1 },
  }},
  { $sort: { "_id.year": 1, "_id.month": 1 } },
  { $project: {
      _id: 0,
      month:        { $concat: [{ $toString: "$_id.year" }, "-", { $toString: "$_id.month" }] },
      totalRevenue: 1,
      totalSales:   1,
  }},
]).forEach(printjson);

// C3. Seller Leaderboard (min 3 reviews)
print("\n── C3: Seller Leaderboard ──");
db.reviews.aggregate([
  { $group:  { _id: "$sellerId", avgRating: { $avg: "$rating" },
               reviewCount: { $sum: 1 } } },
  { $match:  { reviewCount: { $gte: 3 } } },
  { $sort:   { avgRating: -1 } },
  { $limit:  10 },
  { $lookup: { from: "students", localField: "_id",
               foreignField: "_id", as: "sellerInfo" } },
  { $unwind: { path: "$sellerInfo", preserveNullAndEmptyArrays: true } },
  { $project: { _id: 0,
                seller:      { $ifNull: ["$sellerInfo.name", "Unknown"] },
                department:  { $ifNull: ["$sellerInfo.department", "—"] },
                avgRating:   { $round: ["$avgRating", 2] },
                reviewCount: 1 } },
]).forEach(printjson);

// C4. Department-wise Average Discount %
print("\n── C4: Department-wise Average Discount % ──");
db.listings.aggregate([
  { $match: { originalPrice: { $gt: 0 } } },
  { $group: {
      _id: "$department",
      avgDiscountPct: { $avg: {
        $multiply: [
          { $divide: [{ $subtract: ["$originalPrice", "$price"] }, "$originalPrice"] },
          100
        ]
      }},
      listingCount: { $sum: 1 },
  }},
  { $project: { _id: 0,
                department:     "$_id",
                avgDiscountPct: { $round: ["$avgDiscountPct", 2] },
                listingCount:   1 } },
  { $sort: { avgDiscountPct: -1 } },
]).forEach(printjson);

// C5. Full Transaction Details
print("\n── C5: Full Transaction Details (10 completed) ──");
db.transactions.aggregate([
  { $match:  { status: "completed" } },
  { $lookup: { from: "students", localField: "buyerId",
               foreignField: "_id", as: "buyer" } },
  { $unwind: "$buyer" },
  { $lookup: { from: "students", localField: "sellerId",
               foreignField: "_id", as: "seller" } },
  { $unwind: "$seller" },
  { $lookup: { from: "listings", localField: "item.listingId",
               foreignField: "_id", as: "listing" } },
  { $unwind: { path: "$listing", preserveNullAndEmptyArrays: true } },
  { $project: {
      _id:         0,
      date:        { $dateToString: { format: "%Y-%m-%d", date: "$createdAt" } },
      buyer:       "$buyer.name",
      seller:      "$seller.name",
      book:        "$item.title",
      course:      { $ifNull: ["$listing.courseCode", "—"] },
      price:       "$item.price",
      paymentMode: 1,
  }},
  { $limit: 10 },
]).forEach(printjson);

// ══════════════════════════════════════════════════════════════════
// D. INDEX MANAGEMENT
// ══════════════════════════════════════════════════════════════════

print("\n" + "═".repeat(60));
print("  D. INDEX MANAGEMENT");
print("═".repeat(60));

print("\n── D1: List all indexes on listings ──");
db.listings.getIndexes().forEach((idx) => {
  print("  " + idx.name + " → " + JSON.stringify(idx.key));
});

print("\n── D2: List all indexes on transactions ──");
db.transactions.getIndexes().forEach((idx) => {
  print("  " + idx.name + " → " + JSON.stringify(idx.key));
});

// ══════════════════════════════════════════════════════════════════
// E. EXPLAIN / QUERY ANALYSIS
// ══════════════════════════════════════════════════════════════════

print("\n" + "═".repeat(60));
print("  E. EXPLAIN – INDEX vs COLLSCAN");
print("═".repeat(60));

// E1. Force COLLSCAN then IXSCAN – compare
print("\n── E1: COLLSCAN (no index hint) ──");
const collscanStats = db.listings.find(
  { courseCode: "CSE494", price: { $lt: 500 } }
).hint({ $natural: 1 }).explain("executionStats").executionStats;
print("  Stage:              " + collscanStats.executionStages.stage);
print("  totalDocsExamined:  " + collscanStats.totalDocsExamined);
print("  nReturned:          " + collscanStats.nReturned);
print("  executionTimeMillis:" + collscanStats.executionTimeMillis);

print("\n── E2: IXSCAN (compound index hint) ──");
const ixscanStats = db.listings.find(
  { courseCode: "CSE494", price: { $lt: 500 } }
).hint("idx_listings_course_price").explain("executionStats").executionStats;
print("  Stage:              " + ixscanStats.executionStages.stage);
print("  totalDocsExamined:  " + ixscanStats.totalDocsExamined);
print("  nReturned:          " + ixscanStats.nReturned);
print("  executionTimeMillis:" + ixscanStats.executionTimeMillis);

// E3. Covered query
print("\n── E3: Covered query (project only indexed fields) ──");
const coveredPlan = db.listings.find(
  { courseCode: "CSE101" },
  { _id: 0, courseCode: 1, price: 1 }
).hint("idx_listings_course_price").explain("executionStats");
print("  Winning plan stages:");
printjson(coveredPlan.queryPlanner.winningPlan);

print("\n✅  mongosh_queries.js complete\n");
