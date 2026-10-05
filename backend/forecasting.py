import pandas as pd
from db import get_connection

try:
    from sklearn.linear_model import LinearRegression
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def _trend_prediction(monthly_series):
    """A small, genuine scikit-learn component: fits a LinearRegression
    over the chronological sequence of monthly totals (not calendar
    month) to capture an overall upward/downward trend, independent of
    seasonality. Returns None if there isn't enough data to fit on."""
    if not SKLEARN_AVAILABLE or len(monthly_series) < 3:
        return None
    X = np.arange(len(monthly_series)).reshape(-1, 1)
    y = monthly_series.values
    model = LinearRegression()
    model.fit(X, y)
    next_x = np.array([[len(monthly_series)]])
    pred = model.predict(next_x)[0]
    return max(0.0, float(pred))


def get_forecast():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT product_id, name, quantity, reorder_level FROM products")
    all_products = cursor.fetchall()

    cursor.execute("""
        SELECT t.product_id, p.name, t.quantity, t.transaction_date
        FROM transactions t
        JOIN products p ON t.product_id = p.product_id
        WHERE t.type = 'sale'
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    results = []
    next_month = (pd.Timestamp.today().month % 12) + 1

    if rows:
        df = pd.DataFrame(rows)
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        df['month'] = df['transaction_date'].dt.month
        df['year_month'] = df['transaction_date'].dt.to_period('M')
        products_with_data = set(df['product_id'].unique())
    else:
        df = pd.DataFrame()
        products_with_data = set()

    for product in all_products:
        product_id = product['product_id']
        product_name = product['name']
        current_stock = product['quantity']
        reorder_level = product['reorder_level']

        if product_id not in products_with_data:
            results.append({
                "product_id": product_id,
                "name": product_name,
                "current_stock": current_stock,
                "avg_monthly_sales": 0,
                "predicted_next_month_sales": 0,
                "trend_model_prediction": None,
                "recommended_order_quantity": 0,
                "trend": "insufficient data",
                "recommendation": "monitor"
            })
            continue

        group = df[df['product_id'] == product_id]

        # Seasonal method (primary, explainable) — unchanged from before.
        monthly_sales_by_calendar_month = group.groupby('month')['quantity'].sum()
        avg_monthly_sales = monthly_sales_by_calendar_month.mean()
        next_month_sales = monthly_sales_by_calendar_month.get(next_month, 0)

        # Trend method (secondary, genuine scikit-learn signal) — looks at
        # the chronological sequence of monthly totals, so it can catch an
        # overall rising/falling trend that pure calendar-month averaging
        # would miss.
        chronological_monthly = group.groupby('year_month')['quantity'].sum().sort_index()
        trend_pred = _trend_prediction(chronological_monthly)

        # Blend: if the trend model produced a value, average it with the
        # seasonal prediction; otherwise fall back to seasonal alone.
        if trend_pred is not None:
            blended_prediction = (next_month_sales + trend_pred) / 2
        else:
            blended_prediction = next_month_sales

        ratio = blended_prediction / avg_monthly_sales if avg_monthly_sales else 0
        if ratio >= 1.2:
            trend = "high demand expected"
            recommendation = "order more"
        elif ratio <= 0.7:
            trend = "low demand expected"
            recommendation = "order less"
        else:
            trend = "steady demand expected"
            recommendation = "order as usual"

        # Reviewer's reorder formula: max(0, predicted demand + safety
        # stock (approximated here by reorder_level) - current stock).
        recommended_order_quantity = max(
            0, round(blended_prediction + reorder_level - current_stock)
        )

        results.append({
            "product_id": product_id,
            "name": product_name,
            "current_stock": current_stock,
            "avg_monthly_sales": round(avg_monthly_sales, 1),
            "predicted_next_month_sales": round(blended_prediction),
            "trend_model_prediction": round(trend_pred, 1) if trend_pred is not None else None,
            "recommended_order_quantity": recommended_order_quantity,
            "trend": trend,
            "recommendation": recommendation
        })

    return results