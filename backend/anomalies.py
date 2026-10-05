import pandas as pd
from db import get_connection

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def get_anomalies():
    """Flags transactions whose quantity/amount are statistical outliers
    compared to the overall pattern, using IsolationForest (unsupervised —
    no labelled 'fraud' data needed, which fits a student project with no
    real historical fraud examples). Needs a reasonable number of
    transactions to have a meaningful 'normal pattern' to compare against."""
    if not SKLEARN_AVAILABLE:
        return []

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

    if len(rows) < 10:
        return []

    df = pd.DataFrame(rows)
    df['price'] = df['price'].astype(float)
    df['amount'] = df['quantity'] * df['price']

    model = IsolationForest(contamination=0.05, random_state=42)
    features = df[['quantity', 'amount']]
    df['is_anomaly'] = model.fit_predict(features)
    df['anomaly_score'] = model.decision_function(features)

    anomalies_df = df[df['is_anomaly'] == -1].copy()
    if anomalies_df.empty:
        return []

    mean_qty = df['quantity'].mean()
    mean_amt = df['amount'].mean()

    def risk_level(score):
        return "High" if score < -0.12 else "Medium"

    def reason(row):
        if row['quantity'] > mean_qty * 2:
            return "Transaction quantity is significantly higher than typical."
        if row['amount'] > mean_amt * 2:
            return "Transaction amount is significantly higher than typical."
        return "Transaction pattern differs from usual activity."

    anomalies_df['risk_level'] = anomalies_df['anomaly_score'].apply(risk_level)
    anomalies_df['reason'] = anomalies_df.apply(reason, axis=1)
    anomalies_df['transaction_date'] = anomalies_df['transaction_date'].astype(str)
    anomalies_df['anomaly_score'] = anomalies_df['anomaly_score'].round(3)
    anomalies_df['amount'] = anomalies_df['amount'].round(2)

    result = anomalies_df[[
        'transaction_id', 'product_name', 'transaction_date', 'quantity',
        'type', 'amount', 'anomaly_score', 'risk_level', 'reason'
    ]].sort_values('anomaly_score')

    return result.to_dict(orient='records')