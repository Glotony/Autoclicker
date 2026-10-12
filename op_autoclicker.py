import ctypes
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk, messagebox


# ============================================================
# Windows API
# ============================================================

user32 = ctypes.WinDLL("user32", use_last_error=True)
winmm = ctypes.WinDLL("winmm")

# Virtual keys
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77

# Mouse flags
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


user32.SendInput.argtypes = [
    ctypes.c_uint,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
]
user32.SendInput.restype = ctypes.c_uint

user32.GetAsyncKeyState.argtypes = [
    ctypes.c_int
]
user32.GetAsyncKeyState.restype = ctypes.c_short

user32.GetCursorPos.argtypes = [
    ctypes.POINTER(POINT)
]
user32.GetCursorPos.restype = ctypes.c_bool

user32.SetCursorPos.argtypes = [
    ctypes.c_int,
    ctypes.c_int
]
user32.SetCursorPos.restype = ctypes.c_bool


# 1 ms Windows timer resolution while the program is running.
winmm.timeBeginPeriod(1)


# ============================================================
# Configuration
# ============================================================

@dataclass
class Settings:
    cps: float
    button: str
    fixed_position: bool
    x: int
    y: int
    burst_enabled: bool
    burst_count: int
    burst_pause: float


# ============================================================
# Application state
# ============================================================

class State:

    def __init__(self):
        self.lock = threading.Lock()

        self.running = False
        self.total_clicks = 0
        self.session_clicks = 0
        self.session_start = 0.0

    def start(self):

        with self.lock:
            self.running = True
            self.session_clicks = 0
            self.session_start = time.perf_counter()

    def stop(self):

        with self.lock:
            self.running = False

    def is_running(self):

        with self.lock:
            return self.running

    def click(self):

        with self.lock:
            self.total_clicks += 1
            self.session_clicks += 1

    def stats(self):

        with self.lock:

            elapsed = (
                time.perf_counter() - self.session_start
                if self.running and self.session_start
                else 0
            )

            cps = (
                self.session_clicks / elapsed
                if elapsed > 0
                else 0
            )

            return (
                self.running,
                self.total_clicks,
                self.session_clicks,
                cps,
            )


state = State()

shutdown = threading.Event()

command_lock = threading.Lock()

toggle_requested = False
stop_requested = False
capture_requested = False


# ============================================================
# Native clicking
# ============================================================

def send_click(button: str):

    if button == "left":

        down = MOUSEEVENTF_LEFTDOWN
        up = MOUSEEVENTF_LEFTUP

    elif button == "right":

        down = MOUSEEVENTF_RIGHTDOWN
        up = MOUSEEVENTF_RIGHTUP

    elif button == "middle":

        down = MOUSEEVENTF_MIDDLEDOWN
        up = MOUSEEVENTF_MIDDLEUP

    else:

        raise ValueError(
            "Invalid mouse button"
        )

    inputs = (INPUT * 2)()

    # Mouse down
    inputs[0].type = INPUT_MOUSE

    inputs[0].mi = MOUSEINPUT(
        0,
        0,
        0,
        down,
        0,
        None,
    )

    # Mouse up
    inputs[1].type = INPUT_MOUSE

    inputs[1].mi = MOUSEINPUT(
        0,
        0,
        0,
        up,
        0,
        None,
    )

    result = user32.SendInput(
        2,
        inputs,
        ctypes.sizeof(INPUT),
    )

    if result != 2:

        error = ctypes.get_last_error()

        raise ctypes.WinError(error)


# ============================================================
# High precision sleep
# ============================================================

def precise_sleep(seconds: float):

    if seconds <= 0:
        return

    target = (
        time.perf_counter()
        + seconds
    )

    while True:

        remaining = (
            target
            - time.perf_counter()
        )

        if remaining <= 0:
            return

        if remaining > 0.002:

            time.sleep(
                remaining - 0.001
            )

        else:

            while (
                time.perf_counter()
                < target
            ):
                pass

            return


# ============================================================
# Hotkey polling
# ============================================================

def hotkey_thread():

    global toggle_requested
    global stop_requested
    global capture_requested

    previous = {
        VK_F6: False,
        VK_F7: False,
        VK_F8: False,
    }

    while not shutdown.is_set():

        for key in (
            VK_F6,
            VK_F7,
            VK_F8,
        ):

            pressed = bool(
                user32.GetAsyncKeyState(key)
                & 0x8000
            )

            # Detect only:
            # released -> pressed
            if pressed and not previous[key]:

                with command_lock:

                    if key == VK_F6:

                        toggle_requested = True

                    elif key == VK_F7:

                        stop_requested = True

                    elif key == VK_F8:

                        capture_requested = True

            previous[key] = pressed

        time.sleep(0.005)


# ============================================================
# Single permanent click worker
# ============================================================

def click_worker(app):

    next_click = time.perf_counter()

    burst_counter = 0

    while not shutdown.is_set():

        # ----------------------------------------------------
        # Waiting while stopped
        # ----------------------------------------------------

        if not state.is_running():

            time.sleep(0.002)

            next_click = time.perf_counter()

            burst_counter = 0

            continue

        # ----------------------------------------------------
        # Get the latest settings
        # ----------------------------------------------------

        settings = app.settings

        if settings is None:

            time.sleep(0.002)

            continue

        # ----------------------------------------------------
        # Fixed position
        # ----------------------------------------------------

        if settings.fixed_position:

            user32.SetCursorPos(
                settings.x,
                settings.y,
            )

        # ----------------------------------------------------
        # Timing
        # ----------------------------------------------------

        now = time.perf_counter()

        if now < next_click:

            precise_sleep(
                next_click - now
            )

        if not state.is_running():

            continue

        # ----------------------------------------------------
        # Click
        # ----------------------------------------------------

        try:

            send_click(
                settings.button
            )

            state.click()

        except Exception:

            state.stop()

            break

        # ----------------------------------------------------
        # Burst mode
        # ----------------------------------------------------

        if settings.burst_enabled:

            burst_counter += 1

            if (
                burst_counter
                >= settings.burst_count
            ):

                burst_counter = 0

                precise_sleep(
                    settings.burst_pause
                )

                next_click = (
                    time.perf_counter()
                )

                continue

        # ----------------------------------------------------
        # CPS -> interval
        # ----------------------------------------------------

        interval = (
            1.0 / settings.cps
        )

        interval = max(
            interval,
            0.0005
        )

        next_click += interval

        # ----------------------------------------------------
        # Prevent a huge catch-up burst
        # ----------------------------------------------------

        current = time.perf_counter()

        if (
            next_click
            < current - interval * 4
        ):

            next_click = (
                current + interval
            )


# ============================================================
# GUI
# ============================================================

class App:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "OP Autoclicker"
        )

        self.root.geometry(
            "600x560"
        )

        self.root.resizable(
            False,
            False
        )

        self.capture_active = False

        self.settings = None

        # ----------------------------------------------------
        # Variables
        # ----------------------------------------------------

        self.cps_var = tk.StringVar(
            value="20"
        )

        self.button_var = tk.StringVar(
            value="Left"
        )

        self.position_mode = tk.StringVar(
            value="Cursor"
        )

        self.position_text = tk.StringVar(
            value="Cursor position"
        )

        self.burst_enabled = tk.BooleanVar(
            value=False
        )

        self.burst_count = tk.StringVar(
            value="10"
        )

        self.burst_pause = tk.StringVar(
            value="0.25"
        )

        self.status = tk.StringVar(
            value="STOPPED"
        )

        self.stats = tk.StringVar(
            value="Clicks: 0 | CPS: 0.00"
        )

        # ----------------------------------------------------
        # Build GUI
        # ----------------------------------------------------

        self.build_ui()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close,
        )

        # ----------------------------------------------------
        # ONE permanent click worker
        # ----------------------------------------------------

        self.click_thread = threading.Thread(
            target=click_worker,
            args=(self,),
            daemon=True,
        )

        self.click_thread.start()

        # ----------------------------------------------------
        # Hotkey worker
        # ----------------------------------------------------

        self.hotkey_thread = threading.Thread(
            target=hotkey_thread,
            daemon=True,
        )

        self.hotkey_thread.start()

        # ----------------------------------------------------
        # GUI polling
        # ----------------------------------------------------

        self.root.after(
            20,
            self.process_commands,
        )

        self.root.after(
            100,
            self.update_stats,
        )

    # ========================================================
    # GUI
    # ========================================================

    def build_ui(self):

        self.root.configure(
            bg="#111318"
        )

        style = ttk.Style()

        try:

            style.theme_use(
                "clam"
            )

        except tk.TclError:

            pass

        style.configure(
            "TFrame",
            background="#111318",
        )

        style.configure(
            "TLabel",
            background="#111318",
            foreground="#eeeeee",
            font=("Segoe UI", 10),
        )

        style.configure(
            "Title.TLabel",
            background="#111318",
            foreground="#ffffff",
            font=(
                "Segoe UI Semibold",
                24,
            ),
        )

        style.configure(
            "Muted.TLabel",
            background="#111318",
            foreground="#8d929d",
            font=("Segoe UI", 9),
        )

        style.configure(
            "TButton",
            font=(
                "Segoe UI Semibold",
                10,
            ),
            padding=(12, 9),
        )

        container = ttk.Frame(
            self.root,
            padding=25,
        )

        container.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        ttk.Label(
            container,
            text="OP Autoclicker",
            style="Title.TLabel",
        ).pack(
            anchor="w"
        )

        ttk.Label(
            container,
            text=(
                "Native Windows input • "
                "F6/F7/F8 controls"
            ),
            style="Muted.TLabel",
        ).pack(
            anchor="w",
            pady=(2, 20),
        )

        # ----------------------------------------------------
        # Settings
        # ----------------------------------------------------

        frame = ttk.Frame(
            container
        )

        frame.pack(
            fill="x"
        )

        ttk.Label(
            frame,
            text="Clicks per second",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=7,
        )

        ttk.Entry(
            frame,
            textvariable=self.cps_var,
            width=18,
        ).grid(
            row=0,
            column=1,
            sticky="e",
        )

        ttk.Label(
            frame,
            text="Mouse button",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=7,
        )

        ttk.Combobox(
            frame,
            textvariable=self.button_var,
            values=(
                "Left",
                "Right",
                "Middle",
            ),
            state="readonly",
            width=15,
        ).grid(
            row=1,
            column=1,
            sticky="e",
        )

        frame.columnconfigure(
            0,
            weight=1,
        )

        # ----------------------------------------------------
        # Position
        # ----------------------------------------------------

        ttk.Separator(
            container,
        ).pack(
            fill="x",
            pady=16,
        )

        ttk.Label(
            container,
            text="Click position",
            font=(
                "Segoe UI Semibold",
                11,
            ),
        ).pack(
            anchor="w"
        )

        pos = ttk.Frame(
            container
        )

        pos.pack(
            fill="x",
            pady=8,
        )

        ttk.Radiobutton(
            pos,
            text="Follow cursor",
            variable=self.position_mode,
            value="Cursor",
        ).pack(
            side="left"
        )

        ttk.Radiobutton(
            pos,
            text="Fixed position",
            variable=self.position_mode,
            value="Fixed",
        ).pack(
            side="left",
            padx=20,
        )

        ttk.Button(
            pos,
            text="Capture [F8]",
            command=self.capture_position,
        ).pack(
            side="right"
        )

        ttk.Label(
            container,
            textvariable=self.position_text,
            style="Muted.TLabel",
        ).pack(
            anchor="w"
        )

        # ----------------------------------------------------
        # Burst
        # ----------------------------------------------------

        ttk.Separator(
            container,
        ).pack(
            fill="x",
            pady=16,
        )

        burst = ttk.Frame(
            container
        )

        burst.pack(
            fill="x"
        )

        ttk.Checkbutton(
            burst,
            text="Burst mode",
            variable=self.burst_enabled,
        ).pack(
            side="left"
        )

        ttk.Label(
            burst,
            text="Count:",
        ).pack(
            side="left",
            padx=(20, 5),
        )

        ttk.Entry(
            burst,
            textvariable=self.burst_count,
            width=7,
        ).pack(
            side="left"
        )

        ttk.Label(
            burst,
            text="Pause:",
        ).pack(
            side="left",
            padx=(15, 5),
        )

        ttk.Entry(
            burst,
            textvariable=self.burst_pause,
            width=7,
        ).pack(
            side="left"
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        ttk.Separator(
            container,
        ).pack(
            fill="x",
            pady=16,
        )

        status_frame = ttk.Frame(
            container
        )

        status_frame.pack(
            fill="x"
        )

        ttk.Label(
            status_frame,
            text="STATUS",
            style="Muted.TLabel",
        ).pack(
            side="left"
        )

        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status,
            bg="#111318",
            fg="#e05252",
            font=(
                "Segoe UI Semibold",
                11,
            ),
        )

        self.status_label.pack(
            side="left",
            padx=12,
        )

        ttk.Label(
            status_frame,
            textvariable=self.stats,
        ).pack(
            side="right"
        )

        # ----------------------------------------------------
        # Control buttons
        # ----------------------------------------------------

        buttons = ttk.Frame(
            container
        )

        buttons.pack(
            fill="x",
            pady=18,
        )

        ttk.Button(
            buttons,
            text="START / TOGGLE [F6]",
            command=self.toggle,
        ).pack(
            side="left",
            fill="x",
            expand=True,
        )

        ttk.Button(
            buttons,
            text="STOP [F7]",
            command=self.stop,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(12, 0),
        )

        ttk.Label(
            container,
            text=(
                "F6 = Toggle    "
                "F7 = Stop    "
                "F8 = Capture position"
            ),
            style="Muted.TLabel",
        ).pack(
            anchor="w"
        )

    # ========================================================
    # Read settings
    # ========================================================

    def read_settings(self):

        try:

            cps = float(
                self.cps_var.get()
            )

            if cps <= 0:

                raise ValueError(
                    "CPS must be greater than 0."
                )

            # ------------------------------------------------
            # Position
            # ------------------------------------------------

            fixed = (
                self.position_mode.get()
                == "Fixed"
            )

            x = 0
            y = 0

            if fixed:

                text = (
                    self.position_text.get()
                )

                if not text.startswith(
                    "X:"
                ):

                    raise ValueError(
                        "Capture a fixed "
                        "position first."
                    )

                parts = (
                    text
                    .replace(":", "")
                    .split()
                )

                x = int(
                    parts[1]
                )

                y = int(
                    parts[3]
                )

            # ------------------------------------------------
            # Burst
            # ------------------------------------------------

            burst_enabled = bool(
                self.burst_enabled.get()
            )

            burst_count = int(
                self.burst_count.get()
            )

            burst_pause = float(
                self.burst_pause.get()
            )

            if burst_count <= 0:

                raise ValueError(
                    "Burst count must be "
                    "greater than 0."
                )

            if burst_pause < 0:

                raise ValueError(
                    "Burst pause cannot "
                    "be negative."
                )

            return Settings(
                cps=cps,
                button=(
                    self.button_var
                    .get()
                    .lower()
                ),
                fixed_position=fixed,
                x=x,
                y=y,
                burst_enabled=(
                    burst_enabled
                ),
                burst_count=(
                    burst_count
                ),
                burst_pause=(
                    burst_pause
                ),
            )

        except ValueError as e:

            raise ValueError(
                str(e)
            )

    # ========================================================
    # Start
    # ========================================================

    def start(self):

        if state.is_running():

            return

        try:

            self.settings = (
                self.read_settings()
            )

        except ValueError as e:

            messagebox.showerror(
                "Invalid settings",
                str(e),
                parent=self.root,
            )

            return

        state.start()

        self.status.set(
            "RUNNING"
        )

        self.status_label.config(
            fg="#3ddc84"
        )

    # ========================================================
    # Stop
    # ========================================================

    def stop(self):

        state.stop()

        self.status.set(
            "STOPPED"
        )

        self.status_label.config(
            fg="#e05252"
        )

    # ========================================================
    # Toggle
    # ========================================================

    def toggle(self):

        if state.is_running():

            self.stop()

        else:

            self.start()

    # ========================================================
    # Position capture
    # ========================================================

    def capture_position(self):

        if self.capture_active:

            return

        self.capture_active = True

        self.position_text.set(
            "Move mouse to target... "
            "3 seconds"
        )

        threading.Thread(
            target=self.capture_worker,
            daemon=True,
        ).start()

    def capture_worker(self):

        time.sleep(3)

        point = POINT()

        success = user32.GetCursorPos(
            ctypes.byref(point)
        )

        if not success:

            self.root.after(
                0,
                self.capture_failed,
            )

            return

        x = point.x
        y = point.y

        self.root.after(
            0,
            lambda: self.finish_capture(
                x,
                y,
            ),
        )

    def capture_failed(self):

        self.position_text.set(
            "Capture failed"
        )

        self.capture_active = False

    def finish_capture(self, x, y):

        self.position_mode.set(
            "Fixed"
        )

        self.position_text.set(
            f"X: {x}   Y: {y}"
        )

        self.capture_active = False

    # ========================================================
    # Hotkey command handling
    # ========================================================

    def process_commands(self):

        global toggle_requested
        global stop_requested
        global capture_requested

        with command_lock:

            toggle = toggle_requested
            stop = stop_requested
            capture = capture_requested

            toggle_requested = False
            stop_requested = False
            capture_requested = False

        if toggle:

            self.toggle()

        if stop:

            self.stop()

        if capture:

            self.capture_position()

        if not shutdown.is_set():

            self.root.after(
                20,
                self.process_commands,
            )

    # ========================================================
    # Statistics
    # ========================================================

    def update_stats(self):

        (
            running,
            total,
            session,
            cps,
        ) = state.stats()

        self.stats.set(
            f"Clicks: {total:,}   |   "
            f"Session: {session:,}   |   "
            f"CPS: {cps:.2f}"
        )

        if not shutdown.is_set():

            self.root.after(
                100,
                self.update_stats,
            )

    # ========================================================
    # Close
    # ========================================================

    def close(self):

        shutdown.set()

        state.stop()

        try:

            winmm.timeEndPeriod(1)

        except Exception:

            pass

        self.root.destroy()


# ============================================================
# Main
# ============================================================

def main():

    root = tk.Tk()

    App(root)

    root.mainloop()


if __name__ == "__main__":

    main()

