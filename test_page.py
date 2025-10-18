import streamlit as st
import mysql.connector
import pandas as pd
import bcrypt
from datetime import datetime


# --- Styling: skyblue background ---
st.markdown("""
<style>
.stApp {
background: linear-gradient(180deg, #E0F7FF 0%, #FFFFFF 100%);
}
.title {
text-align: center;
color: #0B5376;
font-size:36px;
font-weight:700;
padding-top: 10px;
padding-bottom: 10px;
}
.centered-box {
max-width:900px;
margin-left:auto;
margin-right:auto;
padding:12px;
background: rgba(255,255,255,0.6);
border-radius:12px;
box-shadow: 0 4px 20px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)


# ---------- CONFIG ----------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Bala",
    "database": "cqms",
}

# ---------- DB HELPERS ----------
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def create_sample_support_if_missing():
    """create a default support user (for demo) if not exists"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM userss WHERE role='support' LIMIT 1")
    if cur.fetchone() is None:
        pw = bcrypt.hashpw("support123".encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO userss (username, password_hash, role, email) VALUES (%s,%s,%s,%s)",
            ("support", pw, "support", "support@example.com"),
        )
        conn.commit()
    cur.close()
    conn.close()

# --- AUTHENTICATION ----------
def register_client(username, password, email, mobile):
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO userss (username, password_hash, role, email, mobile) VALUES (%s,%s,%s,%s,%s)",
            (username, pw_hash, "client", email, mobile),
        )
        conn.commit()
        st.success("Registration successful — you can now login.")
    except mysql.connector.Error as e:
        st.error(f"Registration failed: {e.msg}")
    finally:
        cur.close()
        conn.close()

def login(username, password, role):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT user_id, username, password_hash, role, email, mobile FROM userss WHERE username=%s AND role=%s", (username, role))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        return None
    stored_hash = user["password_hash"].encode()
    if bcrypt.checkpw(password.encode(), stored_hash):
        return user
    return None

# ---------- QUERIES ----------

def create_query(client_user_id, client_email, client_mobile, heading, description, screenshot_data=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO queriess (client_user_id, client_email, client_mobile,
                             query_heading, query_description, screenshot,
                             status, date_raised)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (client_user_id, client_email, client_mobile, heading, description,
         screenshot_data, "Open", datetime.now()),
    )
    conn.commit()
    cur.close()
    conn.close()





def get_queries_for_client(client_user_id):
    conn = get_db_connection()
    df = pd.read_sql("SELECT query_id, client_email, client_mobile, query_heading, query_description, status, close_message, date_raised, date_closed FROM queriess WHERE client_user_id=%s ORDER BY date_raised DESC", conn, params=(client_user_id,))
    conn.close()
    return df

def get_all_queries():
    conn = get_db_connection()
    df = pd.read_sql("SELECT q.query_id, u.username as client_username, q.client_email, q.client_mobile, q.query_heading, q.query_description, q.status, q.close_message, q.date_raised, q.date_closed FROM queriess q JOIN users u ON u.user_id=q.client_user_id ORDER BY q.date_raised DESC", conn)
    conn.close()
    return df

def support_update_status(query_id, new_status, close_message=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if new_status == "Closed":
        cur.execute("UPDATE queriess SET status=%s, close_message=%s, date_closed=%s WHERE query_id=%s", (new_status, close_message, datetime.now(), query_id))
    else:
        # clear close fields if reopened
        cur.execute("UPDATE queriess SET status=%s, close_message=NULL, date_closed=NULL WHERE query_id=%s", (new_status, query_id))
    conn.commit()
    cur.close()
    conn.close()



def update_client_query(query_id, client_user_id, new_heading, new_description):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Only allow the query's owner to update
        cur.execute(
            """
            UPDATE queriess
            SET query_heading=%s, query_description=%s, status='Open', date_closed=NULL, close_message=NULL
            WHERE query_id=%s AND client_user_id=%s
            """,
            (new_heading, new_description, query_id, client_user_id)
        )
        conn.commit()
        st.success("Your query has been updated and reopened.")
    except Exception as e:
        st.error(f"Failed to update your query: {e}")
    finally:
        cur.close()
        conn.close()



# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Client Query Management", layout="wide")
st.title("Client Query Management System")

# Ensure a support user exists for demo
create_sample_support_if_missing()


# Left: role selection
with st.sidebar:
    st.header("Login / Role")
    role = st.radio("I am a", ("client", "support"))
    if "user" not in st.session_state:
        st.session_state.user = None

if role == "client":
    st.subheader("Client — Login")
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username", key="client_login_user")
        password = st.text_input("Password", type="password", key="client_login_pass")
        if st.button("Login as Client"):
            user = login(username, password, "client")
            if user:
                st.session_state.user = user
                st.success(f"Welcome {user['username']} (client)") 
                
            else:
                st.error("Invalid client credentials.")
    with col2:
        st.markdown("### New user?")
        if st.button("Register new client"):
            st.session_state.show_register = True

    if st.session_state.get("show_register"):
        st.markdown("---")
        st.subheader("Client Registration")
        r_user = st.text_input("Choose username", key="reg_user")
        r_pass = st.text_input("Choose password", type="password", key="reg_pass")
        r_email = st.text_input("Email", key="reg_email")
        r_mobile = st.text_input("Mobile", key="reg_mobile")
        if st.button("Register"):
            if not r_user or not r_pass:
                st.error("Username and password are required.")
            else:
                register_client(r_user, r_pass, r_email, r_mobile)
                st.session_state.show_register = False

elif role == "support":
    st.subheader("Support — Login")
    s_user = st.text_input("Username", key="support_login_user")
    s_pass = st.text_input("Password", type="password", key="support_login_pass")
    if st.button("Login as Support"):
        user = login(s_user, s_pass, "support")
        if user:
            st.session_state.user = user
            st.success(f"Welcome {user['username']} (support)")
            
        else:
            st.error("Invalid support credentials.")

# If logged in, show appropriate dashboard
user = st.session_state.get("user")
if user:
    st.markdown("---")
    st.write(f"**Logged in as:** {user['username']} — **role:** {user['role']}")
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()

    if user['role'] == 'client':
        st.header("Client Dashboard")
        # Form to create a new query
        with st.form("new_query_form", clear_on_submit=True):
            st.subheader("Raise new query")
            q_heading = st.text_input("Heading")
            q_description = st.text_area("Description")
            uploaded_file = st.file_uploader("Upload a screenshot (optional)", type=["png", "jpg", "jpeg"])

            submitted = st.form_submit_button("Send Query")
            if submitted:
                if not q_heading.strip():
                    st.error("Heading is required.")
                else:
                    image_data = uploaded_file.read() if uploaded_file else None
                    create_query(user['user_id'], user.get('email'), user.get('mobile'),
                         q_heading, q_description, image_data)
                    st.success("Query submitted (status: Open).")

        st.subheader("Your queries")
        df = get_queries_for_client(user['user_id'])
        if df.empty:
            st.info("You have no queries yet.")
        else:
            # show with pandas display — interactive
            st.dataframe(df)

            # allow export to CSV using pandas
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, file_name="my_queries.csv", mime="text/csv")

    elif user['role'] == 'support':
        st.header("Support Dashboard")
        st.subheader("All queries")
        df = get_all_queries()
        if df.empty:
            st.info("No queries in the system.")
        else:
            st.dataframe(df)

            # Quick selection for an individual query
         #--   st.markdown("---")
            st.markdown("---")
            st.subheader("View query screenshot")

            qid_to_view = st.number_input("Enter Query ID to view image", min_value=1, step=1)
            if st.button("Show Image"):
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT screenshot FROM queriess WHERE query_id=%s", (qid_to_view,))
                row = cur.fetchone()
                cur.close()
                conn.close()

                if row and row[0]:
                    st.image(row[0], caption=f"Screenshot for Query ID {qid_to_view}", use_container_width=True)
                else:
                    st.info("No screenshot uploaded for this query.")
            st.subheader("Manage a query")
            qid = st.number_input("Query ID to manage", min_value=1, step=1)
            st.write("Select new status:")
            new_status = st.selectbox("Status", ("Open","In Progress","Closed"))
            close_msg = st.text_area("Close message (optional; used only when closing)", value="", height=80)

            if st.button("Update status"):
                try:
                    support_update_status(qid, new_status, close_msg if new_status == "Closed" else None)
                    st.success(f"Query {qid} marked as {new_status}.")
                except Exception as e:
                    st.error(f"Failed to update: {e}")

            # Summary metrics
            st.markdown("---")
            st.write("### Summary")
            counts = df['status'].value_counts().to_dict()
            col1, col2, col3 = st.columns(3)
            col1.metric("Open", counts.get("Open", 0))
            col2.metric("In Progress", counts.get("In Progress", 0))
            col3.metric("Closed", counts.get("Closed", 0))

            # Export all queries
            all_csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Export all queries", all_csv, file_name="all_queries.csv", mime="text/csv")