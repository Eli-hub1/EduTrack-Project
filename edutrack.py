#!/usr/bin/env python3
"""
EduTrack Student Management System
-----------------------------------
Tkinter + SQLite desktop app following the EduTrack user guide.
Requires Python 3.9+ (standard library only).  Run:  python edutrack.py

Default login on first run:  admin / admin123
Data is stored in  ~/EduTrackSMS/edutrack.db
"""
import csv
import hashlib
import math
import os
import re
import sqlite3
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# ----------------------------------------------------------------- constants
SIDEBAR, BG, CARD = "#17212b", "#f3f5f8", "#ffffff"
ACCENT, ACCENT_DARK = "#b3262e", "#8f1d25"
GREEN, RED, MUTED, TEXT = "#16805d", "#b3262e", "#64748b", "#17212b"
BORDER, LIGHT_ACCENT, GOLD = "#e2e8f0", "#fff1f2", "#c5a66a"
FONT = "Helvetica"
LOGO_PATH = Path(__file__).resolve().parent / "resources" / "Central-Uni-logo.png"
STARTUP_LOGO_PATH = Path(__file__).resolve().parent / "resources" / "Central-Uni-logo-white.png"

PROGRAMMES = [
    "B.Sc. Information Technology",
    "B.Sc. Computer Science",
    "B.Sc. Software Engineering",
    "B.Sc. Business Information Systems",
    "B.Ed. Information Technology",
]
LEVELS = ["100", "200", "300", "400"]

# (minimum score, letter, grade points)
GRADES = [(80, "A", 4.0), (75, "B+", 3.5), (70, "B", 3.0), (65, "C+", 2.5),
          (60, "C", 2.0), (55, "D+", 1.5), (50, "D", 1.0), (0, "F", 0.0)]
PASS_MARK = 50


def grade_of(score):
    """Return (letter, grade points) for a numeric score."""
    for low, letter, points in GRADES:
        if score >= low:
            return letter, points
    return "F", 0.0


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000).hex()


def load_school_logo(subsample):
    return tk.PhotoImage(file=str(LOGO_PATH)).subsample(subsample, subsample)


# ------------------------------------------------------------------ database
class Database:
    def __init__(self):
        folder = Path.home() / "EduTrackSMS"
        folder.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(folder / "edutrack.db")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, salt BLOB NOT NULL, pw_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT DEFAULT '',
                gender TEXT, level TEXT, programme TEXT, active INTEGER DEFAULT 1,
                department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL);
            CREATE TABLE IF NOT EXISTS courses (
                code TEXT PRIMARY KEY, title TEXT NOT NULL, credits INTEGER NOT NULL,
                department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL);
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                course_code TEXT NOT NULL REFERENCES courses(code) ON DELETE CASCADE,
                score REAL NOT NULL,
                UNIQUE (student_id, course_code));
        """)
        for table in ("students", "courses"):
            columns = {row["name"] for row in self.query(f"PRAGMA table_info({table})")}
            if "department_id" not in columns:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN department_id INTEGER "
                    "REFERENCES departments(id) ON DELETE SET NULL")
        self.conn.commit()
        if not self.one("SELECT 1 FROM users"):
            salt = os.urandom(16)
            self.run("INSERT INTO users VALUES (?,?,?)",
                     ("admin", salt, hash_password("admin123", salt)))

    # small helpers
    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def run(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    # domain logic
    def check_login(self, username, password):
        row = self.one("SELECT * FROM users WHERE username = ?", (username,))
        return bool(row) and hash_password(password, row["salt"]) == row["pw_hash"]

    def gpa(self, student_id):
        """Credit-weighted GPA -> (gpa or None, number of results)."""
        rows = self.query(
            "SELECT r.score, c.credits FROM results r "
            "JOIN courses c ON c.code = r.course_code WHERE r.student_id = ?",
            (student_id,))
        credits = sum(r["credits"] for r in rows)
        if not credits:
            return None, 0
        points = sum(grade_of(r["score"])[1] * r["credits"] for r in rows)
        return points / credits, len(rows)


# ------------------------------------------------------------------- styling
def setup_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("Page.TFrame", background=BG)
    s.configure("Card.TFrame", background=CARD)
    s.configure("H1.TLabel", background=BG, foreground=TEXT, font=(FONT, 23, "bold"),
                anchor="center")
    s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=(FONT, 10),
                anchor="center")
    s.configure("H2.TLabel", background=CARD, foreground=TEXT, font=(FONT, 12, "bold"),
                anchor="center")
    s.configure("Field.TLabel", background=CARD, foreground="#334155", font=(FONT, 9, "bold"),
                anchor="center")
    s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=(FONT, 9),
                anchor="center")
    s.configure("Stat.TLabel", background=CARD, foreground=ACCENT, font=(FONT, 25, "bold"),
                anchor="center")
    s.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, font=(FONT, 9),
                anchor="center")
    s.configure("Card.TRadiobutton", background=CARD, foreground=TEXT, font=(FONT, 9),
                anchor="center")
    s.configure("TEntry", padding=(9, 8), fieldbackground="#f8fafc", foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, justify="center")
    s.configure("TCombobox", padding=(8, 7), fieldbackground="#f8fafc", foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, justify="center")
    s.map("TCombobox", fieldbackground=[("readonly", "#f8fafc")],
          foreground=[("disabled", MUTED)])
    s.configure("Treeview", rowheight=36, font=(FONT, 10), borderwidth=0,
                background=CARD, fieldbackground=CARD, foreground=TEXT)
    s.configure("Treeview.Heading", font=(FONT, 9, "bold"), foreground="#475569",
                background="#f1f5f9", relief="flat", padding=(10, 10), anchor="center")
    s.map("Treeview", background=[("selected", "#fce8e9")],
          foreground=[("selected", TEXT)])
    s.configure("AccentBar.TFrame", background=ACCENT)
    s.configure("Vertical.TScrollbar", background="#e2e8f0", troughcolor=CARD,
                bordercolor=CARD, arrowcolor=MUTED)
    for name, bg, hover in (("Accent", ACCENT, ACCENT_DARK), ("Danger", RED, "#b91c1c")):
        s.configure(f"{name}.TButton", background=bg, foreground="white",
                    padding=(12, 9), borderwidth=0, font=(FONT, 9, "bold"))
        s.map(f"{name}.TButton", background=[("disabled", "#eef0f6"), ("active", hover)],
              foreground=[("disabled", "#9ca3af")])
    s.configure("Plain.TButton", background=CARD, foreground=TEXT, padding=(11, 8),
                bordercolor=BORDER, font=(FONT, 9, "bold"))
    s.map("Plain.TButton", background=[("active", "#f1f5f9")],
          foreground=[("disabled", "#9ca3af")])
    s.configure("Green.Horizontal.TProgressbar", background=GREEN,
                troughcolor="#e2e8f0", borderwidth=0)


# ------------------------------------------------------------------ page base
class Page(ttk.Frame):
    title = subtitle = ""

    def __init__(self, parent, app):
        super().__init__(parent, style="Page.TFrame")
        self.app, self.db = app, app.db
        heading = ttk.Frame(self, style="Page.TFrame")
        heading.pack(fill="x", padx=28, pady=(24, 18))
        ttk.Label(heading, text=self.title, style="H1.TLabel").pack(fill="x")
        ttk.Label(heading, text=self.subtitle, style="Sub.TLabel").pack(fill="x", pady=(4, 0))
        self.body = ttk.Frame(self, style="Page.TFrame")
        self.body.pack(fill="both", expand=True, padx=28, pady=(0, 26))

    def refresh(self):
        pass


class SplitPage(Page):
    """Table on the left, details form + buttons on the right."""
    columns = []                 # (id, heading, width)
    noun = "items"
    add_text, upd_text = "Add", "Update"
    form_title = "Details"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

        # ---- left: toolbar + table
        left = ttk.Frame(self.body, style="Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ttk.Frame(left, style="AccentBar.TFrame", height=3).pack(fill="x")
        ttk.Label(left, text=f"{self.noun.title()} directory", style="H2.TLabel"
                  ).pack(fill="x", padx=16, pady=(14, 8))
        self.toolbar = ttk.Frame(left, style="Card.TFrame")
        self.toolbar.pack(fill="x", padx=14, pady=(0, 10))
        table = ttk.Frame(left, style="Card.TFrame")
        table.pack(fill="both", expand=True, padx=14)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in self.columns],
                                 show="headings", selectmode="browse")
        for cid, head, width in self.columns:
            self.tree.heading(cid, text=head, anchor="center")
            self.tree.column(cid, width=width, anchor="center")
        self.tree.tag_configure("even", background="#f8fafc")
        scrollbar = ttk.Scrollbar(table, orient="vertical", style="Vertical.TScrollbar",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.count = ttk.Label(left, style="Muted.TLabel")
        self.count.pack(fill="x", padx=16, pady=12)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # ---- right: form card
        right = ttk.Frame(self.body, style="Card.TFrame", width=300)
        right.grid(row=0, column=1, sticky="ns")
        right.pack_propagate(False)
        ttk.Frame(right, style="AccentBar.TFrame", height=3).pack(fill="x")
        ttk.Label(right, text=self.form_title, style="H2.TLabel").pack(fill="x", padx=18, pady=(16, 2))
        ttk.Label(right, text="Enter details below", style="Muted.TLabel"
                  ).pack(fill="x", padx=18, pady=(0, 10))

        self.msg = tk.Label(right, text="", bg=CARD, wraplength=260, justify="center",
                            font=(FONT, 9), anchor="center", padx=4)
        self.msg.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        btns = ttk.Frame(right, style="Card.TFrame")
        btns.pack(side="bottom", fill="x", padx=16, pady=10)
        btns.columnconfigure((0, 1), weight=1)
        self.add_btn = ttk.Button(btns, text=self.add_text, style="Accent.TButton", command=self._add)
        self.upd_btn = ttk.Button(btns, text=self.upd_text, style="Plain.TButton", command=self._update)
        self.del_btn = ttk.Button(btns, text="Delete", style="Danger.TButton", command=self._delete)
        self.clr_btn = ttk.Button(btns, text="Clear form", style="Plain.TButton", command=self.clear)
        self.add_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        self.upd_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=2)
        self.del_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=2)
        self.clr_btn.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=2)

        self.form = ttk.Frame(right, style="Card.TFrame")
        self.form.pack(fill="both", expand=True, padx=18)
        self.locks = []          # (widget, state while editing, normal state)
        self.build_form(self.form)
        self.set_editing(False)

    # ---- helpers for subclasses
    def label(self, text):
        ttk.Label(self.form, text=text, style="Field.TLabel").pack(fill="x", pady=(12, 4))

    def entry(self, var, lock=False):
        e = ttk.Entry(self.form, textvariable=var, justify="center")
        e.pack(fill="x")
        if lock:
            self.locks.append((e, "readonly", "normal"))
        return e

    def combo(self, var, values, lock=False):
        c = ttk.Combobox(self.form, textvariable=var, values=values, state="readonly",
                         justify="center")
        c.pack(fill="x")
        if lock:
            self.locks.append((c, "disabled", "readonly"))
        return c

    def say(self, text, ok=True):
        self.msg.config(text=("● " + text) if text else "", fg=GREEN if ok else RED)

    # ---- state handling
    def set_editing(self, editing):
        self.add_btn.config(state="disabled" if editing else "normal")
        self.upd_btn.config(state="normal" if editing else "disabled")
        self.del_btn.config(state="normal" if editing else "disabled")
        for widget, editing_state, normal_state in self.locks:
            widget.config(state=editing_state if editing else normal_state)

    def _on_select(self, _event):
        sel = self.tree.selection()
        if sel:
            self.fill(sel[0])
            self.set_editing(True)

    def clear(self, keep_msg=False):
        self.tree.selection_remove(self.tree.selection())
        self.reset_form()
        self.set_editing(False)
        if not keep_msg:
            self.say("")

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        rows = self.rows()
        for index, (iid, values) in enumerate(rows):
            self.tree.insert("", "end", iid=str(iid), values=values,
                             tags=("even",) if index % 2 else ())
        self.count.config(text=f"{len(rows)} {self.noun}")

    def refresh(self):
        self.reload()

    def finish(self, message):
        """Common tail for add / update / delete."""
        self.reload()
        self.clear(keep_msg=True)
        self.say(message)

    # ---- button wrappers: validate -> hand over to subclass
    def _add(self):
        err = self.validate(editing=False)
        self.say(err, False) if err else self.add()

    def _update(self):
        err = self.validate(editing=True)
        self.say(err, False) if err else self.update()

    def _delete(self):
        if self.tree.selection():
            self.delete(self.tree.selection()[0])

    # ---- to be implemented
    def build_form(self, form): ...
    def rows(self): return []
    def fill(self, iid): ...
    def reset_form(self): ...
    def validate(self, editing): return ""
    def add(self): ...
    def update(self): ...
    def delete(self, iid): ...


# ----------------------------------------------------------------- dashboard
class DashboardPage(Page):
    title = "Dashboard"

    def __init__(self, parent, app):
        self.subtitle = f"{self._greeting()}, {app.user.title()}. Here is how things look today."
        super().__init__(parent, app)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(1, weight=1)

        cards = ttk.Frame(self.body, style="Page.TFrame")
        cards.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.stat = {}
        captions = [("students", "Students"), ("departments", "Departments"),
                    ("courses", "Courses"), ("results", "Results recorded"),
                    ("avg", "Average score")]
        for i, (key, caption) in enumerate(captions):
            cards.columnconfigure(i, weight=1, uniform="c")
            card = ttk.Frame(cards, style="Card.TFrame")
            card.grid(row=0, column=i, sticky="ew",
                      padx=(0 if i == 0 else 7, 0 if i == len(captions) - 1 else 7))
            ttk.Frame(card, style="AccentBar.TFrame", height=3).pack(fill="x")
            self.stat[key] = ttk.Label(card, text="0", style="Stat.TLabel")
            self.stat[key].pack(fill="x", padx=18, pady=(14, 0))
            ttk.Label(card, text=caption, style="Muted.TLabel").pack(fill="x", padx=18, pady=(0, 14))

        chart_card = ttk.Frame(self.body, style="Card.TFrame")
        chart_card.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        ttk.Frame(chart_card, style="AccentBar.TFrame", height=3).pack(fill="x")
        ttk.Label(chart_card, text="Grade distribution", style="H2.TLabel").pack(fill="x", padx=18, pady=16)
        self.canvas = tk.Canvas(chart_card, bg=CARD, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.canvas.bind("<Configure>", lambda e: self.draw_chart())
        self.counts = {g[1]: 0 for g in GRADES}

        side = ttk.Frame(self.body, style="Card.TFrame", width=260)
        side.grid(row=1, column=1, sticky="ns")
        side.pack_propagate(False)
        ttk.Frame(side, style="AccentBar.TFrame", height=3).pack(fill="x")
        ttk.Label(side, text="Quick actions", style="H2.TLabel").pack(fill="x", padx=18, pady=16)
        for text, page, style in (("Add a student", "students", "Accent.TButton"),
                                  ("Add a department", "departments", "Plain.TButton"),
                                  ("Add a course", "courses", "Plain.TButton"),
                                  ("Record a result", "results", "Plain.TButton")):
            ttk.Button(side, text=text, style=style, command=lambda p=page: app.show(p)
                       ).pack(fill="x", padx=18, pady=5)
        ttk.Label(side, text="Pass rate (grade D or better)", style="Muted.TLabel"
                  ).pack(fill="x", padx=18, pady=(24, 4))
        self.pass_lbl = ttk.Label(side, text="0%", style="H2.TLabel")
        self.pass_lbl.pack(fill="x", padx=18)
        self.pass_bar = ttk.Progressbar(side, style="Green.Horizontal.TProgressbar", maximum=100)
        self.pass_bar.pack(fill="x", padx=18, pady=8)
        ttk.Label(side, text="Tip: add courses first, then students,\nthen record their results.",
                  style="Muted.TLabel", justify="center", wraplength=220
                  ).pack(side="bottom", fill="x", padx=18, pady=18)

    @staticmethod
    def _greeting():
        hour = datetime.now().hour
        return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    def refresh(self):
        db = self.db
        scores = [r["score"] for r in db.query("SELECT score FROM results")]
        self.stat["students"].config(text=db.one("SELECT COUNT(*) c FROM students")["c"])
        self.stat["departments"].config(text=db.one("SELECT COUNT(*) c FROM departments")["c"])
        self.stat["courses"].config(text=db.one("SELECT COUNT(*) c FROM courses")["c"])
        self.stat["results"].config(text=len(scores))
        self.stat["avg"].config(text=f"{sum(scores) / len(scores):.1f}" if scores else "0.0")
        self.counts = {g[1]: 0 for g in GRADES}
        for sc in scores:
            self.counts[grade_of(sc)[0]] += 1
        rate = 100 * sum(sc >= PASS_MARK for sc in scores) / len(scores) if scores else 0
        self.pass_lbl.config(text=f"{rate:.0f}%")
        self.pass_bar["value"] = rate
        self.draw_chart()

    def draw_chart(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 80:
            return
        top, bottom = 20, h - 22
        peak = max(self.counts.values()) or 1
        slot = w / len(self.counts)
        for line in range(1, 4):
            y_line = top + (bottom - top) * line / 3
            c.create_line(0, y_line, w, y_line, fill="#edf1f5")
        if not any(self.counts.values()):
            c.create_text(w / 2, h / 2, text="No results yet — record a result to see grades here.",
                          fill=MUTED, font=(FONT, 10))
            return
        grade_colors = {
            "A": "#16805d", "B+": "#3a9273", "B": "#62a483", "C+": "#c5a66a",
            "C": "#d29a49", "D+": "#d47a52", "D": "#c85c4a", "F": ACCENT,
        }
        for i, (letter, n) in enumerate(self.counts.items()):
            x0 = i * slot + slot * 0.2
            x1 = (i + 1) * slot - slot * 0.2
            y = bottom - (bottom - top) * n / peak
            if n:
                c.create_rectangle(x0, y, x1, bottom, fill=grade_colors[letter], outline="")
                c.create_text((x0 + x1) / 2, y - 10, text=str(n), fill=TEXT,
                              font=(FONT, 9, "bold"))
            c.create_text((x0 + x1) / 2, bottom + 11, text=letter, fill=MUTED,
                          font=(FONT, 9, "bold"))


# ------------------------------------------------------------------- courses
class CoursesPage(SplitPage):
    title, subtitle = "Courses", "The subjects that students take and are graded in."
    columns = [("code", "Code", 100), ("title", "Title", 220),
               ("department", "Department", 160), ("credits", "Credits", 70)]
    noun, add_text, form_title = "courses", "Add course", "Course details"

    def build_form(self, form):
        self.v_code, self.v_title, self.v_credits = tk.StringVar(), tk.StringVar(), tk.StringVar(value="3")
        self.v_department = tk.StringVar()
        self.department_ids = {}
        self.label("Course code (e.g. ITEC205)")
        self.entry(self.v_code, lock=True)
        self.label("Course title")
        self.entry(self.v_title)
        self.label("Department")
        self.c_department = self.combo(self.v_department, [])
        self.label("Credit hours")
        self.combo(self.v_credits, [str(i) for i in range(1, 7)])

    def refresh(self):
        departments = self.db.query("SELECT id, name FROM departments ORDER BY name")
        self.department_ids = {"(No department)": None}
        self.department_ids.update({r["name"]: r["id"] for r in departments})
        self.c_department.config(values=list(self.department_ids))
        self.reload()

    def rows(self):
        return [(r["code"], (r["code"], r["title"], r["department"] or "—", r["credits"]))
                for r in self.db.query(
                    "SELECT c.*, d.name AS department FROM courses c "
                    "LEFT JOIN departments d ON d.id = c.department_id ORDER BY c.code")]

    def fill(self, iid):
        r = self.db.one("SELECT * FROM courses WHERE code = ?", (iid,))
        self.v_code.set(r["code"]); self.v_title.set(r["title"]); self.v_credits.set(str(r["credits"]))
        self.v_department.set(next(
            (name for name, department_id in self.department_ids.items()
             if department_id == r["department_id"]), "(No department)"))

    def reset_form(self):
        self.v_code.set(""); self.v_title.set(""); self.v_credits.set("3")
        self.v_department.set("(No department)")

    def validate(self, editing):
        code, title = self.v_code.get().strip().upper(), self.v_title.get().strip()
        if not code:
            return "Course code is required."
        if not re.fullmatch(r"[A-Z]{3,5}\d{3}", code):
            return "Course code must be 3-5 letters followed by 3 digits (e.g. ITEC205)."
        if not title:
            return "Course title is required."
        if not editing and self.db.one("SELECT 1 FROM courses WHERE code = ?", (code,)):
            return f"A course with code {code} already exists."
        return ""

    def add(self):
        code = self.v_code.get().strip().upper()
        self.db.run("INSERT INTO courses (code,title,credits,department_id) VALUES (?,?,?,?)",
                    (code, self.v_title.get().strip(), int(self.v_credits.get()),
                     self.department_ids.get(self.v_department.get())))
        self.finish(f"Course {code} was added.")

    def update(self):
        code = self.v_code.get().strip().upper()
        self.db.run("UPDATE courses SET title = ?, credits = ?, department_id = ? WHERE code = ?",
                    (self.v_title.get().strip(), int(self.v_credits.get()),
                     self.department_ids.get(self.v_department.get()), code))
        self.finish(f"Course {code} was updated.")

    def delete(self, code):
        n = self.db.one("SELECT COUNT(*) c FROM results WHERE course_code = ?", (code,))["c"]
        if messagebox.askyesno("Delete course", f"Delete {code}?\n{n} result(s) will also be removed."):
            self.db.run("DELETE FROM courses WHERE code = ?", (code,))
            self.finish(f"Course {code} was deleted.")


# -------------------------------------------------------------- departments
class DepartmentsPage(SplitPage):
    title, subtitle = "Departments", "Manage the academic departments in your university."
    columns = [("code", "Code", 110), ("name", "Department", 220),
               ("description", "Description", 360)]
    noun, add_text, form_title = "departments", "Add department", "Department details"

    def build_form(self, form):
        self.v_code, self.v_name = tk.StringVar(), tk.StringVar()
        self.v_description = tk.StringVar()
        self.label("Department code")
        self.entry(self.v_code, lock=True)
        self.label("Department name")
        self.entry(self.v_name)
        self.label("Description")
        self.entry(self.v_description)

    def rows(self):
        return [(r["id"], (r["code"], r["name"], r["description"]))
                for r in self.db.query("SELECT * FROM departments ORDER BY name")]

    def fill(self, iid):
        row = self.db.one("SELECT * FROM departments WHERE id = ?", (iid,))
        self.v_code.set(row["code"])
        self.v_name.set(row["name"])
        self.v_description.set(row["description"])

    def reset_form(self):
        self.v_code.set("")
        self.v_name.set("")
        self.v_description.set("")

    def validate(self, editing):
        code = self.v_code.get().strip().upper()
        name = self.v_name.get().strip()
        if not re.fullmatch(r"[A-Z0-9-]{2,12}", code):
            return "Department code must be 2-12 letters, digits or hyphens."
        if not name:
            return "Department name is required."
        duplicate = self.db.one(
            "SELECT 1 FROM departments WHERE (code = ? OR name = ?) AND id != ?",
            (code, name, self.tree.selection()[0] if editing else -1))
        return "A department with this code or name already exists." if duplicate else ""

    def add(self):
        self.db.run("INSERT INTO departments (code,name,description) VALUES (?,?,?)",
                    (self.v_code.get().strip().upper(), self.v_name.get().strip(),
                     self.v_description.get().strip()))
        self.finish(f"{self.v_name.get().strip()} was added.")

    def update(self):
        department_id = self.tree.selection()[0]
        name = self.v_name.get().strip()
        self.db.run("UPDATE departments SET code = ?, name = ?, description = ? WHERE id = ?",
                    (self.v_code.get().strip().upper(), name,
                     self.v_description.get().strip(), department_id))
        self.finish(f"{name} was updated.")

    def delete(self, department_id):
        counts = self.db.one(
            "SELECT (SELECT COUNT(*) FROM students WHERE department_id = ?) AS students, "
            "(SELECT COUNT(*) FROM courses WHERE department_id = ?) AS courses",
            (department_id, department_id))
        message = (f"Delete this department? {counts['students']} student(s) and "
                   f"{counts['courses']} course(s) will be left unassigned.")
        if messagebox.askyesno("Delete department", message):
            self.db.run("DELETE FROM departments WHERE id = ?", (department_id,))
            self.finish("Department was deleted.")


# ------------------------------------------------------------------ students
class StudentsPage(SplitPage):
    title, subtitle = "Students", "Register, search and manage every student."
    columns = [("id", "ID", 100), ("name", "Name", 170), ("level", "Level", 55),
               ("prog", "Programme", 170), ("department", "Department", 140),
               ("status", "Status", 70)]
    noun, add_text, form_title = "students", "Add student", "Student details"

    def build_form(self, form):
        self.v_id, self.v_name, self.v_email = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_gender, self.v_level = tk.StringVar(value="Male"), tk.StringVar(value="100")
        self.v_prog, self.v_active = tk.StringVar(value=PROGRAMMES[0]), tk.BooleanVar(value=True)
        self.v_department = tk.StringVar()
        self.department_ids = {}

        # search + export live in the toolbar above the table
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.reload())
        ttk.Label(self.toolbar, text="Search", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Entry(self.toolbar, textvariable=self.search).pack(side="left", fill="x", expand=True)
        ttk.Button(self.toolbar, text="Export CSV", style="Plain.TButton",
                   command=self.export_csv).pack(side="left", padx=(8, 0))
        ttk.Label(self.toolbar, text="", style="Muted.TLabel")  # spacer for symmetry

        self.label("Student ID")
        self.entry(self.v_id, lock=True)
        self.label("Full name")
        self.entry(self.v_name)
        self.label("Email (optional)")
        self.entry(self.v_email)
        self.label("Gender")
        row = ttk.Frame(form, style="Card.TFrame"); row.pack(anchor="w")
        for g in ("Male", "Female"):
            ttk.Radiobutton(row, text=g, value=g, variable=self.v_gender,
                            style="Card.TRadiobutton").pack(side="left", padx=(0, 12))
        self.label("Level")
        self.combo(self.v_level, LEVELS)
        self.label("Programme")
        self.combo(self.v_prog, PROGRAMMES)
        self.label("Department")
        self.c_department = self.combo(self.v_department, [])
        ttk.Checkbutton(form, text="Active student", variable=self.v_active,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(10, 0))

    def refresh(self):
        departments = self.db.query("SELECT id, name FROM departments ORDER BY name")
        self.department_ids = {"(No department)": None}
        self.department_ids.update({r["name"]: r["id"] for r in departments})
        self.c_department.config(values=list(self.department_ids))
        self.reload()

    def rows(self):
        like = f"%{self.search.get().strip()}%"
        data = self.db.query(
            "SELECT s.*, d.name AS department FROM students s "
            "LEFT JOIN departments d ON d.id = s.department_id "
            "WHERE s.id LIKE ? OR s.name LIKE ? OR s.programme LIKE ? OR d.name LIKE ? "
            "ORDER BY s.name", (like, like, like, like))
        return [(r["id"], (r["id"], r["name"], r["level"], r["programme"],
                           r["department"] or "—",
                           "Active" if r["active"] else "Inactive")) for r in data]

    def fill(self, iid):
        r = self.db.one("SELECT * FROM students WHERE id = ?", (iid,))
        self.v_id.set(r["id"]); self.v_name.set(r["name"]); self.v_email.set(r["email"] or "")
        self.v_gender.set(r["gender"]); self.v_level.set(r["level"])
        self.v_prog.set(r["programme"]); self.v_active.set(bool(r["active"]))
        self.v_department.set(next(
            (name for name, department_id in self.department_ids.items()
             if department_id == r["department_id"]), "(No department)"))

    def reset_form(self):
        for v in (self.v_id, self.v_name, self.v_email):
            v.set("")
        self.v_gender.set("Male"); self.v_level.set("100")
        self.v_prog.set(PROGRAMMES[0]); self.v_active.set(True)
        self.v_department.set("(No department)")

    def validate(self, editing):
        sid, name, email = self.v_id.get().strip(), self.v_name.get().strip(), self.v_email.get().strip()
        if not sid:
            return "Student ID is required."
        if not re.fullmatch(r"[A-Za-z0-9-]{3,15}", sid):
            return "Student ID must be 3-15 letters, digits or hyphens."
        if not name:
            return "Full name is required."
        if not (2 <= len(name) <= 64 and all(ch.isalpha() or ch in " .-'" for ch in name)):
            return "Name may only contain letters, spaces, dots, hyphens and apostrophes (2-64 characters)."
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return "Please enter a valid email address."
        if not editing and self.db.one("SELECT 1 FROM students WHERE id = ?", (sid,)):
            return f"A student with ID {sid} already exists."
        return ""

    def _values(self):
        return (self.v_name.get().strip(), self.v_email.get().strip(), self.v_gender.get(),
                self.v_level.get(), self.v_prog.get(), int(self.v_active.get()),
                self.department_ids.get(self.v_department.get()))

    def add(self):
        sid = self.v_id.get().strip()
        self.db.run("INSERT INTO students "
                    "(name,email,gender,level,programme,active,department_id,id) "
                    "VALUES (?,?,?,?,?,?,?,?)", self._values() + (sid,))
        self.finish(f"{self.v_name.get().strip()} was added.")

    def update(self):
        name = self.v_name.get().strip()
        self.db.run("UPDATE students SET name=?,email=?,gender=?,level=?,programme=?,active=?,department_id=? "
                    "WHERE id=?", self._values() + (self.v_id.get().strip(),))
        self.finish(f"{name} was updated.")

    def delete(self, sid):
        n = self.db.one("SELECT COUNT(*) c FROM results WHERE student_id = ?", (sid,))["c"]
        name = self.v_name.get()
        if messagebox.askyesno("Delete student", f"Delete {name}?\n{n} result(s) will also be removed."):
            self.db.run("DELETE FROM students WHERE id = ?", (sid,))
            self.finish(f"{name} was deleted.")

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="students.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        data = self.db.query(
            "SELECT s.id,s.name,s.email,s.gender,s.level,s.programme,s.active,d.name AS department "
            "FROM students s LEFT JOIN departments d ON d.id = s.department_id ORDER BY s.name")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig opens cleanly in Excel
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "Email", "Gender", "Level", "Programme",
                             "Department", "Status"])
            for r in data:
                writer.writerow([r["id"], r["name"], r["email"], r["gender"], r["level"],
                                 r["programme"], r["department"] or "",
                                 "Active" if r["active"] else "Inactive"])
        self.say(f"Exported {len(data)} students.")


# ------------------------------------------------------------------- results
class ResultsPage(SplitPage):
    title, subtitle = "Results", "Record scores. The grade is worked out for you."
    columns = [("student", "Student", 150), ("course", "Course", 210), ("credits", "Credits", 60),
               ("score", "Score", 60), ("grade", "Grade", 60)]
    noun, add_text, upd_text, form_title = "results", "Save result", "Update score", "Result details"

    def build_form(self, form):
        self.v_student, self.v_course, self.v_score = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.students, self.courses = {}, {}       # label -> key
        self.v_score.trace_add("write", lambda *_: self.show_grade())

        self.filter = tk.StringVar()
        self.filter.trace_add("write", lambda *_: self.reload())
        ttk.Label(self.toolbar, text="Search", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Entry(self.toolbar, textvariable=self.filter).pack(side="left", fill="x", expand=True)

        self.label("Student")
        self.c_student = self.combo(self.v_student, [], lock=True)
        self.c_student.bind("<<ComboboxSelected>>", lambda e: self.show_gpa(self.students.get(self.v_student.get())))
        self.label("Course")
        self.c_course = self.combo(self.v_course, [], lock=True)
        self.label("Score (0 - 100)")
        self.entry(self.v_score)
        self.label("Grade")
        self.grade_lbl = tk.Label(form, text="—", bg=CARD, font=(FONT, 16, "bold"),
                                  fg=ACCENT, anchor="center")
        self.grade_lbl.pack(fill="x")
        self.gpa_lbl = ttk.Label(form, text="", style="Muted.TLabel", wraplength=250)
        self.gpa_lbl.pack(fill="x", pady=4)

    def refresh(self):
        s = self.db.query("SELECT id, name FROM students ORDER BY name")
        c = self.db.query("SELECT code, title FROM courses ORDER BY code")
        self.students = {f"{r['id']} - {r['name']}": r["id"] for r in s}
        self.courses = {f"{r['code']} - {r['title']}": r["code"] for r in c}
        self.c_student.config(values=list(self.students))
        self.c_course.config(values=list(self.courses))
        self.reload()

    def rows(self):
        like = f"%{self.filter.get().strip()}%"
        data = self.db.query(
            "SELECT r.id, s.name, c.code, c.title, c.credits, r.score FROM results r "
            "JOIN students s ON s.id = r.student_id JOIN courses c ON c.code = r.course_code "
            "WHERE s.name LIKE ? OR s.id LIKE ? OR c.code LIKE ? OR c.title LIKE ? "
            "ORDER BY s.name, c.code", (like,) * 4)
        return [(r["id"], (r["name"], f"{r['code']} - {r['title']}", r["credits"],
                           f"{r['score']:g}", grade_of(r["score"])[0])) for r in data]

    def show_grade(self):
        try:
            self.grade_lbl.config(text=grade_of(float(self.v_score.get()))[0]
                                  if 0 <= float(self.v_score.get()) <= 100 else "—")
        except ValueError:
            self.grade_lbl.config(text="—")

    def show_gpa(self, sid):
        if not sid:
            self.gpa_lbl.config(text="")
            return
        gpa, n = self.db.gpa(sid)
        name = self.db.one("SELECT name FROM students WHERE id = ?", (sid,))["name"]
        self.gpa_lbl.config(text=f"{name}: GPA {gpa:.2f} from {n} result(s)" if n else f"{name}: no results yet")

    def _label_for(self, mapping, key):
        return next((label for label, k in mapping.items() if k == key), "")

    def fill(self, iid):
        r = self.db.one("SELECT * FROM results WHERE id = ?", (iid,))
        self.v_student.set(self._label_for(self.students, r["student_id"]))
        self.v_course.set(self._label_for(self.courses, r["course_code"]))
        self.v_score.set(f"{r['score']:g}")
        self.show_gpa(r["student_id"])

    def reset_form(self):
        self.v_student.set(""); self.v_course.set(""); self.v_score.set("")
        self.gpa_lbl.config(text="")

    def validate(self, editing):
        if not editing and (not self.students or not self.courses):
            return "Add at least one student and one course before recording results."
        if not editing and (self.v_student.get() not in self.students or self.v_course.get() not in self.courses):
            return "Choose a student and a course."
        try:
            score = float(self.v_score.get())
        except ValueError:
            return "Score must be a number."
        if not (math.isfinite(score) and 0 <= score <= 100):
            return "Score must be between 0 and 100."
        if not editing:
            sid, code = self.students[self.v_student.get()], self.courses[self.v_course.get()]
            if self.db.one("SELECT 1 FROM results WHERE student_id=? AND course_code=?", (sid, code)):
                name = self.db.one("SELECT name FROM students WHERE id = ?", (sid,))["name"]
                return f"{name} already has a result for {code}. Select it in the table and use Update."
        return ""

    def add(self):
        sid, code = self.students[self.v_student.get()], self.courses[self.v_course.get()]
        score = float(self.v_score.get())
        self.db.run("INSERT INTO results (student_id, course_code, score) VALUES (?,?,?)", (sid, code, score))
        self.finish(f"Saved: {code} - {score:g} ({grade_of(score)[0]}).")
        self.show_gpa(sid)

    def update(self):
        rid = self.tree.selection()[0]
        score = float(self.v_score.get())
        sid = self.db.one("SELECT student_id FROM results WHERE id = ?", (rid,))["student_id"]
        self.db.run("UPDATE results SET score = ? WHERE id = ?", (score, rid))
        self.finish(f"Score updated to {score:g} ({grade_of(score)[0]}).")
        self.show_gpa(sid)

    def delete(self, rid):
        if messagebox.askyesno("Delete result", "Delete this result?"):
            self.db.run("DELETE FROM results WHERE id = ?", (rid,))
            self.finish("Result deleted.")


# --------------------------------------------------------------------- login
class LoginFrame(tk.Frame):
    MAX_ATTEMPTS, LOCK_SECONDS = 3, 30

    def __init__(self, app):
        super().__init__(app, bg="#0877bd")
        self.app, self.fails, self.locked_until = app, 0, 0.0

        backdrop = tk.Canvas(self, bg="#0877bd", highlightthickness=0)
        backdrop.place(relwidth=1, relheight=1)
        backdrop.create_oval(-110, 340, 220, 670, fill="#1288cc", outline="")
        backdrop.create_oval(150, 300, 410, 560, fill="#1682c4", outline="")
        backdrop.create_oval(700, -155, 1030, 175, fill="#1682c4", outline="")

        card = tk.Canvas(self, width=790, height=420, bg="#0877bd", highlightthickness=0)
        card.place(relx=0.5, rely=0.5, anchor="center")
        radius = 20
        card.create_rectangle(radius, 0, 790 - radius, 420, fill=CARD, outline="")
        card.create_rectangle(0, radius, 790, 420 - radius, fill=CARD, outline="")
        for x, y in ((0, 0), (790 - 2 * radius, 0),
                     (0, 420 - 2 * radius), (790 - 2 * radius, 420 - 2 * radius)):
            card.create_oval(x, y, x + 2 * radius, y + 2 * radius, fill=CARD, outline="")
        card.create_rectangle(radius, 0, 325, 420, fill="#0877bd", outline="")
        card.create_rectangle(0, radius, 325, 420 - radius, fill="#0877bd", outline="")
        card.create_oval(0, 0, 2 * radius, 2 * radius, fill="#0877bd", outline="")
        card.create_oval(0, 420 - 2 * radius, 2 * radius, 420, fill="#0877bd", outline="")

        brand = tk.Frame(card, bg="#0877bd", width=305, height=420)
        card.create_window(20, 0, anchor="nw", window=brand, width=305, height=420)
        inner = tk.Frame(brand, bg="#0877bd")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, text="WELCOME", bg="#0877bd", fg="white",
                 font=(FONT, 19, "bold")).pack(anchor="center", pady=(0, 10))
        tk.Label(inner, text="YOUR STUDENT PORTAL", bg="#0877bd", fg="#d7efff",
                 font=(FONT, 9, "bold")).pack(anchor="center", pady=(0, 12))
        tk.Label(inner, text="A clearer view of\nstudent progress.", bg="#0877bd", fg="white",
                 font=(FONT, 21, "bold"), justify="center").pack(anchor="center")
        tk.Label(inner, text="Student Management System", bg="#0877bd",
                 fg="#d7efff", font=(FONT, 10)).pack(anchor="center", pady=(12, 0))

        form = tk.Frame(card, bg=CARD, width=445, height=380)
        card.create_window(325, 20, anchor="nw", window=form, width=445, height=380)
        content = tk.Frame(form, bg=CARD, width=340)
        content.place(relx=0.5, rely=0.5, anchor="center", width=340)
        self.school_logo = load_school_logo(14)
        tk.Label(content, image=self.school_logo, bg=CARD).pack(anchor="center", pady=(0, 8))
        tk.Label(content, text="Sign in", bg=CARD, fg=TEXT, font=(FONT, 20, "bold")
                 ).pack(fill="x")
        tk.Label(content, text="Sign in to continue to your workspace.", bg=CARD, fg=MUTED
                 ).pack(fill="x", pady=(4, 20))

        self.user, self.pw, self.show = tk.StringVar(), tk.StringVar(), tk.BooleanVar()
        tk.Label(content, text="Username", bg=CARD, fg="#334155",
                 font=(FONT, 9, "bold"), anchor="w").pack(fill="x", pady=(0, 5))
        self.user_entry = ttk.Entry(content, textvariable=self.user, width=34, justify="left")
        self.user_entry.pack(fill="x", pady=(0, 14))
        tk.Label(content, text="Password", bg=CARD, fg="#334155",
                 font=(FONT, 9, "bold"), anchor="w").pack(fill="x", pady=(0, 5))
        self.pw_entry = ttk.Entry(content, textvariable=self.pw, show="•", width=34,
                                  justify="left")
        self.pw_entry.pack(fill="x", pady=(0, 5))
        ttk.Checkbutton(content, text="Show password", variable=self.show, style="Card.TCheckbutton",
                        command=lambda: self.pw_entry.config(show="" if self.show.get() else "•")
                        ).pack(anchor="w")
        self.err = tk.Label(content, text="", bg=CARD, fg=RED, font=(FONT, 9),
                            wraplength=320, justify="left", anchor="w")
        self.err.pack(fill="x", pady=8)
        self.btn = tk.Button(content, text="Sign in", bg="#0b4f82", activebackground="#083e68",
                             fg="white", activeforeground="white", relief="flat", borderwidth=0,
                             cursor="hand2", font=(FONT, 10, "bold"), pady=9,
                             command=self.attempt)
        self.btn.pack(fill="x")

        for w in (self.user_entry, self.pw_entry):
            w.bind("<Return>", lambda e: self.attempt())
        self.user_entry.focus_set()

    def attempt(self):
        if time.time() < self.locked_until:
            return
        if self.app.db.check_login(self.user.get().strip(), self.pw.get()):
            self.app.show_main(self.user.get().strip())
            return
        self.fails += 1
        self.pw.set("")
        if self.fails >= self.MAX_ATTEMPTS:
            self.fails = 0
            self.locked_until = time.time() + self.LOCK_SECONDS
            self.countdown()
        else:
            self.err.config(text="Invalid username or password.")

    def countdown(self):
        if not self.winfo_exists():
            return
        left = math.ceil(self.locked_until - time.time())
        if left > 0:
            self.btn.config(state="disabled")
            self.err.config(text=f"Too many failed attempts. Try again in {left} seconds.")
            self.after(1000, self.countdown)
        else:
            self.btn.config(state="normal")
            self.err.config(text="")


# ------------------------------------------------------------------ main shell
class MainFrame(tk.Frame):
    NAV = [("dashboard", "Dashboard", DashboardPage), ("departments", "Departments", DepartmentsPage),
           ("students", "Students", StudentsPage), ("courses", "Courses", CoursesPage),
           ("results", "Results", ResultsPage)]

    def __init__(self, app):
        super().__init__(app, bg=BG)
        self.app = app
        side = tk.Frame(self, bg=SIDEBAR, width=246)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.school_logo = load_school_logo(16)
        tk.Label(side, image=self.school_logo, bg=SIDEBAR).pack(anchor="center", padx=18,
                                                                pady=(22, 14))
        tk.Label(side, text="Central Track", bg=SIDEBAR, fg="white",
                 font=(FONT, 17, "bold")).pack(fill="x", padx=18)
        tk.Label(side, text="STUDENT MANAGEMENT", bg=SIDEBAR, fg="#cbd5e1",
                 font=(FONT, 8, "bold")).pack(fill="x", padx=19, pady=(3, 22))
        tk.Frame(side, bg="#344351", height=1).pack(fill="x", padx=18, pady=(0, 18))

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.nav, self.pages = {}, {}
        for key, text, page_cls in self.NAV:
            lbl = tk.Label(side, text=text, bg=SIDEBAR, fg="#d1d5f0", anchor="center",
                           font=(FONT, 10, "bold"), cursor="hand2", pady=11)
            lbl.pack(fill="x", padx=12, pady=3)
            lbl.bind("<Button-1>", lambda e, k=key: self.show(k))
            lbl.bind("<Enter>", lambda e, k=key: self._hover_nav(k, True))
            lbl.bind("<Leave>", lambda e, k=key: self._hover_nav(k, False))
            self.nav[key] = lbl
            self.pages[key] = page_cls(self.content, app)

        tk.Label(side, text=app.user.title(), bg="#263645", fg="white", anchor="center",
                 font=(FONT, 10, "bold"), pady=11).pack(side="bottom", fill="x", padx=12, pady=(0, 16))
        out = tk.Label(side, text="Log out", bg=SIDEBAR, fg="#cbd5e1", anchor="center",
                       cursor="hand2", pady=8)
        out.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        out.bind("<Button-1>", lambda e: app.show_login())
        out.bind("<Enter>", lambda e: out.config(bg="#263645"))
        out.bind("<Leave>", lambda e: out.config(bg=SIDEBAR))
        self.show("dashboard")

    def show(self, key):
        self.active_page = key
        for k, page in self.pages.items():
            page.pack_forget()
            self.nav[k].config(bg=ACCENT if k == key else SIDEBAR, fg="white" if k == key else "#d1d5f0")
        self.pages[key].pack(fill="both", expand=True)
        self.pages[key].refresh()

    def _hover_nav(self, key, entered):
        if key != getattr(self, "active_page", None):
            self.nav[key].config(bg="#263645" if entered else SIDEBAR)


# --------------------------------------------------------------- startup screen
class StartupSplash(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=SIDEBAR)
        self.app = app
        self.step = 0
        self.total_steps = 30

        content = tk.Frame(self, bg=SIDEBAR)
        content.place(relx=0.5, rely=0.5, anchor="center")
        self.school_logo = tk.PhotoImage(file=str(STARTUP_LOGO_PATH)).subsample(5, 5)
        tk.Label(content, image=self.school_logo, bg=SIDEBAR).pack(pady=(0, 12))
        tk.Label(content, text="Central Track", bg=SIDEBAR, fg="white",
                 font=(FONT, 27, "bold")).pack()
        tk.Label(content, text="STUDENT MANAGEMENT SYSTEM", bg=SIDEBAR,
                 fg="#cbd5e1", font=(FONT, 9, "bold")).pack(pady=(4, 18))

        self.progress = tk.Canvas(content, width=320, height=28, bg=SIDEBAR,
                                  highlightthickness=0)
        self.progress.pack()
        self.progress.create_line(16, 14, 304, 14, fill="#344351", width=4)
        self.bar = self.progress.create_line(16, 14, 16, 14, fill=ACCENT,
                                             width=4, capstyle=tk.ROUND)
        self.nodes = [
            self.progress.create_oval(x - 5, 9, x + 5, 19, fill="#64748b", outline="")
            for x in (16, 160, 304)
        ]
        self.status = tk.Label(content, text="Preparing your workspace...",
                               bg=SIDEBAR, fg="white", font=(FONT, 9))
        self.status.pack(pady=(8, 0))
        self.after(60, self.animate)

    def animate(self):
        self.step += 1
        progress = min(self.step / self.total_steps, 1)
        end = 16 + 288 * progress
        self.progress.coords(self.bar, 16, 14, end, 14)
        for index, x in enumerate((16, 160, 304)):
            color = ACCENT if progress >= index / 2 else "#64748b"
            self.progress.itemconfigure(self.nodes[index], fill=color)

        messages = ("Preparing your workspace...", "Loading your dashboard...",
                    "Almost ready...")
        self.status.config(text=messages[min(int(progress * len(messages)), len(messages) - 1)])
        if self.step >= self.total_steps:
            self.app.show_login()
        else:
            self.after(60, self.animate)


# ------------------------------------------------------------------------ app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Central Track - Student Management System")
        self.configure(bg=BG)
        self.app_icon = load_school_logo(24)
        self.iconphoto(True, self.app_icon)
        setup_styles(self)
        try:
            self.db = Database()
        except sqlite3.Error:
            messagebox.showerror("Central Track", "Central Track could not open its database.\n"
                                 "Close other copies of Central Track and try again.")
            self.destroy()
            raise SystemExit(1)
        self.user, self.frame = "", None
        self._swap(StartupSplash(self), "560x340")

    def _swap(self, frame, size):
        if self.frame:
            self.frame.destroy()
        self.frame = frame
        self.frame.pack(fill="both", expand=True)
        self.geometry(size)
        self.minsize(*map(int, size.split("x")))

    def show_login(self):
        self.user = ""
        self._swap(LoginFrame(self), "880x540")

    def show_main(self, username):
        self.user = username
        self._swap(MainFrame(self), "1150x700")

    def show(self, page):                     # used by dashboard quick actions
        self.frame.show(page)


if __name__ == "__main__":
    App().mainloop()
