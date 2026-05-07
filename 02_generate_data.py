"""
MedCart Intelligence Platform — Data Generator
================================================
Generates realistic synthetic pharmacy / health-retail data for India.
Creates SQLite DB + 11 CSV exports ready for Power BI / Tableau.

Usage (from project root):
    python sql/02_generate_data.py
"""

import os
import sys
import sqlite3
import random
import csv
from datetime import date, timedelta
import math

# ── Paths ──────────────────────────────────────────────────────────────────────
# Always resolve relative to THIS script file — works regardless of cwd
THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(THIS_DIR)          # project root
DATA_DIR   = os.path.join(ROOT_DIR, 'data')
DB_PATH    = os.path.join(DATA_DIR, 'medcart.db')
SCHEMA_PATH = os.path.join(THIS_DIR, '01_schema.sql')

def ensure_dirs():
    """Create required directories if missing."""
    for d in [DATA_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)
    # Remove stale DB so we always start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

# ── Seed data ─────────────────────────────────────────────────────────────────
INDIAN_FIRST = [
    'Aarav','Aditi','Akash','Amit','Amrita','Ananya','Anil','Anjali','Arjun',
    'Asha','Bhavna','Deepak','Deepika','Dinesh','Divya','Farhan','Geeta','Gopal',
    'Harsha','Heena','Ishaan','Jaya','Karan','Kavita','Lalit','Lata','Mahesh',
    'Manisha','Mohan','Naina','Neha','Nikhil','Pankaj','Pooja','Pradeep','Priya',
    'Rahul','Rajan','Rakesh','Ramesh','Rani','Ravi','Rekha','Rita','Rohit',
    'Sandeep','Sanjay','Sara','Seema','Shivam','Shreya','Sita','Sneha','Suresh',
    'Swati','Tanvi','Usha','Varun','Vijay','Vikram','Vinod','Yash','Zara',
    'Alok','Bina','Chetan','Disha','Ekta','Faisal','Gaurav','Hina','Isha',
]
INDIAN_LAST = [
    'Sharma','Verma','Singh','Gupta','Patel','Kumar','Joshi','Rao','Nair',
    'Mehta','Shah','Pandey','Dubey','Mishra','Tiwari','Agarwal','Bhat','Chauhan',
    'Desai','Iyer','Kapoor','Malhotra','Pillai','Reddy','Saxena','Yadav',
    'Bose','Chaudhary','Das','Ghosh','Jain','Kaur','Menon','Naidu','Patil',
    'Rathore','Sinha','Thakur','Trivedi','Walia',
]
CITIES_STATES = [
    ('Mumbai','Maharashtra'),('Delhi','Delhi'),('Bengaluru','Karnataka'),
    ('Hyderabad','Telangana'),('Chennai','Tamil Nadu'),('Pune','Maharashtra'),
    ('Jaipur','Rajasthan'),('Kolkata','West Bengal'),('Ahmedabad','Gujarat'),
    ('Lucknow','Uttar Pradesh'),('Nagpur','Maharashtra'),('Indore','Madhya Pradesh'),
    ('Bhopal','Madhya Pradesh'),('Chandigarh','Punjab'),('Kochi','Kerala'),
    ('Coimbatore','Tamil Nadu'),('Surat','Gujarat'),('Vadodara','Gujarat'),
    ('Patna','Bihar'),('Bhubaneswar','Odisha'),
]
SUPPLIERS = [
    ('Sun Pharma Distributors','Mumbai','Maharashtra',4.7),
    ('Cipla Supply Chain','Pune','Maharashtra',4.5),
    ('Dr Reddy Wholesale','Hyderabad','Telangana',4.6),
    ('Lupin Pharma Dist','Nagpur','Maharashtra',4.3),
    ('Alkem Med Supplies','Mumbai','Maharashtra',4.4),
    ('Zydus Distributors','Ahmedabad','Gujarat',4.5),
    ('Abbott India Dist','Delhi','Delhi',4.8),
    ('Mankind Pharma Dist','Jaipur','Rajasthan',4.2),
    ('Glenmark Wholesale','Mumbai','Maharashtra',4.4),
    ('Torrent Pharma Dist','Ahmedabad','Gujarat',4.6),
    ('Wockhardt Supplies','Mumbai','Maharashtra',4.3),
    ('Cadila Healthcare','Ahmedabad','Gujarat',4.5),
    ('Ipca Labs Wholesale','Bengaluru','Karnataka',4.4),
    ('Emcure Distributors','Pune','Maharashtra',4.2),
    ('Intas Pharma Dist','Ahmedabad','Gujarat',4.5),
]
DRUGS = [
    # (name, brand, category, form, unit_price, requires_rx, shelf_life_days)
    ('Paracetamol 500mg','Crocin','Analgesics','Tablet',12,'N',730),
    ('Amoxicillin 500mg','Mox','Antibiotics','Capsule',85,'Y',365),
    ('Metformin 500mg','Glucophage','Diabetes','Tablet',28,'Y',730),
    ('Atorvastatin 10mg','Lipitor','Cardiac','Tablet',45,'Y',730),
    ('Amlodipine 5mg','Norvasc','Cardiac','Tablet',38,'Y',730),
    ('Omeprazole 20mg','Omez','Gastro','Capsule',22,'N',730),
    ('Cetirizine 10mg','Allegra','Allergy','Tablet',15,'N',730),
    ('Azithromycin 500mg','Zithromax','Antibiotics','Tablet',120,'Y',365),
    ('Losartan 50mg','Cozaar','Cardiac','Tablet',55,'Y',730),
    ('Aspirin 75mg','Ecosprin','Cardiac','Tablet',18,'N',730),
    ('Metoprolol 25mg','Betaloc','Cardiac','Tablet',42,'Y',730),
    ('Glimepiride 2mg','Amaryl','Diabetes','Tablet',65,'Y',730),
    ('Telmisartan 40mg','Telmikind','Cardiac','Tablet',48,'Y',730),
    ('Pantoprazole 40mg','Pantodac','Gastro','Tablet',35,'N',730),
    ('Montelukast 10mg','Montair','Respiratory','Tablet',52,'Y',730),
    ('Insulin Glargine','Lantus','Diabetes','Injection',380,'Y',365),
    ('Salbutamol Inhaler','Asthalin','Respiratory','Inhaler',145,'Y',730),
    ('Clopidogrel 75mg','Plavix','Cardiac','Tablet',72,'Y',730),
    ('Ibuprofen 400mg','Brufen','Analgesics','Tablet',18,'N',730),
    ('Dolo 650mg','Dolo','Analgesics','Tablet',14,'N',730),
    ('Vitamin D3 60K','Calcirol','Supplements','Capsule',85,'N',730),
    ('Multivitamin','Supradyn','Supplements','Tablet',220,'N',730),
    ('Calcium + D3','Shelcal','Supplements','Tablet',95,'N',730),
    ('Ranitidine 150mg','Aciloc','Gastro','Tablet',20,'N',730),
    ('Dicyclomine 20mg','Cyclopam','Gastro','Tablet',28,'N',730),
    ('Levocetirizine 5mg','Levocet','Allergy','Tablet',18,'N',730),
    ('Fexofenadine 120mg','Allegra','Allergy','Tablet',22,'N',730),
    ('Methylprednisolone 4mg','Medrol','Steroids','Tablet',62,'Y',365),
    ('Dexamethasone 0.5mg','Decadron','Steroids','Tablet',35,'Y',365),
    ('Amikacin 500mg','Amicin','Antibiotics','Injection',95,'Y',365),
    ('Ceftriaxone 1g','Monocef','Antibiotics','Injection',180,'Y',365),
    ('Metronidazole 400mg','Flagyl','Antibiotics','Tablet',18,'Y',365),
    ('Ciprofloxacin 500mg','Cipro','Antibiotics','Tablet',45,'Y',365),
    ('Enalapril 5mg','Vasotec','Cardiac','Tablet',32,'Y',730),
    ('Furosemide 40mg','Lasix','Cardiac','Tablet',15,'Y',730),
    ('Spironolactone 25mg','Aldactone','Cardiac','Tablet',28,'Y',730),
    ('Thyronorm 50mcg','Thyronorm','Hormones','Tablet',55,'Y',730),
    ('Thyronorm 100mcg','Thyronorm','Hormones','Tablet',72,'Y',730),
    ('Clonazepam 0.5mg','Rivotril','Neuro','Tablet',32,'Y',180),
    ('Alprazolam 0.25mg','Alprax','Neuro','Tablet',18,'Y',180),
    ('Escitalopram 10mg','Nexito','Neuro','Tablet',48,'Y',730),
    ('Sertraline 50mg','Zoloft','Neuro','Tablet',65,'Y',730),
    ('Pregabalin 75mg','Lyrica','Neuro','Capsule',88,'Y',730),
    ('Gabapentin 300mg','Neurontin','Neuro','Capsule',72,'Y',730),
    ('Clobetasol Cream','Tenovate','Derma','Cream',68,'N',730),
    ('Betamethasone Cream','Betnovate','Derma','Cream',55,'N',730),
    ('Clotrimazole 1%','Candid','Derma','Cream',45,'N',730),
    ('Mupirocin 2%','Bactroban','Derma','Cream',95,'N',365),
    ('Ondansetron 4mg','Emeset','Gastro','Tablet',25,'N',730),
    ('Domperidone 10mg','Domstal','Gastro','Tablet',15,'N',730),
    ('Rabeprazole 20mg','Rablet','Gastro','Tablet',38,'N',730),
    ('Drotaverine 80mg','No-Spa','Gastro','Tablet',22,'N',730),
    ('Tramadol 50mg','Ultram','Analgesics','Capsule',42,'Y',730),
    ('Diclofenac 50mg','Voveran','Analgesics','Tablet',22,'N',730),
    ('Naproxen 500mg','Naprosyn','Analgesics','Tablet',30,'N',730),
]
PAYMENT_MODES = ['UPI','Cash','Card','Net Banking','EMI']
CHANNELS = ['online','online','online','walk-in','walk-in']
ORDER_STATUS = ['completed','completed','completed','completed','cancelled']
DOCTORS = [
    'Dr. Anand Sharma','Dr. Priya Menon','Dr. Rajesh Gupta','Dr. Sunita Rao',
    'Dr. Vikram Patel','Dr. Meera Iyer','Dr. Suresh Kumar','Dr. Kavita Singh',
    'Dr. Ravi Verma','Dr. Anjali Nair',
]

def random_name():
    return f"{random.choice(INDIAN_FIRST)} {random.choice(INDIAN_LAST)}"

def random_phone():
    return f"+91 {random.randint(70000,99999)}{random.randint(10000,99999)}"

def random_date(start_date, end_date):
    delta = (end_date - start_date).days
    return start_date + timedelta(days=random.randint(0, delta))

def random_date_str(start_date, end_date):
    return str(random_date(start_date, end_date))

def build_db():
    print("=" * 55)
    print("  MedCart Intelligence Platform — Data Generator")
    print("=" * 55)

    ensure_dirs()

    print(f"\n[1/7] Connecting to database at:\n      {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")

    print("[2/7] Creating schema...")
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        sql = f.read()
    conn.executescript(sql)
    conn.commit()
    print("      Schema created.")

    # ── SUPPLIERS ────────────────────────────────────────────
    print("[3/7] Inserting suppliers, drugs, inventory...")
    supplier_ids = []
    for s in SUPPLIERS:
        cur.execute(
            "INSERT INTO suppliers (name,city,state,phone,email,rating) VALUES (?,?,?,?,?,?)",
            (s[0], s[1], s[2], random_phone(), f"info@{s[0].lower().replace(' ','')}.com", s[3])
        )
        supplier_ids.append(cur.lastrowid)

    # ── DRUGS ────────────────────────────────────────────────
    drug_ids = []
    for d in DRUGS:
        sup = random.choice(supplier_ids)
        cur.execute(
            "INSERT INTO drugs (name,brand,category,form,unit_price,supplier_id,requires_rx,shelf_life_days) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (d[0], d[1], d[2], d[3], d[4], sup, 1 if d[5]=='Y' else 0, d[6])
        )
        drug_ids.append(cur.lastrowid)

    # ── INVENTORY ─────────────────────────────────────────────
    today = date.today()
    for did in drug_ids:
        stock = random.randint(0, 500)
        reorder = random.randint(30, 100)
        mfg = today - timedelta(days=random.randint(30, 365))
        exp = mfg + timedelta(days=random.randint(180, 900))
        cur.execute(
            "INSERT INTO inventory (drug_id,stock_qty,reorder_level,batch_no,manufacture_date,expiry_date) "
            "VALUES (?,?,?,?,?,?)",
            (did, stock, reorder, f"BCH{random.randint(10000,99999)}", str(mfg), str(exp))
        )

    conn.commit()
    print("      Suppliers / drugs / inventory done.")

    # ── PATIENTS ─────────────────────────────────────────────
    print("[4/7] Generating 600 patients...")
    patient_ids = []
    start_reg = date(2022, 1, 1)
    for _ in range(600):
        city, state = random.choice(CITIES_STATES)
        is_chronic = 1 if random.random() < 0.35 else 0
        age = random.randint(18, 80)
        gender = random.choice(['M','F','M','F','M'])
        reg_date = random_date_str(start_reg, today)
        cur.execute(
            "INSERT INTO patients (name,age,gender,city,state,phone,is_chronic,registered_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (random_name(), age, gender, city, state, random_phone(), is_chronic, reg_date)
        )
        patient_ids.append(cur.lastrowid)
    conn.commit()
    print("      600 patients created.")

    # ── ORDERS + ORDER_ITEMS ──────────────────────────────────
    print("[5/7] Generating 12,000 orders with line items...")
    order_start = date(2022, 1, 1)
    order_end   = today

    rx_needed_drugs = [did for did, d in zip(drug_ids, DRUGS) if d[5] == 'Y']
    rx_drug_set = set(rx_needed_drugs)

    total_items = 0
    for _ in range(12000):
        pat_id = random.choice(patient_ids)
        odate  = random_date_str(order_start, order_end)
        status = random.choices(ORDER_STATUS, weights=[90,90,90,90,10], k=1)[0]
        channel = random.choice(CHANNELS)
        payment = random.choice(PAYMENT_MODES)

        # seasonal boost: more orders in winter (Nov-Feb) and monsoon (Jun-Aug)
        month = int(odate[5:7])
        if month in (11,12,1,2,6,7,8):
            n_items = random.randint(1, 5)
        else:
            n_items = random.randint(1, 3)

        # pick drugs for this order
        selected = random.sample(drug_ids, min(n_items, len(drug_ids)))
        needs_rx = any(d in rx_drug_set for d in selected)

        # random discount
        discount = round(random.uniform(0, 0.15) * sum(
            DRUGS[drug_ids.index(d)][4] * random.randint(1,4) for d in selected
        ), 2)

        cur.execute(
            "INSERT INTO orders (patient_id,order_date,status,channel,total_amount,discount,payment_mode) "
            "VALUES (?,?,?,?,0,?,?)",
            (pat_id, odate, status, channel, discount, payment)
        )
        oid = cur.lastrowid
        total_amount = 0

        for did in selected:
            drug_idx = drug_ids.index(did)
            qty  = random.randint(1, 4)
            uprice = DRUGS[drug_idx][4] * random.uniform(0.95, 1.1)
            uprice = round(uprice, 2)
            total_amount += qty * uprice
            cur.execute(
                "INSERT INTO order_items (order_id,drug_id,quantity,unit_price) VALUES (?,?,?,?)",
                (oid, did, qty, uprice)
            )
            total_items += 1

        # Update order total
        cur.execute("UPDATE orders SET total_amount=? WHERE order_id=?",
                    (round(total_amount, 2), oid))

        # Prescription for rx orders
        if needs_rx and status == 'completed':
            cur.execute(
                "INSERT INTO prescriptions (patient_id,order_id,doctor_name,issued_date,valid_days) "
                "VALUES (?,?,?,?,?)",
                (pat_id, oid, random.choice(DOCTORS), odate, 30)
            )

    conn.commit()
    print(f"      12,000 orders, ~{total_items:,} line items created.")

    # ── EXPORT CSVs ───────────────────────────────────────────
    print("[6/7] Exporting CSVs...")
    tables_views = [
        'suppliers','drugs','inventory','patients',
        'orders','order_items','prescriptions',
        'v_daily_revenue','v_inventory_risk','v_rfm','v_drug_sales'
    ]
    for tv in tables_views:
        try:
            cur.execute(f"SELECT * FROM {tv}")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            fpath = os.path.join(DATA_DIR, f"{tv}.csv")
            with open(fpath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
            print(f"      ✓ {tv}.csv  ({len(rows):,} rows)")
        except Exception as e:
            print(f"      ✗ {tv}: {e}")

    conn.close()
    print("\n[7/7] All done!")
    print(f"\n  DB  → {DB_PATH}")
    print(f"  CSVs → {DATA_DIR}/")
    print("\n  Ready for Power BI / Tableau. Run 03_eda.py next.\n")

if __name__ == '__main__':
    build_db()
