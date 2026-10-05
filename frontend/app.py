import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import io

try:
    from streamlit_lottie import st_lottie
    LOTTIE_AVAILABLE = True
except ImportError:
    LOTTIE_AVAILABLE = False

API_URL = "http://localhost:5000"

# Paste a public Lottie JSON URL here (from lottiefiles.com -> pick an
# animation -> copy its "Lottie JSON" link). If this is left blank, or
# there's no internet, the app just skips the animation — nothing breaks.
LOTTIE_WAREHOUSE_URL = ""

st.set_page_config(page_title="Smart IMS", page_icon="📦", layout="wide")


# ============================================================
# CENTRALIZED API HELPER
# ============================================================
def api_request(method, endpoint, json_body=None, params=None, headers=None, timeout=6):
    try:
        response = requests.request(
            method, f"{API_URL}{endpoint}", json=json_body, params=params,
            headers=headers, timeout=timeout
        )
    except requests.exceptions.RequestException:
        return False, {"error": "⚠️ Could not reach the backend server. Make sure it's running on port 5000."}

    if response.status_code >= 400:
        try:
            return False, response.json()
        except ValueError:
            return False, {"error": f"Server returned an unexpected error (status {response.status_code})."}

    try:
        return True, response.json()
    except ValueError:
        return False, {"error": "Server returned a non-JSON response."}


def api_get(endpoint, params=None, default=None):
    ok, data = api_request("GET", endpoint, params=params)
    if not ok:
        st.error(data.get("error", "Request failed"))
        return default if default is not None else []
    return data


def admin_headers():
    return {"X-Username": st.session_state.get("username", "")}


@st.cache_data(ttl=3, show_spinner=False)
def load_lottie(url):
    if not url:
        return None
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.RequestException:
        pass
    return None


def show_lottie_if_available(height=180, key=None):
    if not LOTTIE_AVAILABLE or not LOTTIE_WAREHOUSE_URL:
        return
    anim = load_lottie(LOTTIE_WAREHOUSE_URL)
    if anim:
        st_lottie(anim, height=height, key=key)


def stock_status(quantity, reorder_level):
    if quantity <= 0:
        return "🔴 Out of Stock"
    elif quantity <= reorder_level:
        return "🟠 Low Stock"
    else:
        return "🟢 In Stock"


def to_csv_bytes(records):
    return pd.DataFrame(records).to_csv(index=False).encode("utf-8")


def to_excel_bytes(records):
    buf = io.BytesIO()
    pd.DataFrame(records).to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
div[data-testid="stMetric"] {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    border-radius: 12px;
    padding: 10px;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-6px);
    box-shadow: 0 10px 24px rgba(59, 110, 245, 0.35);
}
.stButton > button {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stButton > button:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 18px rgba(59, 110, 245, 0.45);
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    border-radius: 12px;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.25);
}
.badge-insufficient {
    background: #5B6472; color: white; padding: 4px 12px;
    border-radius: 999px; font-size: 0.85rem; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None
for key in ["last_product_msg", "last_txn_msg", "last_payment_msg", "last_supplier_msg"]:
    if key not in st.session_state:
        st.session_state[key] = None


def login_page():
    st.title("📦 Smart IMS — Login")
    show_lottie_if_available(height=200, key="login_lottie")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                ok, data = api_request("POST", "/login", {"username": username, "password": password})
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.role = data["role"]
                    st.session_state.username = username
                    st.toast(f"Welcome back, {username}! 👋", icon="🎉")
                    st.rerun()
                else:
                    st.error(data.get("error", "Invalid username or password"))

    with tab2:
        st.info("New accounts are created as staff users. Admin access is managed by the system administrator.")
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            submitted = st.form_submit_button("Register")
            if submitted:
                if not new_username.strip() or not new_password:
                    st.error("Username and password are both required.")
                else:
                    ok, data = api_request("POST", "/register", {
                        "username": new_username.strip(), "password": new_password, "role": "staff"
                    })
                    if ok:
                        st.toast("Account created!", icon="✅")
                        st.success("Account created! Go to the Login tab.")
                    else:
                        st.error(data.get("error", "Registration failed"))


if not st.session_state.logged_in:
    login_page()
else:
    st.sidebar.write(f"Logged in as **{st.session_state.username}** ({st.session_state.role})")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📦 Smart IMS")
    st.sidebar.markdown("*AI-powered inventory*")
    st.sidebar.markdown("---")

    page = st.sidebar.radio("Navigate", [
        "📊 Dashboard", "📦 Products", "➕ Add Product",
        "🔁 Record Transaction", "💳 Payments", "📈 Forecast",
        "🤖 AI Alerts", "🏢 Suppliers"
    ])

    # ============================================================
    # DASHBOARD
    # ============================================================
    if page == "📊 Dashboard":
        st.title("Dashboard")
        show_lottie_if_available(height=140, key="dash_lottie")

        products = api_get("/products")
        low_stock = api_get("/products/low-stock")
        summary = api_get("/dashboard/sales-summary", default={})
        anomalies_count = len(api_get("/anomalies"))

        total_products = len(products)
        total_quantity = sum(p.get("quantity", 0) for p in products)
        total_valuation = sum(float(p.get("price", 0)) * p.get("quantity", 0) for p in products)
        low_stock_count = len(low_stock)

        # Row 1 — top-level KPIs
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Products", total_products)
        k2.metric("Stock Quantity", total_quantity)
        k3.metric("Inventory Value", f"₹{total_valuation:,.0f}")
        k4.metric("Total Sales Revenue", f"₹{summary.get('total_sales_revenue', 0):,.0f}")
        k5.metric("Low Stock Alerts", low_stock_count, delta=None if low_stock_count == 0 else "needs attention", delta_color="inverse")

        # Row 2 — Monthly sales trend | Stock by category
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.markdown("#### Monthly Sales Trend")
            trend = summary.get("monthly_trend", [])
            if trend:
                tdf = pd.DataFrame(trend)
                fig = px.line(tdf, x="month_label", y="quantity", markers=True,
                               labels={"month_label": "Month", "quantity": "Units Sold"})
                fig.update_layout(margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True, key="dash_trend_chart")
            else:
                st.info("Not enough sales history yet for a trend line.")
        with r2c2:
            st.markdown("#### Stock by Category")
            if products:
                cat_df = pd.DataFrame(products).groupby("category", dropna=False)["quantity"].sum().reset_index()
                cat_df["category"] = cat_df["category"].fillna("Uncategorized")
                fig = px.bar(cat_df, x="category", y="quantity", color="category",
                             labels={"quantity": "Total Quantity", "category": "Category"})
                fig.update_layout(showlegend=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True, key="dash_category_chart")
            else:
                st.info("No products yet.")

        # Row 3 — Top 5 products | Low stock table
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            st.markdown("#### Top 5 Products Sold")
            top_products = summary.get("top_products", [])
            if top_products:
                tp_df = pd.DataFrame(top_products)
                fig = px.bar(tp_df, x="name", y="quantity", labels={"name": "Product", "quantity": "Units Sold"})
                fig.update_layout(margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True, key="dash_top_products_chart")
            else:
                st.info("No sales recorded yet.")
        with r3c2:
            st.markdown("#### Low Stock Products")
            if low_stock:
                st.dataframe(pd.DataFrame(low_stock), use_container_width=True, hide_index=True)
            else:
                st.success("All products are sufficiently stocked.")

        # Row 4 — AI forecast summary | AI anomaly summary
        r4c1, r4c2 = st.columns(2)
        with r4c1:
            st.markdown("#### AI Forecast Summary")
            forecast_data = api_get("/forecast")
            order_more = [f for f in forecast_data if f.get("recommendation") == "order more"]
            if order_more:
                st.warning(f"📈 {len(order_more)} product(s) predicted to need more stock next month.")
                st.caption(", ".join(f["name"] for f in order_more[:5]))
            else:
                st.info("No products currently flagged for increased demand.")
            st.caption("See the Forecast page for full detail per product.")
        with r4c2:
            st.markdown("#### AI Anomaly Alerts")
            if anomalies_count:
                st.error(f"🤖 {anomalies_count} unusual transaction(s) detected.")
            else:
                st.success("No unusual transaction patterns detected.")
            st.caption("See the AI Alerts page for full detail.")

        if summary.get("most_sold_product"):
            st.caption(
                f"This month — Most sold: **{summary['most_sold_product']}** · "
                f"Least sold: **{summary.get('least_sold_product', '—')}** · "
                f"Total purchase expenditure: ₹{summary.get('total_purchase_expenditure', 0):,.0f}"
            )

    # ============================================================
    # PRODUCTS
    # ============================================================
    elif page == "📦 Products":
        st.title("All Products")
        products = api_get("/products")

        search = st.text_input("🔍 Search products (by name, category, or SKU)")
        if search:
            s = search.lower()
            products = [p for p in products if s in str(p.get("name", "")).lower()
                        or s in str(p.get("category", "")).lower()
                        or s in str(p.get("sku", "")).lower()]

        if products:
            display_rows = []
            for p_ in products:
                row = dict(p_)
                row["status"] = stock_status(p_.get("quantity", 0), p_.get("reorder_level", 0))
                display_rows.append(row)
            df = pd.DataFrame(display_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                st.download_button("⬇️ Download CSV", to_csv_bytes(display_rows), "products.csv", "text/csv")
            with c2:
                st.download_button("⬇️ Download Excel", to_excel_bytes(display_rows), "products.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No products match your search." if search else "No products yet.")

        if st.session_state.role == "admin" and products:
            st.subheader("Delete a Product (Admin Only)")
            product_names = {p["name"]: p["product_id"] for p in products}
            to_delete = st.selectbox("Select product to delete", list(product_names.keys()))
            if st.button("Delete Product"):
                ok, data = api_request("DELETE", f"/products/{product_names[to_delete]}", headers=admin_headers())
                if ok:
                    st.toast(f"{to_delete} deleted.", icon="🗑️")
                    st.rerun()
                else:
                    st.error(data.get("error", "Failed to delete product."))
        elif st.session_state.role != "admin":
            st.caption("Only admins can delete products.")

    # ============================================================
    # ADD / RESTOCK PRODUCT
    # ============================================================
    elif page == "➕ Add Product":
        st.title("Add / Restock Product")
        st.caption("Pick a category and product from what already exists to restock it, or add something brand new.")

        if st.session_state.last_product_msg:
            st.success(st.session_state.last_product_msg)

        products = api_get("/products")
        suppliers = api_get("/suppliers")

        existing_categories = sorted({p["category"] for p in products if p.get("category")})
        supplier_names = sorted({s["name"] for s in suppliers if s.get("name")})

        NEW_CATEGORY = "➕ New Category"
        NEW_PRODUCT = "➕ New Product"
        NEW_SUPPLIER = "➕ New Supplier"

        category_choice = st.selectbox("Category", [NEW_CATEGORY] + existing_categories)

        if category_choice == NEW_CATEGORY:
            category = st.text_input("New Category Name")
            products_in_category = []
        else:
            category = category_choice
            products_in_category = [p for p in products if p.get("category") == category]

        product_name_options = [NEW_PRODUCT] + sorted({p["name"] for p in products_in_category})
        product_choice = st.selectbox("Product Name", product_name_options)

        existing_product = None
        if product_choice != NEW_PRODUCT:
            existing_product = next((p for p in products_in_category if p["name"] == product_choice), None)

        if existing_product:
            st.info(
                f"**{existing_product['name']}** already exists — SKU `{existing_product['sku']}`, "
                f"current stock **{existing_product['quantity']}**, price ₹{existing_product['price']}."
            )
            with st.form("restock_form", clear_on_submit=False):
                price = st.number_input("Price", min_value=0.0, step=0.5, value=float(existing_product["price"]))
                add_quantity = st.number_input("Additional Quantity to Add", min_value=0, step=1, value=0)
                reorder_level = st.number_input("Reorder Level", min_value=0, step=1, value=int(existing_product["reorder_level"]))
                supplier_options = [NEW_SUPPLIER] + supplier_names
                default_idx = supplier_options.index(existing_product["supplier"]) if existing_product.get("supplier") in supplier_options else 0
                supplier_choice = st.selectbox("Supplier", supplier_options, index=default_idx)
                supplier = st.text_input("New Supplier Name") if supplier_choice == NEW_SUPPLIER else supplier_choice
                submitted = st.form_submit_button("Update Stock")

                if submitted:
                    missing_fields = []
                    if not supplier or not supplier.strip():
                        missing_fields.append("Supplier")
                    if price <= 0:
                        missing_fields.append("Price must be greater than ₹0")

                    if missing_fields:
                        for field in missing_fields:
                            st.error(f"Please enter: {field}")
                    else:
                        new_quantity = existing_product["quantity"] + add_quantity
                        ok, data = api_request("PUT", f"/products/{existing_product['product_id']}", {
                            "name": existing_product["name"], "category": category, "price": price,
                            "quantity": new_quantity, "reorder_level": reorder_level, "supplier": supplier.strip()
                        })
                        if ok:
                            st.session_state.last_product_msg = f"✅ {existing_product['name']} restocked! New quantity: {new_quantity}"
                            st.toast("Stock updated!", icon="📦")
                            st.rerun()
                        else:
                            st.error(data.get("error", "Failed to update product"))

        else:
            with st.form("new_product_form", clear_on_submit=True):
                name = st.text_input("Product Name")
                sku = st.text_input("SKU")
                price = st.number_input("Price", min_value=0.0, step=0.5)
                quantity = st.number_input("Initial Quantity", min_value=0, step=1)
                reorder_level = st.number_input("Reorder Level", min_value=0, step=1, value=10)
                supplier_choice = st.selectbox("Supplier", [NEW_SUPPLIER] + supplier_names)
                supplier = st.text_input("New Supplier Name") if supplier_choice == NEW_SUPPLIER else supplier_choice
                submitted = st.form_submit_button("Add Product")

                if submitted:
                    missing_fields = []
                    if not category or not category.strip():
                        missing_fields.append("Category")
                    if not name or not name.strip():
                        missing_fields.append("Product Name")
                    if not sku or not sku.strip():
                        missing_fields.append("SKU")
                    if not supplier or not supplier.strip():
                        missing_fields.append("Supplier")
                    if price <= 0:
                        missing_fields.append("Price must be greater than ₹0")

                    if missing_fields:
                        for field in missing_fields:
                            st.error(f"Please enter: {field}")
                    else:
                        ok, data = api_request("POST", "/products", {
                            "name": name.strip(), "category": category.strip(), "sku": sku.strip().upper(),
                            "price": price, "quantity": quantity,
                            "reorder_level": reorder_level, "supplier": supplier.strip()
                        })
                        if ok:
                            st.session_state.last_product_msg = f"✅ {name} added successfully!"
                            st.toast("Product added!", icon="📦")
                            st.rerun()
                        else:
                            st.error(data.get("error", "Failed to add product"))

    # ============================================================
    # RECORD TRANSACTION
    # ============================================================
    elif page == "🔁 Record Transaction":
        st.title("Record Purchase / Sale")
        st.caption("For quick stock adjustments without a formal payment record. To pay a supplier for a new order, use the Payments page instead.")

        if st.session_state.last_txn_msg:
            st.success(st.session_state.last_txn_msg)

        products = api_get("/products")
        product_names = {p["name"]: p for p in products}

        if not product_names:
            st.info("Add a product first.")
        else:
            selected = st.selectbox("Product", list(product_names.keys()))
            selected_product = product_names[selected]
            t_type = st.radio("Transaction Type", ["sale", "purchase"])

            if t_type == "purchase":
                supplier_label = selected_product.get("supplier") or "no supplier on file"
                st.caption(f"Paying supplier: **{supplier_label}**")
            else:
                st.caption(f"Current stock: **{selected_product.get('quantity', 0)}**")

            with st.form("txn_form", clear_on_submit=True):
                qty = st.number_input("Quantity", min_value=1, step=1)
                t_date = st.date_input("Date", value=date.today())
                payment_method = st.selectbox("Payment Method", ["Online", "Cash on Delivery"]) if t_type == "purchase" else None
                notes = st.text_input("Notes (optional)")
                submitted = st.form_submit_button("Record Transaction")

                if submitted:
                    payload = {
                        "product_id": selected_product.get("product_id"),
                        "type": t_type, "quantity": qty,
                        "transaction_date": str(t_date), "notes": notes,
                    }
                    if t_type == "purchase":
                        payload["payment_method"] = payment_method

                    ok, data = api_request("POST", "/transactions", payload)
                    if ok:
                        st.session_state.last_txn_msg = f"✅ Recorded {t_type} of {qty} × {selected} on {t_date}."
                        st.toast("Transaction recorded!", icon="✅")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(data.get("error", "Failed to record transaction"))

    # ============================================================
    # PAYMENTS
    # ============================================================
    elif page == "💳 Payments":
        st.title("Payments")
        st.caption("Place and pay for a supplier order. Only a masked reference (last 4 digits or UPI ID) is ever stored — never a full card number.")

        if st.session_state.last_payment_msg:
            st.success(st.session_state.last_payment_msg)

        tab_new, tab_history = st.tabs(["New Payment", "Payment History"])

        with tab_new:
            products = api_get("/products")
            product_names = {p["name"]: p for p in products}

            if not product_names:
                st.info("Add a product first before placing an order.")
            else:
                selected = st.selectbox("Product", list(product_names.keys()), key="pay_product")
                selected_product = product_names[selected]
                price = float(selected_product["price"])
                supplier_label = selected_product.get("supplier") or "no supplier on file"
                st.caption(f"Supplier: **{supplier_label}** · Unit price: ₹{price}")

                payment_method = st.radio("Payment Method *", ["Online", "Cash on Delivery"], key="pay_method")
                payment_mode = None
                if payment_method == "Online":
                    payment_mode = st.radio("Pay via *", ["Card", "UPI"], key="pay_mode")

                with st.form("payment_form", clear_on_submit=True):
                    quantity = st.number_input("Quantity to Order", min_value=1, step=1, value=1)
                    total_amount = price * quantity
                    st.metric("Total Amount to Pay", f"₹{total_amount:,.2f}")

                    cardholder, last4, upi_id = None, None, None
                    if payment_method == "Online" and payment_mode == "Card":
                        cardholder = st.text_input("Cardholder Name *")
                        last4 = st.text_input("Card Number — last 4 digits only *", max_chars=4,
                                               help="Only the last 4 digits are recorded — never the full card number.")
                    elif payment_method == "Online" and payment_mode == "UPI":
                        upi_id = st.text_input("UPI ID *", placeholder="name@bank")

                    pay_date = st.date_input("Payment Date", value=date.today())
                    submit_label = "Pay Now" if payment_method == "Online" else "Confirm Cash on Delivery"
                    submitted = st.form_submit_button(submit_label, type="primary")

                    if submitted:
                        missing = []
                        payment_reference = None
                        if payment_method == "Online":
                            if payment_mode == "Card":
                                if not cardholder or not cardholder.strip():
                                    missing.append("Cardholder Name")
                                if not last4 or len(last4) != 4 or not last4.isdigit():
                                    missing.append("Card last 4 digits (must be exactly 4 numbers)")
                                else:
                                    payment_reference = f"Card ending in {last4}"
                            else:
                                if not upi_id or "@" not in upi_id:
                                    missing.append("A valid UPI ID (e.g. name@bank)")
                                else:
                                    payment_reference = upi_id

                        if missing:
                            for m in missing:
                                st.error(m)
                        else:
                            ok, data = api_request("POST", "/payments", {
                                "product_id": selected_product["product_id"],
                                "quantity": quantity,
                                "payment_method": payment_method,
                                "payment_mode": payment_mode,
                                "payment_reference": payment_reference,
                                "payment_date": str(pay_date),
                            })
                            if ok:
                                st.session_state.last_payment_msg = (
                                    f"✅ Paid ₹{data['total_amount']:,.2f} for {quantity} × {selected} "
                                    f"(Payment ID: {data['payment_id']}). Stock updated."
                                )
                                st.toast("Payment successful! 🎉", icon="💳")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(data.get("error", "Payment failed"))

        with tab_history:
            payments = api_get("/payments")
            search = st.text_input("🔍 Search payment history (by product or method)")
            if search and payments:
                s = search.lower()
                payments = [pay for pay in payments if s in str(pay.get("product_name", "")).lower()
                            or s in str(pay.get("payment_method", "")).lower()]

            if payments:
                st.dataframe(pd.DataFrame(payments), use_container_width=True, hide_index=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button("⬇️ Download CSV", to_csv_bytes(payments), "payment_history.csv", "text/csv")
                with c2:
                    st.download_button("⬇️ Download Excel", to_excel_bytes(payments), "payment_history.xlsx",
                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("No payments match your search." if search else "No payments recorded yet.")

    # ============================================================
    # FORECAST
    # ============================================================
    elif page == "📈 Forecast":
        st.title("Seasonal Demand Forecast")
        st.caption(
            "Combines a seasonal-average baseline with a scikit-learn linear regression "
            "trend signal, and recommends how much to reorder for each product."
        )
        forecast_data = api_get("/forecast")

        for item in forecast_data:
            with st.container(border=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.subheader(item["name"])
                    if item["trend"] == "insufficient data":
                        st.markdown('<span class="badge-insufficient">⚠️ Insufficient Data</span>', unsafe_allow_html=True)
                    else:
                        st.caption(item["trend"])
                        if item["recommendation"] == "order more":
                            st.error(f"📈 {item['recommendation'].upper()}")
                        elif item["recommendation"] == "order less":
                            st.warning(f"📉 {item['recommendation'].upper()}")
                        else:
                            st.info(f"➡️ {item['recommendation'].upper()}")

                        st.metric("Recommended Quantity to Order", f"{item.get('recommended_order_quantity', 0)} units")
                        st.caption(f"Current stock: {item.get('current_stock', 0)} units")

                with col2:
                    if item["trend"] != "insufficient data":
                        fig = go.Figure(data=[
                            go.Bar(name="Avg Monthly Sales", x=["Comparison"], y=[item["avg_monthly_sales"]]),
                            go.Bar(name="Predicted Next Month", x=["Comparison"], y=[item["predicted_next_month_sales"]]),
                        ])
                        fig.update_layout(barmode="group", height=200, margin=dict(t=10, b=10, l=10, r=10),
                                           showlegend=True, legend=dict(orientation="h", y=-0.2))
                        st.plotly_chart(fig, use_container_width=True, key=f"forecast_chart_{item['product_id']}")
                        if item.get("trend_model_prediction") is not None:
                            st.caption(f"Linear regression trend signal: {item['trend_model_prediction']} units")
                    else:
                        st.write("Not enough sales history yet to chart a comparison.")

    # ============================================================
    # AI ALERTS (anomaly detection)
    # ============================================================
    elif page == "🤖 AI Alerts":
        st.title("🤖 AI Sales Alerts")
        st.caption("Identifies unusual sales or purchase patterns that may need review, using IsolationForest.")

        anomalies = api_get("/anomalies")

        if anomalies:
            anomaly_df = pd.DataFrame(anomalies)
            total_alerts = len(anomaly_df)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Unusual Transactions Detected", total_alerts)
            with col2:
                high_risk_count = len(anomaly_df[anomaly_df["risk_level"] == "High"])
                st.metric("High-Risk Alerts", high_risk_count)

            st.subheader("Transactions Requiring Review")
            st.dataframe(anomaly_df, use_container_width=True, hide_index=True)

            fig = px.scatter(
                anomaly_df, x="quantity", y="amount", color="risk_level",
                hover_data=["product_name", "transaction_date"],
                title="Unusual Transaction Patterns"
            )
            st.plotly_chart(fig, use_container_width=True, key="anomaly_scatter_chart")

            st.warning(
                "An alert does not automatically mean fraud. It may represent a bulk order, "
                "data-entry issue, special sale, or unusual business activity."
            )
        else:
            st.success("No unusual transaction patterns were detected.")
            st.caption("Note: at least 10 recorded transactions are needed before this detector has enough data to run.")

    # ============================================================
    # SUPPLIERS
    # ============================================================
    elif page == "🏢 Suppliers":
        st.title("Suppliers")

        if st.session_state.last_supplier_msg:
            st.success(st.session_state.last_supplier_msg)

        with st.form("supplier_form", clear_on_submit=True):
            st.subheader("Add New Supplier")
            s_name = st.text_input("Supplier Name")
            s_contact = st.text_input("Contact Person")
            s_phone = st.text_input("Phone")
            s_email = st.text_input("Email")
            s_address = st.text_input("Address")
            submitted = st.form_submit_button("Add Supplier")

            if submitted:
                if not s_name or not s_name.strip():
                    st.error("Supplier Name is required.")
                elif s_email and "@" not in s_email:
                    st.error("Enter a valid email address.")
                else:
                    ok, data = api_request("POST", "/suppliers", {
                        "name": s_name.strip(), "contact_person": s_contact.strip(),
                        "phone": s_phone.strip(), "email": s_email.strip(), "address": s_address.strip()
                    })
                    if ok:
                        st.session_state.last_supplier_msg = f"✅ {s_name} added to suppliers."
                        st.toast("Supplier added!", icon="🏢")
                        st.rerun()
                    else:
                        st.error(data.get("error", "Failed to add supplier"))

        st.divider()
        st.subheader("All Suppliers")
        suppliers = api_get("/suppliers")
        search = st.text_input("🔍 Search suppliers")
        if search and suppliers:
            s = search.lower()
            suppliers = [sup for sup in suppliers if s in str(sup.get("name", "")).lower()]

        if suppliers:
            st.dataframe(pd.DataFrame(suppliers), use_container_width=True, hide_index=True)

            if st.session_state.role == "admin":
                st.subheader("Delete a Supplier (Admin Only)")
                supplier_names = {s["name"]: s["supplier_id"] for s in suppliers}
                to_delete = st.selectbox("Select supplier to delete", list(supplier_names.keys()))
                if st.button("Delete Supplier"):
                    ok, data = api_request("DELETE", f"/suppliers/{supplier_names[to_delete]}", headers=admin_headers())
                    if ok:
                        st.toast(f"{to_delete} deleted.", icon="🗑️")
                        st.rerun()
                    else:
                        st.error(data.get("error", "Failed to delete supplier."))
        else:
            st.info("No suppliers match your search." if search else "No suppliers added yet.")