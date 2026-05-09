import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import csv
import os
import subprocess
import threading
import time
import hashlib

from backend import *
from backend import ScanAnalyzer, FolderInsights, FolderWatcher


class WorkBuddyApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x700")
        self.minsize(1000, 650)

        self._scanner = FolderScanner()
        self._organizer = Organizer()
        self._db = HistoryDB(Path(__file__).with_name(DB_FILENAME))

        self._scan_thread: Optional[threading.Thread] = None
        self._latest_result: Optional[ScanResult] = None
        self._latest_scan_id: Optional[int] = None
        self._dupe_thread: Optional[threading.Thread] = None
        self._current_filter: str = ""
        self._advanced_visible: bool = False
        self._watch_job: Optional[str] = None
        self._schedule_job: Optional[str] = None
        self._last_watch_snapshot: Dict[str, float] = {}

        self._build_ui()
        self._refresh_history()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=10)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")

        self.folder_var = tk.StringVar(value=str(Path.home()))
        folder_entry = ttk.Entry(header, textvariable=self.folder_var)
        folder_entry.grid(row=0, column=1, sticky="ew", padx=(10, 8))

        ttk.Button(header, text="Browse…", command=self._browse_folder).grid(row=0, column=2, padx=(0, 8))

        self.recursive_var = tk.BooleanVar(value=True)
        self.hidden_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(header, text="Recursive", variable=self.recursive_var).grid(row=0, column=3, padx=(0, 8))
        ttk.Checkbutton(header, text="Include hidden", variable=self.hidden_var).grid(row=0, column=4, padx=(0, 8))

        self.scan_btn = ttk.Button(header, text="Scan Folder", command=self._start_scan)
        self.scan_btn.grid(row=0, column=5)

        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=(0, 0, 10, 0))
        right = ttk.Frame(main)
        main.add(left, weight=55)
        main.add(right, weight=45)

        # Left: table + export/organize
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        summary = ttk.LabelFrame(left, text="Summary", padding=10)
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(1, weight=1)

        self.summary_text = tk.StringVar(value="Pick a folder and click Scan Folder.")
        ttk.Label(summary, textvariable=self.summary_text, justify="left").grid(row=0, column=0, sticky="w")

        actions = ttk.LabelFrame(left, text="Actions", padding=10)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        actions.columnconfigure(99, weight=1)

        # Basic actions (always visible)
        ttk.Button(actions, text="Export CSV…", command=self._export_csv).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Export SQLite (save scan)", command=self._save_to_db).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Copy summary", command=self._copy_summary).grid(row=0, column=2, padx=(0, 8))

        self.organize_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(actions, text="Organize into category folders", variable=self.organize_var).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Button(actions, text="Apply Organize", command=self._apply_organize).grid(row=0, column=4, padx=(0, 12))

        self.advanced_btn = ttk.Button(actions, text="Advanced ▸", command=self._toggle_advanced)
        self.advanced_btn.grid(row=0, column=5, sticky="e")

        # Advanced panel (collapsed by default)
        self.advanced_frame = ttk.LabelFrame(left, text="Advanced", padding=10)
        # Not gridded until expanded.
        self.advanced_frame.columnconfigure(9, weight=1)

        ttk.Button(self.advanced_frame, text="Find duplicates…", command=self._start_find_duplicates).grid(
            row=0, column=0, padx=(0, 8), pady=(0, 6), sticky="w"
        )
        ttk.Button(self.advanced_frame, text="Undo last organize", command=self._undo_last_organize).grid(
            row=0, column=1, padx=(0, 8), pady=(0, 6), sticky="w"
        )
        ttk.Button(self.advanced_frame, text="Compare scans…", command=self._compare_scans).grid(
            row=0, column=2, padx=(0, 8), pady=(0, 6), sticky="w"
        )
        ttk.Button(self.advanced_frame, text="Insights / Cleanup…", command=self._open_insights).grid(
            row=0, column=3, padx=(0, 8), pady=(0, 6), sticky="w"
        )
        ttk.Button(self.advanced_frame, text="Undo history…", command=self._open_undo_history).grid(
            row=0, column=4, padx=(0, 8), pady=(0, 6), sticky="w"
        )
        ttk.Button(self.advanced_frame, text="Quarantine…", command=self._open_quarantine_manager).grid(
            row=0, column=5, padx=(0, 8), pady=(0, 6), sticky="w"
        )
        ttk.Button(self.advanced_frame, text="Rules organize…", command=self._open_rules_organize).grid(
            row=0, column=6, padx=(0, 8), pady=(0, 6), sticky="w"
        )

        ttk.Label(self.advanced_frame, text="Filter:").grid(row=0, column=7, padx=(10, 6), pady=(0, 6), sticky="e")
        self.filter_var = tk.StringVar(value="")
        filter_entry = ttk.Entry(self.advanced_frame, textvariable=self.filter_var, width=30)
        filter_entry.grid(row=0, column=8, pady=(0, 6), sticky="w")
        filter_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        ttk.Label(
            self.advanced_frame,
            text="Tip: select a saved scan on the right before using Compare.",
            foreground="#555",
        ).grid(row=1, column=0, columnspan=10, sticky="w")

        # Automation: scheduled scans + watch mode
        auto = ttk.LabelFrame(self.advanced_frame, text="Automation", padding=10)
        auto.grid(row=2, column=0, columnspan=10, sticky="ew", pady=(8, 0))
        auto.columnconfigure(9, weight=1)

        ttk.Label(auto, text="Auto-scan every").grid(row=0, column=0, sticky="w")
        self.autoscan_minutes_var = tk.StringVar(value="0")
        ttk.Entry(auto, textvariable=self.autoscan_minutes_var, width=6).grid(row=0, column=1, padx=(6, 6), sticky="w")
        ttk.Label(auto, text="minutes (0 = off)").grid(row=0, column=2, sticky="w")
        ttk.Button(auto, text="Apply schedule", command=self._apply_schedule).grid(row=0, column=3, padx=(10, 0), sticky="w")

        self.watch_var = tk.BooleanVar(value=False)
        self.watch_check = ttk.Checkbutton(
            auto,
            text="Watch mode (detect changes)",
            variable=self.watch_var,
            command=self._toggle_watch,
        )
        self.watch_check.grid(
            row=0, column=4, padx=(18, 0), sticky="w"
        )
        ttk.Label(auto, text="(lightweight polling)", foreground="#555").grid(row=0, column=5, padx=(6, 0), sticky="w")
        self._sync_watch_availability()

        table_frame = ttk.LabelFrame(left, text="Files (top 500 shown)", padding=10)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        columns = ("category", "ext", "size", "modified", "rel_path")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
        self.tree.heading("category", text="Category")
        self.tree.heading("ext", text="Ext")
        self.tree.heading("size", text="Size")
        self.tree.heading("modified", text="Modified")
        self.tree.heading("rel_path", text="Path")

        self.tree.column("category", width=120, anchor="w")
        self.tree.column("ext", width=70, anchor="w")
        self.tree.column("size", width=90, anchor="e")
        self.tree.column("modified", width=150, anchor="w")
        self.tree.column("rel_path", width=450, anchor="w")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        # Context menu for power users
        self._table_menu = tk.Menu(self, tearoff=0)
        self._table_menu.add_command(label="Open in File Explorer", command=self._open_selected_in_explorer)
        self._table_menu.add_command(label="Copy full path", command=self._copy_selected_full_path)
        self._table_menu.add_separator()
        self._table_menu.add_command(label="Move to Quarantine", command=self._quarantine_selected_file)
        self.tree.bind("<Button-3>", self._show_table_menu)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected_in_explorer())

        # Right: charts + history
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        chart_frame = ttk.LabelFrame(right, text="Charts (data-driven)", padding=10)
        chart_frame.grid(row=0, column=0, sticky="nsew")
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)

        # Give the pie chart more room and avoid label clashes by using a legend.
        self.figure = Figure(figsize=(7.2, 4.2), dpi=100)
        gs = self.figure.add_gridspec(1, 2, width_ratios=[1.5, 1.0])
        self.ax1 = self.figure.add_subplot(gs[0, 0])
        self.ax2 = self.figure.add_subplot(gs[0, 1])
        self.figure.tight_layout(pad=1.2)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._render_empty_charts()

        history = ttk.LabelFrame(right, text="Recent saved scans (SQLite)", padding=10)
        history.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        history.rowconfigure(0, weight=1)
        history.columnconfigure(0, weight=1)

        self.history_list = tk.Listbox(history, height=10)
        self.history_list.grid(row=0, column=0, sticky="nsew")
        history_scroll = ttk.Scrollbar(history, orient="vertical", command=self.history_list.yview)
        self.history_list.configure(yscrollcommand=history_scroll.set)
        history_scroll.grid(row=0, column=1, sticky="ns")

        self.status_var = tk.StringVar(value="Ready.")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(10, 6))
        status.grid(row=2, column=0, sticky="ew")

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self.advanced_btn.configure(text="Advanced ▾")
            # Insert between Actions (row=1) and Files table (row=2)
            self.advanced_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        else:
            self.advanced_btn.configure(text="Advanced ▸")
            self.advanced_frame.grid_forget()

    def _apply_schedule(self) -> None:
        # Cancel existing schedule
        if self._schedule_job is not None:
            try:
                self.after_cancel(self._schedule_job)
            except Exception:
                pass
            self._schedule_job = None

        raw = (self.autoscan_minutes_var.get() or "").strip()
        try:
            minutes = int(raw)
        except Exception:
            minutes = 0

        if minutes <= 0:
            self.status_var.set("Auto-scan schedule disabled.")
            return

        interval_ms = minutes * 60 * 1000

        def tick() -> None:
            # Reschedule first, then attempt scan (so failure doesn't stop the schedule).
            self._schedule_job = self.after(interval_ms, tick)
            try:
                self._start_scan()
            except Exception:
                pass

        self._schedule_job = self.after(interval_ms, tick)
        self.status_var.set(f"Auto-scan scheduled every {minutes} minute(s).")

    def _toggle_watch(self) -> None:
        if self.watch_var.get():
            self._start_watch()
        else:
            self._stop_watch()

    def _start_watch(self) -> None:
        self._stop_watch()
        folder = Path(self.folder_var.get()).expanduser()
        if not folder.exists() or not folder.is_dir():
            self.watch_var.set(False)
            messagebox.showerror("Invalid folder", "Please select a valid folder to watch.")
            return

        recursive = bool(self.recursive_var.get())
        include_hidden = bool(self.hidden_var.get())
        poll_ms = 5000

        def snapshot() -> Dict[str, float]:
            out: Dict[str, float] = {}
            it = folder.rglob("*") if recursive else folder.glob("*")
            for p in it:
                if p.is_dir():
                    continue
                if not include_hidden and self._scanner._is_hidden(p):
                    continue
                try:
                    st = p.stat()
                    out[safe_relpath(p, folder)] = float(st.st_mtime)
                except Exception:
                    continue
            return out

        self._last_watch_snapshot = FolderWatcher.snapshot(
            folder,
            recursive=recursive,
            include_hidden=include_hidden,
            scanner=self._scanner,
        )
        self.status_var.set("Watch mode enabled (polling).")

        def tick() -> None:
            try:
                current = FolderWatcher.snapshot(
                    folder,
                    recursive=recursive,
                    include_hidden=include_hidden,
                    scanner=self._scanner,
                )
                added = set(current.keys()) - set(self._last_watch_snapshot.keys())
                removed = set(self._last_watch_snapshot.keys()) - set(current.keys())
                changed = {k for k, v in current.items() if self._last_watch_snapshot.get(k) != v}

                self._last_watch_snapshot = current
                if added or removed or changed:
                    # Auto-refresh scan when changes detected.
                    self._start_scan()
            finally:
                self._watch_job = self.after(poll_ms, tick)

        self._watch_job = self.after(poll_ms, tick)

    def _stop_watch(self) -> None:
        if self._watch_job is not None:
            try:
                self.after_cancel(self._watch_job)
            except Exception:
                pass
            self._watch_job = None
        self._last_watch_snapshot = {}

    def _get_selected_history_scan_id(self) -> Optional[int]:
        sel = self.history_list.curselection()
        if not sel:
            return None
        text = self.history_list.get(sel[0])
        # Format: "#<id> | ..."
        if not text.startswith("#"):
            return None
        try:
            part = text.split("|", 1)[0].strip()
            return int(part[1:])
        except Exception:
            return None

    def _compare_scans(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return

        scan_id = self._get_selected_history_scan_id()
        if scan_id is None:
            messagebox.showinfo("Select a saved scan", "Pick a saved scan in the list on the right first.")
            return

        header = self._db.get_scan_header(scan_id)
        if not header:
            messagebox.showerror("Not found", f"Saved scan #{scan_id} was not found.")
            return

        _, saved_folder, saved_finished_at, _, _ = header
        current_folder = self._latest_result.folder
        if os.path.normcase(saved_folder) != os.path.normcase(current_folder):
            ok = messagebox.askyesno(
                "Different folder",
                "The selected saved scan is from a different folder.\n\n"
                f"Saved: {saved_folder}\nCurrent: {current_folder}\n\nCompare anyway?",
            )
            if not ok:
                return

        saved_files = self._db.get_scan_files(scan_id)

        def agg_current() -> Dict[str, Tuple[int, int]]:
            out: Dict[str, Tuple[int, int]] = {}
            for r in self._latest_result.records:
                c = r.category
                cnt, sz = out.get(c, (0, 0))
                out[c] = (cnt + 1, sz + int(r.size_bytes))
            return out

        def agg_saved() -> Dict[str, Tuple[int, int]]:
            out: Dict[str, Tuple[int, int]] = {}
            for _rel, cat, _ext, size in saved_files:
                cnt, sz = out.get(cat, (0, 0))
                out[cat] = (cnt + 1, sz + int(size))
            return out

        cur = agg_current()
        old = agg_saved()
        categories = sorted(set(cur.keys()) | set(old.keys()), key=lambda s: s.lower())

        rows: List[Dict[str, str]] = []
        for cat in categories:
            cur_cnt, cur_sz = cur.get(cat, (0, 0))
            old_cnt, old_sz = old.get(cat, (0, 0))
            rows.append(
                {
                    "category": cat,
                    "saved_count": str(old_cnt),
                    "current_count": str(cur_cnt),
                    "delta_count": str(cur_cnt - old_cnt),
                    "saved_size_bytes": str(old_sz),
                    "current_size_bytes": str(cur_sz),
                    "delta_size_bytes": str(cur_sz - old_sz),
                }
            )

        win = tk.Toplevel(self)
        win.title(f"Compare scans (saved #{scan_id} vs current)")
        win.geometry("980x560")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(
            top,
            text=(
                f"Saved scan:  #{scan_id}  ({saved_finished_at})\n"
                f"Saved folder: {saved_folder}\n"
                f"Current folder: {current_folder}"
            ),
            justify="left",
        ).pack(side="left")

        def export() -> None:
            default_name = f"workbuddy_compare_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            out_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=default_name,
            )
            if not out_path:
                return
            try:
                with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(
                        f,
                        fieldnames=[
                            "category",
                            "saved_count",
                            "current_count",
                            "delta_count",
                            "saved_size_bytes",
                            "current_size_bytes",
                            "delta_size_bytes",
                        ],
                    )
                    w.writeheader()
                    w.writerows(rows)
                messagebox.showinfo("Exported", f"Saved CSV:\n{out_path}")
            except Exception as e:
                messagebox.showerror("Export failed", str(e))

        ttk.Button(top, text="Export CSV…", command=export).pack(side="right")

        frame = ttk.Frame(win, padding=(10, 0, 10, 10))
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("category", "saved_count", "current_count", "delta_count", "saved_size", "current_size", "delta_size")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for c in columns:
            tree.heading(c, text=c.replace("_", " ").title())

        tree.column("category", width=180, anchor="w")
        tree.column("saved_count", width=95, anchor="e")
        tree.column("current_count", width=105, anchor="e")
        tree.column("delta_count", width=95, anchor="e")
        tree.column("saved_size", width=120, anchor="e")
        tree.column("current_size", width=130, anchor="e")
        tree.column("delta_size", width=120, anchor="e")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        def to_int(s: str) -> int:
            try:
                return int(s)
            except Exception:
                return 0

        # Show biggest changes first (by absolute delta size).
        for r in sorted(rows, key=lambda d: -abs(to_int(d["delta_size_bytes"]))):
            tree.insert(
                "",
                "end",
                values=(
                    r["category"],
                    r["saved_count"],
                    r["current_count"],
                    r["delta_count"],
                    human_bytes(int(r["saved_size_bytes"])),
                    human_bytes(int(r["current_size_bytes"])),
                    human_bytes(int(r["delta_size_bytes"])),
                ),
            )

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)
            self._sync_watch_availability()

    def _set_busy(self, busy: bool, message: str) -> None:
        self.scan_btn.configure(state=("disabled" if busy else "normal"))
        self.status_var.set(message)

    def _has_active_scan(self) -> bool:
        if not self._latest_result:
            return False
        current_folder = os.path.normcase(str(Path(self.folder_var.get()).expanduser()))
        latest_folder = os.path.normcase(str(Path(self._latest_result.folder).expanduser()))
        return current_folder == latest_folder

    def _sync_watch_availability(self) -> None:
        active_scan = self._has_active_scan()
        self.watch_check.configure(state=("normal" if active_scan else "disabled"))
        if not active_scan:
            self.watch_var.set(False)
            self._stop_watch()

    def _start_scan(self) -> None:
        if self._scan_thread and self._scan_thread.is_alive():
            messagebox.showinfo("Scan already running", "Please wait for the current scan to finish.")
            return

        folder = Path(self.folder_var.get()).expanduser()
        recursive = bool(self.recursive_var.get())
        include_hidden = bool(self.hidden_var.get())

        self._set_busy(True, "Scanning…")

        def run() -> None:
            try:
                t0 = time.time()
                result = self._scanner.scan(folder, recursive=recursive, include_hidden=include_hidden)
                elapsed = time.time() - t0
                self.after(0, lambda: self._on_scan_complete(result, elapsed))
            except Exception as e:
                self.after(0, lambda: self._on_scan_error(str(e)))

        self._scan_thread = threading.Thread(target=run, daemon=True)
        self._scan_thread.start()

    def _on_scan_error(self, message: str) -> None:
        self._set_busy(False, "Ready.")
        self._sync_watch_availability()
        messagebox.showerror("Scan failed", message)

    def _on_scan_complete(self, result: ScanResult, elapsed: float) -> None:
        self._latest_result = result
        self._latest_scan_id = None
        self._current_filter = (self.filter_var.get() or "").strip()

        self._populate_table(result)
        self._render_charts(result)
        self._update_summary(result, elapsed)
        self._set_busy(False, f"Scan complete in {elapsed:.2f}s.")
        self._sync_watch_availability()

    def _update_summary(self, result: ScanResult, elapsed: float) -> None:
        top_categories = ScanAnalyzer.group_counts(result, key="category")[:4]
        top_exts = ScanAnalyzer.group_counts(result, key="ext")[:4]

        cat_str = ", ".join([f"{k} ({v})" for k, v in top_categories]) or "n/a"
        ext_str = ", ".join([f"{k or '[none]'} ({v})" for k, v in top_exts]) or "n/a"

        self.summary_text.set(
            "\n".join(
                [
                    f"Folder: {result.folder}",
                    f"Files: {result.file_count}   Total size: {result.total_size_human}   Time: {elapsed:.2f}s",
                    f"Top categories: {cat_str}",
                    f"Top extensions: {ext_str}",
                ]
            )
        )

    def _populate_table(self, result: ScanResult) -> None:
        q = (self._current_filter or "").strip().lower()
        def matches(r: FileRecord) -> bool:
            if not q:
                return True
            hay = " ".join([r.name, r.rel_path, r.ext, r.category]).lower()
            return q in hay

        for row in self.tree.get_children():
            self.tree.delete(row)
        shown = 0
        for r in result.records:
            if not matches(r):
                continue
            shown += 1
            if shown > 500:
                break
            self.tree.insert(
                "",
                "end",
                values=(r.category, r.ext or "[none]", human_bytes(r.size_bytes), r.modified_iso, r.rel_path),
            )

    def _show_table_menu(self, event: tk.Event) -> None:
        try:
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
            self._table_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._table_menu.grab_release()
            except Exception:
                pass

    def _selected_rel_path(self) -> Optional[str]:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if not vals or len(vals) < 5:
            return None
        return str(vals[4])

    def _open_selected_in_explorer(self) -> None:
        if not self._latest_result:
            return
        rel = self._selected_rel_path()
        if not rel:
            return
        base = Path(self._latest_result.folder)
        full = (base / rel).resolve()
        if not full.exists():
            messagebox.showerror("Not found", f"Path does not exist:\n{full}")
            return
        try:
            if os.name == "nt":
                # Select file in Explorer when possible.
                subprocess.run(["explorer", "/select,", str(full)], check=False)
            else:
                subprocess.run(["xdg-open", str(full if full.is_dir() else full.parent)], check=False)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def _copy_selected_full_path(self) -> None:
        if not self._latest_result:
            return
        rel = self._selected_rel_path()
        if not rel:
            return
        base = Path(self._latest_result.folder)
        full = str((base / rel).resolve())
        self.clipboard_clear()
        self.clipboard_append(full)
        self.status_var.set("Full path copied to clipboard.")

    def _open_insights(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return

        base = Path(self._latest_result.folder)
        records = list(self._latest_result.records)
        folder_key = self._latest_result.folder

        # Largest + oldest lists (using already-collected metadata)
        largest = ScanAnalyzer.largest_files(self._latest_result, limit=25)
        oldest = ScanAnalyzer.oldest_files(self._latest_result, limit=25)

        # Size by category (bytes)
        cat_sizes = ScanAnalyzer.category_sizes(self._latest_result)
        top_cat_sizes = sorted(cat_sizes.items(), key=lambda kv: -kv[1])[:10]

        # Trend from SQLite history (total size over time)
        history = self._db.list_scans_for_folder(folder=folder_key, limit=30)
        history = list(reversed(history))  # oldest -> newest
        trend_x = [h[1] for h in history]
        trend_y = [h[3] for h in history]

        # Empty folder detection
        empty_dirs = FolderInsights.find_empty_dirs(base)

        win = tk.Toplevel(self)
        win.title("Insights / Cleanup")
        win.geometry("1020x620")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(
            top,
            text=(
                f"Folder: {base}\n"
                f"Largest files: {len(largest)} shown | Oldest files: {len(oldest)} shown | Empty folders: {len(empty_dirs)}"
            ),
            justify="left",
        ).pack(side="left")

        def export() -> None:
            default_name = f"workbuddy_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            out_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=default_name,
            )
            if not out_path:
                return
            rows: List[Dict[str, str]] = []
            for r in largest:
                rows.append(
                    {
                        "section": "largest",
                        "name": r.name,
                        "rel_path": r.rel_path,
                        "category": r.category,
                        "ext": r.ext,
                        "size_bytes": str(r.size_bytes),
                        "size_human": human_bytes(r.size_bytes),
                        "modified": r.modified_iso,
                    }
                )
            for r in oldest:
                rows.append(
                    {
                        "section": "oldest",
                        "name": r.name,
                        "rel_path": r.rel_path,
                        "category": r.category,
                        "ext": r.ext,
                        "size_bytes": str(r.size_bytes),
                        "size_human": human_bytes(r.size_bytes),
                        "modified": r.modified_iso,
                    }
                )
            for d in empty_dirs:
                rows.append(
                    {
                        "section": "empty_folder",
                        "name": d.name,
                        "rel_path": safe_relpath(d, base),
                        "category": "",
                        "ext": "",
                        "size_bytes": "0",
                        "size_human": "0 B",
                        "modified": "",
                    }
                )
            try:
                with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(
                        f,
                        fieldnames=["section", "name", "rel_path", "category", "ext", "size_bytes", "size_human", "modified"],
                    )
                    w.writeheader()
                    w.writerows(rows)
                messagebox.showinfo("Exported", f"Saved CSV:\n{out_path}")
            except Exception as e:
                messagebox.showerror("Export failed", str(e))

        ttk.Button(top, text="Export CSV…", command=export).pack(side="right")

        body = ttk.Frame(win, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=0)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(2, weight=1)

        # Charts: size-by-category + trend over time
        chart_box = ttk.LabelFrame(body, text="Analytics (size-based + trend)", padding=10)
        chart_box.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        chart_box.columnconfigure(0, weight=1)
        chart_box.rowconfigure(0, weight=1)

        fig = Figure(figsize=(9.2, 2.6), dpi=100)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 1.0])
        ax_a = fig.add_subplot(gs[0, 0])
        ax_b = fig.add_subplot(gs[0, 1])

        if top_cat_sizes:
            labels = [k for k, _ in top_cat_sizes][::-1]
            values = [v for _, v in top_cat_sizes][::-1]
            ax_a.barh(labels, values)
            ax_a.set_title("Top categories by size")
            ax_a.set_xlabel("Bytes")
        else:
            ax_a.text(0.5, 0.5, "No data", ha="center", va="center")
            ax_a.set_title("Top categories by size")

        if len(trend_x) >= 2:
            # Keep labels readable by sampling a few points.
            ax_b.plot(range(len(trend_y)), trend_y, marker="o", linewidth=1.2)
            ax_b.set_title("Total size trend (saved scans)")
            ax_b.set_xlabel("Scan")
            ax_b.set_ylabel("Bytes")
            tick_idx = list(range(0, len(trend_x), max(1, len(trend_x) // 4)))
            ax_b.set_xticks(tick_idx)
            ax_b.set_xticklabels([trend_x[i].split(" ")[0] for i in tick_idx], rotation=25, ha="right", fontsize=8)
        else:
            ax_b.text(0.5, 0.5, "Save scans to see trend", ha="center", va="center")
            ax_b.set_title("Total size trend (saved scans)")

        fig.tight_layout(pad=1.0)
        chart_canvas = FigureCanvasTkAgg(fig, master=chart_box)
        chart_canvas.get_tk_widget().grid(row=0, column=0, sticky="ew")
        chart_canvas.draw_idle()

        ttk.Label(body, text="Largest files (top 25)").grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Label(body, text="Oldest files (top 25)").grid(row=1, column=1, sticky="w", pady=(0, 6))

        def make_list(parent: ttk.Frame) -> tk.Listbox:
            lb = tk.Listbox(parent, height=18)
            lb.pack(side="left", fill="both", expand=True)
            sc = ttk.Scrollbar(parent, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sc.set)
            sc.pack(side="right", fill="y")
            return lb

        left_col = ttk.Frame(body)
        right_col = ttk.Frame(body)
        left_col.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        right_col.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        left_col.pack_propagate(False)
        right_col.pack_propagate(False)

        lb_largest = make_list(left_col)
        lb_oldest = make_list(right_col)

        for r in largest:
            lb_largest.insert(tk.END, f"{human_bytes(r.size_bytes):>10} | {r.rel_path}")
        for r in oldest:
            lb_oldest.insert(tk.END, f"{r.modified_iso} | {r.rel_path}")

        bottom = ttk.LabelFrame(body, text="Empty folders", padding=10)
        bottom.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        lb_empty = tk.Listbox(bottom, height=6)
        lb_empty.grid(row=0, column=0, sticky="nsew")
        sc2 = ttk.Scrollbar(bottom, orient="vertical", command=lb_empty.yview)
        lb_empty.configure(yscrollcommand=sc2.set)
        sc2.grid(row=0, column=1, sticky="ns")
        for d in empty_dirs[:200]:
            lb_empty.insert(tk.END, safe_relpath(d, base))

    def _quarantine_base_dir(self, base: Path) -> Path:
        return base / QUARANTINE_DIRNAME

    def _quarantine_selected_file(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return
        rel = self._selected_rel_path()
        if not rel:
            return
        base = Path(self._latest_result.folder)
        src = (base / rel)
        if not src.exists() or not src.is_file():
            messagebox.showerror("Not found", f"File does not exist:\n{src}")
            return

        qbase = self._quarantine_base_dir(base)
        qbase.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        qdest_dir = qbase / f"manual_{stamp}"
        qdest_dir.mkdir(parents=True, exist_ok=True)
        qdest = qdest_dir / src.name
        qdest = self._organizer._dedupe_destination(qdest)

        ok = messagebox.askyesno(
            "Confirm quarantine",
            f"This will MOVE the file into:\n{qdest_dir}\n\nFile:\n{src}\n\nProceed?",
        )
        if not ok:
            return

        try:
            shutil.move(str(src), str(qdest))
            items = [(safe_relpath(src, base), safe_relpath(qdest, base))]
            try:
                self._db.save_quarantine_op(base_folder=str(base), items=items, note="manual")
            except Exception:
                pass
            self.status_var.set("Moved to quarantine.")
            messagebox.showinfo("Done", f"Moved to quarantine:\n{qdest}")
        except Exception as e:
            messagebox.showerror("Quarantine failed", str(e))

    def _open_undo_history(self) -> None:
        base = Path(self.folder_var.get()).expanduser()
        if not base.exists() or not base.is_dir():
            messagebox.showerror("Invalid folder", "Please select a valid folder.")
            return

        win = tk.Toplevel(self)
        win.title("Undo history (Organize operations)")
        win.geometry("850x520")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"Folder: {base}", justify="left").pack(side="left")

        body = ttk.Frame(win, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        ops = self._db.list_organize_ops(base_folder=str(base), limit=200)

        columns = ("op_id", "applied_at", "moves")
        tree = ttk.Treeview(body, columns=columns, show="headings")
        tree.heading("op_id", text="Op ID")
        tree.heading("applied_at", text="Applied at")
        tree.heading("moves", text="Moved files")
        tree.column("op_id", width=90, anchor="e")
        tree.column("applied_at", width=220, anchor="w")
        tree.column("moves", width=120, anchor="e")

        yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        for op_id, applied_at, move_count in ops:
            tree.insert("", "end", values=(op_id, applied_at, move_count))

        def undo_selected() -> None:
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            try:
                op_id = int(vals[0])
            except Exception:
                return
            op = self._db.get_organize_op(op_id)
            if not op:
                messagebox.showerror("Not found", "Operation not found in DB.")
                return
            _, op_base, applied_at, rel_moves = op
            if os.path.normcase(op_base) != os.path.normcase(str(base)):
                messagebox.showerror("Mismatch", "This operation belongs to a different folder.")
                return

            preview = "\n".join([f"- {Path(dest).name} → {Path(src).parent}\n" for (src, dest) in rel_moves[:10]])
            if len(rel_moves) > 10:
                preview += f"\n… and {len(rel_moves) - 10} more"

            ok = messagebox.askyesno(
                "Confirm undo",
                f"Undo organize op #{op_id} from:\n{applied_at}\n\nPreview:\n{preview}\n\nProceed?",
            )
            if not ok:
                return

            restored = 0
            skipped = 0
            for src_rel, dest_rel in reversed(rel_moves):
                src = base / dest_rel
                dest = base / src_rel
                try:
                    if not src.exists():
                        skipped += 1
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    final_dest = self._organizer._dedupe_destination(dest)
                    shutil.move(str(src), str(final_dest))
                    restored += 1
                except Exception:
                    skipped += 1

            try:
                self._db.delete_organize_op(op_id)
            except Exception:
                pass

            tree.delete(sel[0])
            messagebox.showinfo("Undo complete", f"Restored: {restored}\nSkipped: {skipped}\n\nTip: Scan again to refresh.")

        ttk.Button(top, text="Undo selected…", command=undo_selected).pack(side="right")

    def _open_quarantine_manager(self) -> None:
        base = Path(self.folder_var.get()).expanduser()
        if not base.exists() or not base.is_dir():
            messagebox.showerror("Invalid folder", "Please select a valid folder.")
            return

        win = tk.Toplevel(self)
        win.title("Quarantine manager")
        win.geometry("980x560")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"Folder: {base}", justify="left").pack(side="left")

        body = ttk.Frame(win, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        columns = ("qop_id", "created_at", "items", "note")
        tree = ttk.Treeview(body, columns=columns, show="headings")
        tree.heading("qop_id", text="QOp ID")
        tree.heading("created_at", text="Created at")
        tree.heading("items", text="Items")
        tree.heading("note", text="Note")
        tree.column("qop_id", width=90, anchor="e")
        tree.column("created_at", width=220, anchor="w")
        tree.column("items", width=80, anchor="e")
        tree.column("note", width=320, anchor="w")

        yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        ops = self._db.list_quarantine_ops(base_folder=str(base), limit=200)
        for qop_id, created_at, note, item_count in ops:
            tree.insert("", "end", values=(qop_id, created_at, item_count, note))

        def restore_selected() -> None:
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            try:
                qop_id = int(vals[0])
            except Exception:
                return
            op = self._db.get_quarantine_op(qop_id)
            if not op:
                messagebox.showerror("Not found", "Quarantine operation not found.")
                return
            _, op_base, created_at, note, items = op
            if os.path.normcase(op_base) != os.path.normcase(str(base)):
                messagebox.showerror("Mismatch", "This operation belongs to a different folder.")
                return

            preview = "\n".join([f"- {Path(qrel).name} → {Path(src).parent}\n" for (src, qrel) in items[:10]])
            if len(items) > 10:
                preview += f"\n… and {len(items) - 10} more"

            ok = messagebox.askyesno(
                "Confirm restore",
                f"Restore quarantine op #{qop_id} ({created_at})\nNote: {note}\n\nPreview:\n{preview}\n\nProceed?",
            )
            if not ok:
                return

            restored = 0
            skipped = 0
            for src_rel, q_rel in items:
                src_path = base / q_rel
                dest_path = base / src_rel
                try:
                    if not src_path.exists():
                        skipped += 1
                        continue
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    final_dest = self._organizer._dedupe_destination(dest_path)
                    shutil.move(str(src_path), str(final_dest))
                    restored += 1
                except Exception:
                    skipped += 1

            try:
                self._db.delete_quarantine_op(qop_id)
            except Exception:
                pass

            tree.delete(sel[0])
            messagebox.showinfo("Restore complete", f"Restored: {restored}\nSkipped: {skipped}\n\nTip: Scan again to refresh.")

        ttk.Button(top, text="Restore selected…", command=restore_selected).pack(side="right")

    def _render_empty_charts(self) -> None:
        self.ax1.clear()
        self.ax2.clear()
        self.ax1.set_title("Files by category")
        self.ax2.set_title("Top extensions")
        self.ax1.text(0.5, 0.5, "No data yet", ha="center", va="center")
        self.ax2.text(0.5, 0.5, "No data yet", ha="center", va="center")
        self.canvas.draw_idle()

    def _render_charts(self, result: ScanResult) -> None:
        self.ax1.clear()
        self.ax2.clear()

        cats = ScanAnalyzer.group_counts(result, key="category")
        exts = ScanAnalyzer.group_counts(result, key="ext")[:10]

        if cats:
            labels = [c[0] for c in cats[:8]]
            values = [c[1] for c in cats[:8]]
            wedges, _, _ = self.ax1.pie(
                values,
                labels=None,
                autopct="%1.0f%%",
                startangle=140,
                pctdistance=0.72,
                textprops={"fontsize": 8},
            )
            self.ax1.legend(
                wedges,
                labels,
                title="Category",
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                fontsize=8,
                title_fontsize=9,
                frameon=False,
            )
            self.ax1.set_aspect("equal")
        self.ax1.set_title("Files by category")

        if exts:
            labels2 = [e[0] if e[0] else "[none]" for e in exts]
            values2 = [e[1] for e in exts]
            self.ax2.barh(labels2[::-1], values2[::-1])
        self.ax2.set_title("Top 10 extensions")

        self.figure.tight_layout(pad=1.2)
        self.canvas.draw_idle()

    def _export_csv(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return

        default_name = f"workbuddy_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=default_name,
        )
        if not out_path:
            return

        df = self._result_to_dataframe(self._latest_result)
        try:
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            self.status_var.set(f"Exported CSV: {out_path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _save_to_db(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return
        try:
            scan_id = self._db.save_scan(self._latest_result)
            self._latest_scan_id = scan_id
            self._refresh_history()
            self.status_var.set(f"Saved scan #{scan_id} to SQLite ({DB_FILENAME}).")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def _refresh_history(self) -> None:
        self.history_list.delete(0, tk.END)
        for scan_id, folder, finished_at, file_count, total_size_bytes in self._db.list_recent_scans(limit=12):
            self.history_list.insert(
                tk.END,
                f"#{scan_id} | {finished_at} | {file_count} files | {human_bytes(total_size_bytes)} | {folder}",
            )

    def _copy_summary(self) -> None:
        text = self.summary_text.get().strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Summary copied to clipboard.")

    def _apply_organize(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return

        if not self.organize_var.get():
            messagebox.showinfo("Nothing to do", "Enable 'Organize into category folders' to use this feature.")
            return

        base = Path(self._latest_result.folder)
        if base == Path.home():
            if not messagebox.askyesno(
                "Warning",
                "You are about to organize your Home folder. This is not recommended.\n\nContinue anyway?",
            ):
                return

        moves = self._organizer.propose_moves(self._latest_result, create_category_folders=True)
        if not moves:
            messagebox.showinfo("No moves", "Nothing to organize.")
            return

        preview = "\n".join([f"- {src.name} → {dest.parent.name}\n" for src, dest in moves[:10]])
        if len(moves) > 10:
            preview += f"\n… and {len(moves) - 10} more"

        ok = messagebox.askyesno(
            "Confirm organize",
            f"This will MOVE files into category folders inside:\n{base}\n\nPreview:\n{preview}\n\nProceed?",
        )
        if not ok:
            return

        executed, skipped = self._organizer.apply_moves(moves)
        moved = len(executed)
        if moved:
            rel_moves = [
                (safe_relpath(src, base), safe_relpath(dest, base))
                for (src, dest) in executed
            ]
            try:
                self._db.save_organize_op(base_folder=str(base), moves=rel_moves)
            except Exception:
                # If logging fails, don't block the core feature.
                pass
        messagebox.showinfo("Done", f"Moved: {moved}\nSkipped (errors/locked): {skipped}\n\nTip: Scan again to refresh.")
        self.status_var.set(f"Organize finished. Moved {moved}, skipped {skipped}.")

    def _apply_filter(self) -> None:
        self._current_filter = (self.filter_var.get() or "").strip()
        if self._latest_result:
            self._populate_table(self._latest_result)

    def _open_rules_organize(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return

        base = Path(self._latest_result.folder)
        if base == Path.home():
            if not messagebox.askyesno(
                "Warning",
                "You are about to organize your Home folder. This is not recommended.\n\nContinue anyway?",
            ):
                return

        win = tk.Toplevel(self)
        win.title("Rules-based organize (dry-run preview)")
        win.geometry("980x560")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"Folder: {base}", justify="left").pack(side="left")

        rule_var = tk.StringVar(value="category")
        ttk.Label(top, text="Rule:").pack(side="left", padx=(20, 6))
        rule_combo = ttk.Combobox(
            top,
            textvariable=rule_var,
            state="readonly",
            values=["category", "date_ym", "category_ext"],
            width=18,
        )
        rule_combo.pack(side="left")

        ttk.Label(top, text="(category / YYYY-MM / category+ext)", foreground="#555").pack(side="left", padx=(8, 0))

        body = ttk.Frame(win, padding=(10, 0, 10, 10))
        body.pack(fill="both", expand=True)
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        summary_var = tk.StringVar(value="Click Preview to see planned moves.")
        ttk.Label(body, textvariable=summary_var, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 6))

        columns = ("src", "dest_folder")
        tree = ttk.Treeview(body, columns=columns, show="headings")
        tree.heading("src", text="Source (relative)")
        tree.heading("dest_folder", text="Destination folder (relative)")
        tree.column("src", width=560, anchor="w")
        tree.column("dest_folder", width=340, anchor="w")

        yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")

        btns = ttk.Frame(body)
        btns.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        btns.columnconfigure(2, weight=1)

        planned: List[Tuple[Path, Path]] = []

        def preview() -> None:
            nonlocal planned
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                planned = self._organizer.propose_moves_rule(self._latest_result, rule=rule_var.get())
            except Exception as e:
                messagebox.showerror("Preview failed", str(e))
                planned = []
                return
            if not planned:
                summary_var.set("No moves planned.")
                return

            # Only show first N for UI; still apply all.
            show_n = 200
            for src, dest in planned[:show_n]:
                tree.insert("", "end", values=(safe_relpath(src, base), safe_relpath(dest.parent, base)))
            extra = ""
            if len(planned) > show_n:
                extra = f" (showing {show_n}, total {len(planned)})"
            summary_var.set(f"Planned moves: {len(planned)}{extra}. Click Apply to execute.")

        def apply() -> None:
            if not planned:
                preview()
                if not planned:
                    return
            ok = messagebox.askyesno(
                "Confirm apply",
                f"This will MOVE {len(planned)} file(s) inside:\n{base}\n\nProceed?",
            )
            if not ok:
                return

            executed, skipped = self._organizer.apply_moves(planned)
            moved = len(executed)
            if moved:
                rel_moves = [(safe_relpath(src, base), safe_relpath(dest, base)) for (src, dest) in executed]
                try:
                    self._db.save_organize_op(base_folder=str(base), moves=rel_moves)
                except Exception:
                    pass
            messagebox.showinfo("Done", f"Moved: {moved}\nSkipped: {skipped}\n\nTip: Scan again to refresh.")
            self.status_var.set(f"Rules organize finished. Moved {moved}, skipped {skipped}.")
            win.destroy()

        ttk.Button(btns, text="Preview", command=preview).grid(row=0, column=0, sticky="w")
        ttk.Button(btns, text="Apply", command=apply).grid(row=0, column=1, sticky="w", padx=(8, 0))

    def _undo_last_organize(self) -> None:
        base = Path(self.folder_var.get()).expanduser()
        if not base.exists() or not base.is_dir():
            messagebox.showerror("Invalid folder", "Please select a valid folder.")
            return

        last = self._db.get_last_organize_op(base_folder=str(base))
        if not last:
            messagebox.showinfo("Nothing to undo", "No organize operation was found for this folder.")
            return
        op_id, applied_at, rel_moves = last

        preview = "\n".join([f"- {Path(dest).name} → {Path(src).parent}\n" for (src, dest) in rel_moves[:10]])
        if len(rel_moves) > 10:
            preview += f"\n… and {len(rel_moves) - 10} more"

        ok = messagebox.askyesno(
            "Confirm undo",
            f"Undo last organize from:\n{applied_at}\n\nThis will MOVE files back inside:\n{base}\n\nPreview:\n{preview}\n\nProceed?",
        )
        if not ok:
            return

        restored = 0
        skipped = 0
        # Undo in reverse order to reduce chances of path conflicts.
        for src_rel, dest_rel in reversed(rel_moves):
            src = base / dest_rel
            dest = base / src_rel
            try:
                if not src.exists():
                    skipped += 1
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                final_dest = self._organizer._dedupe_destination(dest)
                shutil.move(str(src), str(final_dest))
                restored += 1
            except Exception:
                skipped += 1

        try:
            self._db.delete_organize_op(op_id)
        except Exception:
            pass

        messagebox.showinfo("Undo complete", f"Restored: {restored}\nSkipped: {skipped}\n\nTip: Scan again to refresh.")
        self.status_var.set(f"Undo finished. Restored {restored}, skipped {skipped}.")

    def _start_find_duplicates(self) -> None:
        if not self._latest_result:
            messagebox.showinfo("No data", "Scan a folder first.")
            return
        if self._dupe_thread and self._dupe_thread.is_alive():
            messagebox.showinfo("Already running", "Duplicate scan is already running.")
            return

        base = Path(self._latest_result.folder)
        records = list(self._latest_result.records)
        self._set_busy(True, "Finding duplicates…")

        def run() -> None:
            try:
                dupes = self._find_duplicates(base, records)
                self.after(0, lambda: self._on_duplicates_complete(dupes))
            except Exception as e:
                self.after(0, lambda: self._on_scan_error(str(e)))

        self._dupe_thread = threading.Thread(target=run, daemon=True)
        self._dupe_thread.start()

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _find_duplicates(self, base: Path, records: List[FileRecord]) -> List[List[Tuple[Path, int, str]]]:
        # Strategy: group by size first (cheap), then hash only candidates.
        size_map: Dict[int, List[Path]] = {}
        for r in records:
            if r.size_bytes <= 0:
                continue
            p = base / r.rel_path
            size_map.setdefault(r.size_bytes, []).append(p)

        candidate_paths: List[Path] = []
        for sz, paths in size_map.items():
            if len(paths) >= 2:
                candidate_paths.extend(paths)

        # Hash candidates; keep groups by (size, hash).
        groups: Dict[Tuple[int, str], List[Path]] = {}
        for p in candidate_paths:
            try:
                if not p.exists() or not p.is_file():
                    continue
                sz = int(p.stat().st_size)
                digest = self._sha256(p)
                groups.setdefault((sz, digest), []).append(p)
            except Exception:
                continue

        dupes: List[List[Tuple[Path, int, str]]] = []
        for (sz, digest), paths in groups.items():
            if len(paths) >= 2:
                dupes.append([(p, sz, digest) for p in paths])

        dupes.sort(key=lambda g: (-len(g), -g[0][1], g[0][0].as_posix().lower()))
        return dupes

    def _on_duplicates_complete(self, dupes: List[List[Tuple[Path, int, str]]]) -> None:
        self._set_busy(False, "Ready.")
        if not dupes:
            messagebox.showinfo("No duplicates", "No duplicate files were found (size+hash match).")
            return

        win = tk.Toplevel(self)
        win.title("Duplicates (size + SHA-256)")
        win.geometry("900x520")

        top = ttk.Frame(win, padding=10)
        top.pack(fill="x")
        ttk.Label(
            top,
            text=f"Found {len(dupes)} duplicate groups. A group means files with identical size + SHA-256 hash.",
            justify="left",
        ).pack(side="left")

        actions = ttk.Frame(win, padding=(10, 0, 10, 10))
        actions.pack(fill="x")
        ttk.Label(actions, text="Select rows then:").pack(side="left")

        def export() -> None:
            default_name = f"workbuddy_duplicates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            out_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=default_name,
            )
            if not out_path:
                return
            rows: List[Dict[str, str]] = []
            for idx, group in enumerate(dupes, start=1):
                size = group[0][1]
                digest = group[0][2]
                for p, _, _ in group:
                    rows.append(
                        {
                            "group": str(idx),
                            "size_bytes": str(size),
                            "size_human": human_bytes(size),
                            "sha256": digest,
                            "rel_path": safe_relpath(p, base=Path(self._latest_result.folder) if self._latest_result else p.parent),
                            "name": p.name,
                        }
                    )
            try:
                with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=["group", "size_bytes", "size_human", "sha256", "rel_path", "name"])
                    w.writeheader()
                    w.writerows(rows)
                messagebox.showinfo("Exported", f"Saved CSV:\n{out_path}")
            except Exception as e:
                messagebox.showerror("Export failed", str(e))

        ttk.Button(top, text="Export CSV…", command=export).pack(side="right")

        frame = ttk.Frame(win, padding=(10, 0, 10, 10))
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("group", "size", "sha256", "rel_path")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        tree.heading("group", text="Group")
        tree.heading("size", text="Size")
        tree.heading("sha256", text="SHA-256 (prefix)")
        tree.heading("rel_path", text="Path")
        tree.column("group", width=70, anchor="e")
        tree.column("size", width=110, anchor="e")
        tree.column("sha256", width=160, anchor="w")
        tree.column("rel_path", width=520, anchor="w")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        base = Path(self._latest_result.folder) if self._latest_result else Path.home()
        iid_to_path: Dict[str, Path] = {}
        group_to_paths: Dict[int, List[Path]] = {}
        for idx, group in enumerate(dupes, start=1):
            for p, sz, digest in group:
                iid = tree.insert(
                    "",
                    "end",
                    values=(
                        idx,
                        human_bytes(sz),
                        digest[:16] + "…",
                        safe_relpath(p, base),
                    ),
                )
                iid_to_path[str(iid)] = p
                group_to_paths.setdefault(idx, []).append(p)

        def quarantine_paths(paths: List[Path], note: str) -> None:
            if not self._latest_result:
                return
            base_dir = Path(self._latest_result.folder)
            qbase = self._quarantine_base_dir(base_dir)
            qbase.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            qdest_dir = qbase / f"duplicates_{stamp}"
            qdest_dir.mkdir(parents=True, exist_ok=True)

            moved_items: List[Tuple[str, str]] = []
            moved = 0
            skipped = 0
            for p in paths:
                try:
                    if not p.exists() or not p.is_file():
                        skipped += 1
                        continue
                    dest = qdest_dir / p.name
                    dest = self._organizer._dedupe_destination(dest)
                    shutil.move(str(p), str(dest))
                    moved += 1
                    moved_items.append((safe_relpath(p, base_dir), safe_relpath(dest, base_dir)))
                except Exception:
                    skipped += 1

            if moved_items:
                try:
                    self._db.save_quarantine_op(base_folder=str(base_dir), items=moved_items, note=note)
                except Exception:
                    pass

            messagebox.showinfo("Quarantine complete", f"Moved: {moved}\nSkipped: {skipped}\n\nQuarantine:\n{qdest_dir}")
            self.status_var.set(f"Duplicates quarantined. Moved {moved}, skipped {skipped}.")
            try:
                win.destroy()
            except Exception:
                pass

        def move_selected() -> None:
            sel = tree.selection()
            if not sel:
                return
            paths = []
            for iid in sel:
                p = iid_to_path.get(str(iid))
                if p is not None:
                    paths.append(p)
            if not paths:
                return
            ok = messagebox.askyesno("Confirm quarantine", f"Move {len(paths)} selected file(s) to quarantine?")
            if not ok:
                return
            quarantine_paths(paths, note="duplicates_selected")

        def quarantine_all_but_one() -> None:
            # For each group: keep the first path, quarantine the rest.
            paths: List[Path] = []
            for gid, ps in group_to_paths.items():
                if len(ps) <= 1:
                    continue
                # keep one (first), quarantine remaining
                paths.extend(ps[1:])
            if not paths:
                return
            ok = messagebox.askyesno(
                "Confirm quarantine",
                f"This will move {len(paths)} duplicate file(s) to quarantine (keeping 1 per group).\n\nProceed?",
            )
            if not ok:
                return
            quarantine_paths(paths, note="duplicates_keep_one")

        ttk.Button(actions, text="Move selected to Quarantine", command=move_selected).pack(side="left", padx=(10, 8))
        ttk.Button(actions, text="Auto: keep 1 per group", command=quarantine_all_but_one).pack(side="left")

    @staticmethod
    def _result_to_dataframe(result: ScanResult) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "name": r.name,
                    "rel_path": r.rel_path,
                    "ext": r.ext,
                    "category": r.category,
                    "size_bytes": r.size_bytes,
                    "size_human": human_bytes(r.size_bytes),
                    "modified": r.modified_iso,
                }
                for r in result.records
            ]
        )
