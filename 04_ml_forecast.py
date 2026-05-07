"""
MedCart Intelligence Platform — ML Demand Forecasting
=======================================================
Trains a RandomForest model on historical drug category sales.
Outputs a 4-week forward forecast per category + feature importance chart.

Usage (from project root):
    python sql/04_ml_forecast.py
"""

import os
import sqlite3
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

# ── Paths ──────────────────────────────────────────────────────────────────────
THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR    = os.path.dirname(THIS_DIR)
DATA_DIR    = os.path.join(ROOT_DIR, 'data')
CHARTS_DIR  = os.path.join(ROOT_DIR, 'charts')
REPORTS_DIR = os.path.join(ROOT_DIR, 'reports')
DB_PATH     = os.path.join(DATA_DIR, 'medcart.db')

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

BG_COLOR = '#f8f9fa'
PALETTE  = ['#1a73e8','#34a853','#ea4335','#fbbc04','#9c27b0','#00acc1','#ff7043','#8d6e63']

print("=" * 55)
print("  MedCart Intelligence Platform — ML Forecasting")
print("=" * 55)

# ── Load weekly sales by category ─────────────────────────────────────────────
print("\n[1/5] Loading and preparing weekly sales data...")
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("""
    SELECT
        o.order_date,
        d.category,
        SUM(oi.quantity)    AS qty_sold,
        SUM(oi.line_total)  AS revenue
    FROM order_items oi
    JOIN orders  o ON oi.order_id = o.order_id
    JOIN drugs   d ON oi.drug_id  = d.drug_id
    WHERE o.status = 'completed'
    GROUP BY o.order_date, d.category
""", conn)
conn.close()

df['order_date'] = pd.to_datetime(df['order_date'])
df['week'] = df['order_date'].dt.to_period('W').apply(lambda r: r.start_time)
weekly = (df.groupby(['week','category'])
            .agg(qty=('qty_sold','sum'), revenue=('revenue','sum'))
            .reset_index())

categories = sorted(weekly['category'].unique())
print(f"      Categories: {', '.join(categories)}")
print(f"      Weekly records: {len(weekly):,}")

# ── Feature engineering ───────────────────────────────────────────────────────
def make_features(cat_df: pd.DataFrame) -> pd.DataFrame:
    """Build time-series features for one category."""
    cat_df = cat_df.sort_values('week').copy()
    cat_df['week_num'] = np.arange(len(cat_df))

    # Lag features
    for lag in [1, 2, 3, 4, 8, 12]:
        cat_df[f'lag_{lag}'] = cat_df['qty'].shift(lag)

    # Rolling statistics
    for w in [4, 8, 12]:
        cat_df[f'roll_mean_{w}'] = cat_df['qty'].shift(1).rolling(w).mean()
        cat_df[f'roll_std_{w}']  = cat_df['qty'].shift(1).rolling(w).std()

    # Calendar features
    cat_df['month']      = cat_df['week'].dt.month
    cat_df['quarter']    = cat_df['week'].dt.quarter
    cat_df['month_sin']  = np.sin(2 * np.pi * cat_df['month'] / 12)
    cat_df['month_cos']  = np.cos(2 * np.pi * cat_df['month'] / 12)
    cat_df['is_winter']  = cat_df['month'].isin([11, 12, 1, 2]).astype(int)
    cat_df['is_monsoon'] = cat_df['month'].isin([6, 7, 8]).astype(int)

    return cat_df.dropna()

FEATURE_COLS = [
    'week_num',
    'lag_1','lag_2','lag_3','lag_4','lag_8','lag_12',
    'roll_mean_4','roll_std_4',
    'roll_mean_8','roll_std_8',
    'roll_mean_12','roll_std_12',
    'month','quarter',
    'month_sin','month_cos',
    'is_winter','is_monsoon',
]

print("\n[2/5] Engineering features (19 features)...")
all_data = {}
for cat in categories:
    sub = weekly[weekly['category'] == cat][['week','qty']].copy()
    all_data[cat] = make_features(sub)
print("      Done.")

# ── Train models ──────────────────────────────────────────────────────────────
print("\n[3/5] Training RandomForest per category...")
models   = {}
metrics  = []
forecasts = {}

for cat in categories:
    feat_df = all_data[cat]
    X = feat_df[FEATURE_COLS].values
    y = feat_df['qty'].values

    if len(X) < 20:
        print(f"  ⚠  {cat}: not enough data, skipping.")
        continue

    # Time-series cross-validation
    tscv   = TimeSeriesSplit(n_splits=3)
    cv_mae = []
    for tr_idx, te_idx in tscv.split(X):
        m = RandomForestRegressor(n_estimators=150, max_depth=8,
                                   min_samples_leaf=2, random_state=42, n_jobs=-1)
        m.fit(X[tr_idx], y[tr_idx])
        preds = m.predict(X[te_idx])
        cv_mae.append(mean_absolute_error(y[te_idx], preds))

    # Final model on all data
    model = RandomForestRegressor(n_estimators=200, max_depth=10,
                                   min_samples_leaf=2, random_state=42, n_jobs=-1)
    model.fit(X, y)
    train_pred = model.predict(X)

    mae   = mean_absolute_error(y, train_pred)
    rmse  = np.sqrt(mean_squared_error(y, train_pred))
    r2    = r2_score(y, train_pred)
    cv_m  = float(np.mean(cv_mae))

    metrics.append({'Category': cat, 'MAE': round(mae,1), 'RMSE': round(rmse,1),
                    'R²': round(r2, 3), 'CV-MAE': round(cv_m, 1)})
    models[cat] = (model, feat_df)
    print(f"  ✓ {cat:<18} R²={r2:.3f}  MAE={mae:.1f}  CV-MAE={cv_m:.1f}")

# ── 4-week forecast ───────────────────────────────────────────────────────────
print("\n[4/5] Generating 4-week forward forecast...")
forecast_rows = []

for cat, (model, feat_df) in models.items():
    last_row  = feat_df.iloc[-1].copy()
    last_week = last_row['week']
    qty_hist  = list(feat_df['qty'].values)
    week_num  = int(last_row['week_num'])

    for step in range(1, 5):
        next_week = last_week + pd.Timedelta(weeks=step)
        week_num += 1
        month = next_week.month

        # Build feature row
        lag_vals = (qty_hist[-1:] + qty_hist[-2:-1] + qty_hist[-3:-2] +
                    qty_hist[-4:-3] + qty_hist[-8:-7] + qty_hist[-12:-11])
        # pad if not enough history
        while len(lag_vals) < 6:
            lag_vals.append(qty_hist[-1] if qty_hist else 0)

        roll4_mean  = float(np.mean(qty_hist[-4:]))  if len(qty_hist)>=4  else float(np.mean(qty_hist))
        roll4_std   = float(np.std(qty_hist[-4:]))   if len(qty_hist)>=4  else 0.0
        roll8_mean  = float(np.mean(qty_hist[-8:]))  if len(qty_hist)>=8  else roll4_mean
        roll8_std   = float(np.std(qty_hist[-8:]))   if len(qty_hist)>=8  else roll4_std
        roll12_mean = float(np.mean(qty_hist[-12:])) if len(qty_hist)>=12 else roll8_mean
        roll12_std  = float(np.std(qty_hist[-12:])) if len(qty_hist)>=12 else roll8_std

        row = [
            week_num,
            *lag_vals[:6],
            roll4_mean, roll4_std,
            roll8_mean, roll8_std,
            roll12_mean, roll12_std,
            month, (month - 1) // 3 + 1,
            np.sin(2 * np.pi * month / 12),
            np.cos(2 * np.pi * month / 12),
            1 if month in (11,12,1,2) else 0,
            1 if month in (6,7,8) else 0,
        ]
        pred = max(0, float(model.predict([row])[0]))
        qty_hist.append(pred)

        forecast_rows.append({
            'Category': cat,
            'Week': str(next_week.date()),
            'Forecasted_Qty': round(pred, 0),
            'Week_Ahead': step,
        })

forecast_df = pd.DataFrame(forecast_rows)
fc_path = os.path.join(REPORTS_DIR, 'forecast_4week.csv')
forecast_df.to_csv(fc_path, index=False)
print(f"  ✓ Forecast saved: {fc_path}")
print(forecast_df.pivot(index='Category', columns='Week_Ahead', values='Forecasted_Qty')
      .rename(columns={i: f'Week+{i}' for i in range(1,5)}).to_string())

# ── Charts ────────────────────────────────────────────────────────────────────
print("\n[5/5] Generating forecast charts...")

# Chart A — Actual vs Forecast per category
fig, axes = plt.subplots(3, 4, figsize=(18, 12), facecolor=BG_COLOR)
axes = axes.flatten()
plt.rcParams['axes.facecolor'] = BG_COLOR
plt.rcParams['figure.facecolor'] = BG_COLOR

for idx, cat in enumerate(sorted(models.keys())):
    ax = axes[idx]
    feat_df = models[cat][1]
    hist = feat_df.tail(24)
    fc_cat = forecast_df[forecast_df['Category'] == cat]
    fc_weeks = pd.to_datetime(fc_cat['Week'])
    fc_qty   = fc_cat['Forecasted_Qty'].values

    ax.plot(hist['week'], hist['qty'], color=PALETTE[0], lw=1.8, label='Actual')
    ax.plot(fc_weeks, fc_qty, color=PALETTE[2], lw=2, ls='--',
            marker='o', markersize=5, label='Forecast')
    ax.fill_between(fc_weeks, fc_qty * 0.85, fc_qty * 1.15,
                    alpha=0.15, color=PALETTE[2], label='±15% CI')
    ax.set_title(cat, fontsize=11, fontweight='bold')
    ax.set_xlabel('')
    ax.tick_params(axis='x', labelsize=7, rotation=30)
    ax.legend(fontsize=7)
    ax.set_facecolor(BG_COLOR)
    ax.grid(True, color='#dee2e6', linewidth=0.5)
    for spine in ['top','right']:
        ax.spines[spine].set_visible(False)

# Hide unused axes
for j in range(len(models), len(axes)):
    axes[j].set_visible(False)

plt.suptitle('4-Week Demand Forecast by Drug Category', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
path_a = os.path.join(CHARTS_DIR, '09_demand_forecast.png')
plt.savefig(path_a, dpi=150, bbox_inches='tight', facecolor=BG_COLOR)
plt.close()
print("  ✓ 09_demand_forecast.png")

# Chart B — Feature importance (averaged across categories)
importances = np.zeros(len(FEATURE_COLS))
for cat, (model, _) in models.items():
    importances += model.feature_importances_
importances /= len(models)

imp_df = pd.DataFrame({'feature': FEATURE_COLS, 'importance': importances})
imp_df = imp_df.sort_values('importance', ascending=True).tail(15)

fig, ax = plt.subplots(figsize=(10, 7), facecolor=BG_COLOR)
ax.set_facecolor(BG_COLOR)
bars = ax.barh(imp_df['feature'], imp_df['importance'],
               color=[PALETTE[i % len(PALETTE)] for i in range(len(imp_df))])
ax.set_title('Top Feature Importances (Avg across Categories)', fontweight='bold')
ax.set_xlabel('Feature Importance')
ax.bar_label(bars, labels=[f'{v:.3f}' for v in imp_df['importance']], padding=3, fontsize=9)
for spine in ['top','right']:
    ax.spines[spine].set_visible(False)
ax.grid(True, axis='x', color='#dee2e6', linewidth=0.5)
plt.tight_layout()
path_b = os.path.join(CHARTS_DIR, '10_feature_importance.png')
plt.savefig(path_b, dpi=150, bbox_inches='tight', facecolor=BG_COLOR)
plt.close()
print("  ✓ 10_feature_importance.png")

# ── Model metrics table ───────────────────────────────────────────────────────
metrics_df = pd.DataFrame(metrics)
metrics_path = os.path.join(REPORTS_DIR, 'model_metrics.csv')
metrics_df.to_csv(metrics_path, index=False)
print(f"\n  ✓ Model metrics saved: {metrics_path}")
print("\n" + metrics_df.to_string(index=False))

print("\n" + "=" * 55)
print("  ML Forecasting Complete!")
print(f"\n  Charts  → {CHARTS_DIR}/")
print(f"  Reports → {REPORTS_DIR}/")
print("=" * 55 + "\n")
