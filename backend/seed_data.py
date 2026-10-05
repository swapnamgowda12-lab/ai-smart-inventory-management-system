import random
from datetime import date, timedelta
from db import get_connection

def seed_transactions():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT product_id, name FROM products")
    products = cursor.fetchall()

    if not products:
        print("No products found. Add products first.")
        return

    today = date.today()
    start_date = today - timedelta(days=365)

    for product_id, name in products:
        # give each product a "seasonal peak month" for realistic patterns
        peak_month = random.randint(1, 12)
        current = start_date

        while current <= today:
            month_factor = 1.5 if current.month == peak_month else 1.0
            base_sales = random.randint(2, 8)
            daily_sales = int(base_sales * month_factor)

            if daily_sales > 0 and random.random() < 0.6:
                cursor.execute(
                    "INSERT INTO transactions (product_id, type, quantity, transaction_date, notes) VALUES (%s, %s, %s, %s, %s)",
                    (product_id, 'sale', daily_sales, current, 'seed data')
                )
            current += timedelta(days=1)

    conn.commit()
    cursor.close()
    conn.close()
    print("Historical data seeded successfully.")

if __name__ == '__main__':
    seed_transactions()