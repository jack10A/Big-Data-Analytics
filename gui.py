"""Graphical interface for the educational MapReduce word counter.

Run with:  python gui.py
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import scrolledtext

import mapreduce


PROJECT_DIR = Path(__file__).resolve().parent

BG = "#eef2f7"
CARD = "#ffffff"
HEADER = "#102a43"
TEXT = "#102a43"
MUTED = "#627d98"
BORDER = "#d9e2ec"
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
SUCCESS = "#15803d"
DANGER = "#b91c1c"
FONT = "Segoe UI"

MAX_MAPPERS = 256
MAX_REDUCERS = 256


class MapReduceApp:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.running = False
        self.closed = False
        self.last_output_dir = PROJECT_DIR / "output"

        root.title("MapReduce Word Count - Jack Ashraf")
        root.configure(bg=BG)
        root.minsize(960, 740)
        self._center(1140, 900)

        self.tile_titles = []
        self.tile_values = []
        self.tile_subtitles = []
        self.tile_mode = None

        self.input_var = tk.StringVar(value=str(PROJECT_DIR / "input"))
        self.output_var = tk.StringVar(value=str(PROJECT_DIR / "output"))
        self.mappers_var = tk.StringVar(value=str(self._count_input_files()))
        self.reducers_var = tk.StringVar(value=str(mapreduce.DEFAULT_REDUCERS))
        self.status_var = tk.StringVar(value="Ready. Choose your folders and click Run MapReduce.")
        self.output_path_var = tk.StringVar(value="No run yet.")
        self.stat_vars = {
            "mappers": tk.StringVar(value="-"),
            "reducers": tk.StringVar(value="-"),
            "lines": tk.StringVar(value="-"),
            "unique": tk.StringVar(value="-"),
            "total": tk.StringVar(value="-"),
            "time": tk.StringVar(value="-"),
        }

        self._build_style()
        self._build_header()
        self._build_footer()
        self._build_body()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Return>", lambda event: self.start_run())
        root.after(80, self._poll_queue)

    # ------------------------------------------------------------------ setup
    def _count_input_files(self):
        input_dir = PROJECT_DIR / "input"
        try:
            count = len([p for p in input_dir.glob("*.txt") if p.is_file()])
        except OSError:
            count = 0
        return count or 1

    def _center(self, width, height):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = max(960, min(width, screen_w - 80))
        height = max(740, min(height, screen_h - 100))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _adapt_tiles(self, event):
        """Keep the stat cards readable when the window is made shorter."""
        tile_height = event.height / 2
        if tile_height >= 128:
            mode = "large"
        elif tile_height >= 108:
            mode = "medium"
        else:
            mode = "small"
        if mode == self.tile_mode:
            return
        self.tile_mode = mode

        font_size = {"large": 20, "medium": 17, "small": 14}[mode]
        for label in self.tile_values:
            label.configure(font=(FONT, font_size, "bold"))
        for label in self.tile_titles:
            label.grid_configure(pady=(11 if mode != "small" else 6, 0))
        for label in self.tile_subtitles:
            if mode == "small":
                label.grid_remove()
            else:
                label.grid()

    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "App.TEntry", padding=7, fieldbackground="#ffffff",
            bordercolor=BORDER, lightcolor="#ffffff", darkcolor="#ffffff",
        )
        style.map("App.TEntry", bordercolor=[("focus", ACCENT)])
        style.configure(
            "App.TSpinbox", padding=6, arrowsize=13, fieldbackground="#ffffff",
            bordercolor=BORDER, lightcolor="#ffffff", darkcolor="#ffffff",
            foreground=TEXT,
        )
        style.map("App.TSpinbox", bordercolor=[("focus", ACCENT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background="#dde5ef", foreground=MUTED,
            padding=[18, 9], font=(FONT, 10, "bold"), borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", CARD), ("active", "#e8eef6")],
            foreground=[("selected", ACCENT), ("active", TEXT)],
        )
        style.configure(
            "App.TProgressbar", troughcolor="#dce5f0", background=ACCENT,
            borderwidth=0, thickness=6,
        )
        style.layout(
            "App.TProgressbar",
            style.layout("Horizontal.TProgressbar"),
        )
        style.configure(
            "Words.Treeview", background=CARD, fieldbackground=CARD,
            foreground=TEXT, rowheight=28, font=(FONT, 9), borderwidth=0,
        )
        style.configure(
            "Words.Treeview.Heading", background="#f1f5f9", foreground=MUTED,
            font=(FONT, 9, "bold"), relief="flat", padding=6, borderwidth=0,
        )
        style.map(
            "Words.Treeview.Heading", background=[("active", "#e2e8f0")],
        )
        style.map(
            "Words.Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", TEXT)],
        )

    def _build_header(self):
        header = tk.Frame(self.root, bg=HEADER, height=104)
        header.pack(fill="x")
        header.pack_propagate(False)

        left = tk.Frame(header, bg=HEADER)
        left.pack(side="left", padx=26, pady=14)
        tk.Label(
            left, text="MapReduce Word Count", bg=HEADER, fg="white",
            font=(FONT, 19, "bold"),
        ).pack(anchor="w")
        tk.Label(
            left, text="Jack Ashraf  |  231006166  |  Big Data Assignment",
            bg=HEADER, fg="#bcccdc", font=(FONT, 9),
        ).pack(anchor="w", pady=(4, 0))

        badge = tk.Label(
            header, text="Plain Python  /  Threads", bg="#1c3d5c", fg="#d9e2ec",
            font=(FONT, 9, "bold"), padx=14, pady=7,
        )
        badge.pack(side="right", padx=26)

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        settings = tk.Frame(
            body, bg=CARD, highlightbackground=BORDER, highlightthickness=1,
        )
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)

        self._folder_row(settings, 0, "Input folder", self.input_var)
        self._folder_row(settings, 1, "Output folder", self.output_var)

        controls = tk.Frame(settings, bg=CARD)
        controls.grid(row=2, column=0, columnspan=3, sticky="ew", padx=18, pady=(8, 16))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        self._number_control(
            controls, 0, "Mappers", self.mappers_var, 1, MAX_MAPPERS,
            "Map threads / input splits. Capped at the total number of input lines.",
        )
        self._number_control(
            controls, 1, "Reducers", self.reducers_var, 1, MAX_REDUCERS,
            "Each reducer writes its own file; all are merged into final_output.txt.",
        )

        actions = tk.Frame(body, bg=BG)
        actions.grid(row=1, column=0, sticky="ew", pady=(14, 10))
        actions.columnconfigure(2, weight=1)

        self.run_button = self._button(
            actions, "Run MapReduce", self.start_run, primary=True,
        )
        self.run_button.grid(row=0, column=0, sticky="w")

        self.open_button = self._button(
            actions, "Open output folder", self.open_output_folder, primary=False,
        )
        self.open_button.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.progress = ttk.Progressbar(
            actions, style="App.TProgressbar", mode="determinate", value=0,
            length=220,
        )
        self.progress.grid(row=0, column=2, sticky="e", padx=(20, 0))
        self.progress.grid_remove()

        status_bar = tk.Frame(body, bg=BG)
        status_bar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.status_label = tk.Label(
            status_bar, textvariable=self.status_var, bg=BG, fg=MUTED,
            font=(FONT, 9), anchor="w", justify="left",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        self._build_summary_tab()
        self._build_log_tab()

    def _build_footer(self):
        footer = tk.Frame(self.root, bg="#e3eaf3", height=32)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text="Runs locally with Python threads. No Hadoop or Spark installation needed.",
            bg="#e3eaf3", fg=MUTED, font=(FONT, 8),
        ).pack(side="left", padx=22)
        tk.Label(
            footer, text="final_output.txt  =  merged reducer results",
            bg="#e3eaf3", fg=MUTED, font=(FONT, 8, "bold"),
        ).pack(side="right", padx=22)

    def _folder_row(self, parent, row, label_text, variable):
        tk.Label(
            parent, text=label_text, bg=CARD, fg=TEXT,
            font=(FONT, 10, "bold"),
        ).grid(row=row, column=0, sticky="w", padx=(18, 12), pady=(16 if row == 0 else 8, 0))

        entry = ttk.Entry(parent, textvariable=variable, style="App.TEntry")
        entry.grid(
            row=row, column=1, sticky="ew", pady=(16 if row == 0 else 8, 0),
        )

        browse = tk.Button(
            parent, text="Browse...", command=lambda: self.browse_folder(variable),
            bg="#f1f5f9", fg=TEXT, activebackground="#e2e8f0", activeforeground=TEXT,
            relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
            font=(FONT, 9, "bold"),
        )
        browse.grid(
            row=row, column=2, sticky="e", padx=(10, 18),
            pady=(16 if row == 0 else 8, 0),
        )

    def _number_control(self, parent, column, label_text, variable, minimum, maximum,
                        hint):
        block = tk.Frame(parent, bg=CARD)
        block.grid(
            row=0, column=column, sticky="w",
            padx=(0 if column == 0 else 34, 0),
        )

        tk.Label(
            block, text=label_text, bg=CARD, fg=TEXT, font=(FONT, 10, "bold"),
        ).grid(row=0, column=0, sticky="w")

        spinbox = ttk.Spinbox(
            block, from_=minimum, to=maximum, textvariable=variable, width=7,
            style="App.TSpinbox", font=(FONT, 10),
        )
        spinbox.grid(row=1, column=0, sticky="w", pady=(6, 0))

        tk.Label(
            block, text=hint, bg=CARD, fg=MUTED, font=(FONT, 8),
            wraplength=330, justify="left",
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    def _build_summary_tab(self):
        summary = tk.Frame(self.notebook, bg=CARD)
        summary.columnconfigure(0, weight=3, uniform="summary")
        summary.columnconfigure(1, weight=4, uniform="summary")
        summary.rowconfigure(0, weight=1)

        tiles = tk.Frame(summary, bg=CARD)
        tiles.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(16, 6))
        for column in range(3):
            tiles.columnconfigure(column, weight=1, uniform="tile")
        for row in range(2):
            tiles.rowconfigure(row, weight=1, uniform="tile")

        definitions = [
            ("mappers", "MAPPERS USED", "map threads"),
            ("reducers", "REDUCERS", "output files"),
            ("lines", "INPUT LINES", "input data"),
            ("unique", "UNIQUE WORDS", "keys aggregated"),
            ("total", "TOTAL WORDS", "sum of counts"),
            ("time", "RUNTIME", "wall-clock"),
        ]
        for index, (key, title, subtitle) in enumerate(definitions):
            row, column = divmod(index, 3)
            tile = tk.Frame(
                tiles, bg="#f8fafc", highlightbackground="#e2e8f0",
                highlightthickness=1,
            )
            tile.grid(
                row=row, column=column, sticky="nsew",
                padx=(0 if column == 0 else 5, 0 if column == 2 else 5),
                pady=(0 if row == 0 else 5, 0 if row == 1 else 5),
            )
            tile.columnconfigure(0, weight=1)
            tile.rowconfigure(1, weight=1)
            title_label = tk.Label(
                tile, text=title, bg="#f8fafc", fg=MUTED,
                font=(FONT, 7, "bold"),
            )
            title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(11, 0))
            value_label = tk.Label(
                tile, textvariable=self.stat_vars[key], bg="#f8fafc", fg=ACCENT,
                font=(FONT, 20, "bold"),
            )
            value_label.grid(row=1, column=0, sticky="w", padx=12)
            subtitle_label = tk.Label(
                tile, text=subtitle, bg="#f8fafc", fg=MUTED,
                font=(FONT, 8),
            )
            subtitle_label.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))
            self.tile_titles.append(title_label)
            self.tile_values.append(value_label)
            self.tile_subtitles.append(subtitle_label)

        tiles.bind("<Configure>", self._adapt_tiles)

        words_card = tk.Frame(
            summary, bg=CARD, highlightbackground="#e2e8f0", highlightthickness=1,
        )
        words_card.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(16, 6))
        words_card.columnconfigure(0, weight=1)
        words_card.rowconfigure(1, weight=1)

        words_header = tk.Frame(words_card, bg=CARD)
        words_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        tk.Label(
            words_header, text="Most frequent words", bg=CARD, fg=TEXT,
            font=(FONT, 10, "bold"),
        ).pack(side="left")
        tk.Label(
            words_header, text="top 20", bg=CARD, fg=MUTED,
            font=(FONT, 8),
        ).pack(side="right")

        tree_frame = tk.Frame(words_card, bg=CARD)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=("rank", "word", "count"), show="headings",
            style="Words.Treeview", selectmode="browse",
        )
        self.tree.heading("rank", text="#", anchor="center")
        self.tree.heading("word", text="WORD", anchor="w")
        self.tree.heading("count", text="COUNT", anchor="e")
        self.tree.column("rank", width=60, anchor="center", stretch=False)
        self.tree.column("word", width=300, anchor="w")
        self.tree.column("count", width=120, anchor="e", stretch=False)
        self.tree.tag_configure("odd", background="#f8fafc")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda event: self.open_output_folder())

        output_row = tk.Frame(summary, bg=CARD)
        output_row.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 14),
        )
        tk.Label(
            output_row, text="Final output:", bg=CARD, fg=MUTED,
            font=(FONT, 9, "bold"),
        ).pack(side="left")
        tk.Label(
            output_row, textvariable=self.output_path_var, bg=CARD, fg=TEXT,
            font=(FONT, 9),
        ).pack(side="left", padx=(6, 0), fill="x", expand=True)
        tk.Label(
            output_row, text="word <TAB> count", bg=CARD, fg=MUTED,
            font=("Consolas", 8),
        ).pack(side="right")

        self.notebook.add(summary, text="  Summary  ")

    def _build_log_tab(self):
        log_tab = tk.Frame(self.notebook, bg=CARD)
        log_tab.columnconfigure(0, weight=1)
        log_tab.rowconfigure(1, weight=1)

        header = tk.Frame(log_tab, bg=CARD)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        tk.Label(
            header, text="Run log", bg=CARD, fg=TEXT, font=(FONT, 10, "bold"),
        ).pack(side="left")
        clear = tk.Button(
            header, text="Clear", command=self.clear_log, bg=CARD, fg=ACCENT,
            activebackground="#eff6ff", activeforeground=ACCENT_DARK,
            relief="flat", bd=0, cursor="hand2", font=(FONT, 9, "bold"),
            padx=8, pady=2,
        )
        clear.pack(side="right")

        self.log = scrolledtext.ScrolledText(
            log_tab, bg="#0b1220", fg="#c9d6e5", insertbackground="#c9d6e5",
            selectbackground="#1e3a8a", relief="flat", bd=0,
            font=("Consolas", 9), padx=14, pady=12, wrap="word",
        )
        self.log.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.log.tag_configure("info", foreground="#c9d6e5")
        self.log.tag_configure("success", foreground="#86efac")
        self.log.tag_configure("error", foreground="#fca5a5")
        self.log.tag_configure("muted", foreground="#64748b")
        self.log.configure(state="disabled")
        self.append_log("Ready. Waiting for a MapReduce run.", "muted")

        self.notebook.add(log_tab, text="  Run log  ")

    def _button(self, parent, text, command, primary):
        if primary:
            button = tk.Button(
                parent, text=text, command=command, bg=ACCENT, fg="white",
                activebackground=ACCENT_DARK, activeforeground="white",
                disabledforeground="#dbeafe", relief="flat", bd=0,
                padx=20, pady=10, cursor="hand2", font=(FONT, 10, "bold"),
            )
            button.bind("<Enter>", lambda event: self._hover(button, ACCENT_DARK))
            button.bind("<Leave>", lambda event: self._hover(button, ACCENT))
        else:
            button = tk.Button(
                parent, text=text, command=command, bg=CARD, fg=TEXT,
                activebackground="#f1f5f9", activeforeground=TEXT,
                disabledforeground="#94a3b8", relief="flat", bd=0,
                padx=18, pady=10, cursor="hand2", font=(FONT, 10, "bold"),
                highlightbackground=BORDER, highlightcolor=ACCENT,
                highlightthickness=1,
            )
            button.bind("<Enter>", lambda event: self._hover(button, "#f1f5f9"))
            button.bind("<Leave>", lambda event: self._hover(button, CARD))
        return button

    def _hover(self, button, colour):
        if str(button["state"]) == "normal":
            button.configure(bg=colour)

    # ------------------------------------------------------------------- runs
    def browse_folder(self, variable):
        current = variable.get().strip()
        initial = current if Path(current).is_dir() else str(PROJECT_DIR)
        selected = filedialog.askdirectory(
            parent=self.root, title="Choose a folder", initialdir=initial,
        )
        if selected:
            variable.set(os.path.normpath(selected))

    def _read_positive_int(self, variable, name, maximum):
        raw = variable.get().strip()
        try:
            value = int(raw)
        except ValueError:
            raise ValueError(f"{name} must be a whole number.") from None
        if value < 1:
            raise ValueError(f"{name} must be at least 1.")
        if value > maximum:
            raise ValueError(f"{name} must be {maximum} or less.")
        return value

    def start_run(self):
        if self.running:
            return

        input_dir = Path(self.input_var.get().strip())
        output_dir = Path(self.output_var.get().strip())
        try:
            if not self.input_var.get().strip():
                raise ValueError("Please choose an input folder.")
            if not self.output_var.get().strip():
                raise ValueError("Please choose an output folder.")
            num_mappers = self._read_positive_int(
                self.mappers_var, "Mappers", MAX_MAPPERS,
            )
            num_reducers = self._read_positive_int(
                self.reducers_var, "Reducers", MAX_REDUCERS,
            )
            if not input_dir.is_dir():
                raise ValueError(f"Input folder does not exist:\n{input_dir}")
            if input_dir.resolve() == output_dir.resolve():
                raise ValueError("Input and output folders must be different.")
        except (ValueError, OSError) as error:
            messagebox.showwarning("Check your settings", str(error), parent=self.root)
            return

        self.running = True
        self.last_output_dir = output_dir
        self._set_running(True)
        self._reset_summary()
        self.status_var.set("Running MapReduce...")
        self.status_label.configure(fg=ACCENT)
        self.append_log("", "info")
        self.append_log(
            f"Starting: {num_mappers} mapper(s), {num_reducers} reducer(s)", "info",
        )
        self.append_log(f"Input : {input_dir}", "muted")
        self.append_log(f"Output: {output_dir}", "muted")
        self.notebook.select(1)

        worker = threading.Thread(
            target=self._run_worker,
            args=(input_dir, output_dir, num_mappers, num_reducers),
            daemon=True,
            name="mapreduce-gui",
        )
        worker.start()

    def _run_worker(self, input_dir, output_dir, num_mappers, num_reducers):
        def progress(message):
            self.queue.put(("log", message))

        try:
            stats = mapreduce.run(
                input_dir,
                output_dir,
                num_mappers=num_mappers,
                num_reducers=num_reducers,
                progress=progress,
            )
        except Exception as error:
            self.queue.put(("error", str(error)))
        else:
            self.queue.put(("done", stats))

    def _poll_queue(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self.append_log(payload, "info")
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "error":
                    self._on_error(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _on_done(self, stats):
        self.running = False
        self._set_running(False)
        self.stat_vars["mappers"].set(f"{stats['mappers']:,}")
        self.stat_vars["reducers"].set(f"{stats['reducers']:,}")
        self.stat_vars["lines"].set(f"{stats['lines']:,}")
        self.stat_vars["unique"].set(f"{stats['unique_words']:,}")
        self.stat_vars["total"].set(f"{stats['total_words']:,}")
        self.stat_vars["time"].set(f"{stats['seconds']:.2f}s")
        self.output_path_var.set(stats["final_output"])
        self.load_top_words(Path(stats["final_output"]))

        self.status_var.set(
            f"Finished in {stats['seconds']:.2f}s - {stats['unique_words']:,} unique words "
            f"merged into {Path(stats['final_output']).name}."
        )
        self.status_label.configure(fg=SUCCESS)
        self.append_log(
            f"Done: {stats['unique_words']:,} unique words, "
            f"{stats['total_words']:,} words total.", "success",
        )
        self.append_log(f"Final output: {stats['final_output']}", "success")
        self.notebook.select(0)

    def _on_error(self, message):
        self.running = False
        self._set_running(False)
        self.status_var.set("Run failed. See the run log for details.")
        self.status_label.configure(fg=DANGER)
        self.append_log(f"ERROR: {message}", "error")
        self.notebook.select(1)
        messagebox.showerror("MapReduce failed", message, parent=self.root)

    def _set_running(self, running):
        state = "disabled" if running else "normal"
        self.run_button.configure(
            state=state, bg=ACCENT if not running else "#93b4f7",
            cursor="hand2" if not running else "arrow",
        )
        self.open_button.configure(
            state=state, cursor="hand2" if not running else "arrow",
        )
        if running:
            self.progress.grid()
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.progress.grid_remove()

    def _reset_summary(self):
        for variable in self.stat_vars.values():
            variable.set("-")
        self.output_path_var.set("Running...")
        for item in self.tree.get_children():
            self.tree.delete(item)

    def load_top_words(self, final_file, limit=20):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not final_file.is_file():
            return
        pairs = []
        try:
            with final_file.open(encoding="utf-8") as source:
                for line in source:
                    word, _, count = line.rstrip("\n").partition("\t")
                    if word and count.isdigit():
                        pairs.append((word, int(count)))
        except OSError:
            return
        pairs.sort(key=lambda pair: (-pair[1], pair[0]))
        for rank, (word, count) in enumerate(pairs[:limit], start=1):
            tags = ("odd",) if rank % 2 == 0 else ()
            self.tree.insert(
                "", "end", values=(rank, word, f"{count:,}"), tags=tags,
            )

    def open_output_folder(self):
        folder = self.last_output_dir
        if not folder.is_dir():
            messagebox.showinfo(
                "Output folder",
                f"The output folder does not exist yet:\n{folder}\n\nRun the job first.",
                parent=self.root,
            )
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as error:
            messagebox.showerror(
                "Could not open folder", str(error), parent=self.root,
            )

    def append_log(self, message, tag="info"):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _on_close(self):
        if self.running and not messagebox.askyesno(
            "Quit", "A MapReduce run is still in progress. Quit anyway?",
            parent=self.root,
        ):
            return
        self.closed = True
        self.root.destroy()


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    MapReduceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
