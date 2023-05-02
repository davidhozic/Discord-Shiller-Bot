"""
Main file of the DAF GUI.
"""
import subprocess
import multiprocessing as mp
import sys

from importlib.util import find_spec

installed = find_spec("ttkbootstrap") is not None


# Automatically install GUI requirements if GUI is requested to avoid making it an optional dependency
# One other way would be to create a completely different package on pypi for the core daf, but that is a lot of
# work to be done. It is better to auto install.
TTKBOOSTRAP_VERSION = "1.10.1"

if not installed:
    print("Auto installing requirements: ttkbootstrap")
    subprocess.check_call([sys.executable, "-m", "pip", "install", f"ttkbootstrap=={TTKBOOSTRAP_VERSION}"])

from PIL import Image, ImageTk
import tkinter as tk
import tkinter.filedialog as tkfile
import ttkbootstrap.dialogs.dialogs as tkdiag
import ttkbootstrap as ttk
import ttkbootstrap.tableview as tktw

import asyncio
import json
import sys
import os
import daf
import webbrowser

try:
    from .widgets import *
except ImportError:
    from widgets import *


WIN_UPDATE_DELAY = 0.005
CREDITS_TEXT = \
"""
Welcome to Discord Advertisement Framework - UI mode.
The UI runs on top of Discord Advertisement Framework and allows easier usage for those who
don't want to write Python code to use the software.

Authors: David Hozic - Student at UL FE.
"""

GITHUB_URL = "https://github.com/davidhozic/discord-advertisement-framework"
DOC_URL = f"https://daf.davidhozic.com/en/v{daf.VERSION}"

OPTIONAL_MODULES = [
    # Label, optional name, installed var
    ("SQL logging", "sql", daf.logging.sql.SQL_INSTALLED),
    ("Voice messages", "voice", daf.dtypes.GLOBALS.voice_installed),
    ("Web features (Chrome)", "web", daf.web.GLOBALS.selenium_installed),
]


class GLOBAL:
    app: "Application" = None
    restart: mp.Value = None


def gui_except(fnc: Callable):
    """
    Decorator that catches exceptions and displays them in GUI.
    """
    def wrapper(*args, **kwargs):
        try:
            return fnc(*args, **kwargs)
        except Exception as exc:
            tkdiag.Messagebox.show_error(f"{exc}\n(Exception in {fnc.__name__})")

    return wrapper


def gui_confirm_action(fnc: Callable):
    """
    Decorator that asks the user to confirm the action before calling the
    targeted function (fnc).
    """
    def wrapper(*args, **kwargs):
        result = tkdiag.Messagebox.show_question("Are you sure?", "Confirm")
        if result == "Yes":
            return fnc(*args, **kwargs)

    return wrapper


def gui_daf_assert_running():
    if not GLOBAL.app._daf_running:
        raise ConnectionError("Start the framework first (START button)")


class Application():
    def __init__(self) -> None:
        # Window initialization
        win_main = ttk.Window(themename="cosmo")

        # DPI
        set_dpi(win_main.winfo_fpixels('1i'))
        dpi_5 = dpi_scaled(5)
        path = os.path.join(os.path.dirname(__file__), "img/logo.png")
        photo = ImageTk.PhotoImage(file=path)
        win_main.iconphoto(0, photo)

        self.win_main = win_main
        screen_res = int(win_main.winfo_screenwidth() / 1.25), int(win_main.winfo_screenheight() / 1.375)
        win_main.wm_title(f"Discord Advert Framework {daf.VERSION}")
        win_main.wm_minsize(*screen_res)
        win_main.protocol("WM_DELETE_WINDOW", self.close_window)

        # Toolbar
        self.frame_toolbar = ttk.Frame(self.win_main)
        self.frame_toolbar.pack(fill=tk.X, side="top", padx=dpi_5, pady=dpi_5)
        self.bnt_toolbar_start_daf = ttk.Button(self.frame_toolbar, text="Start", command=self.start_daf)
        self.bnt_toolbar_start_daf.pack(side="left")
        self.bnt_toolbar_stop_daf = ttk.Button(self.frame_toolbar, text="Stop", state="disabled", command=self.stop_daf)
        self.bnt_toolbar_stop_daf.pack(side="left")

        # Main Frame
        self.frame_main = ttk.Frame(self.win_main)
        self.frame_main.pack(expand=True, fill=tk.BOTH, side="bottom")
        tabman_mf = ttk.Notebook(self.frame_main)
        tabman_mf.pack(fill=tk.BOTH, expand=True)
        self.tabman_mf = tabman_mf

        # Optional dependencies tab
        self.init_optional_dep_tab()

        # Objects tab
        self.init_schema_tab()

        # Live inspect tab
        self.init_live_inspect_tab()

        # Output tab
        self.init_output_tab()

        # Analytics
        self.init_analytics_tab()

        # Credits tab
        self.init_credits_tab()

        # Status variables
        self._daf_running = False
        self._window_opened = True

        # On close configuration
        self.win_main.protocol("WM_DELETE_WINDOW", self.close_window)

    def init_schema_tab(self):
        self.objects_edit_window = None
        dpi_10 = dpi_scaled(10)
        dpi_5 = dpi_scaled(5)

        tab_schema = ttk.Frame(self.tabman_mf, padding=(dpi_10, dpi_10))
        self.tabman_mf.add(tab_schema, text="Schema definition")

        # Object tab file menu
        bnt_file_menu = ttk.Menubutton(tab_schema, text="Schema")
        menubar_file = ttk.Menu(bnt_file_menu)
        menubar_file.add_command(label="Save schema", command=self.save_schema)
        menubar_file.add_command(label="Load schema", command=self.load_schema)
        menubar_file.add_command(label="Generate script", command=self.generate_daf_script)
        bnt_file_menu.configure(menu=menubar_file)
        bnt_file_menu.pack(anchor=tk.W)

        # Object tab account tab
        frame_tab_account = ttk.Labelframe(
            tab_schema,
            text="Accounts", padding=(dpi_10, dpi_10), bootstyle="primary")
        frame_tab_account.pack(side="left", fill=tk.BOTH, expand=True, pady=dpi_10, padx=dpi_5)

        @gui_except
        @gui_confirm_action
        def import_accounts():
            "Imports account from live view"
            accs = daf.get_accounts()
            for acc in accs:
                acc.intents = None  # Intents cannot be loaded properly

            values = convert_to_object_info(accs, save_original=False)
            if not len(values):
                raise ValueError("Live view has no elements.")

            self.lb_accounts.clear()
            self.lb_accounts.insert(tk.END, *values)

        menu_bnt = ttk.Menubutton(
            frame_tab_account,
            text="Object options"
        )
        menu = ttk.Menu(menu_bnt)
        menu.add_command(
            label="New ACCOUNT",
            command=lambda: self.open_object_edit_window(daf.ACCOUNT, self.lb_accounts)
        )
        menu.add_command(label="Edit", command=self.edit_accounts)
        menu.add_command(label="Remove", command=self.list_del_account)
        menu_bnt.configure(menu=menu)
        menu_bnt.pack(anchor=tk.W)

        frame_account_bnts = ttk.Frame(frame_tab_account)
        frame_account_bnts.pack(fill=tk.X, pady=dpi_5)
        ttk.Button(
            frame_account_bnts, text="Import from live", command=import_accounts
        ).pack(side="left")
        ttk.Button(
            frame_account_bnts, text="Load selection to live", command=lambda: self.add_accounts_daf(True)
        ).pack(side="left")
        self.load_at_start_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame_account_bnts, text="Load all at start", onvalue=True, offvalue=False, state="normal",
            variable=self.load_at_start_var
        ).pack(side="left", padx=dpi_5)

        self.lb_accounts = ListBoxScrolled(frame_tab_account)
        self.lb_accounts.pack(fill=tk.BOTH, expand=True, side="left")

        # Object tab account tab logging tab
        frame_logging = ttk.Labelframe(tab_schema, padding=(dpi_10, dpi_10), text="Logging", bootstyle="primary")
        label_logging_mgr = ttk.Label(frame_logging, text="Selected logger:")
        label_logging_mgr.pack(anchor=tk.N)
        frame_logging.pack(side="left", fill=tk.BOTH, expand=True, pady=dpi_10, padx=dpi_5)

        frame_logger_select = ttk.Frame(frame_logging)
        frame_logger_select.pack(fill=tk.X)
        self.combo_logging_mgr = ComboBoxObjects(frame_logger_select)
        self.bnt_edit_logger = ttk.Button(frame_logger_select, text="Edit", command=self.edit_logger)
        self.combo_logging_mgr.pack(fill=tk.X, side="left", expand=True)
        self.bnt_edit_logger.pack(anchor=tk.N, side="right")

        self.label_tracing = ttk.Label(frame_logging, text="Selected trace level:")
        self.label_tracing.pack(anchor=tk.N)
        frame_tracer_select = ttk.Frame(frame_logging)
        frame_tracer_select.pack(fill=tk.X)
        self.combo_tracing = ComboBoxObjects(frame_tracer_select)
        self.combo_tracing.pack(fill=tk.X, side="left", expand=True)

        self.combo_logging_mgr["values"] = [
            ObjectInfo(daf.LoggerJSON, {"path": "History"}),
            ObjectInfo(daf.LoggerSQL, {}),
            ObjectInfo(daf.LoggerCSV, {"path": "History", "delimiter": ";"}),
        ]

        self.combo_tracing["values"] = [en for en in daf.TraceLEVELS]

    def init_live_inspect_tab(self):
        dpi_10 = dpi_scaled(10)
        dpi_5 = dpi_scaled(5)

        def remove_account():
            selection = list_live_objects.curselection()
            if len(selection):
                @gui_confirm_action
                def _():
                    values = list_live_objects.get()
                    for i in selection:
                        async_execute(
                            daf.remove_object(values[i].real_object),
                            parent_window=self.win_main
                        )

                    async_execute(dummy_task(), lambda x: self.load_live_accounts(), self.win_main)

                _()
            else:
                tkdiag.Messagebox.show_error("Select atlest one item!", "Select errror")

        @gui_except
        def add_account():
            gui_daf_assert_running()
            selection = combo_add_object_edit.combo.current()
            if selection >= 0:
                fnc: ObjectInfo = combo_add_object_edit.combo.get()
                mapping = {k: convert_to_objects(v) for k, v in fnc.data.items()}
                async_execute(fnc.class_(**mapping), parent_window=self.win_main)
            else:
                tkdiag.Messagebox.show_error("Combobox does not have valid selection.", "Combo invalid selection")

        def view_live_account():
            selection = list_live_objects.curselection()
            if len(selection) == 1:
                object_: ObjectInfo = list_live_objects.get()[selection[0]]
                self.open_object_edit_window(
                    daf.ACCOUNT,
                    list_live_objects,
                    old=object_
                )
            else:
                tkdiag.Messagebox.show_error("Select one item!", "Empty list!")

        tab_live = ttk.Frame(self.tabman_mf, padding=(dpi_10, dpi_10))
        self.tabman_mf.add(tab_live, text="Live view")
        frame_add_account = ttk.Frame(tab_live)
        frame_add_account.pack(fill=tk.X, pady=dpi_10)

        combo_add_object_edit = ComboEditFrame(
            self,
            [ObjectInfo(daf.add_object, {})],
            master=frame_add_account,
            check_parameters=False
        )
        ttk.Button(frame_add_account, text="Execute", command=add_account).pack(side="left")
        combo_add_object_edit.pack(side="left", fill=tk.X, expand=True)

        frame_account_opts = ttk.Frame(tab_live)
        frame_account_opts.pack(fill=tk.X, pady=dpi_5)
        ttk.Button(frame_account_opts, text="Refresh", command=self.load_live_accounts).pack(side="left")
        ttk.Button(frame_account_opts, text="Edit", command=view_live_account).pack(side="left")
        ttk.Button(frame_account_opts, text="Remove", command=remove_account).pack(side="left")

        list_live_objects = ListBoxScrolled(tab_live)
        list_live_objects.pack(fill=tk.BOTH, expand=True)
        self.list_live_objects = list_live_objects

    def init_output_tab(self):
        self.tab_output = ttk.Frame(self.tabman_mf)
        self.tabman_mf.add(self.tab_output, text="Output")
        text_output = ListBoxScrolled(self.tab_output)
        text_output.listbox.unbind("<Control-c>")
        text_output.listbox.unbind("<BackSpace>")
        text_output.listbox.unbind("<Delete>")
        text_output.pack(fill=tk.BOTH, expand=True)

        class STDIOOutput:
            def flush(self_):
                pass

            def write(self_, data: str):
                if data == '\n':
                    return

                for r in daf.tracing.TRACE_COLOR_MAP.values():
                    data = data.replace(r, "")

                text_output.insert(tk.END, data.replace("\033[0m", ""))
                if len(text_output.get()) > 1000:
                    text_output.delete(0, 500)

                text_output.see(tk.END)

        self._oldstdout = sys.stdout
        sys.stdout = STDIOOutput()

    def init_credits_tab(self):
        dpi_10 = dpi_scaled(10)
        dpi_30 = dpi_scaled(30)
        logo_img = Image.open(f"{os.path.dirname(__file__)}/img/logo.png")
        logo_img = logo_img.resize(
            (dpi_scaled(400), dpi_scaled(400)),
            resample=0
        )
        logo = ImageTk.PhotoImage(logo_img)
        self.tab_info = ttk.Frame(self.tabman_mf)
        self.tabman_mf.add(self.tab_info, text="About")
        info_bnts_frame = ttk.Frame(self.tab_info)
        info_bnts_frame.pack(pady=dpi_30)
        ttk.Button(info_bnts_frame, text="Github", command=lambda: webbrowser.open(GITHUB_URL)).grid(row=0, column=0)
        ttk.Button(
            info_bnts_frame,
            text="Documentation",
            command=lambda: webbrowser.open(DOC_URL)
        ).grid(row=0, column=1)
        ttk.Label(self.tab_info, text="Like the app? Give it a star :) on GitHub (^)").pack(pady=dpi_10)
        ttk.Label(self.tab_info, text=CREDITS_TEXT).pack()
        label_logo = ttk.Label(self.tab_info, image=logo)
        label_logo.image = logo
        label_logo.pack()

    def init_analytics_tab(self):
        dpi_10 = dpi_scaled(10)
        dpi_5 = dpi_scaled(5)
        tab_analytics = ttk.Notebook(self.tabman_mf, padding=(dpi_5, dpi_5))  # ttk.Frame(self.tabman_mf, padding=(dpi_10, dpi_10))
        self.tabman_mf.add(tab_analytics, text="Analytics")

        def create_analytic_frame(
                getter_history: str,
                getter_counts: str,
                log_class: type,
                counts_coldata: dict,
                tab_name: str
        ):
            """
            Creates a logging tab.

            Parameters
            -------------
            getter_history: str
                The name of the LoggerBASE method that is used to retrieve actual logs.
            getter_counts: str
                The name of the LoggerBASE method that is used to retrieve counts.
            log_class: type
                The class of the log entry class (xLOG).
            counts_coldata: dict
                Column data for TableView used for counts.
            tab_name: str
                The title to write inside the tab button.
            """
            async def analytics_load_history():
                gui_daf_assert_running()
                logger = daf.get_logger()
                if not isinstance(logger, daf.LoggerSQL):
                    raise ValueError("Analytics only allowed when using LoggerSQL")

                param_object = combo_history.combo.get()
                data = param_object.data.copy()
                for k, v in data.items():
                    if isinstance(v, ObjectInfo):
                        data[k] = convert_to_objects(v)

                items = await getattr(logger, getter_history)(
                    **data
                )
                items = convert_to_object_info(items, cache=True)
                lst_history.clear()
                lst_history.insert(tk.END, *items)

            frame_message = ttk.Frame(tab_analytics, padding=(dpi_5, dpi_5))
            tab_analytics.add(frame_message, text=tab_name)
            frame_msg_history = ttk.Labelframe(frame_message, padding=(dpi_10, dpi_10), text="Logs", bootstyle="primary")
            frame_msg_history.pack(fill=tk.BOTH, expand=True)

            combo_history = ComboEditFrame(
                self,
                [ObjectInfo(getattr(daf.logging.LoggerBASE, getter_history), {})],
                frame_msg_history,
                check_parameters=False
            )
            combo_history.pack(fill=tk.X)

            frame_msg_history_bnts = ttk.Frame(frame_msg_history)
            frame_msg_history_bnts.pack(fill=tk.X, pady=dpi_10)
            ttk.Button(
                frame_msg_history_bnts,
                text="Get logs",
                command=lambda: async_execute(analytics_load_history(), parent_window=self.win_main)
            ).pack(side="left", fill=tk.X)
            ttk.Button(
                frame_msg_history_bnts,
                command=lambda: self.show_log(lst_history, log_class),
                text="View log"
            ).pack(side="left", fill=tk.X)
            lst_history = ListBoxScrolled(frame_msg_history)
            lst_history.pack(expand=True, fill=tk.BOTH)

            # Number of messages
            async def analytics_load_num():
                gui_daf_assert_running()
                logger = daf.get_logger()
                if not isinstance(logger, daf.LoggerSQL):
                    raise ValueError("Analytics only allowed when using LoggerSQL")

                param_object = combo_count.combo.get()
                data = param_object.data.copy()
                for k, v in data.items():
                    if isinstance(v, ObjectInfo):
                        data[k] = convert_to_objects(v)

                count = await getattr(logger, getter_counts)(
                    **data
                )

                tw_num.delete_rows()
                tw_num.insert_rows(0, count)
                tw_num.goto_first_page()

            frame_num = ttk.Labelframe(frame_message, padding=(dpi_10, dpi_10), text="Counts", bootstyle="primary")
            combo_count = ComboEditFrame(
                self,
                [ObjectInfo(getattr(daf.logging.LoggerBASE, getter_counts), {})],
                frame_num,
                check_parameters=False
            )
            combo_count.pack(fill=tk.X)
            tw_num = tktw.Tableview(
                frame_num,
                bootstyle="primary",
                coldata=counts_coldata,
                searchable=True,
                paginated=True,
                autofit=True)

            ttk.Button(
                frame_num,
                text="Calculate",
                command=lambda: async_execute(analytics_load_num(), parent_window=self.win_main)
            ).pack(anchor=tk.W, pady=dpi_10)

            frame_num.pack(fill=tk.BOTH, expand=True, pady=dpi_5)
            tw_num.pack(expand=True, fill=tk.BOTH)

        # Message tab
        create_analytic_frame(
            "analytic_get_message_log",
            "analytic_get_num_messages",
            # SQL is an optional feature so fake the object if not present
            getattr(daf.logging.sql, "MessageLOG", object),
            [
                {"text": "Date", "stretch": True},
                {"text": "Number of successful", "stretch": True},
                {"text": "Number of failed", "stretch": True},
                {"text": "Guild snowflake", "stretch": True},
                {"text": "Guild name", "stretch": True},
                {"text": "Author snowflake", "stretch": True},
                {"text": "Author name", "stretch": True},
            ],
            "Message tracking"
        )

        # Invite tab
        create_analytic_frame(
            "analytic_get_invite_log",
            "analytic_get_num_invites",
            # SQL is an optional feature so fake the object if not present
            getattr(daf.logging.sql, "InviteLOG", object),
            [
                {"text": "Date", "stretch": True},
                {"text": "Count", "stretch": True},
                {"text": "Guild snowflake", "stretch": True},
                {"text": "Guild name", "stretch": True},
                {"text": "Invite ID", "stretch": True},
            ],
            "Invite tracking"
        )

    def init_optional_dep_tab(self):
        dpi_10 = dpi_scaled(10)
        dpi_5 = dpi_scaled(5)
        frame_optionals = ttk.Frame(self.tabman_mf, padding=(dpi_10, dpi_10))
        self.tabman_mf.add(frame_optionals, text="Optional modules")
        ttk.Label(
            frame_optionals,
            text=
            "This section allows you to install optional packages available inside DAF\n"
            "Be aware that loading may be slower when installing these."
        ).pack(anchor=tk.NW)
        frame_optionals_packages = ttk.Frame(frame_optionals)
        frame_optionals_packages.pack(fill=tk.BOTH, expand=True)

        def install_deps(optional: str, gauge: ttk.Floodgauge, bnt: ttk.Button):
            @gui_except
            def _installer():
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install",
                    f"discord-advert-framework[{optional}]=={daf.VERSION}"
                ])
                tkdiag.Messagebox.show_info("The GUI will now reload. Save your changes!")
                GLOBAL.restart.value = True
                self.close_window()

            return _installer

        for row, (title, optional_name, installed_flag) in enumerate(OPTIONAL_MODULES):
            ttk.Label(frame_optionals_packages, text=title).grid(row=row, column=0)
            gauge = ttk.Floodgauge(
                frame_optionals_packages, bootstyle=ttk.SUCCESS if installed_flag else ttk.DANGER, value=0
            )
            gauge.grid(pady=dpi_5, row=row, column=1)
            if not installed_flag:
                gauge.start()
                bnt_install = ttk.Button(frame_optionals_packages, text="Install")
                bnt_install.configure(command=install_deps(optional_name, gauge, bnt_install))
                bnt_install.grid(row=row, column=1)

    @property
    def opened(self) -> bool:
        return self._window_opened

    def open_object_edit_window(self, *args, **kwargs):
        if self.objects_edit_window is None or self.objects_edit_window.closed:
            self.objects_edit_window = ObjectEditWindow()
            self.objects_edit_window.open_object_edit_frame(*args, **kwargs)

    def load_live_accounts(self):
        object_infos = convert_to_object_info(daf.get_accounts(), save_original=True)
        self.list_live_objects.clear()
        self.list_live_objects.insert(tk.END, *object_infos)

    def show_log(self, listbox: ListBoxScrolled, type_):
        selection = listbox.curselection()
        if len(selection) == 1:
            object_: ObjectInfo = listbox.get()[selection[0]]
            self.open_object_edit_window(
                type_,
                listbox,
                old=object_,
                check_parameters=False,
                allow_save=False
            )
        else:
            tkdiag.Messagebox.show_error("Select ONE item!", "Empty list!")

    def edit_logger(self):
        selection = self.combo_logging_mgr.current()
        if selection >= 0:
            object_: ObjectInfo = self.combo_logging_mgr.get()
            self.open_object_edit_window(object_.class_, self.combo_logging_mgr, old=object_)
        else:
            tkdiag.Messagebox.show_error("Select atleast one item!", "Empty list!")

    def edit_accounts(self):
        selection = self.lb_accounts.curselection()
        if len(selection):
            object_: ObjectInfo = self.lb_accounts.get()[selection[0]]
            self.open_object_edit_window(daf.ACCOUNT, self.lb_accounts, old=object_)
        else:
            tkdiag.Messagebox.show_error("Select atleast one item!", "Empty list!")

    def list_del_account(self):
        selection = self.lb_accounts.curselection()
        if len(selection):
            @gui_confirm_action
            def _():
                self.lb_accounts.delete(*selection)
            _()
        else:
            tkdiag.Messagebox.show_error("Select atleast one item!", "Empty list!")

    def generate_daf_script(self):
        """
        Converts the schema into DAF script
        """
        filename = tkfile.asksaveasfilename(filetypes=[("DAF Python script", "*.py")], )
        if filename == "":
            return

        if not filename.endswith(".py"):
            filename += ".py"

        logger = self.combo_logging_mgr.get()
        tracing = self.combo_tracing.get()
        logger_is_present = str(logger) != ""
        tracing_is_present = str(tracing) != ""
        run_logger_str = "\n    logger=logger," if logger_is_present else ""
        run_tracing_str = f"\n    debug={tracing}" if tracing_is_present else ""

        accounts: list[ObjectInfo] = self.lb_accounts.get()

        accounts_str, imports, other_str = convert_objects_to_script(accounts)
        imports = "\n".join(set(imports))
        if other_str != "":
            other_str = "\n" + other_str

        if logger_is_present:
            logger_str, logger_imports, _ = convert_objects_to_script(logger)
            logger_imports = "\n".join(set(logger_imports))
        else:
            logger_imports = ""

        _ret = f'''
"""
Automatically generated file for Discord Advertisement Framework {daf.VERSION}.
This can be run eg. 24/7 on a server without graphical interface.

The file has the required classes and functions imported, then the logger is defined and the
accounts list is defined.

At the bottom of the file the framework is then started with the run function.
"""

# Import the necessary items
{logger_imports}
{imports}
{f"from {tracing.__module__} import {tracing.__class__.__name__}" if tracing_is_present else ""}
import daf{other_str}

# Define the logger
{f"logger = {logger_str}" if logger_is_present else ""}

# Defined accounts
accounts = {accounts_str}

# Run the framework (blocking)
daf.run(
    accounts=accounts,{run_logger_str}{run_tracing_str}
)
'''
        with open(filename, "w", encoding="utf-8") as file:
            file.write(_ret)

        tkdiag.Messagebox.show_info(f"Saved to {filename}", "Finished", self.win_main)

    @gui_except
    def save_schema(self) -> bool:
        filename = tkfile.asksaveasfilename(filetypes=[("JSON", "*.json")])
        if filename == "":
            return False

        json_data = {
            "loggers": {
                "all": convert_to_json(self.combo_logging_mgr["values"]),
                "selected_index": self.combo_logging_mgr.current(),
            },
            "tracing": self.combo_tracing.current(),
            "accounts": convert_to_json(self.lb_accounts.get()),
        }

        if not filename.endswith(".json"):
            filename += ".json"

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(json_data, file, indent=2)

        tkdiag.Messagebox.show_info(f"Saved to {filename}", "Finished", self.win_main)

        return True

    @gui_except
    def load_schema(self):
        filename = tkfile.askopenfilename(filetypes=[("JSON", "*.json")])
        if filename == "":
            return

        with open(filename, "r", encoding="utf-8") as file:
            json_data = json.load(file)

            # Load accounts
            accounts = convert_from_json(json_data["accounts"])
            self.lb_accounts.clear()
            self.lb_accounts.listbox.insert(tk.END, *accounts)

            # Load loggers
            loggers = [convert_from_json(x) for x in json_data["loggers"]["all"]]
            self.combo_logging_mgr["values"] = loggers
            selected_index = json_data["loggers"]["selected_index"]
            if selected_index >= 0:
                self.combo_logging_mgr.current(selected_index)

            # Tracing
            tracing_index = json_data["tracing"]
            if tracing_index >= 0:
                self.combo_tracing.current(json_data["tracing"])

    @gui_except
    def start_daf(self):
        logger = self.combo_logging_mgr.get()
        if isinstance(logger, str) and logger == "":
            logger = None
        elif logger is not None:
            logger = convert_to_objects(logger)

        tracing = self.combo_tracing.get()
        if isinstance(tracing, str) and tracing == "":
            tracing = None

        async_execute(daf.initialize(logger=logger, debug=tracing), parent_window=self.win_main)
        self._daf_running = True
        if self.load_at_start_var.get():
            self.add_accounts_daf()

        self.bnt_toolbar_start_daf.configure(state="disabled")
        self.bnt_toolbar_stop_daf.configure(state="enabled")

    def stop_daf(self):
        async_execute(daf.shutdown(), parent_window=self.win_main)
        self._daf_running = False
        self.bnt_toolbar_start_daf.configure(state="enabled")
        self.bnt_toolbar_stop_daf.configure(state="disabled")

    @gui_except
    def add_accounts_daf(self, selection: bool = False):
        gui_daf_assert_running()
        accounts = self.lb_accounts.get()
        if selection:
            indexes = self.lb_accounts.curselection()
            if not len(indexes):
                raise ValueError("Select at least one item.")

            indexes = set(indexes)
            accounts = [a for i, a in enumerate(accounts) if i in indexes]

        for account in accounts:
            async_execute(daf.add_object(convert_to_objects(account)), parent_window=self.win_main)

    def close_window(self):
        resp = tkdiag.Messagebox.yesnocancel("Do you wish to save?", "Save?", alert=True, parent=self.win_main)
        if resp is None or resp == "Cancel" or resp == "Yes" and not self.save_schema():
            return

        self._window_opened = False
        if self._daf_running:
            self.stop_daf()

        async def _tmp():
            sys.stdout = self._oldstdout

        async_execute(_tmp())

    async def _process(self):
        self.win_main.update()


def run(restart: mp.Value):
    GLOBAL.restart = restart
    app = Application()
    GLOBAL.app = app

    async def update_task():
        while app.opened:
            await app._process()
            await asyncio.sleep(WIN_UPDATE_DELAY)

    loop = asyncio.new_event_loop()
    async_start(loop)
    loop.run_until_complete(update_task())
    loop.run_until_complete(async_stop())


if __name__ == "__main__":
    mp.freeze_support()
    restart = mp.Value('b', True)
    while restart.value:
        restart.value = False
        main_p = mp.Process(target=run, args=(restart,))
        main_p.start()
        main_p.join()
