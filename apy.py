import streamlit as st
import mysql.connector
import hashlib
from datetime import datetime, timedelta

# ---------------- DB CONNECTION ----------------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Madhu17!",
        database="book_club_db",
        autocommit=True
    )

conn = get_connection()
c = conn.cursor(dictionary=True)

# ---------------- AUTO RECONNECT ----------------
def check_connection():
    global conn, c
    try:
        conn.ping(reconnect=True, attempts=3, delay=2)
    except:
        conn = get_connection()
        c = conn.cursor(dictionary=True)

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- HASH ----------------
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

# ---------------- AUTH ----------------
def register(u, e, p):
    check_connection()
    try:
        c.execute(
            "INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",
            (u, e, hash_password(p))
        )
        return True
    except:
        return False

def login(u, p):
    check_connection()
    c.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (u, hash_password(p))
    )
    return c.fetchone()

# ---------------- BOOK ----------------
def add_book(t, a, g, q):
    check_connection()
    c.execute(
        "INSERT INTO books(title,author,genre,quantity) VALUES(%s,%s,%s,%s)",
        (t, a, g, q)
    )

def get_books():
    check_connection()
    c.execute("SELECT * FROM books")
    return c.fetchall()

# ---------------- DELETE BOOK ----------------
def delete_book(book_id):
    check_connection()

    # check if issued
    c.execute("""
    SELECT * FROM transactions 
    WHERE book_id=%s AND status='issued'
    """, (book_id,))
    
    if c.fetchone():
        return "issued"

    # delete related data
    c.execute("DELETE FROM reviews WHERE book_id=%s", (book_id,))
    c.execute("DELETE FROM transactions WHERE book_id=%s", (book_id,))
    c.execute("DELETE FROM books WHERE id=%s", (book_id,))
    
    return "deleted"

# ---------------- ISSUE ----------------
def issue(uid, bid):
    check_connection()
    c.execute("SELECT quantity FROM books WHERE id=%s", (bid,))
    b = c.fetchone()

    if b and b["quantity"] > 0:
        issue_date = datetime.now().date()
        due_date = issue_date + timedelta(days=7)

        c.execute("""
        INSERT INTO transactions(user_id,book_id,issue_date,due_date,status)
        VALUES(%s,%s,%s,%s,'issued')
        """, (uid, bid, issue_date, due_date))

        c.execute("UPDATE books SET quantity=quantity-1 WHERE id=%s", (bid,))
        return True
    return False

# ---------------- RETURN ----------------
def return_book(tid, bid):
    check_connection()
    c.execute("SELECT due_date FROM transactions WHERE id=%s", (tid,))
    data = c.fetchone()

    if not data:
        return None

    today = datetime.now().date()
    fine = 0

    if data["due_date"] and today > data["due_date"]:
        fine = (today - data["due_date"]).days * 10

    c.execute("""
    UPDATE transactions
    SET return_date=%s, status='returned', fine=%s
    WHERE id=%s
    """, (today, fine, tid))

    c.execute("UPDATE books SET quantity=quantity+1 WHERE id=%s", (bid,))
    return fine

# ---------------- SEARCH ----------------
def search(k):
    check_connection()
    c.execute("""
    SELECT * FROM books
    WHERE title LIKE %s OR author LIKE %s
    """, ('%' + k + '%', '%' + k + '%'))
    return c.fetchall()

# ---------------- REVIEW ----------------
def add_review(bid, uid, review, rating):
    check_connection()
    c.execute("""
    INSERT INTO reviews(book_id,user_id,review,rating)
    VALUES(%s,%s,%s,%s)
    """, (bid, uid, review, rating))

def get_reviews(bid):
    check_connection()
    c.execute("SELECT review,rating FROM reviews WHERE book_id=%s", (bid,))
    return c.fetchall()

# ---------------- UI ----------------
st.title("📚 Book Club Management System")

# LOGIN / REGISTER
if not st.session_state.user:
    menu = st.sidebar.selectbox("Menu", ["Login", "Register"])

    if menu == "Register":
        u = st.text_input("Username")
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")

        if st.button("Register"):
            if register(u, e, p):
                st.success("Registered Successfully")
            else:
                st.error("Username exists")

    elif menu == "Login":
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            user = login(u, p)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid Login")

# AFTER LOGIN
else:
    user = st.session_state.user
    st.sidebar.write(f"👋 {user['username']}")

    choice = st.sidebar.selectbox(
        "Options",
        ["Search", "Available", "Issue", "Return", "Review", "Add Book", "Delete Book"]
    )

    # SEARCH
    if choice == "Search":
        k = st.text_input("Search Book")
        if st.button("Search"):
            for b in search(k):
                st.write(f"{b['title']} | {b['author']} | Qty:{b['quantity']}")

    # AVAILABLE
    elif choice == "Available":
        for b in get_books():
            st.write(f"{b['title']} | Available: {b['quantity']}")

    # ISSUE
    elif choice == "Issue":
        books = get_books()
        if books:
            book_dict = {f"{b['title']} (ID:{b['id']})": b['id'] for b in books}
            selected = st.selectbox("Select Book", list(book_dict.keys()))

            if st.button("Issue"):
                if issue(user['id'], book_dict[selected]):
                    st.success("Issued")
                else:
                    st.error("Not available")

    # RETURN
    elif choice == "Return":
        tid = st.number_input("Transaction ID", min_value=1)
        bid = st.number_input("Book ID", min_value=1)

        if st.button("Return"):
            fine = return_book(tid, bid)
            if fine is None:
                st.error("Invalid ID")
            elif fine > 0:
                st.warning(f"Fine ₹{fine}")
            else:
                st.success("Returned")

    # REVIEW
    elif choice == "Review":
        bid = st.number_input("Book ID", min_value=1)
        review = st.text_area("Review")
        rating = st.slider("Rating", 1, 5)

        if st.button("Submit"):
            add_review(bid, user['id'], review, rating)
            st.success("Added")

        for r in get_reviews(bid):
            st.write(f"⭐ {r['rating']} - {r['review']}")

    # ADD BOOK
    elif choice == "Add Book":
        title = st.text_input("Title")
        author = st.text_input("Author")
        genre = st.text_input("Genre")
        quantity = st.number_input("Quantity", min_value=1)

        if st.button("Add"):
            add_book(title, author, genre, quantity)
            st.success("Book Added")

    # DELETE BOOK
    elif choice == "Delete Book":
        books = get_books()
        if books:
            book_dict = {f"{b['title']} (ID:{b['id']})": b['id'] for b in books}
            selected = st.selectbox("Select Book", list(book_dict.keys()))

            if st.button("Delete"):
                result = delete_book(book_dict[selected])

                if result == "issued":
                    st.error("Cannot delete. Book is issued.")
                else:
                    st.success("Deleted successfully")