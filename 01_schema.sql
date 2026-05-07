-- ============================================================
--  MedCart Intelligence Platform — Database Schema
--  SQLite compatible
-- ============================================================

PRAGMA foreign_keys = ON;

-- ── 1. SUPPLIERS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    city          TEXT    NOT NULL,
    state         TEXT    NOT NULL,
    phone         TEXT,
    email         TEXT,
    rating        REAL    DEFAULT 4.0,
    created_at    TEXT    DEFAULT (date('now'))
);

-- ── 2. DRUGS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drugs (
    drug_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    brand         TEXT,
    category      TEXT    NOT NULL,
    form          TEXT    NOT NULL,   -- Tablet / Syrup / Injection / Cream
    unit_price    REAL    NOT NULL,
    supplier_id   INTEGER REFERENCES suppliers(supplier_id),
    requires_rx   INTEGER DEFAULT 0,  -- 1 = prescription required
    shelf_life_days INTEGER DEFAULT 730
);

-- ── 3. INVENTORY ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id       INTEGER REFERENCES drugs(drug_id),
    stock_qty     INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 50,
    batch_no      TEXT,
    manufacture_date TEXT,
    expiry_date   TEXT,
    last_updated  TEXT    DEFAULT (datetime('now'))
);

-- ── 4. PATIENTS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    patient_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    age           INTEGER,
    gender        TEXT,
    city          TEXT,
    state         TEXT,
    phone         TEXT,
    is_chronic    INTEGER DEFAULT 0,   -- 1 = chronic patient
    registered_at TEXT    DEFAULT (date('now'))
);

-- ── 5. ORDERS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER REFERENCES patients(patient_id),
    order_date    TEXT    NOT NULL,
    status        TEXT    DEFAULT 'completed',
    channel       TEXT    DEFAULT 'online',   -- online / walk-in
    total_amount  REAL    DEFAULT 0,
    discount      REAL    DEFAULT 0,
    payment_mode  TEXT    DEFAULT 'UPI'
);

-- ── 6. ORDER ITEMS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER REFERENCES orders(order_id),
    drug_id       INTEGER REFERENCES drugs(drug_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL    NOT NULL,
    line_total    REAL    GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- ── 7. PRESCRIPTIONS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prescriptions (
    rx_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER REFERENCES patients(patient_id),
    order_id      INTEGER REFERENCES orders(order_id),
    doctor_name   TEXT,
    issued_date   TEXT,
    valid_days    INTEGER DEFAULT 30
);

-- ════════════════════════════════════════════════════════════
--  ANALYTICAL VIEWS
-- ════════════════════════════════════════════════════════════

-- Daily revenue view
CREATE VIEW IF NOT EXISTS v_daily_revenue AS
SELECT
    o.order_date,
    COUNT(DISTINCT o.order_id)    AS total_orders,
    SUM(o.total_amount)           AS revenue,
    AVG(o.total_amount)           AS avg_order_value
FROM orders o
WHERE o.status = 'completed'
GROUP BY o.order_date;

-- Inventory risk view
CREATE VIEW IF NOT EXISTS v_inventory_risk AS
SELECT
    d.drug_id,
    d.name          AS drug_name,
    d.category,
    i.stock_qty,
    i.reorder_level,
    i.expiry_date,
    CASE
        WHEN i.stock_qty <= 0                                          THEN 'Out of Stock'
        WHEN i.stock_qty < i.reorder_level                            THEN 'Low Stock'
        WHEN julianday(i.expiry_date) - julianday('now') <= 90        THEN 'Near Expiry'
        ELSE 'Healthy'
    END AS risk_status,
    ROUND(julianday(i.expiry_date) - julianday('now'), 0) AS days_to_expiry
FROM drugs d
JOIN inventory i ON d.drug_id = i.drug_id;

-- RFM patient segmentation view
CREATE VIEW IF NOT EXISTS v_rfm AS
SELECT
    p.patient_id,
    p.name,
    p.is_chronic,
    COUNT(DISTINCT o.order_id)                              AS frequency,
    ROUND(SUM(o.total_amount), 2)                          AS monetary,
    ROUND(julianday('now') - julianday(MAX(o.order_date)), 0) AS recency_days
FROM patients p
JOIN orders o ON p.patient_id = o.patient_id
WHERE o.status = 'completed'
GROUP BY p.patient_id;

-- Drug sales summary view
CREATE VIEW IF NOT EXISTS v_drug_sales AS
SELECT
    d.drug_id,
    d.name      AS drug_name,
    d.category,
    d.form,
    SUM(oi.quantity)                AS total_qty_sold,
    ROUND(SUM(oi.line_total), 2)   AS total_revenue,
    COUNT(DISTINCT oi.order_id)    AS orders_count
FROM drugs d
JOIN order_items oi ON d.drug_id = oi.drug_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY d.drug_id;
