from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import os
import re
import pandas as pd
from db import get_connection
from forecasting import get_forecast
from anomalies import get_anomalies

app = Flask(__name__)
CORS(app)


def is_admin(username):
    """Looks up the role actually stored for this username in the
    database, rather than trusting anything the frontend claims. This is
    a real improvement over zero backend enforcement — the honest limit
    is that nothing cryptographically proves the request really came
    from that user (no signed session token yet), so this stops an
    accidental or lazy bypass, not a determined attacker who already
    knows a valid admin username. Full protection needs token-based auth."""
    if not username:
        return False
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return bool(user) and user['role'] == 'admin'


def is_valid_email_format(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


@app.route('/')
def home():
    return {"message": "Smart IMS backend is running"}


# ---------------- AUTH ----------------
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    # Public registration ALWAYS creates a staff account. Admin accounts
    # are not self-service — an existing admin must create them (today,
    # manually in the database; a future enhancement would add an
    # "Admin: create admin user" screen restricted to logged-in admins).
    role = 'staff'

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, hashed.decode('utf-8'), role)
        )
        conn.commit()
        return jsonify({"message": "user created"}), 201
    except Exception as e:
        if '1062' in str(e) or 'Duplicate' in str(e):
            return jsonify({"error": f"Username '{username}' is already taken"}), 409
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify({"message": "login successful", "role": user['role']}), 200
    return jsonify({"error": "invalid credentials"}), 401


# ---------------- PRODUCTS ----------------
@app.route('/products', methods=['POST'])
def add_product():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    sku = (data.get('sku') or '').strip().upper()
    supplier = (data.get('supplier') or '').strip()
    price = data.get('price', 0)
    quantity = data.get('quantity', 0)
    reorder_level = data.get('reorder_level', 10)

    errors = []
    if not name:
        errors.append("Product Name is required")
    if not category:
        errors.append("Category is required")
    if not sku:
        errors.append("SKU is required")
    if not supplier:
        errors.append("Supplier is required")
    try:
        price = float(price)
        if price <= 0:
            errors.append("Price must be greater than 0")
    except (TypeError, ValueError):
        errors.append("Price must be a number")
    try:
        quantity = int(quantity)
        if quantity < 0:
            errors.append("Quantity cannot be negative")
    except (TypeError, ValueError):
        errors.append("Quantity must be a whole number")

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO products (name, category, sku, price, quantity, reorder_level, supplier) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (name, category, sku, price, quantity, reorder_level, supplier)
        )
        conn.commit()
        return jsonify({"message": "product added", "product_id": cursor.lastrowid}), 201
    except Exception as e:
        if '1062' in str(e) or 'Duplicate' in str(e):
            return jsonify({"error": f"SKU '{sku}' already exists"}), 409
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/products', methods=['GET'])
def get_products():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(products), 200


@app.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    supplier = (data.get('supplier') or '').strip()
    price = data.get('price')
    quantity = data.get('quantity')
    reorder_level = data.get('reorder_level')

    errors = []
    if not name:
        errors.append("Product Name is required")
    if not category:
        errors.append("Category is required")
    try:
        price = float(price)
        if price <= 0:
            errors.append("Price must be greater than 0")
    except (TypeError, ValueError):
        errors.append("Price must be a number")
    try:
        quantity = int(quantity)
        if quantity < 0:
            errors.append("Quantity cannot be negative")
    except (TypeError, ValueError):
        errors.append("Quantity must be a whole number")

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE products SET name=%s, category=%s, price=%s, quantity=%s, reorder_level=%s, supplier=%s WHERE product_id=%s",
            (name, category, price, quantity, reorder_level, supplier, product_id)
        )
        conn.commit()
        return jsonify({"message": "product updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    username = request.headers.get('X-Username')
    if not is_admin(username):
        return jsonify({"error": "Admin access required"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE product_id=%s", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "product deleted"}), 200


@app.route('/products/low-stock', methods=['GET'])
def low_stock_products():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE quantity <= reorder_level")
    low_stock = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(low_stock), 200


# ---------------- TRANSACTIONS ----------------
@app.route('/transactions', methods=['POST'])
def add_transaction():
    data = request.get_json()
    product_id = data.get('product_id')
    t_type = data.get('type')
    quantity = data.get('quantity')
    t_date = data.get('transaction_date')
    notes = data.get('notes', '')
    payment_method = data.get('payment_method', None)

    if not product_id or not t_type or not quantity or not t_date:
        return jsonify({"error": "product_id, type, quantity, transaction_date are required"}), 400

    conn = get_connection()
    check_cursor = conn.cursor(dictionary=True)
    check_cursor.execute("SELECT quantity FROM products WHERE product_id = %s", (product_id,))
    product = check_cursor.fetchone()
    check_cursor.close()

    if not product:
        conn.close()
        return jsonify({"error": "product not found"}), 404

    if t_type == 'sale' and quantity > product['quantity']:
        conn.close()
        return jsonify({"error": f"Insufficient stock: only {product['quantity']} unit(s) available"}), 400

    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO transactions (product_id, type, quantity, transaction_date, notes, payment_method) VALUES (%s, %s, %s, %s, %s, %s)",
            (product_id, t_type, quantity, t_date, notes, payment_method)
        )
        new_id = cursor.lastrowid

        if t_type == 'purchase':
            cursor.execute("UPDATE products SET quantity = quantity + %s WHERE product_id = %s", (quantity, product_id))
        elif t_type == 'sale':
            cursor.execute("UPDATE products SET quantity = quantity - %s WHERE product_id = %s", (quantity, product_id))

        conn.commit()
        return jsonify({"message": "transaction recorded", "transaction_id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/transactions', methods=['GET'])
def get_transactions():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM transactions ORDER BY transaction_date DESC")
    txns = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(txns), 200


# ---------------- FORECAST ----------------
@app.route('/forecast', methods=['GET'])
def forecast():
    return jsonify(get_forecast()), 200


# ---------------- AI ANOMALY DETECTION ----------------
@app.route('/anomalies', methods=['GET'])
def anomalies():
    return jsonify(get_anomalies()), 200


# ---------------- DASHBOARD SALES SUMMARY ----------------
@app.route('/dashboard/sales-summary', methods=['GET'])
def sales_summary():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.quantity, t.type, t.transaction_date, p.name, p.price
        FROM transactions t JOIN products p ON t.product_id = p.product_id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    empty = {
        "total_sales_revenue": 0, "total_purchase_expenditure": 0,
        "total_sales_transactions": 0, "most_sold_product": None,
        "least_sold_product": None, "monthly_trend": [], "top_products": []
    }
    if not rows:
        return jsonify(empty), 200

    df = pd.DataFrame(rows)
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['price'] = df['price'].astype(float)
    df['amount'] = df['quantity'] * df['price']

    sales_df = df[df['type'] == 'sale']
    purchase_df = df[df['type'] == 'purchase']

    total_sales_revenue = round(float(sales_df['amount'].sum()), 2)
    total_purchase_expenditure = round(float(purchase_df['amount'].sum()), 2)
    total_sales_transactions = int(len(sales_df))

    most_sold, least_sold = None, None
    this_month = pd.Timestamp.today().month
    this_month_sales = sales_df[sales_df['transaction_date'].dt.month == this_month]
    if not this_month_sales.empty:
        product_totals = this_month_sales.groupby('name')['quantity'].sum().sort_values(ascending=False)
        if len(product_totals):
            most_sold = product_totals.index[0]
            least_sold = product_totals.index[-1]

    monthly_trend = []
    if not sales_df.empty:
        sdf = sales_df.copy()
        sdf['month_label'] = sdf['transaction_date'].dt.strftime('%Y-%m')
        trend = sdf.groupby('month_label')['quantity'].sum().reset_index().sort_values('month_label')
        monthly_trend = trend.to_dict(orient='records')

    top_products = []
    if not sales_df.empty:
        top = sales_df.groupby('name')['quantity'].sum().sort_values(ascending=False).head(5).reset_index()
        top_products = top.to_dict(orient='records')

    return jsonify({
        "total_sales_revenue": total_sales_revenue,
        "total_purchase_expenditure": total_purchase_expenditure,
        "total_sales_transactions": total_sales_transactions,
        "most_sold_product": most_sold,
        "least_sold_product": least_sold,
        "monthly_trend": monthly_trend,
        "top_products": top_products
    }), 200


# ---------------- SUPPLIERS ----------------
@app.route('/suppliers', methods=['POST'])
def add_supplier():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    contact_person = (data.get('contact_person') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()
    address = (data.get('address') or '').strip()

    if not name:
        return jsonify({"error": "Supplier Name is required"}), 400
    if email and not is_valid_email_format(email):
        return jsonify({"error": "Enter a valid email address"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES (%s, %s, %s, %s, %s)",
            (name, contact_person, phone, email, address)
        )
        conn.commit()
        return jsonify({"message": "supplier added", "supplier_id": cursor.lastrowid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()


@app.route('/suppliers', methods=['GET'])
def get_suppliers():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM suppliers")
    suppliers = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(suppliers), 200


@app.route('/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    username = request.headers.get('X-Username')
    if not is_admin(username):
        return jsonify({"error": "Admin access required"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM suppliers WHERE supplier_id=%s", (supplier_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "supplier deleted"}), 200


# ---------------- POS WEBHOOK (extension feature) ----------------
@app.route('/webhook/sale', methods=['POST'])
def webhook_sale():
    api_key = request.headers.get('X-API-Key')
    if api_key != os.getenv('POS_API_KEY'):
        return jsonify({"error": "invalid or missing API key"}), 401

    data = request.get_json()
    sku = data.get('sku')
    quantity = data.get('quantity')
    t_date = data.get('transaction_date')

    if not sku or not quantity or not t_date:
        return jsonify({"error": "sku, quantity, transaction_date are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT product_id FROM products WHERE sku = %s", (sku,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        conn.close()
        return jsonify({"error": f"no product found with SKU '{sku}'"}), 404

    product_id = product['product_id']
    cursor2 = conn.cursor()
    try:
        cursor2.execute(
            "INSERT INTO transactions (product_id, type, quantity, transaction_date, notes) VALUES (%s, %s, %s, %s, %s)",
            (product_id, 'sale', quantity, t_date, 'via POS webhook')
        )
        new_id = cursor2.lastrowid
        cursor2.execute("UPDATE products SET quantity = quantity - %s WHERE product_id = %s", (quantity, product_id))
        conn.commit()
        return jsonify({"message": "sale received from POS", "transaction_id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor2.close()
        cursor.close()
        conn.close()


# ---------------- PAYMENTS ----------------
@app.route('/payments', methods=['POST'])
def make_payment():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    payment_method = data.get('payment_method')
    payment_mode = data.get('payment_mode')
    payment_reference = data.get('payment_reference')
    payment_date = data.get('payment_date')

    if not product_id or not quantity or not payment_method or not payment_date:
        return jsonify({"error": "product_id, quantity, payment_method, payment_date are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT price FROM products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()
    if not product:
        cursor.close()
        conn.close()
        return jsonify({"error": "product not found"}), 404

    total_amount = float(product['price']) * int(quantity)

    cursor2 = conn.cursor()
    try:
        cursor2.execute(
            "INSERT INTO payments (product_id, quantity, total_amount, payment_method, payment_mode, payment_reference, status, payment_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (product_id, quantity, total_amount, payment_method, payment_mode, payment_reference, 'Success', payment_date)
        )
        payment_id = cursor2.lastrowid

        cursor2.execute(
            "INSERT INTO transactions (product_id, type, quantity, transaction_date, notes, payment_method) VALUES (%s,%s,%s,%s,%s,%s)",
            (product_id, 'purchase', quantity, payment_date, f"Paid via {payment_method}", payment_method)
        )
        cursor2.execute("UPDATE products SET quantity = quantity + %s WHERE product_id = %s", (quantity, product_id))

        conn.commit()
        return jsonify({"message": "payment successful", "payment_id": payment_id, "total_amount": total_amount}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        cursor2.close()
        cursor.close()
        conn.close()


@app.route('/payments', methods=['GET'])
def get_payments():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT pay.payment_id, p.name AS product_name, pay.quantity, pay.total_amount,
               pay.payment_method, pay.payment_mode, pay.payment_reference, pay.status, pay.payment_date
        FROM payments pay
        JOIN products p ON pay.product_id = p.product_id
        ORDER BY pay.payment_date DESC, pay.payment_id DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)