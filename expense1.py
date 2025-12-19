import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
from collections import defaultdict
import sqlite3
import os
import shutil
import csv
import hashlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- FIX: Register SQLite Adapter for Python 3.12+ ---
def adapt_datetime(ts):
    return ts.isoformat(" ")

sqlite3.register_adapter(datetime, adapt_datetime)

# --- UTILITY: Password Hashing ---
def hash_password(password, salt=None):
    if not salt:
        salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt + key

def verify_password(stored_password, provided_password):
    salt = stored_password[:32]
    stored_key = stored_password[32:]
    key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return key == stored_key

class DatabaseManager:
    def __init__(self):
        self.db_path = "expenseshare_final.db"
        self.connect()
        
    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            self.create_tables()
        except Exception as e:
            messagebox.showerror("Database Error", f"Error: {e}")
            
    def create_tables(self):
        cursor = self.connection.cursor()
        
        # Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB, 
                email TEXT,
                currency TEXT DEFAULT 'USD',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Groups Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups_table (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                color TEXT DEFAULT '#E3F2FD',
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)
        
        # Group Members
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups_table(group_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE(group_id, user_id)
            )
        """)
        
        # Expenses Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT DEFAULT 'General',
                receipt_path TEXT,
                payer_id INTEGER NOT NULL,
                group_id INTEGER,
                split_type TEXT DEFAULT 'equal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (payer_id) REFERENCES users(user_id),
                FOREIGN KEY (group_id) REFERENCES groups_table(group_id) ON DELETE SET NULL
            )
        """)
        
        # Expense Splits
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expense_splits (
                split_id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expenses(expense_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Settlements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settlements (
                settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                settled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                FOREIGN KEY (to_user_id) REFERENCES users(user_id)
            )
        """)
        
        # Friends
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (friend_id) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE(user_id, friend_id)
            )
        """)
        self.connection.commit()
        cursor.close()

    # --- Auth Methods ---
    def register_user(self, username, password, email=None, currency='USD'):
        try:
            cursor = self.connection.cursor()
            pwd_hash = hash_password(password)
            cursor.execute("INSERT INTO users (username, password_hash, email, currency) VALUES (?, ?, ?, ?)", 
                         (username, pwd_hash, email, currency))
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        except Exception as e:
            print(e)
            return None

    def login_user(self, username, password):
        cursor = self.connection.cursor()
        cursor.execute("SELECT user_id, username, password_hash, currency FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and user['password_hash']:
            if verify_password(user['password_hash'], password):
                return user
        return None

    # --- Data Methods ---
    def get_all_users(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT user_id, username FROM users ORDER BY username")
        return cursor.fetchall()

    def add_friend(self, user_id, friend_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)", (user_id, friend_id))
            cursor.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)", (friend_id, user_id))
            self.connection.commit()
            return True
        except: return False

    def get_friends(self, user_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username 
            FROM friends f JOIN users u ON f.friend_id = u.user_id 
            WHERE f.user_id = ? ORDER BY u.username
        """, (user_id,))
        return cursor.fetchall()

    def create_group(self, group_name, created_by, members, color):
        try:
            cursor = self.connection.cursor()
            cursor.execute("INSERT INTO groups_table (group_name, color, created_by) VALUES (?, ?, ?)", 
                         (group_name, color, created_by))
            gid = cursor.lastrowid
            for mid in members:
                cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", (gid, mid))
            self.connection.commit()
            return gid
        except: return None

    def get_user_groups(self, user_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.color 
            FROM groups_table g JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = ? ORDER BY g.created_at DESC
        """, (user_id,))
        return cursor.fetchall()

    def get_group_members(self, group_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = ? ORDER BY u.username
        """, (group_id,))
        return cursor.fetchall()

    def add_expense(self, description, amount, category, receipt_path, payer_id, group_id, split_type, splits):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO expenses (description, amount, category, receipt_path, payer_id, group_id, split_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (description, amount, category, receipt_path, payer_id, group_id, split_type))
            eid = cursor.lastrowid
            
            for uid, amt in splits.items():
                cursor.execute("INSERT INTO expense_splits (expense_id, user_id, amount) VALUES (?, ?, ?)", 
                             (eid, uid, amt))
            self.connection.commit()
            return eid
        except Exception as e:
            print(e)
            return None

    def get_user_expenses(self, user_id, limit=None):
        cursor = self.connection.cursor()
        query = """
            SELECT DISTINCT e.*, u.username as payer_name, g.group_name
            FROM expenses e
            JOIN users u ON e.payer_id = u.user_id
            LEFT JOIN groups_table g ON e.group_id = g.group_id
            LEFT JOIN expense_splits es ON e.expense_id = es.expense_id
            WHERE e.payer_id = ? OR es.user_id = ?
            ORDER BY e.created_at DESC
        """
        if limit: query += f" LIMIT {limit}"
        cursor.execute(query, (user_id, user_id))
        return [dict(row) for row in cursor.fetchall()]

    def get_group_expenses(self, group_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT e.*, u.username as payer_name
            FROM expenses e
            JOIN users u ON e.payer_id = u.user_id
            WHERE e.group_id = ?
            ORDER BY e.created_at DESC
        """, (group_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_monthly_summary(self, user_id):
        now = datetime.now()
        first_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        last_month = first_current - timedelta(days=1)
        first_prev = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        cursor = self.connection.cursor()
        
        def get_total(start, end):
            # Sum of shares (splits) where user is involved
            cursor.execute("""
                SELECT SUM(es.amount) 
                FROM expense_splits es
                JOIN expenses e ON es.expense_id = e.expense_id
                WHERE es.user_id = ? AND e.created_at BETWEEN ? AND ?
            """, (user_id, start, end))
            res = cursor.fetchone()[0]
            return res if res else 0.0

        current_total = get_total(first_current, now)
        prev_total = get_total(first_prev, first_current)
        return current_total, prev_total

    def get_category_breakdown(self, user_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT e.category, SUM(es.amount) as total
            FROM expense_splits es
            JOIN expenses e ON es.expense_id = e.expense_id
            WHERE es.user_id = ?
            GROUP BY e.category
        """, (user_id,))
        return {row['category']: row['total'] for row in cursor.fetchall()}

    def calculate_balances(self, user_id):
        # Simplified debt algorithm
        net = defaultdict(float)
        cursor = self.connection.cursor()
        
        # 1. Calculate raw net balances from expenses
        cursor.execute("SELECT e.payer_id, es.user_id, es.amount FROM expenses e JOIN expense_splits es ON e.expense_id = es.expense_id")
        for pid, uid, amt in cursor.fetchall():
            if pid == uid: continue
            net[pid] += amt
            net[uid] -= amt
            
        # 2. Adjust for settlements
        cursor.execute("SELECT from_user_id, to_user_id, amount FROM settlements")
        for fid, tid, amt in cursor.fetchall():
            net[fid] += amt
            net[tid] -= amt
            
        # 3. Simplify
        debtors = sorted([(k, v) for k, v in net.items() if v < -0.01], key=lambda x: x[1])
        creditors = sorted([(k, v) for k, v in net.items() if v > 0.01], key=lambda x: x[1], reverse=True)
        
        simplified = []
        i, j = 0, 0
        while i < len(debtors) and j < len(creditors):
            did, damt = debtors[i]
            cid, camt = creditors[j]
            amt = min(abs(damt), camt)
            simplified.append((did, cid, amt))
            
            damt += amt
            camt -= amt
            
            if abs(damt) < 0.01: i += 1
            else: debtors[i] = (did, damt)
            if abs(camt) < 0.01: j += 1
            else: creditors[j] = (cid, camt)
            
        # Filter for current user
        res = defaultdict(float)
        for f, t, a in simplified:
            if f == user_id: res[t] -= a  # I owe them
            elif t == user_id: res[f] += a # They owe me
        return res

    def settle_balance(self, from_id, to_id, amount):
        try:
            cursor = self.connection.cursor()
            cursor.execute("INSERT INTO settlements (from_user_id, to_user_id, amount) VALUES (?, ?, ?)", 
                         (from_id, to_id, amount))
            self.connection.commit()
            return True
        except: return False

    def close(self):
        if self.connection: self.connection.close()


class AuthWindow:
    def __init__(self, root, db_manager):
        self.root = root
        self.db = db_manager
        self.user_data = None
        
        self.root.title("ExpenseShare Pro - Login")
        self.center_window(400, 500)
        self.root.configure(bg="#F5F5F5")
        
        self.is_register = False
        self.create_ui()
        
    def center_window(self, w, h):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        
    def create_ui(self):
        for w in self.root.winfo_children(): w.destroy()
        
        frame = tk.Frame(self.root, bg="white", padx=30, pady=30, relief=tk.RIDGE, bd=1)
        frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        title = "Register" if self.is_register else "Login"
        tk.Label(frame, text=title, font=("Arial", 24, "bold"), bg="white", fg="#333").pack(pady=(0, 20))
        
        tk.Label(frame, text="Username", bg="white", fg="#666").pack(anchor="w")
        self.user_ent = tk.Entry(frame, font=("Arial", 12))
        self.user_ent.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(frame, text="Password", bg="white", fg="#666").pack(anchor="w")
        self.pass_ent = tk.Entry(frame, font=("Arial", 12), show="*")
        self.pass_ent.pack(fill=tk.X, pady=(0, 15))
        
        if self.is_register:
            tk.Label(frame, text="Currency", bg="white", fg="#666").pack(anchor="w")
            self.curr_var = tk.StringVar(value="USD")
            curr_cb = ttk.Combobox(frame, textvariable=self.curr_var, values=["USD", "EUR", "INR", "GBP", "JPY"], state="readonly")
            curr_cb.pack(fill=tk.X, pady=(0, 20))
            
            tk.Button(frame, text="Create Account", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), 
                     command=self.do_register, pady=10).pack(fill=tk.X)
            tk.Button(frame, text="Back to Login", bg="white", fg="#0288D1", bd=0, 
                     command=self.toggle_mode).pack(pady=10)
        else:
            tk.Button(frame, text="Login", bg="#0288D1", fg="white", font=("Arial", 11, "bold"), 
                     command=self.do_login, pady=10).pack(fill=tk.X, pady=(20, 10))
            tk.Button(frame, text="Create New Account", bg="white", fg="#4CAF50", bd=0, 
                     command=self.toggle_mode).pack()

    def toggle_mode(self):
        self.is_register = not self.is_register
        self.create_ui()
        
    def do_login(self):
        u = self.user_ent.get().strip()
        p = self.pass_ent.get().strip()
        if not u or not p: return messagebox.showerror("Error", "Required fields missing")
        
        user = self.db.login_user(u, p)
        if user:
            self.user_data = user
            self.root.destroy()
        else:
            messagebox.showerror("Error", "Invalid credentials")
            
    def do_register(self):
        u = self.user_ent.get().strip()
        p = self.pass_ent.get().strip()
        c = self.curr_var.get()
        if not u or not p: return messagebox.showerror("Error", "Required fields missing")
        
        uid = self.db.register_user(u, p, None, c)
        if uid:
            messagebox.showinfo("Success", "Account created! Please login.")
            self.toggle_mode()
        else:
            messagebox.showerror("Error", "Username already exists")


class ExpenseApp:
    def __init__(self, root, db, user_data):
        self.root = root
        self.db = db
        self.uid = user_data['user_id']
        self.uname = user_data['username']
        self.currency = user_data['currency']
        
        self.symbols = {'USD': '$', 'EUR': '€', 'INR': '₹', 'GBP': '£', 'JPY': '¥'}
        self.cur_sym = self.symbols.get(self.currency, '$')
        
        self.root.title(f"ExpenseShare Pro - {self.uname}")
        self.root.geometry("1280x800")
        
        if not os.path.exists("receipts"):
            os.makedirs("receipts")
            
        self.setup_styles()
        self.create_layout()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Card.TFrame", background="white", relief="ridge", borderwidth=1)
        
    def create_layout(self):
        sidebar = tk.Frame(self.root, bg="#2C3E50", width=220)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        tk.Label(sidebar, text=f"💰 ExpenseShare", font=("Arial", 16, "bold"), fg="white", bg="#2C3E50").pack(pady=30)
        
        self.nav_btns = {}
        opts = [("Dashboard", self.view_dashboard), ("Groups", self.view_groups), 
                ("Friends", self.view_friends), ("Activity", self.view_activity),
                ("Analytics", self.view_analytics)]
        
        for name, cmd in opts:
            btn = tk.Button(sidebar, text=f"  {name}", font=("Arial", 11), bg="#34495E", fg="white", bd=0, 
                          anchor="w", padx=20, pady=12, command=cmd, cursor="hand2")
            btn.pack(fill=tk.X, pady=2)
            self.nav_btns[name] = btn
            
        tk.Button(sidebar, text="  Logout", font=("Arial", 11), bg="#C0392B", fg="white", bd=0, 
                 anchor="w", padx=20, pady=12, command=self.root.destroy).pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        self.main_area = tk.Frame(self.root, bg="#F5F5F5")
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.view_dashboard()

    def clear_main(self):
        for w in self.main_area.winfo_children(): w.destroy()
        for b in self.nav_btns.values(): b.config(bg="#34495E")

    # --- VIEW: DASHBOARD ---
    def view_dashboard(self):
        self.clear_main()
        self.nav_btns["Dashboard"].config(bg="#1ABC9C")
        
        top = tk.Frame(self.main_area, bg="#F5F5F5")
        top.pack(fill=tk.X, padx=30, pady=20)
        tk.Label(top, text="Dashboard", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        
        tk.Button(top, text="+ Expense", bg="#0288D1", fg="white", font=("Arial", 10, "bold"), 
                 padx=15, pady=8, bd=0, command=self.open_add_expense).pack(side=tk.RIGHT)
        tk.Button(top, text="Export CSV", bg="#7f8c8d", fg="white", font=("Arial", 10), 
                 padx=15, pady=8, bd=0, command=self.export_csv).pack(side=tk.RIGHT, padx=10)

        canvas = tk.Canvas(self.main_area, bg="#F5F5F5", highlightthickness=0)
        scroll = ttk.Scrollbar(self.main_area, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#F5F5F5")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=1000)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=30)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Monthly Summary Cards
        curr, prev = self.db.get_monthly_summary(self.uid)
        diff = curr - prev
        diff_str = f"+{self.cur_sym}{diff:.2f}" if diff >= 0 else f"-{self.cur_sym}{abs(diff):.2f}"
        color = "#E74C3C" if diff > 0 else "#2ECC71"
        
        stats_frame = tk.Frame(scroll_frame, bg="#F5F5F5")
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.create_card(stats_frame, "This Month", f"{self.cur_sym}{curr:.2f}", f"{diff_str} vs last", color)
        
        bal = self.db.calculate_balances(self.uid)
        owed = sum(v for v in bal.values() if v > 0)
        debt = sum(abs(v) for v in bal.values() if v < 0)
        
        self.create_card(stats_frame, "You are owed", f"{self.cur_sym}{owed:.2f}", "", "#27ae60")
        self.create_card(stats_frame, "You owe", f"{self.cur_sym}{debt:.2f}", "", "#c0392b")

        # Content Grid
        content_grid = tk.Frame(scroll_frame, bg="#F5F5F5")
        content_grid.pack(fill=tk.BOTH, expand=True)
        
        # Recent Expenses (Left)
        left_col = tk.Frame(content_grid, bg="#F5F5F5")
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(left_col, text="Recent Expenses", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(anchor="w", pady=(0, 10))
        
        self.render_expense_list(left_col, self.db.get_user_expenses(self.uid, limit=5))

        # Friends Balances (Right) - FIXED PACK
        right_col = tk.Frame(content_grid, bg="#F5F5F5", width=300) 
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, padx=(10, 0))
        right_col.pack_propagate(False)
        
        tk.Label(right_col, text="Friends Balances", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(anchor="w", pady=(0, 10))
        self.render_balances(right_col, bal)

    def create_card(self, parent, title, value, sub="", sub_col="black"):
        c = tk.Frame(parent, bg="white", padx=20, pady=15, relief=tk.RIDGE, bd=1)
        c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(c, text=title, font=("Arial", 10), fg="#7f8c8d", bg="white").pack(anchor="w")
        tk.Label(c, text=value, font=("Arial", 20, "bold"), bg="white").pack(anchor="w", pady=5)
        if sub: tk.Label(c, text=sub, font=("Arial", 9, "bold"), fg=sub_col, bg="white").pack(anchor="w")

    # --- VIEW: GROUPS ---
    def view_groups(self):
        self.clear_main()
        self.nav_btns["Groups"].config(bg="#1ABC9C")
        
        top = tk.Frame(self.main_area, bg="#F5F5F5")
        top.pack(fill=tk.X, padx=30, pady=20)
        tk.Label(top, text="Groups", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        tk.Button(top, text="+ Create Group", bg="#0288D1", fg="white", font=("Arial", 10), 
                 padx=15, pady=8, bd=0, command=self.create_group_dialog).pack(side=tk.RIGHT)
        
        container = tk.Frame(self.main_area, bg="#F5F5F5")
        container.pack(fill=tk.BOTH, expand=True, padx=30)
        
        groups = self.db.get_user_groups(self.uid)
        if not groups:
            tk.Label(container, text="No groups yet.", bg="#F5F5F5", fg="#999", font=("Arial", 12)).pack(pady=50)
            return

        row, col = 0, 0
        for g in groups:
            mems = self.db.get_group_members(g['group_id'])
            card = tk.Frame(container, bg=g['color'], relief=tk.RIDGE, bd=1, cursor="hand2")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=20)
            
            tk.Label(card, text=g['group_name'], font=("Arial", 14, "bold"), bg=g['color']).pack(pady=(10,5))
            tk.Label(card, text=f"{len(mems)} members", font=("Arial", 10), bg=g['color'], fg="#555").pack()
            
            # Click to view details
            card.bind("<Button-1>", lambda e, gid=g['group_id'], gn=g['group_name']: self.show_group_details(gid, gn))
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, gid=g['group_id'], gn=g['group_name']: self.show_group_details(gid, gn))
                
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        for i in range(3): container.columnconfigure(i, weight=1)

    def show_group_details(self, gid, gname):
        self.clear_main()
        top = tk.Frame(self.main_area, bg="#F5F5F5")
        top.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(top, text=gname, font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        tk.Button(top, text="Back", command=self.view_groups).pack(side=tk.RIGHT, padx=5)
        
        content = tk.Frame(self.main_area, bg="#F5F5F5")
        content.pack(fill=tk.BOTH, expand=True, padx=30)
        
        mems = [m['username'] for m in self.db.get_group_members(gid)]
        tk.Label(content, text=f"Members: {', '.join(mems)}", bg="white", padx=10, pady=10, relief=tk.RIDGE).pack(fill=tk.X, pady=(0,20))
        
        tk.Label(content, text="Group Expenses", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(anchor="w", pady=(0,10))
        exps = self.db.get_group_expenses(gid)
        self.render_expense_list(content, exps)

    # --- VIEW: FRIENDS ---
    def view_friends(self):
        self.clear_main()
        self.nav_btns["Friends"].config(bg="#1ABC9C")
        
        top = tk.Frame(self.main_area, bg="#F5F5F5")
        top.pack(fill=tk.X, padx=30, pady=20)
        tk.Label(top, text="Friends", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        tk.Button(top, text="+ Add Friend", bg="#0288D1", fg="white", font=("Arial", 10), 
                 padx=15, pady=8, bd=0, command=self.add_friend_dialog).pack(side=tk.RIGHT)
        
        container = tk.Frame(self.main_area, bg="white", relief=tk.RIDGE, bd=1)
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        friends = self.db.get_friends(self.uid)
        bal = self.db.calculate_balances(self.uid)
        
        if not friends:
             tk.Label(container, text="No friends added.", bg="white", fg="#999").pack(pady=50)
        else:
            for f in friends:
                fid = f['user_id']
                row = tk.Frame(container, bg="white", padx=20, pady=15, relief=tk.GROOVE, bd=1)
                row.pack(fill=tk.X, pady=5, padx=10)
                
                tk.Label(row, text=f['username'], font=("Arial", 12, "bold"), bg="white").pack(side=tk.LEFT)
                
                amt = bal.get(fid, 0)
                if abs(amt) < 0.01:
                    txt, col = "Settled up", "#999"
                elif amt > 0:
                    txt, col = f"Owes you {self.cur_sym}{amt:.2f}", "#27ae60"
                else:
                    txt, col = f"You owe {self.cur_sym}{abs(amt):.2f}", "#c0392b"
                    
                tk.Label(row, text=txt, font=("Arial", 10, "bold"), fg=col, bg="white").pack(side=tk.RIGHT)

    # --- VIEW: ACTIVITY ---
    def view_activity(self):
        self.clear_main()
        self.nav_btns["Activity"].config(bg="#1ABC9C")
        
        tk.Label(self.main_area, text="Activity Feed", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(anchor="w", padx=30, pady=20)
        
        container = tk.Frame(self.main_area, bg="#F5F5F5")
        container.pack(fill=tk.BOTH, expand=True, padx=30)
        
        canvas = tk.Canvas(container, bg="#F5F5F5", highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#F5F5F5")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=1000)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.render_expense_list(scroll_frame, self.db.get_user_expenses(self.uid))

    # --- VIEW: ANALYTICS ---
    def view_analytics(self):
        self.clear_main()
        self.nav_btns["Analytics"].config(bg="#1ABC9C")
        
        tk.Label(self.main_area, text="Spending Analytics", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(anchor="w", padx=30, pady=20)
        
        data = self.db.get_category_breakdown(self.uid)
        if not data:
            tk.Label(self.main_area, text="Not enough data to generate charts.", font=("Arial", 12), bg="#F5F5F5").pack(pady=50)
            return

        fig, ax = plt.subplots(figsize=(8, 6), facecolor="#F5F5F5")
        labels = list(data.keys())
        sizes = list(data.values())
        colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99', '#c2c2f0', '#ffb3e6']
        
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90, pctdistance=0.85)
        centre_circle = plt.Circle((0,0),0.70,fc='#F5F5F5')
        fig.gca().add_artist(centre_circle)
        ax.axis('equal')  
        ax.set_title("Expenses by Category", fontsize=14, fontweight='bold')
        
        canvas = FigureCanvasTkAgg(fig, master=self.main_area)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

    # --- HELPERS ---
    def render_expense_list(self, parent, expenses):
        if not expenses:
            tk.Label(parent, text="No activity yet.", bg="#F5F5F5", fg="#7f8c8d").pack(anchor="w")
            return
            
        for e in expenses:
            f = tk.Frame(parent, bg="white", padx=15, pady=10, relief=tk.FLAT)
            f.pack(fill=tk.X, pady=2)
            
            row1 = tk.Frame(f, bg="white")
            row1.pack(fill=tk.X)
            dt = datetime.fromisoformat(e['created_at']).strftime("%b %d")
            tk.Label(row1, text=f"{dt} • {e.get('category','General')}", font=("Arial", 8, "bold"), fg="#95a5a6", bg="white").pack(side=tk.LEFT)
            
            if e['receipt_path']:
                lbl = tk.Label(row1, text="📎 Receipt", font=("Arial", 8), fg="#3498db", bg="white", cursor="hand2")
                lbl.pack(side=tk.RIGHT)
                lbl.bind("<Button-1>", lambda ev, p=e['receipt_path']: self.show_receipt(p))
            
            row2 = tk.Frame(f, bg="white")
            row2.pack(fill=tk.X, pady=(2, 0))
            tk.Label(row2, text=e['description'], font=("Arial", 11, "bold"), bg="white").pack(side=tk.LEFT)
            
            amt_col = "#e74c3c" if e['payer_id'] == self.uid else "#2c3e50"
            tk.Label(row2, text=f"{self.cur_sym}{e['amount']:.2f}", font=("Arial", 11, "bold"), fg=amt_col, bg="white").pack(side=tk.RIGHT)
            
            group_txt = e['group_name'] if e['group_name'] else "Personal"
            tk.Label(f, text=f"Paid by {e['payer_name']} in {group_txt}", font=("Arial", 9), fg="#7f8c8d", bg="white").pack(anchor="w")

    def render_balances(self, parent, balances):
        friends = self.db.get_friends(self.uid)
        friends_map = {f['user_id']: f['username'] for f in friends}
        
        container = tk.Frame(parent, bg="white", relief=tk.RIDGE, bd=1)
        container.pack(fill=tk.X)
        
        has_bal = False
        for uid, amount in balances.items():
            if abs(amount) < 0.01: continue
            has_bal = True
            name = friends_map.get(uid, f"User {uid}")
            
            row = tk.Frame(container, bg="white", padx=10, pady=8)
            row.pack(fill=tk.X, pady=1)
            
            tk.Label(row, text=name, font=("Arial", 10), bg="white").pack(side=tk.LEFT)
            col = "#27ae60" if amount > 0 else "#c0392b"
            txt = f"owes you {self.cur_sym}{amount:.2f}" if amount > 0 else f"you owe {self.cur_sym}{abs(amount):.2f}"
            tk.Label(row, text=txt, font=("Arial", 9, "bold"), fg=col, bg="white").pack(side=tk.RIGHT)
            tk.Button(row, text="Settle", bg="#ecf0f1", bd=0, font=("Arial", 8), 
                     command=lambda u=uid, n=name, a=amount: self.settle_up(u, n, a)).pack(side=tk.RIGHT, padx=5)
        
        if not has_bal:
            tk.Label(container, text="Settled up! 🎉", bg="white", fg="#95a5a6", pady=20).pack()

    # --- DIALOGS & ACTIONS ---
    def open_add_expense(self):
        AddExpenseDialog(self.root, self.db, self.uid, self.uname, self.currency)

    def show_receipt(self, path):
        if os.path.exists(path):
            try: os.startfile(path) 
            except: 
                try: 
                    import subprocess
                    subprocess.call(['xdg-open', path])
                except: messagebox.showinfo("Receipt", f"File saved at: {path}")
        else: messagebox.showerror("Error", "Receipt file not found.")

    def settle_up(self, friend_id, name, amount):
        if amount > 0:
            msg = f"{name} owes you {self.cur_sym}{amount:.2f}. Confirm they paid you?"
            fid, tid = friend_id, self.uid
        else:
            msg = f"You owe {name} {self.cur_sym}{abs(amount):.2f}. Confirm you paid them?"
            fid, tid = self.uid, friend_id
            
        if messagebox.askyesno("Settle Up", msg):
            self.db.settle_balance(fid, tid, abs(amount))
            self.view_dashboard()

    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not filename: return
        exps = self.db.get_user_expenses(self.uid)
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Description', 'Category', 'Amount', 'Currency', 'Payer', 'Group', 'Type'])
                for e in exps:
                    writer.writerow([e['created_at'], e['description'], e['category'], e['amount'], self.currency, e['payer_name'], e['group_name'] or 'Personal', e['split_type']])
            messagebox.showinfo("Success", "Export successful!")
        except Exception as e: messagebox.showerror("Error", str(e))

    def create_group_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Create Group")
        d.geometry("300x400")
        tk.Label(d, text="Group Name").pack(pady=5)
        name_ent = tk.Entry(d)
        name_ent.pack(pady=5)
        
        tk.Label(d, text="Members").pack(pady=5)
        frame = tk.Frame(d)
        frame.pack(fill=tk.BOTH, expand=True)
        
        vars = {}
        for f in self.db.get_friends(self.uid):
            v = tk.BooleanVar()
            tk.Checkbutton(frame, text=f['username'], variable=v).pack(anchor="w")
            vars[f['user_id']] = v
            
        def save():
            mems = [self.uid] + [uid for uid, v in vars.items() if v.get()]
            if len(mems) < 2: return messagebox.showerror("Error", "Need 2+ members")
            if self.db.create_group(name_ent.get(), self.uid, mems, '#E3F2FD'):
                d.destroy()
                self.view_groups()
        tk.Button(d, text="Create", command=save).pack(pady=10)

    def add_friend_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Add Friend")
        d.geometry("300x200")
        tk.Label(d, text="Select User").pack(pady=10)
        
        users = self.db.get_all_users()
        current_friends = [f['user_id'] for f in self.db.get_friends(self.uid)]
        avail = [u for u in users if u['user_id'] != self.uid and u['user_id'] not in current_friends]
        
        if not avail:
            tk.Label(d, text="No users available").pack()
            return
            
        combo = ttk.Combobox(d, values=[u['username'] for u in avail], state="readonly")
        combo.pack(pady=5)
        
        def add():
            u = next((x for x in avail if x['username'] == combo.get()), None)
            if u and self.db.add_friend(self.uid, u['user_id']):
                messagebox.showinfo("Success", "Friend added!")
                d.destroy()
                self.view_friends()
        tk.Button(d, text="Add", command=add).pack(pady=10)


class AddExpenseDialog:
    def __init__(self, parent, db, user_id, username, currency):
        self.db = db
        self.uid = user_id
        self.uname = username
        self.curr = currency
        self.receipt_path = None
        
        self.win = tk.Toplevel(parent)
        self.win.title("Add Expense")
        self.win.geometry("500x750")
        self.setup_ui()
        
    def setup_ui(self):
        canvas = tk.Canvas(self.win)
        scroll = ttk.Scrollbar(self.win, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        pad = {'padx': 20, 'pady': 5}
        
        tk.Label(frame, text="Description", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        self.desc_ent = tk.Entry(frame, width=40)
        self.desc_ent.pack(**pad)
        
        tk.Label(frame, text=f"Amount ({self.curr})", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        self.amt_ent = tk.Entry(frame, width=40)
        self.amt_ent.pack(**pad)
        
        tk.Label(frame, text="Category", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        cats = ["Food 🍔", "Transport 🚕", "Rent 🏠", "Utilities 💡", "Entertainment 🎬", "Shopping 🛍️", "General"]
        self.cat_var = tk.StringVar(value="General")
        ttk.Combobox(frame, textvariable=self.cat_var, values=cats, state="readonly").pack(fill=tk.X, **pad)
        
        tk.Label(frame, text="Receipt (Optional)", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        r_frame = tk.Frame(frame)
        r_frame.pack(fill=tk.X, **pad)
        self.r_lbl = tk.Label(r_frame, text="No file selected", fg="gray")
        self.r_lbl.pack(side=tk.LEFT)
        tk.Button(r_frame, text="Upload", command=self.upload_receipt).pack(side=tk.RIGHT)
        
        tk.Label(frame, text="Group", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        groups = self.db.get_user_groups(self.uid)
        g_opts = ["No Group (Personal)"] + [g['group_name'] for g in groups]
        self.g_map = {g['group_name']: g['group_id'] for g in groups}
        self.g_var = tk.StringVar(value=g_opts[0])
        g_cb = ttk.Combobox(frame, textvariable=self.g_var, values=g_opts, state="readonly")
        g_cb.pack(fill=tk.X, **pad)
        g_cb.bind("<<ComboboxSelected>>", self.refresh_members)
        
        tk.Label(frame, text="Split Type", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        self.split_type = tk.StringVar(value="equal")
        rb_frame = tk.Frame(frame)
        rb_frame.pack(fill=tk.X, **pad)
        tk.Radiobutton(rb_frame, text="Equal (=)", variable=self.split_type, value="equal", command=self.update_split_ui).pack(side=tk.LEFT)
        tk.Radiobutton(rb_frame, text="Exact ($)", variable=self.split_type, value="exact", command=self.update_split_ui).pack(side=tk.LEFT)
        tk.Radiobutton(rb_frame, text="Percent (%)", variable=self.split_type, value="percent", command=self.update_split_ui).pack(side=tk.LEFT)
        
        tk.Label(frame, text="Split With:", font=("Arial", 10, "bold")).pack(anchor="w", **pad)
        self.members_frame = tk.Frame(frame)
        self.members_frame.pack(fill=tk.BOTH, **pad)
        
        b_frame = tk.Frame(frame)
        b_frame.pack(pady=20)
        tk.Button(b_frame, text="Save", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), padx=20, pady=10, command=self.save).pack(side=tk.LEFT, padx=10)
        tk.Button(b_frame, text="Cancel", command=self.win.destroy).pack(side=tk.LEFT)
        
        self.refresh_members()

    def upload_receipt(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.pdf")])
        if f:
            ext = os.path.splitext(f)[1]
            fname = f"receipt_{int(datetime.now().timestamp())}{ext}"
            dest = os.path.join("receipts", fname)
            shutil.copy(f, dest)
            self.receipt_path = dest
            self.r_lbl.config(text=os.path.basename(f), fg="green")

    def refresh_members(self, event=None):
        for w in self.members_frame.winfo_children(): w.destroy()
        g_name = self.g_var.get()
        self.participants = []
        
        if g_name == "No Group (Personal)":
            self.participants.append((self.uid, self.uname))
            for f in self.db.get_friends(self.uid): self.participants.append((f['user_id'], f['username']))
        else:
            gid = self.g_map[g_name]
            for m in self.db.get_group_members(gid): self.participants.append((m['user_id'], m['username']))
        self.inputs = {}
        self.update_split_ui()

    def update_split_ui(self):
        for w in self.members_frame.winfo_children(): w.destroy()
        stype = self.split_type.get()
        self.inputs = {}
        
        for uid, name in self.participants:
            row = tk.Frame(self.members_frame)
            row.pack(fill=tk.X, pady=2)
            var = tk.BooleanVar(value=True)
            tk.Checkbutton(row, text=name, variable=var, width=15, anchor="w").pack(side=tk.LEFT)
            
            if stype == "equal":
                self.inputs[uid] = {'check': var, 'entry': None}
            elif stype == "exact":
                tk.Label(row, text="$").pack(side=tk.LEFT)
                ent = tk.Entry(row, width=10)
                ent.pack(side=tk.LEFT)
                ent.insert(0, "0.00")
                self.inputs[uid] = {'check': var, 'entry': ent}
            elif stype == "percent":
                ent = tk.Entry(row, width=5)
                ent.pack(side=tk.LEFT)
                ent.insert(0, "0")
                tk.Label(row, text="%").pack(side=tk.LEFT)
                self.inputs[uid] = {'check': var, 'entry': ent}

    def save(self):
        try:
            desc = self.desc_ent.get()
            total = float(self.amt_ent.get())
            cat = self.cat_var.get()
            stype = self.split_type.get()
            gid = self.g_map.get(self.g_var.get(), None)
            
            selected_uids = [u for u, data in self.inputs.items() if data['check'].get()]
            if not selected_uids: return messagebox.showerror("Error", "Select 1+ person")
            
            splits = {}
            if stype == "equal":
                share = total / len(selected_uids)
                for uid in selected_uids: splits[uid] = share
            elif stype == "exact":
                csum = 0
                for uid in selected_uids:
                    v = float(self.inputs[uid]['entry'].get())
                    splits[uid], csum = v, csum + v
                if abs(csum - total) > 0.05: return messagebox.showerror("Error", "Totals don't match")
            elif stype == "percent":
                cpct = 0
                for uid in selected_uids:
                    p = float(self.inputs[uid]['entry'].get())
                    splits[uid], cpct = (p / 100.0) * total, cpct + p
                if abs(cpct - 100) > 0.5: return messagebox.showerror("Error", "Percents must match 100%")
            
            if self.db.add_expense(desc, total, cat, self.receipt_path, self.uid, gid, stype, splits):
                messagebox.showinfo("Success", "Expense added!")
                self.win.destroy()
        except Exception as e: messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    db_mgr = DatabaseManager()
    root = tk.Tk()
    auth = AuthWindow(root, db_mgr)
    root.mainloop()
    
    if auth.user_data:
        main_root = tk.Tk()
        app = ExpenseApp(main_root, db_mgr, auth.user_data)
        main_root.mainloop()