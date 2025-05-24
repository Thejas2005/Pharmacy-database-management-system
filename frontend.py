import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import psycopg2
from psycopg2 import extras # For dict cursor
from datetime import date, datetime, timedelta
from decimal import Decimal
import sys
import os
from tkcalendar import DateEntry
import bcrypt # For password hashing
import configparser # For config file
import logging # For logging
import re # For input validation
 
# --- Configuration ---
CONFIG = configparser.ConfigParser()
CONFIG_FILE = 'config.ini'
APP_VERSION = "1.1.0" # Added for About window
 
LOW_STOCK_ICON = "⚠️"  # Warning sign
EXPIRING_SOON_ICON = "❗" # Exclamation mark
EXPIRED_ICON = "☠️" # Skull and crossbones or similar
 
def load_config():
    config_updated = False
    if not os.path.exists(CONFIG_FILE):
        # Create a default config if it doesn't exist
        CONFIG['Database'] = {
            'host': "localhost", 'port': 6677, 'user': "postgres",
            'password': "qazwerty", 'database': "pharmacy_db"
        }
        CONFIG['Logging'] = {'log_file': 'pharmacy_app.log', 'log_level': 'INFO'}
        CONFIG['Alerts'] = {'expiring_soon_days': '30', 'low_stock_threshold': '10'} # Add Alerts here
        with open(CONFIG_FILE, 'w') as configfile:
            CONFIG.write(configfile)
        messagebox.showinfo("Config Created", f"{CONFIG_FILE} created with default settings. Please review it.")
        config_updated = True # To avoid re-reading immediately if just created
 
    if not config_updated: # If file existed, read it
        CONFIG.read(CONFIG_FILE)
 
    # Ensure Alerts section exists even if the file was old
    if 'Alerts' not in CONFIG:
        CONFIG['Alerts'] = {} # Create the section if it's missing
        config_updated = True # Mark that we need to update the file
 
    # Ensure specific alert keys exist with defaults
    if 'expiring_soon_days' not in CONFIG['Alerts']:
        CONFIG['Alerts']['expiring_soon_days'] = '30'
        config_updated = True
    if 'low_stock_threshold' not in CONFIG['Alerts']:
        CONFIG['Alerts']['low_stock_threshold'] = '10'
        config_updated = True
 
    if config_updated and os.path.exists(CONFIG_FILE): # Save changes if any defaults were added to an existing file
        with open(CONFIG_FILE, 'w') as configfile:
            CONFIG.write(configfile)
        logger.info(f"Config file '{CONFIG_FILE}' updated with default alert settings.")
 
 
load_config() # Call it once at the start
DB_CONFIG = CONFIG['Database']
# Now safely access ALERT_CONFIG
ALERT_CONFIG = CONFIG['Alerts']
 
# --- Logging Setup ---
LOG_FILE = CONFIG.get('Logging', 'log_file', fallback='pharmacy_app.log')
LOG_LEVEL_STR = CONFIG.get('Logging', 'log_level', fallback='INFO').upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)
 
logging.basicConfig(
    filename=LOG_FILE, level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)
 
# --- Tooltip Helper Class ---
class ToolTip:
    # ... (Tooltip class remains the same as your provided version)
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)
 
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
 
    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None
 
# --- Database Helper Functions ---
def db_connect():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as err:
        logger.error(f"Failed to connect to database: {err}", exc_info=True)
        messagebox.showerror("Database Error", f"Failed to connect to database: {err}")
        return None
 
def execute_query(query, params=None, fetch_one=False, fetch_all=False, is_dml=False, use_dict_cursor=False):
    conn = db_connect()
    if not conn: return None
    cursor_factory = psycopg2.extras.DictCursor if use_dict_cursor else None
    cursor = conn.cursor(cursor_factory=cursor_factory)
    result, last_error = None, None
    try:
        cursor.execute(query, params or ())
        if is_dml:
            conn.commit(); result = cursor.rowcount
        elif fetch_one: result = cursor.fetchone()
        elif fetch_all: result = cursor.fetchall()
    except psycopg2.Error as err:
        last_error = err
        logger.error(f"DB query failed: {err}\nQuery: {query}\nParams: {params}", exc_info=True)
        messagebox.showerror("Query Error", f"Database query failed: {err}")
        conn.rollback()
    finally:
        cursor.close(); conn.close()
    execute_query.last_error = last_error
    return result
 
# --- Login Window Class ---
class LoginWindow:
    # ... (LoginWindow class remains largely the same, ensuring bcrypt.checkpw is used)
    def __init__(self, root):
        self.root = root
        self.root.title("PharmaFlow Pro - Login")
        self.root.resizable(False, False)
        self._center_window(400, 280)
        self.main_frame = ttk.Frame(root, padding="20 20 20 20")
        self.main_frame.pack(expand=True, fill=tk.BOTH)
        ttk.Label(self.main_frame, text="Pharmacy Login", font=("Helvetica", 16, "bold"), anchor=tk.CENTER).pack(pady=(0, 20), fill=tk.X)
        user_frame = ttk.Frame(self.main_frame); user_frame.pack(fill=tk.X, pady=5)
        ttk.Label(user_frame, text="Username:", width=10, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.username_entry = ttk.Entry(user_frame); self.username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ToolTip(self.username_entry, "Enter your system username")
        pass_frame = ttk.Frame(self.main_frame); pass_frame.pack(fill=tk.X, pady=5)
        ttk.Label(pass_frame, text="Password:", width=10, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.password_entry = ttk.Entry(pass_frame, show="*"); self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.password_entry.bind("<Return>", self.attempt_login)
        ToolTip(self.password_entry, "Enter your password")
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self.main_frame, textvariable=self.status_var, foreground="red", anchor=tk.CENTER)
        self.status_label.pack(pady=(10, 5), fill=tk.X)
        login_button = ttk.Button(self.main_frame, text="Login", command=self.attempt_login, width=10)
        login_button.pack(pady=(5, 10))
        ToolTip(login_button, "Click to log in")
        self.username_entry.focus_set()
 
    def _center_window(self, width, height):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        cx, cy = int(sw / 2 - width / 2), int(sh / 2 - height / 2)
        self.root.geometry(f'{width}x{height}+{cx}+{cy}')
 
    def attempt_login(self, event=None):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.status_var.set("Username and Password required."); self.status_label.config(foreground="red"); return
 
        query = "SELECT password, role FROM employees WHERE username = %s"
        user_data = execute_query(query, (username,), fetch_one=True, use_dict_cursor=True)
 
        if user_data:
            stored_hashed_password = user_data['password']
            user_role = user_data['role']
            # Ensure stored_hashed_password is bytes for bcrypt.checkpw if it's not already
            if isinstance(stored_hashed_password, str):
                stored_hashed_password_bytes = stored_hashed_password.encode('utf-8')
            else: # Assuming it's already bytes if not str
                stored_hashed_password_bytes = stored_hashed_password
 
            if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password_bytes):
                logger.info(f"User '{username}' logged in successfully with role '{user_role}'.")
                self.status_var.set(""); self.root.destroy()
                launch_main_app(username, user_role)
            else:
                logger.warning(f"Failed login for '{username}': Invalid password.")
                self.status_var.set("Invalid username or password."); self.status_label.config(foreground="red")
                self.password_entry.delete(0, tk.END)
        else:
            logger.warning(f"Failed login: Username '{username}' not found.")
            self.status_var.set("Invalid username or password."); self.status_label.config(foreground="red")
            self.password_entry.delete(0, tk.END)
 
 
# --- "About" Window ---
class AboutWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("About PharmaFlow Pro")
        self.geometry("350x200")
        self.transient(parent)
        self.grab_set()
        # Center window relative to parent (simplified)
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        self_width = 350
        self_height = 200
        position_x = parent_x + (parent_width // 2) - (self_width // 2)
        position_y = parent_y + (parent_height // 2) - (self_height // 2)
        self.geometry(f"+{position_x}+{position_y}")
 
 
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(expand=True, fill=tk.BOTH)
 
        ttk.Label(main_frame, text="PharmaFlow Pro", font=("Helvetica", 16, "bold")).pack(pady=(0,10))
        ttk.Label(main_frame, text=f"Version: {APP_VERSION}").pack()
        ttk.Label(main_frame, text="Pharmacy Management System").pack()
        ttk.Label(main_frame, text="(c) 2024 Your Name/Company").pack(pady=(10,0))
 
        ttk.Button(main_frame, text="OK", command=self.destroy).pack(pady=20)
        self.focus_set()
 
 
# --- Main Application Class ---
class PharmacyApp:
    def __init__(self, root, username, user_role):
        self.root = root
        self.username = username
        self.user_role = user_role
        self.root.title(f"PharmaFlow Pro - Logged in as: {username} ({user_role.capitalize()})")
        self._center_window(1400, 800) # Slightly larger for new tabs
        self.root.minsize(1200, 700)
 
        self.create_menu()
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)
 
        self.inventory_frame = ttk.Frame(self.notebook, padding="10")
        self.prescription_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.inventory_frame, text=' Inventory ')
        self.notebook.add(self.prescription_frame, text=' Prescription Bill ')
 
        if self.user_role == 'admin': # Only admin can see these
            self.suppliers_frame = ttk.Frame(self.notebook, padding="10")
            self.patients_frame = ttk.Frame(self.notebook, padding="10")
            self.reports_frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(self.suppliers_frame, text=' Suppliers ')
            self.notebook.add(self.patients_frame, text=' Patients ')
            self.notebook.add(self.reports_frame, text=' Reports ')
 
        self._init_inventory_vars()
        self._init_prescription_vars()
        if self.user_role == 'admin':
            self._init_suppliers_vars()
            self._init_patients_vars()
            # self._init_reports_vars() # if needed
 
        try:
            self.create_inventory_widgets()
            self.create_prescription_widgets()
            if self.user_role == 'admin':
                self.create_suppliers_widgets()
                self.create_patients_widgets()
                self.create_reports_widgets()
        except AttributeError as ae:
             logger.critical(f"Missing method during GUI setup: {ae}", exc_info=True)
             messagebox.showerror("Initialization Error", f"Missing method: {ae}")
             if self.root.winfo_exists(): self.root.destroy(); return
        except Exception as e:
            logger.critical(f"GUI Creation Error: {e}", exc_info=True)
            messagebox.showerror("GUI Creation Error", f"Failed to create layout: {e}")
            if self.root.winfo_exists(): self.root.destroy(); return
 
        self.fetch_inventory_data()
        self.populate_prescription_medicine_dropdown()
 
        self.status_bar = tk.Label(root, text="Ready", relief=tk.SUNKEN, anchor=tk.W, bd=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.update_status(f"Welcome, {self.username}! System ready.")
        logger.info("PharmacyApp initialized.")
 
    def _init_inventory_vars(self):
        # ... (remains same)
        self.ref_no_var = tk.StringVar(); self.med_name_var = tk.StringVar()
        self.issue_date_var = tk.StringVar(); self.exp_date_var = tk.StringVar()
        self.stock_qty_var = tk.StringVar(); self.age_gap_var = tk.StringVar()
        self.uses_var = tk.StringVar(); self.storage_var = tk.StringVar()
        self.price_var = tk.StringVar(); self.dose_var = tk.StringVar()
        self.search_by_var = tk.StringVar(); self.search_txt_var = tk.StringVar()
        self.inventory_table = None
 
    def _init_prescription_vars(self):
        # ... (remains same)
        self.patient_name_var = tk.StringVar() # For prescription bill
        self.prescription_patient_id_var = tk.StringVar() # For linking to patient record
        self.prescription_medicine_var = tk.StringVar()
        self.prescription_quantity_var = tk.IntVar(value=1)
        self.prescription_total_amount_var = tk.StringVar(value="€ 0.00")
        self.current_prescription_items = []
        self.prescription_item_counter = 1
        self.medicine_ref_lookup = {}
        self.medicine_dropdown = None
        self.prescription_tree = None
        self.dose_display_var = tk.StringVar(value="N/A")
        self.price_display_var = tk.StringVar(value="€ --.--")
        self.stock_display_var = tk.StringVar(value="--")
 
    def _init_suppliers_vars(self):
        self.supplier_id_var = tk.StringVar()
        self.supplier_name_var = tk.StringVar()
        self.supplier_contact_person_var = tk.StringVar()
        self.supplier_phone_var = tk.StringVar()
        self.supplier_email_var = tk.StringVar()
        self.supplier_address_var = tk.StringVar()
        self.suppliers_tree = None
        self.supplier_search_var = tk.StringVar()
 
 
    def _init_patients_vars(self):
        self.patient_id_var = tk.StringVar() # For patient form
        self.patient_full_name_var = tk.StringVar()
        self.patient_dob_var = tk.StringVar()
        self.patient_gender_var = tk.StringVar()
        self.patient_phone_var = tk.StringVar()
        self.patient_email_var = tk.StringVar()
        self.patient_address_var = tk.StringVar()
        self.patient_allergies_var = tk.StringVar()
        self.patients_tree = None
        self.patient_search_var = tk.StringVar()
 
 
    def _center_window(self, w, h):
        # ... (remains same)
        sw=self.root.winfo_screenwidth(); sh=self.root.winfo_screenheight(); cx=int(sw/2-w/2); cy=int(sh/2-h/2); self.root.geometry(f'{w}x{h}+{cx}+{cy}')
 
 
    def update_status(self, msg):
        # ... (remains same)
         if hasattr(self, 'status_bar') and self.status_bar: self.status_bar.config(text=msg)
         logger.info(f"Status update: {msg}")
 
    def create_menu(self):
        menu_bar=tk.Menu(self.root); self.root.config(menu=menu_bar)
        file_menu=tk.Menu(menu_bar,tearoff=0)
        menu_bar.add_cascade(label="File",menu=file_menu)
        if self.user_role == 'admin':
            file_menu.add_command(label="Settings",command=lambda: self.open_settings(self.root))
            file_menu.add_separator()
        file_menu.add_command(label="Logout",command=self.logout)
        file_menu.add_command(label="Exit",command=self.exit_app)
 
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About PharmaFlow Pro", command=self.show_about_window)
 
    def show_about_window(self):
        AboutWindow(self.root)
 
    def open_settings(self, parent):
        # ... (remains same)
        if self.user_role != 'admin':
            messagebox.showwarning("Access Denied", "Only administrators can access settings.")
            logger.warning(f"User '{self.username}' (role: {self.user_role}) tried to access admin settings.")
            return
        try: SettingsWindow(parent, self.username)
        except Exception as e:
            logger.error(f"Failed to open settings window: {e}", exc_info=True)
            messagebox.showerror("Settings Error", f"Failed to open settings: {e}")
 
    def logout(self):
        # ... (remains same)
        if messagebox.askokcancel("Logout", "Are you sure you want to logout?"):
            logger.info(f"User '{self.username}' logged out.")
            self.root.destroy(); main()
 
    def exit_app(self):
        # ... (remains same)
        if messagebox.askokcancel("Exit", "Are you sure you want to exit PharmaFlow Pro?"):
            logger.info("Application exited by user."); self.root.quit()
 
    def create_inventory_widgets(self):
        # ... (Inventory widgets creation largely same, check _format_inventory_row_for_display for icon logic)
        # (Make sure Tooltips are added as in your provided version)
        manage_frame = ttk.Frame(self.inventory_frame)
        manage_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        info_frame = ttk.LabelFrame(manage_frame, text="Medicine Details", padding="15")
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        buttons_frame = ttk.LabelFrame(manage_frame, text="Actions", padding="15")
        buttons_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        AGE_GAP_OPTIONS = ['All Ages', 'Infant', 'Children', '12+', 'Adults', 'Elderly', 'As Prescribed', 'N/A', '']
        STORAGE_OPTIONS = ['Room Temperature', 'Cool Dry Place', 'Refrigerate', 'Protect from Light', 'Keep Frozen', 'Store Below 25°C', 'Store Below 30°C', 'Discard after opening', '']
        ttk.Label(info_frame, text="Ref No:").grid(row=0, column=0, padx=5, pady=(5,0), sticky=tk.W)
        ref_entry = ttk.Entry(info_frame, textvariable=self.ref_no_var, width=25)
        ref_entry.grid(row=1, column=0, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(ref_entry, "Unique Reference Number for the medicine (e.g., SKU)")
        ttk.Label(info_frame, text="Medicine Name:").grid(row=0, column=2, padx=5, pady=(5,0), sticky=tk.W)
        med_name_entry = ttk.Entry(info_frame, textvariable=self.med_name_var, width=25)
        med_name_entry.grid(row=1, column=2, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(med_name_entry, "Full name of the medicine")
        ttk.Label(info_frame, text="Issue Date:").grid(row=2, column=0, padx=5, pady=(5,0), sticky=tk.W)
        issue_date_entry = DateEntry(info_frame, textvariable=self.issue_date_var, width=22, date_pattern='yyyy-mm-dd', state='readonly', showweeknumbers=False, firstweekday='monday')
        issue_date_entry.grid(row=3, column=0, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(issue_date_entry, "Date the medicine batch was issued/received (YYYY-MM-DD)")
        ttk.Label(info_frame, text="Expiry Date:").grid(row=2, column=2, padx=5, pady=(5,0), sticky=tk.W)
        exp_date_entry = DateEntry(info_frame, textvariable=self.exp_date_var, width=22, date_pattern='yyyy-mm-dd', state='readonly', showweeknumbers=False, firstweekday='monday')
        exp_date_entry.grid(row=3, column=2, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(exp_date_entry, "Expiry date of the medicine batch (YYYY-MM-DD)")
        ttk.Label(info_frame, text="Stock Qty:").grid(row=4, column=0, padx=5, pady=(5,0), sticky=tk.W)
        stock_entry = ttk.Entry(info_frame, textvariable=self.stock_qty_var, width=25)
        stock_entry.grid(row=5, column=0, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(stock_entry, "Current quantity in stock (integer)")
        ttk.Label(info_frame, text="Age Gap:").grid(row=4, column=2, padx=5, pady=(5,0), sticky=tk.W)
        age_gap_combo = ttk.Combobox(info_frame, textvariable=self.age_gap_var, values=AGE_GAP_OPTIONS, width=22, state='readonly')
        age_gap_combo.grid(row=5, column=2, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW); age_gap_combo.set(AGE_GAP_OPTIONS[0])
        ToolTip(age_gap_combo, "Recommended age group for the medicine")
        ttk.Label(info_frame, text="Uses:").grid(row=6, column=0, padx=5, pady=(5,0), sticky=tk.W)
        uses_entry = ttk.Entry(info_frame, textvariable=self.uses_var, width=25)
        uses_entry.grid(row=7, column=0, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(uses_entry, "Primary uses or indications of the medicine")
        ttk.Label(info_frame, text="Storage:").grid(row=6, column=2, padx=5, pady=(5,0), sticky=tk.W)
        storage_combo = ttk.Combobox(info_frame, textvariable=self.storage_var, values=STORAGE_OPTIONS, width=22, state='readonly')
        storage_combo.grid(row=7, column=2, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW); storage_combo.set(STORAGE_OPTIONS[0])
        ToolTip(storage_combo, "Recommended storage conditions")
        ttk.Label(info_frame, text="Price (€):").grid(row=8, column=0, padx=5, pady=(5,0), sticky=tk.W)
        price_entry = ttk.Entry(info_frame, textvariable=self.price_var, width=25)
        price_entry.grid(row=9, column=0, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(price_entry, "Selling price per unit (e.g., 12.99)")
        ttk.Label(info_frame, text="Advised Dose:").grid(row=8, column=2, padx=5, pady=(5,0), sticky=tk.W)
        dose_entry = ttk.Entry(info_frame, textvariable=self.dose_var, width=25)
        dose_entry.grid(row=9, column=2, columnspan=2, padx=5, pady=(0,5), sticky=tk.EW)
        ToolTip(dose_entry, "Advised dosage instructions")
        info_frame.grid_columnconfigure(1, weight=1); info_frame.grid_columnconfigure(3, weight=1)
        btn_width = 12; btn_state = tk.NORMAL if self.user_role == 'admin' else tk.DISABLED
        add_btn = ttk.Button(buttons_frame, text="Add New", command=self.add_inventory_data, width=btn_width, state=btn_state)
        add_btn.pack(pady=5, fill=tk.X); ToolTip(add_btn, "Add new medicine (Admin only)")
        update_btn = ttk.Button(buttons_frame, text="Update", command=self.update_inventory_data, width=btn_width, state=btn_state)
        update_btn.pack(pady=5, fill=tk.X); ToolTip(update_btn, "Update selected medicine (Admin only)")
        delete_btn = ttk.Button(buttons_frame, text="Delete", command=self.delete_inventory_data, width=btn_width, state=btn_state)
        delete_btn.pack(pady=5, fill=tk.X); ToolTip(delete_btn, "Delete selected medicine (Admin only)")
        reset_btn = ttk.Button(buttons_frame, text="Reset Fields", command=self.reset_fields, width=btn_width)
        reset_btn.pack(pady=5, fill=tk.X); ToolTip(reset_btn, "Clear all input fields")
        table_frame = ttk.Frame(self.inventory_frame); table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(10,0))
        search_frame = ttk.Frame(table_frame); search_frame.pack(fill=tk.X, pady=(5, 5))
        ttk.Label(search_frame, text="Search By:").pack(side=tk.LEFT, padx=(0, 5))
        search_options = ["Ref No", "Medicine Name", "Uses", "Age Gap", "Stock Qty (Exact)", "Price (Exact)", "Expiring Soon (Days)", "Low Stock"]
        search_combo = ttk.Combobox(search_frame, textvariable=self.search_by_var, values=search_options, state="readonly", width=20); search_combo.pack(side=tk.LEFT, padx=5)
        if search_options: search_combo.current(0); self.search_by_var.set(search_combo.get())
        ToolTip(search_combo, "Select criteria to search by")
        txt_search = ttk.Entry(search_frame, textvariable=self.search_txt_var, width=30); txt_search.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        txt_search.bind("<KeyRelease>", lambda e: self.search_inventory_data())
        ToolTip(txt_search, "Enter search term (for 'Expiring Soon', enter days, e.g., 30. For 'Low Stock', no term needed)")
        search_btn = ttk.Button(search_frame, text="Search", command=self.search_inventory_data, width=10)
        search_btn.pack(side=tk.LEFT, padx=5); ToolTip(search_btn, "Perform search")
        show_all_btn = ttk.Button(search_frame, text="Show All", command=self.fetch_inventory_data, width=10)
        show_all_btn.pack(side=tk.LEFT, padx=5); ToolTip(show_all_btn, "Display all medicines")
        tree_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL); tree_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        self.inventory_table = ttk.Treeview(table_frame, columns=("alert", "ref", "medname", "issd", "expd", "stock", "age", "uses", "storage", "price", "dose"), show="headings", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y); tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X); self.inventory_table.pack(fill=tk.BOTH, expand=True)
        tree_scroll_y.config(command=self.inventory_table.yview); tree_scroll_x.config(command=self.inventory_table.xview)
        headings = {"alert":"!", "ref":"RefNo", "medname":"Medicine", "issd":"Issued", "expd":"Expires", "stock":"Stock", "age":"Age", "uses":"Uses", "storage":"Storage", "price":"Price(€)", "dose":"Dose"}
        col_widths = {"alert":25, "ref":70, "medname":180, "issd":80, "expd":80, "stock":50, "age":80, "uses":150, "storage":120, "price":70, "dose":150}
        col_anchors= {"alert":tk.CENTER, "stock":tk.CENTER, "price":tk.E, "age":tk.CENTER, "issd":tk.CENTER, "expd":tk.CENTER}
        for cid, text in headings.items():
            anchor = col_anchors.get(cid, tk.W); stretch = (cid in ['medname', 'uses', 'dose', 'storage'])
            self.inventory_table.heading(cid, text=text, anchor=anchor); self.inventory_table.column(cid, width=col_widths.get(cid, 100), anchor=anchor, stretch=stretch)
        self.inventory_table.bind("<ButtonRelease-1>", self.get_inventory_cursor)
 
    def _format_inventory_row_for_display(self, db_row):
        if not isinstance(db_row, (psycopg2.extras.DictRow)): return None
        row_dict = dict(db_row)
        formatted = [None] * 11 # Added one for alert icon
        alert_icon = ""
 
        try:
            exp_d = row_dict.get("exp_date")
            stock_qty = row_dict.get("stockqty", 0)
            expiring_soon_days = int(ALERT_CONFIG.get('expiring_soon_days', 30))
            low_stock_threshold = int(ALERT_CONFIG.get('low_stock_threshold', 10))
 
            if isinstance(exp_d, date):
                today = date.today()
                if exp_d < today: alert_icon = EXPIRED_ICON
                elif (exp_d - today).days <= expiring_soon_days: alert_icon = EXPIRING_SOON_ICON
            if stock_qty is not None and stock_qty <= low_stock_threshold:
                alert_icon += LOW_STOCK_ICON if alert_icon else LOW_STOCK_ICON # Append or set
 
            formatted[0] = alert_icon
            formatted[1] = str(row_dict.get("ref_no", ""))
            formatted[2] = str(row_dict.get("medicine_name", ""))
            issue_d = row_dict.get("issue_date"); formatted[3] = issue_d.isoformat() if isinstance(issue_d, date) else ""
            formatted[4] = exp_d.isoformat() if isinstance(exp_d, date) else ""
            formatted[5] = str(stock_qty) if stock_qty is not None else ""
            formatted[6] = str(row_dict.get("age_gap", ""))
            formatted[7] = str(row_dict.get("uses", ""))
            formatted[8] = str(row_dict.get("storage", ""))
            price_val = row_dict.get("price"); formatted[9] = f"€{float(price_val):.2f}" if isinstance(price_val, (Decimal, int, float)) else ""
            formatted[10] = str(row_dict.get("dose", ""))
            return formatted
        except (IndexError, ValueError, TypeError) as e:
            logger.error(f"Error formatting inventory row: {e}. Row: {row_dict}", exc_info=True)
            return None
 
    def fetch_inventory_data(self):
        # ... (Modify to call new _format_inventory_row_for_display)
        if not self.inventory_table: return
        query = "SELECT ref_no, medicine_name, issue_date, exp_date, stockqty, age_gap, uses, storage, price, dose FROM medicines ORDER BY medicine_name"
        rows = execute_query(query, fetch_all=True, use_dict_cursor=True)
        self.inventory_table.delete(*self.inventory_table.get_children()); count = 0
        if rows:
            for row_data in rows:
                fmt_values = self._format_inventory_row_for_display(row_data)
                if fmt_values:
                    self.inventory_table.insert("", tk.END, values=fmt_values)
                    count += 1
        elif rows is None: self.update_status("Error fetching inventory."); return
        self.update_status(f"Inventory loaded. {count} items.")
 
    def get_inventory_cursor(self, event=""):
        # ... (Adjust for the new 'alert' column at index 0)
        if not self.inventory_table: return
        try:
            row_id = self.inventory_table.focus();
            if not row_id: return
            vals = self.inventory_table.item(row_id)["values"]
            if len(vals) == 11: # Now 11 columns with alert
                self.ref_no_var.set(vals[1]); self.med_name_var.set(vals[2]); self.issue_date_var.set(vals[3]); self.exp_date_var.set(vals[4])
                self.stock_qty_var.set(vals[5]); self.age_gap_var.set(vals[6]); self.uses_var.set(vals[7]); self.storage_var.set(vals[8])
                self.price_var.set(str(vals[9]).replace('€', '').strip()); self.dose_var.set(vals[10])
                self.update_status(f"Selected: {vals[2]} ({vals[1]})")
        except Exception as e:
            logger.error(f"Error in get_inventory_cursor: {e}", exc_info=True)
            self.update_status(f"Error selecting: {e}")
 
 
    def validate_inventory_fields(self, check_ref_exists_for_add=False):
        # ... (largely same, ensure it's robust)
        ref = self.ref_no_var.get().strip(); name = self.med_name_var.get().strip()
        stock_str = self.stock_qty_var.get().strip(); price_str = self.price_var.get().strip()
        issue_str = self.issue_date_var.get().strip(); expiry_str = self.exp_date_var.get().strip()
        errors = []
        if not ref: errors.append("Ref No required.")
        elif not re.match(r"^[a-zA-Z0-9_-]+$", ref): errors.append("Ref No: A-Z, 0-9, _, - allowed.")
        if not name: errors.append("Medicine Name required.")
        try:
            if stock_str and int(stock_str)<0: errors.append("Stock >= 0.")
            if price_str and Decimal(price_str)<0: errors.append("Price >= 0.")
        except ValueError: errors.append("Stock/Price must be numbers.")
        def check_date(d, n):
            if not d: return True
            try: datetime.strptime(d, '%Y-%m-%d'); return True
            except ValueError: errors.append(f"{n} must be YYYY-MM-DD."); return False
        if not check_date(issue_str, "Issue Date") or not check_date(expiry_str, "Expiry Date"): pass # Error added in list
        if issue_str and expiry_str:
             try:
                 if datetime.strptime(expiry_str,'%Y-%m-%d').date() < datetime.strptime(issue_str,'%Y-%m-%d').date():
                      errors.append("Expiry cannot be before Issue Date.")
             except ValueError: pass # Format error handled above
        if check_ref_exists_for_add:
            count = execute_query("SELECT 1 FROM medicines WHERE lower(ref_no) = lower(%s) LIMIT 1", (ref.lower(),), fetch_one=True)
            if count: errors.append(f"Ref No '{ref}' exists.");
            elif execute_query.last_error: errors.append("DB error checking RefNo.")
        if errors: messagebox.showwarning("Validation Error", "\n".join(errors)); return False
        return True
 
    def _get_inventory_params_from_fields(self):
        # ... (Ensure Decimal for price)
        try:
            s=self.stock_qty_var.get().strip(); p=self.price_var.get().strip(); iss=self.issue_date_var.get().strip(); exp=self.exp_date_var.get().strip()
            return (self.ref_no_var.get().strip(), self.med_name_var.get().strip(), iss or None, exp or None, int(s) if s else None,
                    self.age_gap_var.get().strip() or None, self.uses_var.get().strip() or None, self.storage_var.get().strip() or None,
                    Decimal(p) if p else None, self.dose_var.get().strip() or None)
        except ValueError as e:
            logger.error(f"Error parsing inventory field data: {e}", exc_info=True)
            messagebox.showerror("Data Error", f"Invalid number: {e}"); return None
 
    def add_inventory_data(self): # Admin only
        # ... (same logic, ensure role check)
        if self.user_role != 'admin': messagebox.showwarning("Access Denied", "Admin only."); return
        if not self.validate_inventory_fields(True): return
        params = self._get_inventory_params_from_fields();
        if params is None: return
        q="INSERT INTO medicines (ref_no,medicine_name,issue_date,exp_date,stockqty,age_gap,uses,storage,price,dose) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        rows = execute_query(q, params, is_dml=True)
        if rows: self.fetch_inventory_data(); self.populate_prescription_medicine_dropdown(); messagebox.showinfo("Success", "Medicine added."); n,r=params[1],params[0]; self.reset_fields(); self.update_status(f"Added: {n} ({r})")
        elif rows==0: messagebox.showwarning("No Change", "Add failed (0 rows)."); self.update_status("Add failed.")
 
    def update_inventory_data(self): # Admin only
        # ... (same logic, ensure role check)
        if self.user_role != 'admin': messagebox.showwarning("Access Denied", "Admin only."); return
        if not self.inventory_table or not self.inventory_table.focus(): messagebox.showwarning("No Selection", "Select item."); return
        original_ref_no = self.inventory_table.item(self.inventory_table.focus())["values"][1] # Assuming ref is index 1 after alert
        if not self.validate_inventory_fields(False): return
        params = self._get_inventory_params_from_fields();
        if params is None: return
        new_ref_no = params[0]
        # If ref_no is changed, check for conflicts
        if new_ref_no.lower() != original_ref_no.lower():
            count = execute_query("SELECT 1 FROM medicines WHERE lower(ref_no) = lower(%s) LIMIT 1", (new_ref_no.lower(),), fetch_one=True)
            if count: messagebox.showwarning("Duplicate", f"New Ref No '{new_ref_no}' already exists."); return
        # Update uses the original_ref_no in WHERE, but sets all fields including potentially new ref_no
        q_final="UPDATE medicines SET medicine_name=%s,issue_date=%s,exp_date=%s,stockqty=%s,age_gap=%s,uses=%s,storage=%s,price=%s,dose=%s, ref_no=%s WHERE ref_no=%s"
        params_upd_with_new_ref = list(params[1:]) + [new_ref_no] + [original_ref_no] # medicine_name to dose, then new_ref, then original_ref for WHERE
        rows = execute_query(q_final, tuple(params_upd_with_new_ref), is_dml=True)
        if rows is not None: self.fetch_inventory_data(); self.populate_prescription_medicine_dropdown(); n=self.med_name_var.get().strip(); messagebox.showinfo("Success", f"'{n}' updated."); self.update_status(f"Updated: {n} ({new_ref_no})")
 
 
    def delete_inventory_data(self): # Admin only
        # ... (same logic, ensure role check)
        if self.user_role != 'admin': messagebox.showwarning("Access Denied", "Admin only."); return
        if not self.inventory_table or not self.inventory_table.focus(): messagebox.showwarning("No Selection", "Select item."); return
        ref = self.ref_no_var.get().strip(); name = self.med_name_var.get().strip()
        if not ref: messagebox.showwarning("Error", "Ref No empty."); return
        # Check dependencies (e.g., in sales_items, purchase_order_items) before allowing delete
        # For simplicity, this check is omitted here, but crucial in a real app.
        # Foreign Key constraints with ON DELETE RESTRICT in DB would prevent deletion if dependencies exist.
        if messagebox.askyesno("Confirm", f"Delete '{name}' ({ref})? This action cannot be undone and might fail if this medicine is part of existing sales or purchase orders."):
            rows = execute_query("DELETE FROM medicines WHERE ref_no=%s", (ref,), is_dml=True)
            if rows: self.fetch_inventory_data(); self.populate_prescription_medicine_dropdown(); self.reset_fields(); messagebox.showinfo("Deleted", f"'{name}' deleted."); self.update_status(f"Deleted: {name} ({ref})")
            elif rows == 0: messagebox.showwarning("Not Found", f"'{name}' not found for deletion."); self.update_status(f"Not found ({ref}).")
            elif execute_query.last_error: messagebox.showerror("Delete Failed", f"Could not delete '{name}'. It might be referenced in other records (e.g., sales). Error: {execute_query.last_error}")
 
 
    def reset_fields(self):
        # ... (same logic)
        self.ref_no_var.set(""); self.med_name_var.set(""); self.issue_date_var.set(""); self.exp_date_var.set("")
        self.stock_qty_var.set(""); self.age_gap_var.set("All Ages"); self.uses_var.set(""); self.storage_var.set("Room Temperature")
        self.price_var.set(""); self.dose_var.set("")
        if self.inventory_table:
             sel=self.inventory_table.focus()
             if sel: self.inventory_table.selection_remove(sel)
        self.update_status("Fields cleared.")
 
    def search_inventory_data(self):
        # ... (Modify to include "Low Stock" and use _format_inventory_row_for_display)
        if not self.inventory_table: return
        s_by = self.search_by_var.get(); term = self.search_txt_var.get().strip()
        if not s_by: messagebox.showwarning("Search", "Select criteria."); return
        if not term and s_by not in ["Show All", "Low Stock"]:
             if s_by not in ["Expiring Soon (Days)"]: messagebox.showwarning("Search", "Enter search term."); return
 
        base_query = "SELECT ref_no, medicine_name, issue_date, exp_date, stockqty, age_gap, uses, storage, price, dose FROM medicines"
        where_clauses = []; params_list = []
        cols={"Ref No":"ref_no","Medicine Name":"medicine_name","Uses":"uses","Age Gap":"age_gap"}
 
        if s_by in cols:
            where_clauses.append(f"LOWER({cols[s_by]}) ILIKE %s"); params_list.append(f"%{term.lower()}%")
        elif s_by == "Stock Qty (Exact)":
            try: where_clauses.append("stockqty = %s"); params_list.append(int(term))
            except ValueError: messagebox.showwarning("Search", "Enter valid number for Stock Qty."); return
        elif s_by == "Price (Exact)":
            try: where_clauses.append("price = %s"); params_list.append(Decimal(term))
            except ValueError: messagebox.showwarning("Search", "Enter valid number for Price."); return
        elif s_by == "Expiring Soon (Days)":
            try:
                days = int(term); expiring_soon_days_val = date.today() + timedelta(days=days)
                where_clauses.append("exp_date >= CURRENT_DATE AND exp_date <= %s"); params_list.append(expiring_soon_days_val)
            except ValueError: messagebox.showwarning("Search", "Enter valid number of days."); return
        elif s_by == "Low Stock":
            low_stock_val = int(ALERT_CONFIG.get('low_stock_threshold', 10))
            where_clauses.append("stockqty <= %s"); params_list.append(low_stock_val)
        else: messagebox.showerror("Search", "Invalid criteria."); return
 
        full_query = base_query
        if where_clauses: full_query += " WHERE " + " AND ".join(where_clauses)
        full_query += " ORDER BY medicine_name"
 
        rows=execute_query(full_query, tuple(params_list), fetch_all=True, use_dict_cursor=True)
        self.inventory_table.delete(*self.inventory_table.get_children()); count=0
        if rows:
            for r_data in rows:
                fmt=self._format_inventory_row_for_display(r_data)
                if fmt: self.inventory_table.insert("", tk.END, values=fmt); count+=1
        elif rows is None: self.update_status("Search error."); return
        self.update_status(f"{count} items found for '{term if term or s_by=='Low Stock' else s_by}' in '{s_by}'.")
 
 
    def create_prescription_widgets(self):
        # ... (Largely same, ensure ToolTips and patient_id handling if linking prescriptions to patients table)
        panned = ttk.PanedWindow(self.prescription_frame, orient=tk.HORIZONTAL)
        panned.pack(fill=tk.BOTH, expand=True, pady=10)
        add_item_frame = ttk.LabelFrame(panned, text="Add Item to Prescription", padding="15")
        panned.add(add_item_frame, weight=40)
        current_prescription_frame = ttk.LabelFrame(panned, text="Current Prescription", padding="15")
        panned.add(current_prescription_frame, weight=60)
        # Patient Name / ID selection
        pat_frame = ttk.Frame(add_item_frame)
        pat_frame.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(pat_frame, text="Patient Name:").pack(side=tk.LEFT, padx=(0,5))
        patient_entry = ttk.Entry(pat_frame, textvariable=self.patient_name_var, width=30)
        patient_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ToolTip(patient_entry, "Enter patient's full name (optional, or select registered patient)")
        # Add a button to select patient from Patients tab if desired
        # ttk.Button(pat_frame, text="Select...", command=self.select_patient_for_prescription).pack(side=tk.LEFT, padx=5)
 
        ttk.Label(add_item_frame, text="Select Medicine:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.medicine_dropdown = ttk.Combobox(add_item_frame, textvariable=self.prescription_medicine_var, state="readonly", width=38)
        self.medicine_dropdown.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky=tk.EW)
        self.medicine_dropdown.bind("<<ComboboxSelected>>", self.update_medicine_details_display)
        ToolTip(self.medicine_dropdown, "Select medicine from available stock")
        ttk.Label(add_item_frame, text="Instructions:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        dose_display_label = ttk.Label(add_item_frame, textvariable=self.dose_display_var, wraplength=280, justify=tk.LEFT, relief=tk.GROOVE, padding=3, foreground="blue")
        dose_display_label.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky=tk.EW, ipady=5)
        ToolTip(dose_display_label, "Advised dosage for the selected medicine")
        ttk.Label(add_item_frame, text="Unit Price:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        price_val_label = ttk.Label(add_item_frame, textvariable=self.price_display_var, font=("Helvetica", 10, "bold"))
        price_val_label.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(price_val_label, "Price per unit of the selected medicine")
        ttk.Label(add_item_frame, text="Available:").grid(row=3, column=2, padx=5, pady=5, sticky=tk.E)
        stock_val_label = ttk.Label(add_item_frame, textvariable=self.stock_display_var, font=("Helvetica", 10, "bold"))
        stock_val_label.grid(row=3, column=3, padx=5, pady=5, sticky=tk.W)
        ToolTip(stock_val_label, "Current stock quantity available")
        ttk.Label(add_item_frame, text="Quantity Reqd:").grid(row=4, column=0, padx=5, pady=15, sticky=tk.W)
        qty_spinbox = ttk.Spinbox(add_item_frame, from_=1, to=999, textvariable=self.prescription_quantity_var, width=10)
        qty_spinbox.grid(row=4, column=1, padx=5, pady=15, sticky=tk.W)
        ToolTip(qty_spinbox, "Enter quantity of medicine required")
        add_button = ttk.Button(add_item_frame, text="Add to Prescription", command=self.add_item_to_prescription)
        add_button.grid(row=5, column=0, columnspan=4, padx=5, pady=20)
        ToolTip(add_button, "Add selected medicine and quantity to the current bill")
        add_item_frame.grid_columnconfigure(1, weight=1); add_item_frame.grid_columnconfigure(3, weight=1)
        tree_frame = ttk.Frame(current_prescription_frame); tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL); scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.prescription_tree = ttk.Treeview(tree_frame, columns=("Sr", "Name", "HowToTake", "Qty", "Price", "Total"), show="headings", yscrollcommand=scroll.set)
        self.prescription_tree.pack(fill=tk.BOTH, expand=True); scroll.config(command=self.prescription_tree.yview)
        h={"Sr":("Sr.",30,tk.CENTER), "Name":("Medicine",180,tk.W), "HowToTake":("Instructions",200,tk.W), "Qty":("Qty",40,tk.CENTER), "Price":("Unit €",70,tk.E), "Total":("Total €",80,tk.E)}
        for i,(t,w,a) in h.items(): self.prescription_tree.heading(i,text=t,anchor=a); self.prescription_tree.column(i,width=w,stretch=(i in ["Name","HowToTake"]),anchor=a)
        bot_frame = ttk.Frame(current_prescription_frame); bot_frame.pack(fill=tk.X, pady=5)
        ttk.Label(bot_frame, text="Grand Total:", font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        total_amount_label = ttk.Label(bot_frame, textvariable=self.prescription_total_amount_var, font=('Helvetica', 14, 'bold'), anchor=tk.E)
        total_amount_label.pack(side=tk.RIGHT, padx=10); ToolTip(total_amount_label, "Total amount for the current prescription")
        btn_frame = ttk.Frame(current_prescription_frame); btn_frame.pack(pady=(10,0))
        generate_bill_btn = ttk.Button(btn_frame, text="Generate Bill", command=self.generate_prescription_bill, width=15)
        generate_bill_btn.pack(side=tk.LEFT, padx=10); ToolTip(generate_bill_btn, "Finalize and generate the bill")
        clear_pres_btn = ttk.Button(btn_frame, text="Clear Prescription", command=self.clear_prescription, width=15)
        clear_pres_btn.pack(side=tk.LEFT, padx=10); ToolTip(clear_pres_btn, "Clear all items from current bill")
 
    def update_medicine_details_display(self, event=None):
        # ... (same logic)
        name = self.prescription_medicine_var.get()
        if not name: self.dose_display_var.set("N/A"); self.price_display_var.set("€ --.--"); self.stock_display_var.set("--"); return
        ref = self.medicine_ref_lookup.get(name)
        if not ref: self.dose_display_var.set("Error"); self.price_display_var.set("Error"); self.stock_display_var.set("Err"); return
        res = execute_query("SELECT dose, price, stockqty FROM medicines WHERE ref_no = %s", (ref,), fetch_one=True, use_dict_cursor=True)
        if res:
            dose=str(res['dose']) if res['dose'] else "N/A"; price=res['price']; stock=int(res['stockqty']) if res['stockqty'] is not None else 0
            self.dose_display_var.set(dose); self.price_display_var.set(f"€{float(price):.2f}" if isinstance(price,(Decimal,int,float)) else "€ --.--"); self.stock_display_var.set(str(stock))
        else: self.dose_display_var.set("N/A"); self.price_display_var.set("€ --.--"); self.stock_display_var.set("--")
 
    def populate_prescription_medicine_dropdown(self):
        # ... (same logic)
        if not self.medicine_dropdown: logger.warning("Dropdown widget not ready."); return
        q="SELECT ref_no, medicine_name FROM medicines WHERE stockqty > 0 ORDER BY medicine_name"
        res=execute_query(q, fetch_all=True, use_dict_cursor=True)
        mlist=[]; self.medicine_ref_lookup.clear()
        if res:
            for item in res:
                dn=str(item['medicine_name']) if item['medicine_name'] else "?"; rn=str(item['ref_no']) if item['ref_no'] else ""
                if rn: mlist.append(dn); self.medicine_ref_lookup[dn]=rn
        self.medicine_dropdown['values']=mlist
        if mlist: self.prescription_medicine_var.set(mlist[0]); self.update_medicine_details_display()
        else: self.prescription_medicine_var.set(""); self.update_medicine_details_display()
 
 
    def add_item_to_prescription(self):
        # ... (same logic, including check for existing item)
        if not self.prescription_tree or not self.medicine_dropdown: return
        name = self.prescription_medicine_var.get()
        try: qty = self.prescription_quantity_var.get()
        except tk.TclError: messagebox.showerror("Invalid", "Qty must be number."); return
        if not name: messagebox.showwarning("Missing", "Select medicine."); return
        if qty <= 0: messagebox.showwarning("Invalid", "Qty must be > 0."); return
        ref = self.medicine_ref_lookup.get(name)
        if not ref: messagebox.showerror("Error", "Cannot find Ref No."); return
        res = execute_query("SELECT medicine_name, stockqty, price, dose FROM medicines WHERE ref_no=%s", (ref,), fetch_one=True, use_dict_cursor=True)
        if not res: messagebox.showerror("Error", f"Data for '{name}' not found."); self.populate_prescription_medicine_dropdown(); return
        m_name=str(res['medicine_name']) if res['medicine_name'] else "?"; stock=int(res['stockqty']) if res['stockqty'] is not None else 0; price=Decimal(str(res['price'])) if isinstance(res['price'],(Decimal,int,float)) else Decimal('0.00'); dose=str(res['dose']) if res['dose'] else "N/A"
        if qty > stock: messagebox.showwarning("Stock Low", f"Only {stock} of '{m_name}' left."); return
        total_item_price = qty * price
        item_data = {'ref_no':ref,'name':m_name,'qty':qty,'unit_price':price,'total_price':total_item_price,'dose':dose,'sr_no':self.prescription_item_counter}
        existing_item = next((i for i in self.current_prescription_items if i['ref_no'] == ref), None)
        if existing_item:
            if messagebox.askyesno("Item Exists", f"'{m_name}' is already in bill. Add this quantity to existing entry?"):
                new_qty = existing_item['qty'] + qty
                if new_qty > stock: messagebox.showwarning("Stock Low", f"Cannot add {qty} more. Total {new_qty} exceeds stock {stock}."); return
                existing_item['qty'] = new_qty; existing_item['total_price'] = new_qty * price
                for child_id in self.prescription_tree.get_children(): # Update Treeview
                    if self.prescription_tree.item(child_id, 'values')[1] == m_name:
                        self.prescription_tree.item(child_id, values=(self.prescription_tree.item(child_id, 'values')[0], m_name, dose, str(new_qty), f"€ {price:.2f}", f"€ {existing_item['total_price']:.2f}"))
                        break
            else: # Add as new line
                self.current_prescription_items.append(item_data)
                self.prescription_tree.insert("", tk.END, iid=f"item_{self.prescription_item_counter}", values=(self.prescription_item_counter, m_name, dose, str(qty), f"€ {price:.2f}", f"€ {total_item_price:.2f}"))
                self.prescription_item_counter += 1
        else: # New item
            self.current_prescription_items.append(item_data)
            self.prescription_tree.insert("", tk.END, iid=f"item_{self.prescription_item_counter}", values=(self.prescription_item_counter, m_name, dose, str(qty), f"€ {price:.2f}", f"€ {total_item_price:.2f}"))
            self.prescription_item_counter += 1
        self.update_prescription_grand_total(); self.update_status(f"Added: {qty}x{m_name}"); self.prescription_quantity_var.set(1)
 
 
    def update_prescription_grand_total(self):
        # ... (same logic)
        total=sum(i['total_price'] for i in self.current_prescription_items); self.prescription_total_amount_var.set(f"€ {total:.2f}")
 
    def generate_prescription_bill(self):
        if not self.current_prescription_items: messagebox.showwarning("Empty", "Add items."); return
        p_name = self.patient_name_var.get().strip()
 
        if not p_name and not messagebox.askyesno("Confirm", "Patient name empty. Continue?"): return
        grand_total=sum(i['total_price'] for i in self.current_prescription_items); count=len(self.current_prescription_items)
        if not messagebox.askyesno("Confirm", f"Patient: {p_name or 'N/A'}\nItems: {count}\nTotal: € {grand_total:.2f}\nGenerate Bill?"): return
 
        conn=db_connect();
        if not conn: return
        cursor=conn.cursor()
        try:
            # --- DEBUG START ---
            print("DEBUG: Attempting to insert into sales_transactions...")
            trans_query = """INSERT INTO sales_transactions (patient_name, employee_username, total_amount)
                             VALUES (%s, %s, %s) RETURNING transaction_id;"""
            params_trans = (p_name or None, self.username, grand_total)
            print(f"DEBUG: trans_query: {trans_query}")
            print(f"DEBUG: params_trans: {params_trans}, length: {len(params_trans)}")
            # --- DEBUG END ---
            cursor.execute(trans_query, params_trans)
 
            fetched_row = cursor.fetchone()
            # --- DEBUG START ---
            print(f"DEBUG: fetched_row from sales_transactions insert: {fetched_row}")
            # --- DEBUG END ---
            if fetched_row is None or len(fetched_row) == 0:
                raise psycopg2.DatabaseError("Failed to retrieve transaction_id after insert into sales_transactions.")
            transaction_id = fetched_row[0]
            print(f"DEBUG: Obtained transaction_id: {transaction_id}")
 
 
            update_stock_q = "UPDATE medicines SET stockqty = stockqty - %s WHERE ref_no = %s AND stockqty >= %s"
            insert_item_q = """INSERT INTO sales_items (transaction_id, medicine_ref_no, medicine_name, quantity_sold, unit_price, item_total)
                               VALUES (%s, %s, %s, %s, %s, %s);"""
 
            for item_index, item in enumerate(self.current_prescription_items): # Added index for logging
                # --- DEBUG START ---
                print(f"DEBUG: Processing item {item_index + 1} for stock update: {item['name']}")
                params_stock_update = (item['qty'], item['ref_no'], item['qty'])
                print(f"DEBUG: update_stock_q: {update_stock_q}")
                print(f"DEBUG: params_stock_update: {params_stock_update}, length: {len(params_stock_update)}")
                # --- DEBUG END ---
                cursor.execute(update_stock_q, params_stock_update)
                if cursor.rowcount==0: raise psycopg2.DatabaseError(f"Stock update fail for {item['name']}. Billing rolled back.")
 
                # --- DEBUG START ---
                print(f"DEBUG: Processing item {item_index + 1} for sales_items insert: {item['name']}")
                params_sales_item = (
                    transaction_id,
                    item['ref_no'],
                    item['name'],
                    item['qty'],
                    item['unit_price'],
                    item['total_price']
                )
                print(f"DEBUG: insert_item_q: {insert_item_q}")
                print(f"DEBUG: params_sales_item: {params_sales_item}, length: {len(params_sales_item)}")
                # --- DEBUG END ---
                cursor.execute(insert_item_q, params_sales_item)
 
            conn.commit()
            logger.info(f"Bill #{transaction_id} generated for patient '{p_name}' by {self.username}.")
            self._display_prescription_receipt(grand_total, p_name, transaction_id)
            self.clear_prescription(); self.fetch_inventory_data(); self.populate_prescription_medicine_dropdown()
            self.update_status(f"Bill #{transaction_id} for {p_name or 'Patient'}. Total: €{grand_total:.2f}")
        except(psycopg2.Error, Exception) as err:
            conn.rollback(); logger.error(f"Billing Error: {err}", exc_info=True)
            # Make sure the original error message is preserved or enhanced
            error_message_detail = f"Error: {str(err)}"
            if isinstance(err, IndexError) and "tuple index out of range" in str(err):
                 error_message_detail = "Error: tuple index out of range. This usually means a mismatch between SQL placeholders and parameters."
 
            messagebox.showerror("Billing Error", f"{error_message_detail}\nRolled back.");
            self.update_status("Billing error.")
        finally:
            cursor.close(); conn.close()
 
 
    def _display_prescription_receipt(self, total, patient_name, transaction_id):
        # ... (same logic, ensures transaction_id is displayed)
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"); lines=[f"-- PharmaFlow Pro --",f"    Prescription Bill", f"Bill No: {transaction_id}",f"Date: {ts}",f"Patient: {patient_name or 'N/A'}",f"Pharmacist: {self.username}","-"*60,f"{'Sr':<3} {'Medicine':<25} {'Qty':<4} {'Instructions':<30}","-"*60];
        for i in self.current_prescription_items:
            dose_line = i['dose'][:29] + '…' if len(i['dose']) > 30 else i['dose']
            lines.append(f"{i['sr_no']:<3} {i['name'][:24]:<25} {i['qty']:<4} {dose_line:<30}")
        lines.extend(["="*60, f"{'Grand Total:':<52} €{total:>7.2f}", "-"*60, "Thank you! Follow instructions carefully."]); receipt="\n".join(lines)
        win=tk.Toplevel(self.root); win.title(f"Receipt - Bill #{transaction_id}"); win.geometry("550x450")
        txt=tk.Text(win,wrap="word",font=("Courier New",10),height=25,width=75); txt.pack(padx=10,pady=10,fill=tk.BOTH,expand=True)
        txt.insert(tk.END,receipt); txt.config(state=tk.DISABLED);
        close_btn=ttk.Button(win, text="Close", command=win.destroy); close_btn.pack(pady=10)
        ToolTip(close_btn, "Close this receipt window"); win.transient(self.root); win.grab_set(); self.root.wait_window(win)
 
    def clear_prescription(self):
        # ... (same logic)
        if self.prescription_tree: self.prescription_tree.delete(*self.prescription_tree.get_children())
        self.current_prescription_items.clear(); self.prescription_total_amount_var.set("€ 0.00"); self.prescription_item_counter=1; self.prescription_quantity_var.set(1)
        self.patient_name_var.set(""); self.prescription_patient_id_var.set("")
        if self.medicine_dropdown and self.medicine_dropdown['values']: self.prescription_medicine_var.set(self.medicine_dropdown['values'][0]); self.update_medicine_details_display()
        else: self.prescription_medicine_var.set(""); self.dose_display_var.set("N/A"); self.price_display_var.set("€ --.--"); self.stock_display_var.set("--")
        self.update_status("Prescription cleared.")
 
    # --- Supplier Management (Admin Only) ---
    def create_suppliers_widgets(self):
        # Basic CRUD for suppliers
        # Top: Form for Add/Update, Bottom: Treeview, Right: Buttons
        # This is a simplified version. A real one would be more complex.
        if self.user_role != 'admin': return
 
        # Main PanedWindow for form and tree
        panned = ttk.PanedWindow(self.suppliers_frame, orient=tk.VERTICAL)
        panned.pack(fill=tk.BOTH, expand=True)
 
        form_frame_outer = ttk.LabelFrame(panned, text="Supplier Details", padding="10")
        panned.add(form_frame_outer, weight=1)
 
        form_frame = ttk.Frame(form_frame_outer)
        form_frame.pack(fill=tk.X, padx=5, pady=5)
 
        ttk.Label(form_frame, text="ID:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        id_entry = ttk.Entry(form_frame, textvariable=self.supplier_id_var, state='readonly', width=10)
        id_entry.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        ToolTip(id_entry, "Supplier ID (auto-generated)")
 
        ttk.Label(form_frame, text="Name*:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        name_entry = ttk.Entry(form_frame, textvariable=self.supplier_name_var, width=40)
        name_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
        ToolTip(name_entry, "Supplier's company name (required)")
 
        ttk.Label(form_frame, text="Contact Person:").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
        contact_entry = ttk.Entry(form_frame, textvariable=self.supplier_contact_person_var, width=40)
        contact_entry.grid(row=2, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
 
        ttk.Label(form_frame, text="Phone:").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
        phone_entry = ttk.Entry(form_frame, textvariable=self.supplier_phone_var, width=20)
        phone_entry.grid(row=3, column=1, padx=5, pady=2, sticky=tk.W)
 
        ttk.Label(form_frame, text="Email:").grid(row=3, column=2, padx=5, pady=2, sticky=tk.W)
        email_entry = ttk.Entry(form_frame, textvariable=self.supplier_email_var, width=30)
        email_entry.grid(row=3, column=3, padx=5, pady=2, sticky=tk.EW)
 
        ttk.Label(form_frame, text="Address:").grid(row=4, column=0, padx=5, pady=2, sticky=tk.NW)
        address_text = tk.Text(form_frame, height=3, width=38) # Using tk.Text for multiline
        address_text.grid(row=4, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
        self.supplier_address_text_widget = address_text # Store reference to get/set text
        ToolTip(address_text, "Supplier's physical address")
 
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_columnconfigure(3, weight=1)
 
        button_bar = ttk.Frame(form_frame_outer)
        button_bar.pack(fill=tk.X, pady=10)
        ttk.Button(button_bar, text="Add New", command=self.add_supplier).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_bar, text="Update", command=self.update_supplier).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_bar, text="Delete", command=self.delete_supplier).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_bar, text="Clear Fields", command=self.clear_supplier_fields).pack(side=tk.LEFT, padx=5)
 
 
        tree_frame_outer = ttk.LabelFrame(panned, text="Supplier List", padding="10")
        panned.add(tree_frame_outer, weight=3)
 
        search_sup_frame = ttk.Frame(tree_frame_outer)
        search_sup_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_sup_frame, text="Search Name:").pack(side=tk.LEFT, padx=2)
        ttk.Entry(search_sup_frame, textvariable=self.supplier_search_var, width=30).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(search_sup_frame, text="Search", command=self.fetch_suppliers_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_sup_frame, text="Show All", command=lambda: (self.supplier_search_var.set(""), self.fetch_suppliers_data())).pack(side=tk.LEFT, padx=2)
 
 
        self.suppliers_tree = ttk.Treeview(tree_frame_outer, columns=("id", "name", "contact", "phone", "email"), show="headings")
        self.suppliers_tree.pack(fill=tk.BOTH, expand=True)
        cols_sup = {"id":"ID", "name":"Supplier Name", "contact":"Contact Person", "phone":"Phone", "email":"Email"}
        widths_sup = {"id":50, "name":200, "contact":150, "phone":120, "email":180}
        for c_id, c_text in cols_sup.items():
            self.suppliers_tree.heading(c_id, text=c_text)
            self.suppliers_tree.column(c_id, width=widths_sup[c_id], stretch=tk.YES if c_id in ["name", "email"] else tk.NO)
        self.suppliers_tree.bind("<ButtonRelease-1>", self.get_supplier_cursor)
        self.fetch_suppliers_data()
 
    def fetch_suppliers_data(self):
        if not self.suppliers_tree: return
        self.suppliers_tree.delete(*self.suppliers_tree.get_children())
        search_term = self.supplier_search_var.get().strip()
        query = "SELECT supplier_id, supplier_name, contact_person, phone_number, email, address FROM suppliers"
        params = []
        if search_term:
            query += " WHERE LOWER(supplier_name) ILIKE %s"
            params.append(f"%{search_term.lower()}%")
        query += " ORDER BY supplier_name"
        rows = execute_query(query, tuple(params), fetch_all=True, use_dict_cursor=True)
        if rows:
            for row in rows:
                self.suppliers_tree.insert("", tk.END, values=(row['supplier_id'], row['supplier_name'], row['contact_person'], row['phone_number'], row['email']))
        self.update_status(f"{len(rows) if rows else 0} suppliers found.")
 
 
    def get_supplier_cursor(self, event=""):
        if not self.suppliers_tree.focus(): return
        item = self.suppliers_tree.item(self.suppliers_tree.focus())
        values = item['values']
        if not values or len(values) < 5: return
 
        self.supplier_id_var.set(values[0])
        self.supplier_name_var.set(values[1])
        self.supplier_contact_person_var.set(values[2] if values[2] else "")
        self.supplier_phone_var.set(values[3] if values[3] else "")
        self.supplier_email_var.set(values[4] if values[4] else "")
        # Fetch address separately as it's not in Treeview values for brevity
        address_data = execute_query("SELECT address FROM suppliers WHERE supplier_id = %s", (values[0],), fetch_one=True)
        self.supplier_address_text_widget.delete("1.0", tk.END)
        if address_data and address_data[0]:
            self.supplier_address_text_widget.insert("1.0", address_data[0])
 
 
    def add_supplier(self):
        name = self.supplier_name_var.get().strip()
        if not name: messagebox.showwarning("Required", "Supplier Name is required."); return
        params = (name, self.supplier_contact_person_var.get().strip() or None,
                  self.supplier_phone_var.get().strip() or None, self.supplier_email_var.get().strip() or None,
                  self.supplier_address_text_widget.get("1.0", tk.END).strip() or None)
        query = "INSERT INTO suppliers (supplier_name, contact_person, phone_number, email, address) VALUES (%s, %s, %s, %s, %s)"
        if execute_query(query, params, is_dml=True):
            messagebox.showinfo("Success", "Supplier added."); self.fetch_suppliers_data(); self.clear_supplier_fields()
        # else error shown by execute_query
 
    def update_supplier(self):
        sup_id = self.supplier_id_var.get()
        if not sup_id: messagebox.showwarning("Selection", "Select a supplier to update."); return
        name = self.supplier_name_var.get().strip()
        if not name: messagebox.showwarning("Required", "Supplier Name is required."); return
        params = (name, self.supplier_contact_person_var.get().strip() or None,
                  self.supplier_phone_var.get().strip() or None, self.supplier_email_var.get().strip() or None,
                  self.supplier_address_text_widget.get("1.0", tk.END).strip() or None, sup_id)
        query = """UPDATE suppliers SET supplier_name=%s, contact_person=%s, phone_number=%s, email=%s, address=%s
                   WHERE supplier_id=%s"""
        if execute_query(query, params, is_dml=True):
            messagebox.showinfo("Success", "Supplier updated."); self.fetch_suppliers_data(); self.clear_supplier_fields()
 
    def delete_supplier(self):
        sup_id = self.supplier_id_var.get()
        if not sup_id: messagebox.showwarning("Selection", "Select a supplier to delete."); return
        if messagebox.askyesno("Confirm", f"Delete supplier '{self.supplier_name_var.get()}'? This might fail if they are linked to purchase orders."):
            # Check for FK dependencies (purchase_orders)
            linked_pos = execute_query("SELECT 1 FROM purchase_orders WHERE supplier_id = %s LIMIT 1", (sup_id,), fetch_one=True)
            if linked_pos:
                messagebox.showerror("Delete Failed", "Cannot delete supplier. They are linked to existing purchase orders.")
                return
            if execute_query("DELETE FROM suppliers WHERE supplier_id=%s", (sup_id,), is_dml=True):
                messagebox.showinfo("Success", "Supplier deleted."); self.fetch_suppliers_data(); self.clear_supplier_fields()
 
    def clear_supplier_fields(self):
        self.supplier_id_var.set("")
        self.supplier_name_var.set("")
        self.supplier_contact_person_var.set("")
        self.supplier_phone_var.set("")
        self.supplier_email_var.set("")
        self.supplier_address_text_widget.delete("1.0", tk.END)
        if self.suppliers_tree and self.suppliers_tree.focus():
            self.suppliers_tree.selection_remove(self.suppliers_tree.focus())
 
 
    # --- Patient Management (Admin Only) ---
    def create_patients_widgets(self):
        if self.user_role != 'admin': return
        # Similar structure to suppliers: PanedWindow, Form, Treeview
        panned_patients = ttk.PanedWindow(self.patients_frame, orient=tk.VERTICAL)
        panned_patients.pack(fill=tk.BOTH, expand=True)
 
        pat_form_outer = ttk.LabelFrame(panned_patients, text="Patient Details", padding="10")
        panned_patients.add(pat_form_outer, weight=1)
        pat_form = ttk.Frame(pat_form_outer); pat_form.pack(fill=tk.X, padx=5, pady=5)
 
        ttk.Label(pat_form, text="ID:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(pat_form, textvariable=self.patient_id_var, state='readonly', width=10).grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        ttk.Label(pat_form, text="Full Name*:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(pat_form, textvariable=self.patient_full_name_var, width=40).grid(row=1, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
 
        ttk.Label(pat_form, text="DOB (YYYY-MM-DD):").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
        DateEntry(pat_form, textvariable=self.patient_dob_var, width=18, date_pattern='yyyy-mm-dd', state='readonly').grid(row=2, column=1, padx=5, pady=2, sticky=tk.W)
        ttk.Label(pat_form, text="Gender:").grid(row=2, column=2, padx=5, pady=2, sticky=tk.W)
        ttk.Combobox(pat_form, textvariable=self.patient_gender_var, values=["Male", "Female", "Other", ""], width=18, state='readonly').grid(row=2, column=3, padx=5, pady=2, sticky=tk.W)
 
        ttk.Label(pat_form, text="Phone:").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(pat_form, textvariable=self.patient_phone_var, width=20).grid(row=3, column=1, padx=5, pady=2, sticky=tk.W)
        ttk.Label(pat_form, text="Email:").grid(row=3, column=2, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(pat_form, textvariable=self.patient_email_var, width=30).grid(row=3, column=3, padx=5, pady=2, sticky=tk.EW)
 
        ttk.Label(pat_form, text="Address:").grid(row=4, column=0, padx=5, pady=2, sticky=tk.NW)
        self.patient_address_text_widget = tk.Text(pat_form, height=2, width=38)
        self.patient_address_text_widget.grid(row=4, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
        ttk.Label(pat_form, text="Allergies/Notes:").grid(row=5, column=0, padx=5, pady=2, sticky=tk.NW)
        self.patient_allergies_text_widget = tk.Text(pat_form, height=2, width=38)
        self.patient_allergies_text_widget.grid(row=5, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
 
        pat_form.grid_columnconfigure(1, weight=1); pat_form.grid_columnconfigure(3, weight=1)
        pat_button_bar = ttk.Frame(pat_form_outer); pat_button_bar.pack(fill=tk.X, pady=10)
        ttk.Button(pat_button_bar, text="Add New", command=self.add_patient).pack(side=tk.LEFT, padx=5)
        ttk.Button(pat_button_bar, text="Update", command=self.update_patient).pack(side=tk.LEFT, padx=5)
        # ttk.Button(pat_button_bar, text="Delete", command=self.delete_patient).pack(side=tk.LEFT, padx=5) # Deleting patients needs careful consideration of privacy and linked data
        ttk.Button(pat_button_bar, text="Clear Fields", command=self.clear_patient_fields).pack(side=tk.LEFT, padx=5)
 
        pat_tree_outer = ttk.LabelFrame(panned_patients, text="Patient List", padding="10")
        panned_patients.add(pat_tree_outer, weight=3)
        search_pat_frame = ttk.Frame(pat_tree_outer); search_pat_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_pat_frame, text="Search Name/Phone:").pack(side=tk.LEFT, padx=2)
        ttk.Entry(search_pat_frame, textvariable=self.patient_search_var, width=30).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(search_pat_frame, text="Search", command=self.fetch_patients_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_pat_frame, text="Show All", command=lambda: (self.patient_search_var.set(""), self.fetch_patients_data())).pack(side=tk.LEFT, padx=2)
 
        self.patients_tree = ttk.Treeview(pat_tree_outer, columns=("id", "name", "dob", "phone", "email"), show="headings")
        self.patients_tree.pack(fill=tk.BOTH, expand=True)
        cols_pat = {"id":"ID", "name":"Full Name", "dob":"DOB", "phone":"Phone", "email":"Email"}
        widths_pat = {"id":50, "name":200, "dob":100, "phone":120, "email":180}
        for c_id, c_text in cols_pat.items():
            self.patients_tree.heading(c_id, text=c_text)
            self.patients_tree.column(c_id, width=widths_pat[c_id], stretch=tk.YES if c_id in ["name", "email"] else tk.NO)
        self.patients_tree.bind("<ButtonRelease-1>", self.get_patient_cursor)
        self.fetch_patients_data()
 
    def fetch_patients_data(self):
        if not self.patients_tree: return
        self.patients_tree.delete(*self.patients_tree.get_children())
        search = self.patient_search_var.get().strip().lower()
        query = "SELECT patient_id, full_name, date_of_birth, phone_number, email FROM patients"
        params = []
        if search:
            query += " WHERE LOWER(full_name) ILIKE %s OR phone_number ILIKE %s"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY full_name"
        rows = execute_query(query, tuple(params), fetch_all=True, use_dict_cursor=True)
        if rows:
            for row in rows:
                dob_str = row['date_of_birth'].isoformat() if isinstance(row['date_of_birth'], date) else ""
                self.patients_tree.insert("", tk.END, values=(row['patient_id'], row['full_name'], dob_str, row['phone_number'], row['email']))
        self.update_status(f"{len(rows) if rows else 0} patients found.")
 
 
    def get_patient_cursor(self, event=""):
        if not self.patients_tree.focus(): return
        item = self.patients_tree.item(self.patients_tree.focus())
        values = item['values']
        if not values or len(values) < 5: return
        pat_id = values[0]
        full_details = execute_query("SELECT * FROM patients WHERE patient_id = %s", (pat_id,), fetch_one=True, use_dict_cursor=True)
        if full_details:
            self.patient_id_var.set(full_details['patient_id'])
            self.patient_full_name_var.set(full_details['full_name'])
            self.patient_dob_var.set(full_details['date_of_birth'].isoformat() if full_details['date_of_birth'] else "")
            self.patient_gender_var.set(full_details['gender'] or "")
            self.patient_phone_var.set(full_details['phone_number'] or "")
            self.patient_email_var.set(full_details['email'] or "")
            self.patient_address_text_widget.delete("1.0", tk.END)
            self.patient_address_text_widget.insert("1.0", full_details['address'] or "")
            self.patient_allergies_text_widget.delete("1.0", tk.END)
            self.patient_allergies_text_widget.insert("1.0", full_details['allergies_notes'] or "")
 
 
    def add_patient(self):
        name = self.patient_full_name_var.get().strip()
        if not name: messagebox.showwarning("Required", "Patient Full Name is required."); return
        dob = self.patient_dob_var.get().strip() or None
        params = (name, dob, self.patient_gender_var.get().strip() or None,
                  self.patient_phone_var.get().strip() or None, self.patient_email_var.get().strip() or None,
                  self.patient_address_text_widget.get("1.0", tk.END).strip() or None,
                  self.patient_allergies_text_widget.get("1.0", tk.END).strip() or None)
        query = """INSERT INTO patients (full_name, date_of_birth, gender, phone_number, email, address, allergies_notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        if execute_query(query, params, is_dml=True):
            messagebox.showinfo("Success", "Patient added."); self.fetch_patients_data(); self.clear_patient_fields()
 
 
    def update_patient(self):
        pat_id = self.patient_id_var.get()
        if not pat_id: messagebox.showwarning("Selection", "Select a patient to update."); return
        name = self.patient_full_name_var.get().strip()
        if not name: messagebox.showwarning("Required", "Patient Full Name is required."); return
        dob = self.patient_dob_var.get().strip() or None
        params = (name, dob, self.patient_gender_var.get().strip() or None,
                  self.patient_phone_var.get().strip() or None, self.patient_email_var.get().strip() or None,
                  self.patient_address_text_widget.get("1.0", tk.END).strip() or None,
                  self.patient_allergies_text_widget.get("1.0", tk.END).strip() or None, pat_id)
        query = """UPDATE patients SET full_name=%s, date_of_birth=%s, gender=%s, phone_number=%s, email=%s,
                   address=%s, allergies_notes=%s WHERE patient_id=%s"""
        if execute_query(query, params, is_dml=True):
            messagebox.showinfo("Success", "Patient updated."); self.fetch_patients_data(); self.clear_patient_fields()
 
 
    def clear_patient_fields(self):
        self.patient_id_var.set(""); self.patient_full_name_var.set(""); self.patient_dob_var.set("")
        self.patient_gender_var.set(""); self.patient_phone_var.set(""); self.patient_email_var.set("")
        self.patient_address_text_widget.delete("1.0", tk.END)
        self.patient_allergies_text_widget.delete("1.0", tk.END)
        if self.patients_tree and self.patients_tree.focus():
            self.patients_tree.selection_remove(self.patients_tree.focus())
 
 
    # --- Reports (Admin Only) ---
    def create_reports_widgets(self):
        if self.user_role != 'admin': return
        # Placeholder for reports. This would be a complex module.
        # Could use matplotlib for charts (requires embedding in Tkinter)
        # or just display data in Treeviews/Text widgets.
 
        report_type_var = tk.StringVar(value="Daily Sales")
        ttk.Label(self.reports_frame, text="Select Report Type:", font=("Helvetica", 12)).pack(pady=10)
        report_combo = ttk.Combobox(self.reports_frame, textvariable=report_type_var,
                                    values=["Daily Sales", "Monthly Sales", "Top Selling Medicines", "Sales by Employee"],
                                    state="readonly", width=30)
        report_combo.pack(pady=5)
 
        date_frame = ttk.Frame(self.reports_frame)
        date_frame.pack(pady=5)
        ttk.Label(date_frame, text="From:").pack(side=tk.LEFT, padx=5)
        self.report_from_date_var = tk.StringVar(value=date.today().isoformat())
        DateEntry(date_frame, textvariable=self.report_from_date_var, width=12, date_pattern='yyyy-mm-dd').pack(side=tk.LEFT)
        ttk.Label(date_frame, text="To:").pack(side=tk.LEFT, padx=5)
        self.report_to_date_var = tk.StringVar(value=date.today().isoformat())
        DateEntry(date_frame, textvariable=self.report_to_date_var, width=12, date_pattern='yyyy-mm-dd').pack(side=tk.LEFT)
 
        ttk.Button(self.reports_frame, text="Generate Report", command=self.generate_report).pack(pady=10)
 
        self.report_display_text = tk.Text(self.reports_frame, height=20, width=100, wrap=tk.WORD, font=("Courier New", 9))
        self.report_display_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.report_display_text.config(state=tk.DISABLED)
 
 
    def generate_report(self):
        self.report_display_text.config(state=tk.NORMAL)
        self.report_display_text.delete("1.0", tk.END)
        report_type = self.report_display_text.master.children['!combobox'].get() # Hacky way to get combo value
        from_d_str = self.report_from_date_var.get()
        to_d_str = self.report_to_date_var.get()
 
        try:
            from_d = datetime.strptime(from_d_str, "%Y-%m-%d").date()
            to_d = datetime.strptime(to_d_str, "%Y-%m-%d").date()
            if from_d > to_d:
                messagebox.showwarning("Date Error", "From date cannot be after To date."); return
        except ValueError:
            messagebox.showerror("Date Error", "Invalid date format. Use YYYY-MM-DD."); return
 
        report_content = f"--- Report: {report_type} from {from_d_str} to {to_d_str} ---\n\n"
 
        # Adjust to_d for SQL BETWEEN (inclusive of the whole day)
        # For date columns, direct comparison is fine. For timestamp, you'd adjust.
 
        if report_type == "Daily Sales" or report_type == "Monthly Sales": # Simplified to total sales in period
            query = """SELECT SUM(total_amount) as total_sales, COUNT(*) as num_transactions
                       FROM sales_transactions
                       WHERE DATE(transaction_date) BETWEEN %s AND %s;"""
            result = execute_query(query, (from_d, to_d), fetch_one=True, use_dict_cursor=True)
            if result and result['total_sales'] is not None:
                report_content += f"Total Sales: € {result['total_sales']:.2f}\n"
                report_content += f"Number of Transactions: {result['num_transactions']}\n"
            else: report_content += "No sales data found for this period.\n"
 
        elif report_type == "Top Selling Medicines": # By quantity
            query = """SELECT si.medicine_name_snapshot, SUM(si.quantity_sold) as total_qty_sold
                       FROM sales_items si
                       JOIN sales_transactions st ON si.transaction_id = st.transaction_id
                       WHERE DATE(st.transaction_date) BETWEEN %s AND %s
                       GROUP BY si.medicine_name_snapshot
                       ORDER BY total_qty_sold DESC LIMIT 10;"""
            results = execute_query(query, (from_d, to_d), fetch_all=True, use_dict_cursor=True)
            if results:
                report_content += "Top 10 Selling Medicines (by Quantity):\n"
                for i, row in enumerate(results):
                    report_content += f"{i+1}. {row['medicine_name_snapshot']}: {row['total_qty_sold']} units\n"
            else: report_content += "No sales data for top medicines in this period.\n"
 
        elif report_type == "Sales by Employee":
            query = """SELECT st.employee_username, SUM(st.total_amount) as total_sales_by_employee, COUNT(*) as num_trans_by_employee
                       FROM sales_transactions st
                       WHERE DATE(st.transaction_date) BETWEEN %s AND %s AND st.employee_username IS NOT NULL
                       GROUP BY st.employee_username
                       ORDER BY total_sales_by_employee DESC;"""
            results = execute_query(query, (from_d, to_d), fetch_all=True, use_dict_cursor=True)
            if results:
                report_content += "Sales by Employee:\n"
                for row in results:
                    report_content += f"- {row['employee_username']}: € {row['total_sales_by_employee']:.2f} ({row['num_trans_by_employee']} transactions)\n"
            else: report_content += "No sales data by employee in this period.\n"
 
 
        self.report_display_text.insert(tk.END, report_content)
        self.report_display_text.config(state=tk.DISABLED)
        self.update_status(f"{report_type} generated.")
 
 
# --- Settings Window Class ---
class SettingsWindow(tk.Toplevel):
    # ... (remains largely same, ensure bcrypt for password change)
    def __init__(self, parent, username):
        super().__init__(parent)
        self.title(f"Settings - {username}")
        self.parent = parent; self.username = username
        self.geometry("450x320"); self.transient(parent); self.grab_set(); self._center_window()
        self.notebook = ttk.Notebook(self); self.notebook.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)
        self.security_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.security_frame, text=' Change Password ')
        self._create_security_widgets()
 
    def _center_window(self):
        self.update_idletasks()
        p_x,p_y,p_w,p_h = self.parent.winfo_x(),self.parent.winfo_y(),self.parent.winfo_width(),self.parent.winfo_height()
        w,h = self.winfo_width(),self.winfo_height()
        c_x,c_y = p_x+(p_w-w)//2, p_y+(p_h-h)//2
        self.geometry(f'+{c_x}+{c_y}')
 
    def _create_security_widgets(self):
        frame = ttk.LabelFrame(self.security_frame, text=f"Change Password for '{self.username}'", padding="15")
        frame.pack(fill=tk.BOTH, pady=10, expand=True)
        self.cur_var,self.new_var,self.cnf_var = tk.StringVar(),tk.StringVar(),tk.StringVar()
        ttk.Label(frame, text="Current Password:").grid(row=0, column=0, padx=5, pady=8, sticky=tk.W)
        cur_pass_entry = ttk.Entry(frame, textvariable=self.cur_var, show="*"); cur_pass_entry.grid(row=0, column=1, padx=5, pady=8, sticky=tk.EW); ToolTip(cur_pass_entry, "Enter current password")
        ttk.Label(frame, text="New Password:").grid(row=1, column=0, padx=5, pady=8, sticky=tk.W)
        new_pass_entry = ttk.Entry(frame, textvariable=self.new_var, show="*"); new_pass_entry.grid(row=1, column=1, padx=5, pady=8, sticky=tk.EW); ToolTip(new_pass_entry, "Enter new password (min 6 chars)")
        ttk.Label(frame, text="Confirm New Password:").grid(row=2, column=0, padx=5, pady=8, sticky=tk.W)
        cnf_pass_entry = ttk.Entry(frame, textvariable=self.cnf_var, show="*"); cnf_pass_entry.grid(row=2, column=1, padx=5, pady=8, sticky=tk.EW); ToolTip(cnf_pass_entry, "Re-enter new password")
        frame.grid_columnconfigure(1, weight=1)
        change_pass_btn = ttk.Button(frame, text="Change Password", command=self.change_password); change_pass_btn.grid(row=3, column=0, columnspan=2, pady=20); ToolTip(change_pass_btn, "Confirm and change password")
 
    def change_password(self):
        cur_pass,new_pass,cnf_pass = self.cur_var.get(),self.new_var.get(),self.cnf_var.get()
        if not cur_pass or not new_pass or not cnf_pass: messagebox.showerror("Error", "All fields required.", parent=self); return
        if len(new_pass) < 6: messagebox.showwarning("Weak Password", "New password min 6 chars.", parent=self); return
        if new_pass != cnf_pass: messagebox.showerror("Mismatch", "New passwords don't match.", parent=self); self.new_var.set(""); self.cnf_var.set(""); return
 
        user_data = execute_query("SELECT password FROM employees WHERE username = %s", (self.username,), fetch_one=True, use_dict_cursor=True)
        if user_data and bcrypt.checkpw(cur_pass.encode('utf-8'), user_data['password'].encode('utf-8')):
            hashed_new_password = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            rows = execute_query("UPDATE employees SET password = %s WHERE username = %s", (hashed_new_password, self.username), is_dml=True)
            if rows: logger.info(f"Password changed for '{self.username}'."); messagebox.showinfo("Success", "Password updated.", parent=self); self.destroy()
            else:
                logger.error(f"Password update fail for '{self.username}'. Err: {execute_query.last_error}")
                messagebox.showerror("Error", f"Password update failed. DB Err: {execute_query.last_error}", parent=self) if execute_query.last_error else messagebox.showerror("Error", "Password update failed (0 rows).", parent=self)
        else: logger.warning(f"Pwd change fail for '{self.username}': Incorrect current password."); messagebox.showerror("Auth Failed", "Incorrect current password.", parent=self); self.cur_var.set("")
 
 
# --- Function to Launch Main App ---
def launch_main_app(username, user_role):
    # ... (remains same)
    root = tk.Tk()
    app_instance = None
    try:
        logger.info(f"Initializing PharmacyApp for user '{username}' with role '{user_role}'.")
        app_instance = PharmacyApp(root, username, user_role)
        if hasattr(app_instance, 'inventory_table') and app_instance.inventory_table is not None:
            logger.info("PharmacyApp initialization successful. Starting mainloop...")
            root.mainloop()
        else: logger.error("PharmacyApp init incomplete. Critical widgets not found.")
    except Exception as e:
        msg = f"Critical error during app startup: {e}"; logger.critical(msg, exc_info=True)
        messagebox.showerror("Application Startup Error", msg)
    finally:
        logger.info("--- launch_main_app: Cleaning up ---")
        try:
            if root and root.winfo_exists(): root.destroy(); logger.info("Root window destroyed.")
        except tk.TclError as destroy_error: logger.warning(f"Ignoring TclError during cleanup: {destroy_error}")
        except Exception as cleanup_error: logger.error(f"Unexpected cleanup error: {cleanup_error}", exc_info=True)
 
# --- Main Execution ---
def main():
    # ... (remains same, ensures initial admin user is created with hashed password and role)
    logger.info("Application starting...")
    logger.info(f"DB: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, db={DB_CONFIG['database']}")
    conn_test = db_connect()
    if not conn_test: logger.critical("Initial DB connection failed. App cannot start."); return
    else: conn_test.close(); logger.info("Initial DB connection test successful.")
 
    count_res = execute_query("SELECT COUNT(*) FROM employees", fetch_one=True)
    if count_res is None: logger.critical("Failed to check users. App cannot start."); return
 
    if count_res[0] == 0:
        logger.info("No users found. Prompting for initial admin setup.")
        temp_root = tk.Tk(); temp_root.withdraw()
        if messagebox.askyesno("First Run Setup", "No users exist. Create 'admin' user?\n(Password: 'adminpass', Role: 'admin')", parent=temp_root):
            admin_username = 'admin'; admin_password = 'adminpass'; admin_role = 'admin'
            hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            res = execute_query("INSERT INTO employees (username, password, role) VALUES (%s, %s, %s)", (admin_username, hashed_password, admin_role), is_dml=True)
            if res: logger.info(f"Initial admin '{admin_username}' created."); messagebox.showinfo("Success", f"User '{admin_username}' (role '{admin_role}') created.\nPassword: {admin_password}", parent=temp_root)
            else: logger.error("Failed to create initial admin."); messagebox.showerror("Setup Error", "Failed to create initial admin. Check DB logs.", parent=temp_root); temp_root.destroy(); return
        else: logger.info("User declined initial admin setup. App cannot start."); messagebox.showinfo("Info", "App cannot start without users.", parent=temp_root); temp_root.destroy(); return
        if temp_root.winfo_exists(): temp_root.destroy()
 
    logger.info("Launching login window..."); login_root = tk.Tk()
    LoginWindow(login_root); login_root.mainloop()
    logger.info("Application finished or login window closed.")
 
 
if __name__ == "__main__":
    main()
