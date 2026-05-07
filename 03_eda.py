"""
MedCart Intelligence Platform — Exploratory Data Analysis
==========================================================
Generates 8 professional charts saved to charts/ folder.

Usage (from project root):
    python sql/03_eda.py
"""

import os
import sqlite3
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import matplotlib
matplotlib.use('Agg')   # non-interactive backend — works everywhere
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import seaborn as sns

# ── Paths ──────────────────────────────────────────────────────────────────────
THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(THIS_DIR)
DATA_DIR   = os.path.join(ROOT_DIR, 'data')
CHARTS_DIR = os.path.join(ROOT_DIR, 'charts')
DB_PATH    = os.path.join(DATA_DIR, 'medcart.db')

os.makedirs(CHARTS_DIR, exist_ok=True)

# ── Style ──────────────────────────────────────────────────────────────────────
PALETTE    = ['#1a73e8','#34a853','#ea4335','#fbbc04','#9c27b0','#00acc1','#ff7043','#8d6e63']
BG_COLOR   = '#f8f9fa'
GRID_COLOR = '#dee2e6'

plt.rcParams.update({
    'figure.facecolor': BG_COLOR,
    'axes.facecolor':   BG_COLOR,
    'axes.grid':        True,
    'grid.color':       GRID_COLOR,
    'grid.linewidth':   0.6,
    'axes.spines.top':  False,
    'axes.spines.right':False,
    'font.family':      'DejaVu Sans',
    'axes.titlesize':   14,
    'axes.titleweight': 'bold',
    'axes.labelsize':   11,
})

def load(query):
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query(query, conn)
    conn.close()
    return df

def save(name):
    path = os.path.join(CHARTS_DIR, name)
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=BG_COLOR)
    plt.close()
    print(f"  ✓ {name}")
    return path

print("=" * 55)
print("  MedCart Intelligence Platform — EDA")
print("=" * 55)
print(f"\nLoading data from: {DB_PATH}\n")

# ═══════════════════════════════════════════════════════════
# CHART 1 — Monthly Revenue Trend
# ═══════════════════════════════════════════════════════════
df = load("""
    SELECT strftime('%Y-%m', order_date) AS month,
           SUM(total_amount) AS revenue,
           COUNT(order_id)   AS orders
    FROM orders
    WHERE status='completed'
    GROUP BY month
    ORDER BY month
""")
df['month_dt'] = pd.to_datetime(df['month'])
df['revenue_L'] = df['revenue'] / 100000   # in Lakhs

fig, ax1 = plt.subplots(figsize=(14, 5))
ax2 = ax1.twinx()
ax1.fill_between(range(len(df)), df['revenue_L'], alpha=0.25, color=PALETTE[0])
ax1.plot(range(len(df)), df['revenue_L'], color=PALETTE[0], lw=2.5, label='Revenue (₹ Lakhs)')
ax2.bar(range(len(df)), df['orders'], alpha=0.4, color=PALETTE[1], label='Orders')

# X-axis ticks (every 3 months)
step = max(1, len(df) // 10)
ticks = list(range(0, len(df), step))
ax1.set_xticks(ticks)
ax1.set_xticklabels([df['month'].iloc[i] for i in ticks], rotation=45, ha='right')
ax1.set_ylabel('Revenue (₹ Lakhs)', color=PALETTE[0])
ax2.set_ylabel('Orders Count', color=PALETTE[1])
ax1.set_title('Monthly Revenue Trend & Order Volume (2022–2025)')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1+lines2, labels1+labels2, loc='upper left')
plt.tight_layout()
save('01_monthly_revenue.png')

# ═══════════════════════════════════════════════════════════
# CHART 2 — Revenue by Drug Category
# ═══════════════════════════════════════════════════════════
df = load("""
    SELECT d.category, ROUND(SUM(oi.line_total),2) AS revenue
    FROM order_items oi
    JOIN drugs d ON oi.drug_id = d.drug_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY d.category
    ORDER BY revenue DESC
""")
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(df['category'], df['revenue']/100000, color=PALETTE[:len(df)])
ax.bar_label(bars, labels=[f'₹{v:.1f}L' for v in df['revenue']/100000],
             padding=5, fontsize=10, fontweight='bold')
ax.set_xlabel('Revenue (₹ Lakhs)')
ax.set_title('Revenue by Drug Category')
ax.invert_yaxis()
plt.tight_layout()
save('02_category_revenue.png')

# ═══════════════════════════════════════════════════════════
# CHART 3 — Seasonality Heatmap (Month × Day of Week)
# ═══════════════════════════════════════════════════════════
df = load("""
    SELECT strftime('%m', order_date) AS month,
           CAST(strftime('%w', order_date) AS INTEGER) AS dow,
           SUM(total_amount) AS revenue
    FROM orders WHERE status='completed'
    GROUP BY month, dow
""")
df['month'] = df['month'].astype(int)
df['dow']   = df['dow'].astype(int)
pivot = df.pivot(index='month', columns='dow', values='revenue').fillna(0)
pivot.index = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
pivot.columns = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

fig, ax = plt.subplots(figsize=(10, 7))
sns.heatmap(pivot/1000, ax=ax, cmap='Blues', linewidths=0.3,
            annot=True, fmt='.0f', cbar_kws={'label':'Revenue (₹ Thousands)'})
ax.set_title('Revenue Seasonality — Month × Day of Week')
ax.set_xlabel('Day of Week')
ax.set_ylabel('Month')
plt.tight_layout()
save('03_seasonality_heatmap.png')

# ═══════════════════════════════════════════════════════════
# CHART 4 — RFM Customer Segmentation
# ═══════════════════════════════════════════════════════════
df = load("SELECT frequency, monetary, recency_days, is_chronic FROM v_rfm")
df['segment'] = pd.cut(df['frequency'],
    bins=[0, 2, 5, 10, 999],
    labels=['One-time (1-2)', 'Occasional (3-5)', 'Regular (6-10)', 'VIP (10+)']
)
seg_colors = {
    'One-time (1-2)': PALETTE[3],
    'Occasional (3-5)': PALETTE[0],
    'Regular (6-10)': PALETTE[1],
    'VIP (10+)': PALETTE[2],
}
fig, ax = plt.subplots(figsize=(10, 7))
for seg, grp in df.groupby('segment', observed=True):
    ax.scatter(grp['recency_days'], grp['monetary'],
               s=60, alpha=0.55, label=str(seg), color=seg_colors[str(seg)])
ax.set_xlabel('Recency (Days Since Last Order)')
ax.set_ylabel('Total Monetary Value (₹)')
ax.set_title('RFM Customer Segmentation')
ax.legend(title='Segment')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'₹{x:,.0f}'))
plt.tight_layout()
save('04_rfm_segmentation.png')

# ═══════════════════════════════════════════════════════════
# CHART 5 — Inventory Risk Matrix
# ═══════════════════════════════════════════════════════════
df = load("SELECT drug_name, category, stock_qty, reorder_level, days_to_expiry, risk_status FROM v_inventory_risk")
risk_colors = {
    'Healthy': PALETTE[1],
    'Low Stock': PALETTE[3],
    'Near Expiry': PALETTE[0],
    'Out of Stock': PALETTE[2],
}
fig, ax = plt.subplots(figsize=(11, 7))
for status, grp in df.groupby('risk_status'):
    ax.scatter(grp['stock_qty'], grp['days_to_expiry'],
               s=120, label=status, color=risk_colors.get(status, 'grey'),
               edgecolors='white', linewidth=0.6, alpha=0.85)
# Threshold lines
ax.axvline(x=df['reorder_level'].mean(), ls='--', color='orange', alpha=0.6, label='Avg Reorder Level')
ax.axhline(y=90, ls='--', color='red', alpha=0.6, label='90-day Expiry Alert')
ax.set_xlabel('Stock Quantity')
ax.set_ylabel('Days to Expiry')
ax.set_title('Inventory Risk Matrix — Stock vs Expiry')
ax.legend()
plt.tight_layout()
save('05_inventory_risk.png')

# ═══════════════════════════════════════════════════════════
# CHART 6 — Top 15 Drugs by Revenue
# ═══════════════════════════════════════════════════════════
df = load("""
    SELECT drug_name, total_revenue, total_qty_sold
    FROM v_drug_sales
    ORDER BY total_revenue DESC LIMIT 15
""")
fig, ax = plt.subplots(figsize=(11, 6))
bars = ax.bar(range(len(df)), df['total_revenue']/1000,
              color=[PALETTE[i % len(PALETTE)] for i in range(len(df))])
ax.bar_label(bars, labels=[f'₹{v:.0f}K' for v in df['total_revenue']/1000],
             padding=3, fontsize=8.5, fontweight='bold')
ax.set_xticks(range(len(df)))
ax.set_xticklabels(df['drug_name'], rotation=45, ha='right', fontsize=9)
ax.set_ylabel('Revenue (₹ Thousands)')
ax.set_title('Top 15 Drugs by Revenue')
plt.tight_layout()
save('06_top_drugs_revenue.png')

# ═══════════════════════════════════════════════════════════
# CHART 7 — Channel Mix & Payment Mode Analysis
# ═══════════════════════════════════════════════════════════
df_ch = load("""
    SELECT channel, COUNT(*) AS orders, SUM(total_amount) AS revenue
    FROM orders WHERE status='completed'
    GROUP BY channel
""")
df_pay = load("""
    SELECT payment_mode, COUNT(*) AS orders
    FROM orders WHERE status='completed'
    GROUP BY payment_mode ORDER BY orders DESC
""")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
wedges, texts, autotexts = ax1.pie(
    df_ch['orders'], labels=df_ch['channel'], autopct='%1.1f%%',
    colors=PALETTE[:len(df_ch)], startangle=90,
    wedgeprops={'edgecolor':'white','linewidth':2}
)
ax1.set_title('Order Channel Mix')
bars = ax2.bar(df_pay['payment_mode'], df_pay['orders'],
               color=PALETTE[:len(df_pay)])
ax2.set_title('Payment Mode Distribution')
ax2.set_xlabel('Payment Mode')
ax2.set_ylabel('Number of Orders')
ax2.bar_label(bars, padding=3, fontsize=9)
plt.suptitle('Channel & Payment Analysis', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
save('07_channel_payment.png')

# ═══════════════════════════════════════════════════════════
# CHART 8 — Chronic vs Non-Chronic Patient Lifetime Value
# ═══════════════════════════════════════════════════════════
df = load("""
    SELECT p.is_chronic,
           COUNT(DISTINCT p.patient_id) AS patients,
           ROUND(AVG(sub.total),2) AS avg_ltv,
           ROUND(AVG(sub.freq),2)  AS avg_orders
    FROM patients p
    JOIN (
        SELECT patient_id,
               SUM(total_amount) AS total,
               COUNT(order_id)   AS freq
        FROM orders WHERE status='completed'
        GROUP BY patient_id
    ) sub ON p.patient_id = sub.patient_id
    GROUP BY p.is_chronic
""")
df['label'] = df['is_chronic'].map({0:'Non-Chronic', 1:'Chronic'})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
colors = [PALETTE[0], PALETTE[2]]
b1 = ax1.bar(df['label'], df['avg_ltv'], color=colors)
ax1.set_title('Avg Lifetime Value (₹)')
ax1.set_ylabel('₹')
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'₹{x:,.0f}'))
ax1.bar_label(b1, labels=[f'₹{v:,.0f}' for v in df['avg_ltv']], padding=4, fontweight='bold')

b2 = ax2.bar(df['label'], df['avg_orders'], color=colors)
ax2.set_title('Avg Orders per Patient')
ax2.set_ylabel('Orders')
ax2.bar_label(b2, labels=[f'{v:.1f}' for v in df['avg_orders']], padding=4, fontweight='bold')

plt.suptitle('Chronic vs Non-Chronic Patient Analysis', fontsize=14, fontweight='bold')
plt.tight_layout()
save('08_chronic_vs_regular.png')

print(f"\n  All charts saved to: {CHARTS_DIR}/")
print("  Run 04_ml_forecast.py next.\n")
