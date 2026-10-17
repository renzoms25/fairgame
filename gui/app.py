#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

"""Desktop window for FairGame.  The bot itself runs as a background process (gui/runner.py)"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from tkinter import messagebox

import customtkinter as ctk

from cli.setup_wizard import build_config, normalize_website, parse_asins
from common.paths import AMAZON_CONFIG_PATH, AMAZON_CREDENTIAL_FILE
from gui.logic import (
    AMAZON_SITES,
    build_bot_args,
    format_log_line,
    items_from_config,
    load_options,
    parse_price_input,
    save_options,
    status_for_line,
)
from gui.runner import BotProcess
from utils.encryption import read_encrypted_config, write_encrypted_config
from utils.version import version

PROFILE_DIR = ".profile-amz"
MAX_LOG_LINES = 5000
GREEN = ("#2f9e44", "#2f9e44")
GREEN_HOVER = ("#2b8a3e", "#2b8a3e")
RED = ("#e03131", "#e03131")
RED_HOVER = ("#c92a2a", "#c92a2a")
MUTED = ("gray40", "gray65")

OPTION_SECTIONS = [
    (
        "Buying",
        [
            (
                "single_shot",
                "Stop after buying one item",
                "Otherwise it buys one of each item on the Items tab.",
            ),
            ("used", "Allow used items", "Otherwise only new items are bought."),
            (
                "checkshipping",
                "Allow paid shipping",
                "Shipping then counts toward your highest price.",
            ),
        ],
    ),
    (
        "Display and sounds",
        [
            (
                "sounds",
                "Play sounds",
                "Alert sounds when it signs in, finds stock or buys.",
            ),
            (
                "headless",
                "Hide the Chrome window",
                "Chrome runs invisibly. You can't step in if Amazon asks for something.",
            ),
            ("no_image", "Don't load images", "Slightly faster page loads."),
            (
                "discord",
                "Show FairGame status on Discord",
                "Only if the Discord app is open.",
            ),
        ],
    ),
    (
        "Troubleshooting",
        [
            ("log_stock_check", "Show every stock check on the Activity tab", ""),
            ("detailed", "Take extra screenshots", "Can slow checkout down."),
            (
                "slow_mode",
                "Slow mode",
                "Waits for pages to fully load. Try this if checks fail on a slow connection.",
            ),
            (
                "captcha_wait",
                "Wait for me to solve captchas",
                "Gives you 60 seconds when it can't solve one itself.",
            ),
            (
                "shipping_bypass",
                "Choose a shipping address automatically (risky)",
                'Clicks the first "ship to this address" button. Check where it shipped!',
            ),
        ],
    ),
]


def open_folder(path):
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class ItemCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_remove,
        asins=(),
        reserve_min=None,
        reserve_max=None,
        website=AMAZON_SITES[0],
    ):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.title = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"))
        self.title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        ctk.CTkButton(
            self,
            text="Remove",
            width=70,
            height=24,
            fg_color="transparent",
            border_width=1,
            text_color=MUTED,
            command=lambda: on_remove(self),
        ).grid(row=0, column=1, sticky="e", padx=12, pady=(10, 0))

        ctk.CTkLabel(
            self,
            text="Amazon product link (one per line; with several, it buys whichever is in stock first)",
            text_color=MUTED,
            anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 0))
        self.links = ctk.CTkTextbox(self, height=58, wrap="none")
        self.links.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12)
        if asins:
            self.links.insert(
                "1.0", "\n".join(f"https://{website}/dp/{asin}" for asin in asins)
            )

        prices = ctk.CTkFrame(self, fg_color="transparent")
        prices.grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 12))
        ctk.CTkLabel(prices, text="Lowest price").pack(side="left")
        self.reserve_min = ctk.CTkEntry(prices, width=90, placeholder_text="e.g. 10")
        self.reserve_min.pack(side="left", padx=(6, 18))
        ctk.CTkLabel(prices, text="Highest price").pack(side="left")
        self.reserve_max = ctk.CTkEntry(prices, width=90, placeholder_text="e.g. 50")
        self.reserve_max.pack(side="left", padx=(6, 0))
        if reserve_min is not None:
            self.reserve_min.insert(0, f"{reserve_min:g}")
        if reserve_max is not None:
            self.reserve_max.insert(0, f"{reserve_max:g}")

    def set_number(self, number):
        self.number = number
        self.title.configure(text=f"Item {number}")

    def read(self):
        """Returns (asins, reserve_min, reserve_max) or raises ValueError with a friendly message"""
        name = f"Item {self.number}"
        asins, unrecognized = parse_asins(self.links.get("1.0", "end"))
        if unrecognized:
            raise ValueError(
                f"{name}: this doesn't look like an Amazon product link:\n{unrecognized[0]}"
            )
        if not asins:
            raise ValueError(f"{name}: paste the Amazon link of the product you want.")
        try:
            reserve_min = parse_price_input(self.reserve_min.get())
            reserve_max = parse_price_input(self.reserve_max.get())
        except ValueError:
            raise ValueError(
                f"{name}: enter a lowest and highest price, like 10 and 50."
            )
        if reserve_min > reserve_max:
            raise ValueError(
                f"{name}: the lowest price must be less than the highest price."
            )
        return asins, reserve_min, reserve_max


class FairGameApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FairGame")
        self.geometry("800x680")
        self.minsize(700, 580)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.events = queue.Queue()
        self.bot = BotProcess(
            on_line=lambda line: self.events.put(("line", line)),
            on_exit=lambda code, stopped: self.events.put(("exit", (code, stopped))),
        )
        self.options = load_options()
        self.option_vars = {}
        self.cards = []
        self.busy = False
        self.final_status = None

        self.build_header()
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=16)
        for name in ["Items", "Account", "Options", "Activity"]:
            self.tabs.add(name)
        self.build_items_tab(self.tabs.tab("Items"))
        self.account_tab = self.tabs.tab("Account")
        self.build_account_tab()
        self.build_options_tab(self.tabs.tab("Options"))
        self.build_activity_tab(self.tabs.tab("Activity"))
        self.build_footer()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll_events)

    # ---------------------------------------------------------------- layout

    def build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            header, text="FairGame", font=ctk.CTkFont(size=26, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(header, text=f"v{version}", text_color=MUTED).pack(
            side="left", padx=8, pady=(8, 0)
        )
        ctk.CTkLabel(
            header,
            text="Buys an Amazon item for you when it's in stock at your price.",
            text_color=MUTED,
        ).pack(side="right", pady=(8, 0))

    def build_items_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        site_row = ctk.CTkFrame(tab, fg_color="transparent")
        site_row.grid(row=0, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkLabel(site_row, text="Amazon site").pack(side="left")
        self.site = ctk.CTkComboBox(site_row, values=AMAZON_SITES, width=200)
        self.site.pack(side="left", padx=10)

        ctk.CTkLabel(
            tab,
            anchor="w",
            justify="left",
            text_color=MUTED,
            text="Open the product on Amazon, copy the link from your browser's address bar and paste it below.\n"
            "FairGame buys one of each item when it's in stock between your lowest and highest price (before tax).",
        ).grid(row=1, column=0, sticky="ew", pady=8)

        self.cards_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.cards_frame.grid(row=2, column=0, sticky="nsew")
        self.cards_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            tab,
            text="+  Add another item",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.add_card,
        ).grid(row=3, column=0, sticky="w", pady=8)

        website, groups = AMAZON_SITES[0], []
        if os.path.exists(AMAZON_CONFIG_PATH):
            try:
                with open(AMAZON_CONFIG_PATH, encoding="utf-8") as f:
                    website, groups = items_from_config(json.load(f))
            except (OSError, ValueError):
                pass
        self.site.set(website)
        for asins, reserve_min, reserve_max in groups:
            self.add_card(asins, reserve_min, reserve_max)
        if not self.cards:
            self.add_card()

    def add_card(self, asins=(), reserve_min=None, reserve_max=None):
        card = ItemCard(
            self.cards_frame,
            self.remove_card,
            asins,
            reserve_min,
            reserve_max,
            self.site.get(),
        )
        self.cards.append(card)
        self.layout_cards()

    def remove_card(self, card):
        if len(self.cards) == 1:
            messagebox.showinfo("FairGame", "You need at least one item.", parent=self)
            return
        self.cards.remove(card)
        card.destroy()
        self.layout_cards()

    def layout_cards(self):
        for number, card in enumerate(self.cards, start=1):
            card.set_number(number)
            card.grid(row=number, column=0, sticky="ew", pady=(0, 10))

    def build_account_tab(self):
        for child in self.account_tab.winfo_children():
            child.destroy()
        frame = ctk.CTkFrame(self.account_tab, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_columnconfigure(1, weight=1)
        self.amazon_email = self.amazon_password = self.unlock_confirm = None

        def entry_row(row, label, show=None):
            ctk.CTkLabel(frame, text=label, anchor="w").grid(
                row=row, column=0, sticky="w", pady=6, padx=(0, 12)
            )
            entry = ctk.CTkEntry(frame, show=show, width=320)
            entry.grid(row=row, column=1, sticky="w", pady=6)
            return entry

        title_font = ctk.CTkFont(size=16, weight="bold")
        if os.path.exists(AMAZON_CREDENTIAL_FILE):
            self.account_mode = "unlock"
            ctk.CTkLabel(
                frame, text="Your Amazon login is saved ✓", font=title_font
            ).grid(row=0, column=0, columnspan=2, sticky="w")
            ctk.CTkLabel(
                frame,
                anchor="w",
                justify="left",
                text_color=MUTED,
                text="It's stored encrypted on this computer. Enter your FairGame password to unlock it.",
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
            self.unlock_password = entry_row(2, "FairGame password", show="•")
            self.unlock_password.bind("<Return>", lambda _: self.on_start())
            ctk.CTkButton(
                frame,
                text="Use a different Amazon account",
                fg_color="transparent",
                border_width=1,
                text_color=("gray10", "gray90"),
                command=self.forget_login,
            ).grid(row=3, column=1, sticky="w", pady=(24, 0))
            ctk.CTkLabel(
                frame,
                text="Forgot your FairGame password? Use a different account and sign in again.",
                text_color=MUTED,
            ).grid(row=4, column=1, sticky="w", pady=4)
        else:
            self.account_mode = "create"
            ctk.CTkLabel(frame, text="Sign in to Amazon", font=title_font).grid(
                row=0, column=0, columnspan=2, sticky="w"
            )
            ctk.CTkLabel(
                frame,
                anchor="w",
                justify="left",
                text_color=MUTED,
                text="FairGame signs in to Amazon for you. Your login is stored encrypted on this computer and is\n"
                "only ever sent to Amazon. Make up a FairGame password to lock it; you'll enter it each time.",
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
            self.amazon_email = entry_row(2, "Amazon email or phone")
            self.amazon_password = entry_row(3, "Amazon password", show="•")
            self.unlock_password = entry_row(4, "New FairGame password", show="•")
            self.unlock_confirm = entry_row(5, "Repeat FairGame password", show="•")

    def build_options_tab(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)
        row = 0

        delay_row = ctk.CTkFrame(scroll, fg_color="transparent")
        delay_row.grid(row=row, column=0, sticky="w", pady=(4, 0))
        ctk.CTkLabel(delay_row, text="Seconds between stock checks").pack(side="left")
        self.delay = ctk.CTkEntry(delay_row, width=70)
        self.delay.insert(0, f"{self.options['delay']:g}")
        self.delay.pack(side="left", padx=10)
        row += 1
        ctk.CTkLabel(
            scroll,
            text="Checking too often can get your account limited by Amazon. 3 or more is safer.",
            text_color=MUTED,
        ).grid(row=row, column=0, sticky="w")
        row += 1

        for section, options in OPTION_SECTIONS:
            ctk.CTkLabel(
                scroll, text=section, font=ctk.CTkFont(size=15, weight="bold")
            ).grid(row=row, column=0, sticky="w", pady=(18, 4))
            row += 1
            for key, label, description in options:
                var = ctk.BooleanVar(value=self.options[key])
                self.option_vars[key] = var
                ctk.CTkCheckBox(scroll, text=label, variable=var).grid(
                    row=row, column=0, sticky="w", pady=(6, 0)
                )
                row += 1
                if description:
                    ctk.CTkLabel(scroll, text=description, text_color=MUTED).grid(
                        row=row, column=0, sticky="w", padx=(30, 0)
                    )
                    row += 1

        buttons = ctk.CTkFrame(scroll, fg_color="transparent")
        buttons.grid(row=row, column=0, sticky="w", pady=(20, 8))
        ctk.CTkButton(
            buttons,
            text="Open FairGame folder",
            command=lambda: open_folder(os.getcwd()),
        ).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Reset Chrome profile",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.reset_profile,
        ).pack(side="left", padx=10)

    def build_activity_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.log = ctk.CTkTextbox(
            tab, wrap="word", font=ctk.CTkFont(family="Courier", size=12)
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.tag_config("ERROR", foreground="#e5484d")
        self.log.tag_config("CRITICAL", foreground="#e5484d")
        self.log.tag_config("WARNING", foreground="#d39e00")
        self.log.configure(state="disabled")
        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="w", pady=(8, 0))
        for text, command in [
            ("Open screenshots", lambda: open_folder("screenshots")),
            ("Open log files", lambda: open_folder("logs")),
            ("Clear", self.clear_log),
        ]:
            ctk.CTkButton(
                buttons,
                text=text,
                width=120,
                fg_color="transparent",
                border_width=1,
                text_color=("gray10", "gray90"),
                command=command,
            ).pack(side="left", padx=(0, 8))

    def build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=14)
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            footer, text="Ready", anchor="w", font=ctk.CTkFont(size=14)
        )
        self.status.grid(row=0, column=0, sticky="w")
        self.test_mode = ctk.BooleanVar(value=self.options["test"])
        ctk.CTkSwitch(
            footer, text="Test mode (won't buy)", variable=self.test_mode
        ).grid(row=0, column=1, padx=16)
        self.start_button = ctk.CTkButton(
            footer,
            text="Start",
            width=150,
            height=42,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=GREEN,
            hover_color=GREEN_HOVER,
            command=self.on_start,
        )
        self.start_button.grid(row=0, column=2)

    # ---------------------------------------------------------------- actions

    def collect_options(self):
        options = {key: var.get() for key, var in self.option_vars.items()}
        options["test"] = self.test_mode.get()
        try:
            options["delay"] = max(0.0, float(self.delay.get().strip()))
        except ValueError:
            raise ValueError(
                'Options: "Seconds between stock checks" must be a number, like 3.'
            )
        return options

    def collect_account(self):
        password = self.unlock_password.get()
        if self.account_mode == "unlock":
            if not password:
                raise ValueError("Enter your FairGame password on the Account tab.")
            return {"mode": "unlock", "password": password}
        email, amazon_password = (
            self.amazon_email.get().strip(),
            self.amazon_password.get(),
        )
        if not email or not amazon_password:
            raise ValueError("Enter your Amazon email and password on the Account tab.")
        if not password:
            raise ValueError("Make up a FairGame password on the Account tab.")
        if password != self.unlock_confirm.get():
            raise ValueError(
                "The two FairGame passwords on the Account tab don't match."
            )
        return {
            "mode": "create",
            "password": password,
            "username": email,
            "amazon_password": amazon_password,
        }

    def on_start(self):
        if self.busy:
            return
        if self.bot.running:
            self.set_status("Stopping…")
            self.bot.stop()
            return

        try:
            website = normalize_website(self.site.get())
            if not website.startswith("www.amazon."):
                raise ValueError("Items: choose an Amazon site from the list.")
            groups = [card.read() for card in self.cards]
            options = self.collect_options()
            account = self.collect_account()
        except ValueError as e:
            message = str(e)
            if message.startswith("Item"):
                self.tabs.set("Items")
            elif message.startswith("Options"):
                self.tabs.set("Options")
            elif "Account tab" in message:
                self.tabs.set("Account")
            messagebox.showwarning("FairGame", message, parent=self)
            return

        if not options["test"] and not messagebox.askyesno(
            "Really buy?",
            "Test mode is off, so FairGame will really place an order when it finds your item.\n\n"
            "Make sure your default address and payment method are set on Amazon. Continue?",
            icon="warning",
            parent=self,
        ):
            return

        os.makedirs(os.path.dirname(AMAZON_CONFIG_PATH), exist_ok=True)
        with open(AMAZON_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(build_config(website, groups), f, indent=2)
        self.site.set(website)
        self.options = options
        save_options(options)

        self.busy = True
        self.final_status = None
        self.start_button.configure(state="disabled")
        self.set_status("Unlocking your login…")
        self.tabs.set("Activity")
        threading.Thread(
            target=self.unlock_and_launch,
            args=(account, build_bot_args(options)),
            daemon=True,
        ).start()

    def unlock_and_launch(self, account, args):
        """Runs off the UI thread because the key derivation takes a few seconds"""
        try:
            if account["mode"] == "create":
                write_encrypted_config(
                    {
                        "username": account["username"],
                        "password": account["amazon_password"],
                    },
                    AMAZON_CREDENTIAL_FILE,
                    account["password"],
                )
            else:
                read_encrypted_config(AMAZON_CREDENTIAL_FILE, account["password"])
        except ValueError:
            self.events.put(("error", "That FairGame password is wrong."))
            return
        except OSError as e:
            self.events.put(("error", f"Couldn't read or save your login: {e}"))
            return
        self.events.put(("launch", (account, args)))

    def launch(self, account, args):
        if account["mode"] == "create":
            self.build_account_tab()
            self.unlock_password.insert(0, account["password"])
        try:
            self.bot.start(args, account["password"])
        except OSError as e:
            self.on_error(f"Couldn't start the bot: {e}")
            return
        self.busy = False
        self.append_log(
            f"--- Started{' in TEST MODE' if '--test' in args else ''} ---", None
        )
        self.set_status("Starting…")
        self.start_button.configure(
            state="normal", text="Stop", fg_color=RED, hover_color=RED_HOVER
        )

    def on_error(self, message):
        self.busy = False
        self.set_status("Ready")
        self.start_button.configure(state="normal")
        if "password" in message:
            self.tabs.set("Account")
        messagebox.showerror("FairGame", message, parent=self)

    def on_bot_exit(self, code, stopped):
        self.start_button.configure(
            text="Start", fg_color=GREEN, hover_color=GREEN_HOVER
        )
        if stopped:
            self.append_log("--- Stopped ---", None)
            self.set_status("Stopped")
        else:
            self.append_log(f"--- Bot exited (code {code}) ---", None)
            self.set_status(
                self.final_status or "Stopped. See the Activity tab for details."
            )

    def forget_login(self):
        if self.bot.running:
            messagebox.showinfo("FairGame", "Stop FairGame first.", parent=self)
            return
        if messagebox.askyesno(
            "FairGame", "Remove the saved Amazon login from this computer?", parent=self
        ):
            os.remove(AMAZON_CREDENTIAL_FILE)
            self.build_account_tab()

    def reset_profile(self):
        if self.bot.running:
            messagebox.showinfo("FairGame", "Stop FairGame first.", parent=self)
            return
        if messagebox.askyesno(
            "FairGame",
            "Reset FairGame's Chrome profile? You'll have to sign in to Amazon again in Chrome.",
            parent=self,
        ):
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)
            messagebox.showinfo("FairGame", "Chrome profile reset.", parent=self)

    def on_close(self):
        if self.bot.running:
            if not messagebox.askyesno(
                "FairGame", "FairGame is running. Stop it and quit?", parent=self
            ):
                return
            self.bot.stop()
        self.destroy()

    # ---------------------------------------------------------------- output

    def poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "line":
                    self.handle_line(payload)
                elif kind == "exit":
                    self.on_bot_exit(*payload)
                elif kind == "launch":
                    self.launch(*payload)
                elif kind == "error":
                    self.on_error(payload)
        except queue.Empty:
            pass
        self.after(100, self.poll_events)

    def handle_line(self, line):
        if not line.strip():
            return
        text, level = format_log_line(line)
        self.append_log(text, level)
        status = status_for_line(line)
        if status:
            self.set_status(status)
            self.final_status = status

    def append_log(self, text, level):
        self.log.configure(state="normal")
        self.log.insert(
            "end",
            text + "\n",
            level if level in ("ERROR", "CRITICAL", "WARNING") else None,
        )
        excess = int(self.log.index("end-1c").split(".")[0]) - MAX_LOG_LINES
        if excess > 0:
            self.log.delete("1.0", f"{excess + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def set_status(self, text):
        self.status.configure(text=text)


def run_gui():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    FairGameApp().mainloop()
