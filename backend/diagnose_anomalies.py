"""
Run this directly to see exactly what the anomaly detector sees in your
real database: python diagnose_anomalies.py
"""
import pandas as pd
from sklearn.ensemble import IsolationForest
from db import get_connection

conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute("""
    SELECT t.transaction_id, p.name AS product_name, t.transaction_date,
           t.quantity, t.type, p.price
    FROM transactions t
    JOIN products p ON t.product_id = p.product_id
""")
rows = cursor.fetchall()
cursor.close()
conn.close()

print(f"Total rows fetched: {len(rows)}")

df = pd.DataFrame(rows)
print("\n--- dtypes ---")
print(df.dtypes)

print("\n--- any nulls? ---")
print(df.isnull().sum())

df['price'] = df['price'].astype(float)
df['amount'] = df['quantity'] * df['price']

print("\n--- quantity describe ---")
print(df['quantity'].describe())
print("\n--- amount describe ---")
print(df['amount'].describe())

print("\n--- top 5 largest quantity rows ---")
print(df.sort_values('quantity', ascending=False)[['transaction_id', 'product_name', 'quantity', 'amount', 'type']].head(5))

model = IsolationForest(contamination=0.05, random_state=42)
features = df[['quantity', 'amount']]
df['is_anomaly'] = model.fit_predict(features)
df['anomaly_score'] = model.decision_function(features)

print("\n--- is_anomaly value counts ---")
print(df['is_anomaly'].value_counts())

print("\n--- the 10 lowest (most anomalous) scores ---")
print(df.sort_values('anomaly_score').head(10)[['transaction_id', 'product_name', 'quantity', 'amount', 'anomaly_score', 'is_anomaly']])