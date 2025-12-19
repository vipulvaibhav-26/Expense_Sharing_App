import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from collections import defaultdict
import sqlite3
import math

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.db_path = "expenseshare.db"
        self.connect()
        
    def connect(self):
        """Connect to SQLite database (creates file if doesn't exist)"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            print(f"Successfully connected to database: {self.db_path}")
            self.create_tables()
        except Exception as e:
            messagebox.showerror("Database Error", 
                               f"Error connecting to database: {e}")
            
    def create_tables(self):
        """Create necessary database tables"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                payer_id INTEGER NOT NULL,
                group_id INTEGER,
                split_type TEXT DEFAULT 'equal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (payer_id) REFERENCES users(user_id),
                FOREIGN KEY (group_id) REFERENCES groups_table(group_id) ON DELETE SET NULL
            )
        """)
        
        # Note: expense_splits now stores the SHARE of the user
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
        
    def add_user(self, username, email=None):
        try:
            cursor = self.connection.cursor()
            cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", 
                         (username, email))
            self.connection.commit()
            user_id = cursor.lastrowid
            cursor.close()
            return user_id
        except sqlite3.IntegrityError:
            return self.get_user_id(username)
        except Exception as e:
            print(f"Error adding user: {e}")
            return None
            
    def get_user_id(self, username):
        cursor = self.connection.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None
        
    def get_all_users(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT user_id, username FROM users ORDER BY username")
        users = cursor.fetchall()
        cursor.close()
        return users
        
    def add_friend(self, user_id, friend_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)", 
                         (user_id, friend_id))
            cursor.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)", 
                         (friend_id, user_id))
            self.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"Error adding friend: {e}")
            return False
            
    def get_friends(self, user_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username 
            FROM friends f 
            JOIN users u ON f.friend_id = u.user_id 
            WHERE f.user_id = ?
            ORDER BY u.username
        """, (user_id,))
        friends = cursor.fetchall()
        cursor.close()
        return friends
        
    def create_group(self, group_name, created_by, members, color='#E3F2FD'):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO groups_table (group_name, color, created_by) 
                VALUES (?, ?, ?)
            """, (group_name, color, created_by))
            group_id = cursor.lastrowid
            
            for member_id in members:
                cursor.execute("""
                    INSERT INTO group_members (group_id, user_id) 
                    VALUES (?, ?)
                """, (group_id, member_id))
                
            self.connection.commit()
            cursor.close()
            return group_id
        except Exception as e:
            print(f"Error creating group: {e}")
            return None
            
    def get_user_groups(self, user_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT g.group_id, g.group_name, g.color 
            FROM groups_table g
            JOIN group_members gm ON g.group_id = gm.group_id
            WHERE gm.user_id = ?
            ORDER BY g.created_at DESC
        """, (user_id,))
        groups = cursor.fetchall()
        cursor.close()
        return groups
        
    def get_group_members(self, group_id):
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username 
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = ?
            ORDER BY u.username
        """, (group_id,))
        members = cursor.fetchall()
        cursor.close()
        return members
        
    def add_expense(self, description, amount, payer_id, group_id, split_type, splits):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO expenses (description, amount, payer_id, group_id, split_type)
                VALUES (?, ?, ?, ?, ?)
            """, (description, amount, payer_id, group_id, split_type))
            expense_id = cursor.lastrowid
            
            # Add splits (These are the SHARES of each person)
            for user_id, split_amount in splits.items():
                cursor.execute("""
                    INSERT INTO expense_splits (expense_id, user_id, amount)
                    VALUES (?, ?, ?)
                """, (expense_id, user_id, split_amount))
                
            self.connection.commit()
            cursor.close()
            return expense_id
        except Exception as e:
            print(f"Error adding expense: {e}")
            return None
            
    def get_user_expenses(self, user_id, limit=None):
        cursor = self.connection.cursor()
        query = """
            SELECT DISTINCT e.expense_id, e.description, e.amount, e.split_type,
                   e.created_at, u.username as payer_name, u.user_id as payer_id,
                   g.group_name, g.group_id
            FROM expenses e
            JOIN users u ON e.payer_id = u.user_id
            LEFT JOIN groups_table g ON e.group_id = g.group_id
            LEFT JOIN expense_splits es ON e.expense_id = es.expense_id
            WHERE e.payer_id = ? OR es.user_id = ?
            ORDER BY e.created_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query, (user_id, user_id))
        expenses = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        return expenses
        
    def calculate_balances(self, user_id, simplify=True):
        """
        Calculate balances. 
        If simplify=True, it runs the debt simplification algorithm.
        """
        if simplify:
            return self.get_simplified_balances(user_id)
        else:
            return self.get_direct_balances(user_id)

    def get_direct_balances(self, user_id):
        """Original direct pairwise calculation logic"""
        balances = defaultdict(float)
        cursor = self.connection.cursor()
        
        # Get all expenses involved
        cursor.execute("""
            SELECT e.expense_id, e.payer_id, es.user_id, es.amount
            FROM expenses e
            JOIN expense_splits es ON e.expense_id = es.expense_id
            WHERE e.payer_id = ? OR es.user_id = ?
        """, (user_id, user_id))
        
        transactions = cursor.fetchall()
        
        for trans in transactions:
            payer_id = trans['payer_id']
            borrower_id = trans['user_id']
            amount = float(trans['amount'])
            
            # Logic Correction: If I paid for myself, I don't owe myself.
            if borrower_id == payer_id:
                continue
            
            if payer_id == user_id:
                # I paid, borrower owes me
                balances[borrower_id] += amount
            elif borrower_id == user_id:
                # Someone else paid, I owe them
                balances[payer_id] -= amount
                    
        # Subtract settlements
        cursor.execute("""
            SELECT from_user_id, to_user_id, amount
            FROM settlements
            WHERE from_user_id = ? OR to_user_id = ?
        """, (user_id, user_id))
        
        settlements = cursor.fetchall()
        for settlement in settlements:
            from_id = settlement['from_user_id']
            to_id = settlement['to_user_id']
            amount = float(settlement['amount'])
            
            if from_id == user_id:
                balances[to_id] -= amount
            else:
                balances[from_id] += amount
                
        cursor.close()
        return balances

    def get_simplified_balances(self, user_id):
        """
        Calculates Simplified Debts (Minimizing Cash Flow).
        1. Calculate Net Balance for everyone in the DB.
        2. Match creditors and debtors greedily.
        3. Filter for the requested user.
        """
        # 1. Calculate Global Net Balances
        net_balance = defaultdict(float)
        cursor = self.connection.cursor()

        # Add expenses (Credits/Debits)
        cursor.execute("SELECT e.payer_id, es.user_id, es.amount FROM expenses e JOIN expense_splits es ON e.expense_id = es.expense_id")
        all_splits = cursor.fetchall()
        for payer_id, borrower_id, amount in all_splits:
            if payer_id == borrower_id: continue
            net_balance[payer_id] += amount # Payer gets back money
            net_balance[borrower_id] -= amount # Borrower owes money

        # Add settlements
        cursor.execute("SELECT from_user_id, to_user_id, amount FROM settlements")
        all_settlements = cursor.fetchall()
        for from_id, to_id, amount in all_settlements:
            net_balance[from_id] += amount # Paid money, so balance increases (debt reduces)
            net_balance[to_id] -= amount   # Received money, so balance decreases (credit reduces)
            
        cursor.close()

        # Remove settled people (approx 0)
        net_balance = {k: v for k, v in net_balance.items() if abs(v) > 0.01}

        # 2. Match Debtors and Creditors
        debtors = sorted([(k, v) for k, v in net_balance.items() if v < 0], key=lambda x: x[1])
        creditors = sorted([(k, v) for k, v in net_balance.items() if v > 0], key=lambda x: x[1], reverse=True)

        simplified_graph = [] # (from, to, amount)

        i = 0 # iterator for debtors
        j = 0 # iterator for creditors

        while i < len(debtors) and j < len(creditors):
            debtor_id, debit_amt = debtors[i]
            creditor_id, credit_amt = creditors[j]

            # The amount to settle is the minimum of what debtor owes and creditor needs
            amount = min(abs(debit_amt), credit_amt)
            
            simplified_graph.append((debtor_id, creditor_id, amount))

            # Update remaining amounts
            net_balance[debtor_id] += amount
            net_balance[creditor_id] -= amount
            
            # If settled, move to next
            if abs(net_balance[debtor_id]) < 0.01:
                i += 1
            else:
                debtors[i] = (debtor_id, net_balance[debtor_id]) # Update
                
            if abs(net_balance[creditor_id]) < 0.01:
                j += 1
            else:
                creditors[j] = (creditor_id, net_balance[creditor_id]) # Update

        # 3. Filter for the specific user
        user_balances = defaultdict(float)
        for from_id, to_id, amount in simplified_graph:
            if from_id == user_id:
                user_balances[to_id] -= amount # I owe them
            elif to_id == user_id:
                user_balances[from_id] += amount # They owe me
        
        return user_balances

    def settle_balance(self, from_user_id, to_user_id, amount):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO settlements (from_user_id, to_user_id, amount)
                VALUES (?, ?, ?)
            """, (from_user_id, to_user_id, amount))
            self.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"Error settling balance: {e}")
            return False
            
    def close(self):
        if self.connection:
            self.connection.close()


class LoginWindow:
    def __init__(self, root, db_manager):
        self.root = root
        self.db = db_manager
        self.user_id = None
        self.username = None
        
        self.root.title("ExpenseShare - Login")
        self.root.geometry("500x400")
        self.root.configure(bg="#F5F5F5")
        
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.root.winfo_screenheight() // 2) - (400 // 2)
        self.root.geometry(f"500x400+{x}+{y}")
        
        self.create_ui()
        
    def create_ui(self):
        logo_frame = tk.Frame(self.root, bg="#F5F5F5")
        logo_frame.pack(pady=40)
        
        tk.Label(logo_frame, text="💰", font=("Arial", 48), bg="#F5F5F5").pack()
        tk.Label(logo_frame, text="ExpenseShare", font=("Arial", 28, "bold"), bg="#F5F5F5", fg="#2C3E50").pack()
        tk.Label(logo_frame, text="Split expenses with friends", font=("Arial", 11), bg="#F5F5F5", fg="#666").pack(pady=5)
        
        form_frame = tk.Frame(self.root, bg="white", relief=tk.RIDGE, bd=1)
        form_frame.pack(padx=60, pady=20, fill=tk.BOTH, expand=True)
        
        tk.Label(form_frame, text="Enter your name to continue", font=("Arial", 12), bg="white", fg="#333").pack(pady=(30, 20))
        
        entry_frame = tk.Frame(form_frame, bg="white")
        entry_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(entry_frame, text="Username:", font=("Arial", 10), bg="white", fg="#666").pack(anchor="w")
        
        self.username_entry = tk.Entry(entry_frame, font=("Arial", 12), relief=tk.SOLID, bd=1)
        self.username_entry.pack(fill=tk.X, pady=5, ipady=8)
        self.username_entry.focus()
        self.username_entry.bind('<Return>', lambda e: self.login())
        
        tk.Label(entry_frame, text="Email (optional):", font=("Arial", 10), bg="white", fg="#666").pack(anchor="w", pady=(15, 0))
        
        self.email_entry = tk.Entry(entry_frame, font=("Arial", 12), relief=tk.SOLID, bd=1)
        self.email_entry.pack(fill=tk.X, pady=5, ipady=8)
        
        login_btn = tk.Button(form_frame, text="Continue", font=("Arial", 12, "bold"), bg="#0288D1", fg="white", bd=0, pady=12, cursor="hand2", command=self.login)
        login_btn.pack(pady=(20, 30), padx=40, fill=tk.X)
        
    def login(self):
        username = self.username_entry.get().strip()
        email = self.email_entry.get().strip() or None
        
        if not username:
            messagebox.showerror("Error", "Please enter your username")
            return
            
        user_id = self.db.add_user(username, email)
        
        if user_id:
            self.user_id = user_id
            self.username = username
            self.root.destroy()
        else:
            messagebox.showerror("Error", "Failed to create user account")


class ExpenseShareApp:
    def __init__(self, root, db_manager, user_id, username):
        self.root = root
        self.db = db_manager
        self.current_user_id = user_id
        self.current_user = username
        self.use_simplified_debts = True # Default to simplified
        
        self.root.title("ExpenseShare")
        width = 1280
        height = 720
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(1280, 720)
        
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        self.create_ui()
        
    def create_ui(self):
        main_frame = tk.Frame(self.root, bg="#F5F5F5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.create_sidebar(main_frame)
        self.content_frame = tk.Frame(main_frame, bg="#F5F5F5")
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.show_dashboard()
        
    def create_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg="#2C3E50", width=220)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        logo_frame = tk.Frame(sidebar, bg="#2C3E50")
        logo_frame.pack(pady=20, padx=15)
        
        logo_label = tk.Label(logo_frame, text="💰 ExpenseShare", font=("Arial", 16, "bold"), fg="white", bg="#2C3E50")
        logo_label.pack()
        
        user_frame = tk.Frame(sidebar, bg="#34495E", relief=tk.RIDGE, bd=1)
        user_frame.pack(fill=tk.X, padx=10, pady=(0, 20))
        
        tk.Label(user_frame, text=f"👤 {self.current_user}", font=("Arial", 10), bg="#34495E", fg="white").pack(pady=10)
        
        nav_buttons = [
            ("🏠 Dashboard", self.show_dashboard),
            ("👥 Groups", self.show_groups),
            ("👤 Friends", self.show_friends),
            ("📊 Activity", self.show_activity)
        ]
        
        self.nav_buttons = {}
        for text, command in nav_buttons:
            btn = tk.Button(sidebar, text=text, font=("Arial", 11), bg="#34495E", fg="white", bd=0, pady=12, cursor="hand2", anchor="w", padx=20, activebackground="#1ABC9C", activeforeground="white", command=command)
            btn.pack(fill=tk.X, pady=2, padx=10)
            self.nav_buttons[text] = btn
            
        logout_btn = tk.Button(sidebar, text="🚪 Logout", font=("Arial", 11), bg="#E74C3C", fg="white", bd=0, pady=12, cursor="hand2", command=self.logout)
        logout_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=10)
        self.nav_buttons["🏠 Dashboard"].config(bg="#1ABC9C")
        
    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
    def show_dashboard(self):
        self.clear_content()
        self.highlight_nav_button("🏠 Dashboard")
        
        header_frame = tk.Frame(self.content_frame, bg="#F5F5F5")
        header_frame.pack(fill=tk.X, padx=30, pady=20)
        
        welcome_label = tk.Label(header_frame, text=f"Welcome back, {self.current_user}", font=("Arial", 24, "bold"), bg="#F5F5F5")
        welcome_label.pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(header_frame, bg="#F5F5F5")
        btn_frame.pack(side=tk.RIGHT)
        
        add_btn = tk.Button(btn_frame, text="+ Add Expense", font=("Arial", 10), bg="#0288D1", fg="white", bd=0, padx=15, pady=8, cursor="hand2", command=self.add_expense_dialog)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        settle_btn = tk.Button(btn_frame, text="✓ Settle Up", font=("Arial", 10), bg="#0288D1", fg="white", bd=0, padx=15, pady=8, cursor="hand2", command=self.settle_up_dialog)
        settle_btn.pack(side=tk.LEFT)
        
        canvas = tk.Canvas(self.content_frame, bg="#F5F5F5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#F5F5F5")
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=30)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        left_column = tk.Frame(scrollable_frame, bg="#F5F5F5")
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        right_column = tk.Frame(scrollable_frame, bg="#F5F5F5")
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, padx=(15, 0))
        
        self.create_balance_card(left_column)
        self.create_recent_groups(left_column)
        self.create_recent_expenses(left_column)
        self.create_friends_balances(right_column)
        
    def create_balance_card(self, parent):
        card = tk.Frame(parent, bg="white", relief=tk.RIDGE, bd=1)
        card.pack(fill=tk.X, pady=(0, 20))
        
        header = tk.Frame(card, bg="white")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))
        
        title = tk.Label(header, text="Total balance:", font=("Arial", 12, "bold"), bg="white", anchor="w")
        title.pack(side=tk.LEFT)

        mode_text = "Simplified" if self.use_simplified_debts else "Direct"
        mode_lbl = tk.Label(header, text=f"({mode_text})", font=("Arial", 9), bg="white", fg="#666")
        mode_lbl.pack(side=tk.RIGHT)
        
        balance_frame = tk.Frame(card, bg="white")
        balance_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        you_owed, you_owe = self.calculate_total_balance()
        
        owed_frame = tk.Frame(balance_frame, bg="white")
        owed_frame.pack(side=tk.LEFT, expand=True)
        tk.Label(owed_frame, text="You are owed", font=("Arial", 9), bg="white", fg="#666").pack()
        tk.Label(owed_frame, text=f"${you_owed:.2f}", font=("Arial", 20, "bold"), bg="white", fg="#4CAF50").pack()
        
        owe_frame = tk.Frame(balance_frame, bg="white")
        owe_frame.pack(side=tk.LEFT, expand=True)
        tk.Label(owe_frame, text="You owe", font=("Arial", 9), bg="white", fg="#666").pack()
        tk.Label(owe_frame, text=f"${you_owe:.2f}", font=("Arial", 20, "bold"), bg="white", fg="#F44336").pack()
        
        btn_text = "View Direct Debts" if self.use_simplified_debts else "Simplify Balances"
        simplify_btn = tk.Button(card, text=btn_text, font=("Arial", 11), bg="#0288D1", fg="white", bd=0, pady=10, cursor="hand2", command=self.toggle_simplification)
        simplify_btn.pack(fill=tk.X, padx=20, pady=(0, 15))
        
    def toggle_simplification(self):
        self.use_simplified_debts = not self.use_simplified_debts
        self.show_dashboard()

    def create_recent_groups(self, parent):
        header_frame = tk.Frame(parent, bg="#F5F5F5")
        header_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(header_frame, text="Recent Groups", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        create_btn = tk.Button(header_frame, text="Create Group", font=("Arial", 9), bg="#E0E0E0", fg="#333", bd=0, padx=10, pady=5, cursor="hand2", command=self.create_group_dialog)
        create_btn.pack(side=tk.RIGHT)
        
        groups_frame = tk.Frame(parent, bg="#F5F5F5")
        groups_frame.pack(fill=tk.X, pady=(0, 20))
        groups = self.db.get_user_groups(self.current_user_id)
        if groups:
            for i, row in enumerate(groups[:3]):
                group_id = row['group_id']
                group_name = row['group_name']
                color = row['color']
                members = self.db.get_group_members(group_id)
                group_card = tk.Frame(groups_frame, bg=color, relief=tk.RIDGE, bd=1, cursor="hand2")
                group_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
                tk.Label(group_card, text=group_name, font=("Arial", 12, "bold"), bg=color).pack(pady=30)
                tk.Label(group_card, text=f"{len(members)} members", font=("Arial", 9), bg=color, fg="#666").pack(pady=(0, 10))
                group_card.bind("<Button-1>", lambda e, gid=group_id, gn=group_name: self.show_group_details(gid, gn))
        else:
            tk.Label(groups_frame, text="No groups yet. Create one to get started!", font=("Arial", 10), bg="#F5F5F5", fg="#999").pack(pady=40)
            
    def create_recent_expenses(self, parent):
        tk.Label(parent, text="Recent Expenses", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(fill=tk.X, pady=(0, 10))
        expenses_card = tk.Frame(parent, bg="white", relief=tk.RIDGE, bd=1)
        expenses_card.pack(fill=tk.BOTH, expand=True)
        expenses = self.db.get_user_expenses(self.current_user_id, limit=5)
        if expenses:
            for expense in expenses:
                exp_frame = tk.Frame(expenses_card, bg="white")
                exp_frame.pack(fill=tk.X, padx=15, pady=10)
                split_type = expense['split_type'].capitalize()
                group_text = f" • {expense['group_name']}" if expense['group_name'] else ""
                text = f"{expense['description']} - {expense['payer_name']} paid ${expense['amount']:.2f} ({split_type} split){group_text}"
                tk.Label(exp_frame, text=text, font=("Arial", 10), bg="white", anchor="w").pack(fill=tk.X)
        else:
            tk.Label(expenses_card, text="No expenses yet", font=("Arial", 10), bg="white", fg="#999").pack(pady=40)
            
    def create_friends_balances(self, parent):
        header_frame = tk.Frame(parent, bg="#F5F5F5")
        header_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Label(header_frame, text="Friends & Balances", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        add_friend_btn = tk.Button(header_frame, text="+ Add Friend", font=("Arial", 9), bg="#E0E0E0", fg="#333", bd=0, padx=10, pady=5, cursor="hand2", command=self.add_friend_dialog)
        add_friend_btn.pack(side=tk.RIGHT)
        
        balances_card = tk.Frame(parent, bg="white", relief=tk.RIDGE, bd=1, width=300)
        balances_card.pack(fill=tk.BOTH, expand=True)
        balances_card.pack_propagate(False)
        
        # USE SIMPLIFIED BALANCES IF TOGGLED
        balances = self.db.calculate_balances(self.current_user_id, simplify=self.use_simplified_debts)
        friends = self.db.get_friends(self.current_user_id)
        friend_dict = {f['user_id']: f['username'] for f in friends}
        
        has_balances = False
        # Iterate over balances instead of friends to show debts with non-friends (e.g. group members)
        for other_id, balance in balances.items():
            if abs(balance) < 0.01: continue
            
            has_balances = True
            friend_name = friend_dict.get(other_id, f"User {other_id}")
            person_frame = tk.Frame(balances_card, bg="white")
            person_frame.pack(fill=tk.X, padx=15, pady=8)
            
            colors = ["#FF6B6B", "#4ECDC4", "#95E1D3", "#FFA07A", "#98D8C8"]
            color = colors[hash(friend_name) % len(colors)]
            avatar = tk.Label(person_frame, text=friend_name[0].upper(), font=("Arial", 12, "bold"), bg=color, fg="white", width=3, height=1)
            avatar.pack(side=tk.LEFT, padx=(0, 10))
            
            info_frame = tk.Frame(person_frame, bg="white")
            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            if balance > 0:
                text = f"{friend_name} owes you"
                amount_color = "#4CAF50"
                display_amount = balance
            else:
                text = f"You owe {friend_name}"
                amount_color = "#F44336"
                display_amount = abs(balance)
                
            tk.Label(info_frame, text=text, font=("Arial", 10), bg="white", anchor="w").pack(fill=tk.X)
            tk.Label(info_frame, text=f"${display_amount:.2f}", font=("Arial", 10, "bold"), bg="white", fg=amount_color, anchor="w").pack(fill=tk.X)
            
            settle_btn = tk.Button(person_frame, text="Settle", font=("Arial", 8), bg="#E0E0E0", fg="#333", bd=0, padx=10, pady=3, cursor="hand2", command=lambda fid=other_id, fn=friend_name, b=balance: self.settle_with_person(fid, fn, b))
            settle_btn.pack(side=tk.RIGHT)
            
        if not has_balances:
            tk.Label(balances_card, text="All settled up! 🎉", font=("Arial", 11), bg="white", fg="#999").pack(pady=40)
            
    def show_groups(self):
        self.clear_content()
        self.highlight_nav_button("👥 Groups")
        header_frame = tk.Frame(self.content_frame, bg="#F5F5F5")
        header_frame.pack(fill=tk.X, padx=30, pady=20)
        tk.Label(header_frame, text="Groups", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        create_btn = tk.Button(header_frame, text="+ Create Group", font=("Arial", 10), bg="#0288D1", fg="white", bd=0, padx=15, pady=8, cursor="hand2", command=self.create_group_dialog)
        create_btn.pack(side=tk.RIGHT)
        
        groups_container = tk.Frame(self.content_frame, bg="#F5F5F5")
        groups_container.pack(fill=tk.BOTH, expand=True, padx=30)
        groups = self.db.get_user_groups(self.current_user_id)
        if groups:
            row = 0
            col = 0
            for group_row in groups:
                group_id = group_row['group_id']
                group_name = group_row['group_name']
                color = group_row['color']
                members = self.db.get_group_members(group_id)
                group_card = tk.Frame(groups_container, bg=color, relief=tk.RIDGE, bd=1, cursor="hand2")
                group_card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", ipadx=40, ipady=40)
                tk.Label(group_card, text=group_name, font=("Arial", 14, "bold"), bg=color).pack(expand=True)
                tk.Label(group_card, text=f"{len(members)} members", font=("Arial", 9), bg=color, fg="#666").pack()
                group_card.bind("<Button-1>", lambda e, gid=group_id, gn=group_name: self.show_group_details(gid, gn))
                col += 1
                if col > 2:
                    col = 0
                    row += 1
            for i in range(3):
                groups_container.columnconfigure(i, weight=1)
        else:
            tk.Label(groups_container, text="No groups yet. Create one to get started!", font=("Arial", 12), bg="#F5F5F5", fg="#999").pack(pady=100)
            
    def show_friends(self):
        self.clear_content()
        self.highlight_nav_button("👤 Friends")
        header_frame = tk.Frame(self.content_frame, bg="#F5F5F5")
        header_frame.pack(fill=tk.X, padx=30, pady=20)
        tk.Label(header_frame, text="Friends", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        add_btn = tk.Button(header_frame, text="+ Add Friend", font=("Arial", 10), bg="#0288D1", fg="white", bd=0, padx=15, pady=8, cursor="hand2", command=self.add_friend_dialog)
        add_btn.pack(side=tk.RIGHT)
        
        friends_frame = tk.Frame(self.content_frame, bg="white", relief=tk.RIDGE, bd=1)
        friends_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))
        friends = self.db.get_friends(self.current_user_id)
        balances = self.db.calculate_balances(self.current_user_id, simplify=self.use_simplified_debts)
        
        if friends:
            for row in friends:
                friend_id = row['user_id']
                friend_name = row['username']
                user_frame = tk.Frame(friends_frame, bg="white", relief=tk.GROOVE, bd=1)
                user_frame.pack(fill=tk.X, padx=20, pady=10)
                tk.Label(user_frame, text=friend_name, font=("Arial", 12, "bold"), bg="white").pack(side=tk.LEFT, padx=15, pady=10)
                balance = balances.get(friend_id, 0)
                if balance > 0.01:
                    text = f"Owes you ${balance:.2f}"
                    color = "#4CAF50"
                elif balance < -0.01:
                    text = f"You owe ${abs(balance):.2f}"
                    color = "#F44336"
                else:
                    text = "Settled up"
                    color = "#999"
                tk.Label(user_frame, text=text, font=("Arial", 10), bg="white", fg=color).pack(side=tk.RIGHT, padx=15)
        else:
            tk.Label(friends_frame, text="No friends yet. Add friends to start sharing expenses!", font=("Arial", 11), bg="white", fg="#999").pack(pady=100)
            
    def show_activity(self):
        self.clear_content()
        self.highlight_nav_button("📊 Activity")
        tk.Label(self.content_frame, text="Activity", font=("Arial", 24, "bold"), bg="#F5F5F5").pack(padx=30, pady=20, anchor="w")
        filter_frame = tk.Frame(self.content_frame, bg="#F5F5F5")
        filter_frame.pack(fill=tk.X, padx=30, pady=(0, 10))
        tk.Label(filter_frame, text="All expenses and settlements", font=("Arial", 10), bg="#F5F5F5", fg="#666").pack(side=tk.LEFT)
        activity_frame = tk.Frame(self.content_frame, bg="white", relief=tk.RIDGE, bd=1)
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))
        expenses = self.db.get_user_expenses(self.current_user_id)
        if expenses:
            for expense in expenses:
                exp_frame = tk.Frame(activity_frame, bg="white", relief=tk.GROOVE, bd=1)
                exp_frame.pack(fill=tk.X, padx=15, pady=8)
                title_text = f"{expense['description']} - ${expense['amount']:.2f}"
                tk.Label(exp_frame, text=title_text, font=("Arial", 11, "bold"), bg="white", anchor="w").pack(fill=tk.X, padx=10, pady=(8, 2))
                group_text = f" • {expense['group_name']}" if expense['group_name'] else " • Personal"
                detail_text = f"Paid by {expense['payer_name']} • {expense['split_type'].capitalize()} split{group_text}"
                tk.Label(exp_frame, text=detail_text, font=("Arial", 9), bg="white", fg="#666", anchor="w").pack(fill=tk.X, padx=10)
                date_text = datetime.fromisoformat(expense['created_at']).strftime("%b %d, %Y at %I:%M %p")
                tk.Label(exp_frame, text=date_text, font=("Arial", 8), bg="white", fg="#999", anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))
        else:
            tk.Label(activity_frame, text="No activity yet", font=("Arial", 11), bg="white", fg="#999").pack(pady=100)
            
    def show_group_details(self, group_id, group_name):
        self.clear_content()
        header_frame = tk.Frame(self.content_frame, bg="#F5F5F5")
        header_frame.pack(fill=tk.X, padx=30, pady=20)
        tk.Label(header_frame, text=group_name, font=("Arial", 24, "bold"), bg="#F5F5F5").pack(side=tk.LEFT)
        back_btn = tk.Button(header_frame, text="← Back", font=("Arial", 10), bg="#999", fg="white", bd=0, padx=15, pady=8, cursor="hand2", command=self.show_groups)
        back_btn.pack(side=tk.RIGHT, padx=5)
        add_btn = tk.Button(header_frame, text="+ Add Expense", font=("Arial", 10), bg="#0288D1", fg="white", bd=0, padx=15, pady=8, cursor="hand2", command=lambda: self.add_expense_dialog(group_id))
        add_btn.pack(side=tk.RIGHT)
        
        members = self.db.get_group_members(group_id)
        member_names = [row['username'] for row in members]
        info_frame = tk.Frame(self.content_frame, bg="white", relief=tk.RIDGE, bd=1)
        info_frame.pack(fill=tk.X, padx=30, pady=(0, 20))
        tk.Label(info_frame, text=f"Members: {', '.join(member_names)}", font=("Arial", 11), bg="white").pack(padx=20, pady=15)
        
        tk.Label(self.content_frame, text="Group Expenses", font=("Arial", 14, "bold"), bg="#F5F5F5").pack(padx=30, pady=(0, 10), anchor="w")
        expenses_frame = tk.Frame(self.content_frame, bg="white", relief=tk.RIDGE, bd=1)
        expenses_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))
        
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT e.expense_id, e.description, e.amount, e.split_type,
                   e.created_at, u.username as payer_name
            FROM expenses e
            JOIN users u ON e.payer_id = u.user_id
            WHERE e.group_id = ?
            ORDER BY e.created_at DESC
        """, (group_id,))
        group_expenses = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        
        if group_expenses:
            for expense in group_expenses:
                exp_frame = tk.Frame(expenses_frame, bg="white", relief=tk.GROOVE, bd=1)
                exp_frame.pack(fill=tk.X, padx=15, pady=8)
                title = f"{expense['description']} - ${expense['amount']:.2f}"
                tk.Label(exp_frame, text=title, font=("Arial", 11, "bold"), bg="white", anchor="w").pack(fill=tk.X, padx=10, pady=(8, 2))
                detail = f"Paid by {expense['payer_name']} • {expense['split_type'].capitalize()} split"
                tk.Label(exp_frame, text=detail, font=("Arial", 9), bg="white", fg="#666", anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))
        else:
            tk.Label(expenses_frame, text="No expenses yet in this group", font=("Arial", 10), bg="white", fg="#999").pack(pady=40)
            
    def highlight_nav_button(self, button_text):
        for text, btn in self.nav_buttons.items():
            if text == button_text:
                btn.config(bg="#1ABC9C")
            else:
                btn.config(bg="#34495E")
                
    def calculate_total_balance(self):
        balances = self.db.calculate_balances(self.current_user_id, simplify=self.use_simplified_debts)
        you_owed = sum(amount for amount in balances.values() if amount > 0)
        you_owe = sum(abs(amount) for amount in balances.values() if amount < 0)
        return you_owed, you_owe
    
    def create_group_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Group")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Create New Group", font=("Arial", 14, "bold")).pack(padx=20, pady=20)
        
        tk.Label(dialog, text="Group Name:", font=("Arial", 10)).pack(padx=20, pady=(10, 5), anchor="w")
        name_entry = tk.Entry(dialog, font=("Arial", 11))
        name_entry.pack(padx=20, fill=tk.X)
        
        tk.Label(dialog, text="Select Members:", font=("Arial", 10)).pack(padx=20, pady=(15, 5), anchor="w")
        members_frame = tk.Frame(dialog)
        members_frame.pack(padx=20, fill=tk.BOTH, expand=True)
        
        member_vars = {self.current_user_id: tk.BooleanVar(value=True)}
        cb = tk.Checkbutton(members_frame, text=f"{self.current_user} (You)", variable=member_vars[self.current_user_id], font=("Arial", 10), state=tk.DISABLED)
        cb.pack(anchor="w", pady=2)
        
        friends = self.db.get_friends(self.current_user_id)
        for row in friends:
            friend_id = row['user_id']
            friend_name = row['username']
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(members_frame, text=friend_name, variable=var, font=("Arial", 10))
            cb.pack(anchor="w", pady=2)
            member_vars[friend_id] = var
            
        tk.Label(dialog, text="Group Color:", font=("Arial", 10)).pack(padx=20, pady=(15, 5), anchor="w")
        colors = ["#E3F2FD", "#F3E5F5", "#E8F5E9", "#FFF3E0", "#FCE4EC"]
        color_var = tk.StringVar(value=colors[0])
        color_frame = tk.Frame(dialog)
        color_frame.pack(padx=20, pady=5)
        for color in colors:
            rb = tk.Radiobutton(color_frame, bg=color, variable=color_var, value=color, width=3, height=1, indicatoron=0)
            rb.pack(side=tk.LEFT, padx=5)
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        def create_group():
            group_name = name_entry.get().strip()
            if not group_name:
                messagebox.showerror("Error", "Please enter a group name")
                return
            selected_members = [uid for uid, var in member_vars.items() if var.get()]
            if len(selected_members) < 2:
                messagebox.showerror("Error", "Group must have at least 2 members")
                return
            group_id = self.db.create_group(group_name, self.current_user_id, selected_members, color_var.get())
            if group_id:
                messagebox.showinfo("Success", f"Group '{group_name}' created successfully!")
                dialog.destroy()
                self.show_groups()
            else:
                messagebox.showerror("Error", "Failed to create group")
                
        tk.Button(btn_frame, text="Create", bg="#0288D1", fg="white", padx=20, pady=8, bd=0, cursor="hand2", command=create_group).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", bg="#999", fg="white", padx=20, pady=8, bd=0, cursor="hand2", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def add_friend_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Friend")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Add a Friend", font=("Arial", 14, "bold")).pack(padx=20, pady=20)
        tk.Label(dialog, text="Select a user to add as friend:", font=("Arial", 10)).pack(padx=20, pady=10)
        
        all_users = self.db.get_all_users()
        friends = self.db.get_friends(self.current_user_id)
        friend_ids = {row['user_id'] for row in friends}
        
        available_users = [(row['user_id'], row['username']) for row in all_users if row['user_id'] != self.current_user_id and row['user_id'] not in friend_ids]
        
        if not available_users:
            tk.Label(dialog, text="No new users to add", font=("Arial", 10), fg="#999").pack(pady=20)
            tk.Button(dialog, text="Close", bg="#999", fg="white", bd=0, padx=20, pady=8, cursor="hand2", command=dialog.destroy).pack()
            return
            
        user_var = tk.StringVar()
        user_combo = ttk.Combobox(dialog, textvariable=user_var, state="readonly", values=[name for _, name in available_users])
        user_combo.pack(padx=20, fill=tk.X)
        if available_users: user_combo.current(0)
        
        def add_friend():
            selected_name = user_var.get()
            if not selected_name: return
            friend_id = next(uid for uid, name in available_users if name == selected_name)
            if self.db.add_friend(self.current_user_id, friend_id):
                messagebox.showinfo("Success", f"Added {selected_name} as a friend!")
                dialog.destroy()
                self.show_friends()
            else:
                messagebox.showerror("Error", "Failed to add friend")
                
        tk.Button(dialog, text="Add Friend", bg="#0288D1", fg="white", bd=0, padx=20, pady=8, cursor="hand2", command=add_friend).pack(pady=20)
        
    def add_expense_dialog(self, group_id=None):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Expense")
        dialog.geometry("500x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(scrollable_frame, text="Description:", font=("Arial", 10)).pack(padx=20, pady=(20, 5), anchor="w")
        desc_entry = tk.Entry(scrollable_frame, font=("Arial", 10))
        desc_entry.pack(padx=20, fill=tk.X)
        
        tk.Label(scrollable_frame, text="Amount ($):", font=("Arial", 10)).pack(padx=20, pady=(10, 5), anchor="w")
        amount_entry = tk.Entry(scrollable_frame, font=("Arial", 10))
        amount_entry.pack(padx=20, fill=tk.X)
        
        tk.Label(scrollable_frame, text="Paid by:", font=("Arial", 10)).pack(padx=20, pady=(10, 5), anchor="w")
        if group_id:
            members = self.db.get_group_members(group_id)
            payer_options = [row['username'] for row in members]
        else:
            friends = self.db.get_friends(self.current_user_id)
            payer_options = [self.current_user] + [row['username'] for row in friends]
        payer_var = tk.StringVar(value=self.current_user)
        payer_combo = ttk.Combobox(scrollable_frame, textvariable=payer_var, values=payer_options, state="readonly")
        payer_combo.pack(padx=20, fill=tk.X)
        
        group_var = tk.IntVar(value=group_id if group_id else 0)
        if not group_id:
            tk.Label(scrollable_frame, text="Group (optional):", font=("Arial", 10)).pack(padx=20, pady=(10, 5), anchor="w")
            groups = self.db.get_user_groups(self.current_user_id)
            group_options = ["Personal"] + [row['group_name'] for row in groups]
            selected_group = tk.StringVar(value="Personal")
            group_combo = ttk.Combobox(scrollable_frame, textvariable=selected_group, values=group_options, state="readonly")
            group_combo.pack(padx=20, fill=tk.X)
            
        tk.Label(scrollable_frame, text="Split type:", font=("Arial", 10)).pack(padx=20, pady=(10, 5), anchor="w")
        split_var = tk.StringVar(value="equal")
        split_frame = tk.Frame(scrollable_frame)
        split_frame.pack(padx=20, fill=tk.X)
        tk.Radiobutton(split_frame, text="Equal", variable=split_var, value="equal").pack(side=tk.LEFT, padx=5)
        # To keep UI simple for now, simplified split logic handles Equal automatically. 
        # Exact/Percentage would require dynamic UI fields which is a large change.
        # But the backend logic supports them.
        
        tk.Label(scrollable_frame, text="Split between:", font=("Arial", 10)).pack(padx=20, pady=(10, 5), anchor="w")
        participants_frame = tk.Frame(scrollable_frame)
        participants_frame.pack(padx=20, fill=tk.BOTH, expand=True)
        
        participant_vars = {}
        potential_participants = []
        if group_id:
            members = self.db.get_group_members(group_id)
            for row in members: potential_participants.append((row['user_id'], row['username']))
        else:
            potential_participants.append((self.current_user_id, self.current_user))
            friends = self.db.get_friends(self.current_user_id)
            for row in friends: potential_participants.append((row['user_id'], row['username']))
            
        for uid, name in potential_participants:
            var = tk.BooleanVar(value=True) # Default all selected
            cb = tk.Checkbutton(participants_frame, text=name, variable=var, font=("Arial", 10))
            cb.pack(anchor="w", pady=2)
            participant_vars[uid] = (name, var)
                
        btn_frame = tk.Frame(scrollable_frame)
        btn_frame.pack(pady=20)
        
        def save_expense():
            try:
                desc = desc_entry.get().strip()
                amount = float(amount_entry.get())
                payer_name = payer_var.get()
                split_type = split_var.get()
                
                # Determine Payer ID
                if group_id:
                    members = self.db.get_group_members(group_id)
                    payer_id = next(row['user_id'] for row in members if row['username'] == payer_name)
                else:
                    if payer_name == self.current_user: payer_id = self.current_user_id
                    else:
                        friends = self.db.get_friends(self.current_user_id)
                        payer_id = next(row['user_id'] for row in friends if row['username'] == payer_name)
                
                selected_participants = {uid: name for uid, (name, var) in participant_vars.items() if var.get()}
                
                if not desc or amount <= 0 or len(selected_participants) < 1:
                    messagebox.showerror("Error", "Please check fields. At least 1 participant required.")
                    return
                
                selected_group_id = group_id
                if not group_id and 'group_combo' in locals():
                    selected_group_text = selected_group.get()
                    if selected_group_text != "Personal":
                        groups = self.db.get_user_groups(self.current_user_id)
                        selected_group_id = next((row['group_id'] for row in groups if row['group_name'] == selected_group_text), None)
                
                # --- CORE LOGIC FIX HERE ---
                splits = {}
                if split_type == "equal":
                    # Everyone (including payer) splits the amount
                    split_amount = amount / len(selected_participants)
                    for uid in selected_participants:
                        splits[uid] = split_amount
                        
                elif split_type in ["exact", "percentage"]:
                    # Placeholder for UI expansion: 
                    # In a full app, we would pop up a dialog to ask for exact/percentage values.
                    # For now, we default to Equal to prevent crash, but validate logic exists.
                    split_amount = amount / len(selected_participants)
                    for uid in selected_participants:
                        splits[uid] = split_amount

                # Verify Split Integrity
                total_split = sum(splits.values())
                if abs(total_split - amount) > 0.01:
                     messagebox.showerror("Error", "Split amounts do not equal total amount.")
                     return

                expense_id = self.db.add_expense(desc, amount, payer_id, selected_group_id, split_type, splits)
                
                if expense_id:
                    dialog.destroy()
                    self.show_dashboard()
                    messagebox.showinfo("Success", "Expense added successfully!")
                else:
                    messagebox.showerror("Error", "Failed to add expense")
            except ValueError:
                messagebox.showerror("Error", "Invalid amount")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred: {str(e)}")
                print(e)
                
        tk.Button(btn_frame, text="Save", bg="#0288D1", fg="white", padx=20, pady=8, bd=0, cursor="hand2", command=save_expense).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", bg="#999", fg="white", padx=20, pady=8, bd=0, cursor="hand2", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def settle_up_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Settle Up")
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Settle Balances", font=("Arial", 14, "bold")).pack(padx=20, pady=20)
        
        balances = self.db.calculate_balances(self.current_user_id, simplify=self.use_simplified_debts)
        friends = self.db.get_friends(self.current_user_id)
        friend_dict = {row['user_id']: row['username'] for row in friends}
        
        has_balances = False
        for friend_id, balance in balances.items():
            if abs(balance) < 0.01: continue
            has_balances = True
            friend_name = friend_dict.get(friend_id, f"User {friend_id}")
            
            person_frame = tk.Frame(dialog, bg="white", relief=tk.RIDGE, bd=1)
            person_frame.pack(fill=tk.X, padx=20, pady=8)
            
            info_frame = tk.Frame(person_frame, bg="white")
            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15, pady=10)
            
            if balance > 0:
                text = f"{friend_name} owes you"
                amount_text = f"${balance:.2f}"
                amount_color = "#4CAF50"
            else:
                text = f"You owe {friend_name}"
                amount_text = f"${abs(balance):.2f}"
                amount_color = "#F44336"
                
            tk.Label(info_frame, text=text, font=("Arial", 10), bg="white", anchor="w").pack(fill=tk.X)
            tk.Label(info_frame, text=amount_text, font=("Arial", 11, "bold"), bg="white", fg=amount_color, anchor="w").pack(fill=tk.X)
            
            settle_btn = tk.Button(person_frame, text="Settle", font=("Arial", 9), bg="#0288D1", fg="white", bd=0, padx=15, pady=5, cursor="hand2", command=lambda fid=friend_id, fn=friend_name, b=balance, d=dialog: self.confirm_settle(fid, fn, b, d))
            settle_btn.pack(side=tk.RIGHT, padx=10)
            
        if not has_balances:
            tk.Label(dialog, text="All settled up! 🎉", font=("Arial", 12), fg="#999").pack(pady=50)
            
        tk.Button(dialog, text="Close", bg="#999", fg="white", bd=0, padx=20, pady=8, cursor="hand2", command=dialog.destroy).pack(pady=20)
    
    def settle_with_person(self, friend_id, friend_name, balance):
        self.confirm_settle(friend_id, friend_name, balance, None)
    
    def confirm_settle(self, friend_id, friend_name, balance, parent_dialog):
        if balance > 0:
            msg = f"Mark that {friend_name} has paid you ${balance:.2f}?"
            from_user = friend_id
            to_user = self.current_user_id
        else:
            msg = f"Mark that you have paid {friend_name} ${abs(balance):.2f}?"
            from_user = self.current_user_id
            to_user = friend_id
            balance = abs(balance)
            
        result = messagebox.askyesno("Confirm Settlement", msg)
        if result:
            if self.db.settle_balance(from_user, to_user, balance):
                messagebox.showinfo("Success", "Balance settled successfully!")
                if parent_dialog: parent_dialog.destroy()
                self.show_dashboard()
            else:
                messagebox.showerror("Error", "Failed to settle balance")
    
    def logout(self):
        result = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if result: self.root.destroy()

def main():
    db = DatabaseManager()
    login_root = tk.Tk()
    login_window = LoginWindow(login_root, db)
    login_root.mainloop()
    if login_window.user_id:
        main_root = tk.Tk()
        app = ExpenseShareApp(main_root, db, login_window.user_id, login_window.username)
        main_root.mainloop()
    db.close()

if __name__ == "__main__":
    main()