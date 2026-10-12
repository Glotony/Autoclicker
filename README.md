Autoclicker
Autoclicker is a lightweight Windows desktop application that automates repetitive mouse clicks. Use its graphical interface to choose the clicking speed, mouse button, click location, and optional burst settings.
Download
Download Autoclicker for Windows (Autoclicker.exe)
How to start
1. Download Autoclicker.exe using the link above.
2. Open your browser's Downloads folder and double-click Autoclicker.exe.
3. The application will open. Choose your settings and start clicking.
You do not need to install Python, open Command Prompt or PowerShell, or type any commands. Download the .exe file and run it like a normal Windows program.
Windows may display a security warning because the application is not signed. Only run it if you downloaded it from this repository and you trust the file.
Features
- Adjustable click speed — set the target rate in clicks per second (CPS). The default is 20 CPS.
- Left, right, and middle mouse buttons — choose which button to automate.
- Follow cursor — click wherever the mouse cursor currently is.
- Fixed position — capture a screen coordinate and repeatedly click that point.
- Position capture — press F8 or click Capture [F8], then move the cursor to the target during the three-second countdown.
- Burst mode — click a chosen number of times, pause for a configurable duration, and repeat.
- Keyboard shortcuts — start, stop, and capture a position without needing to click the app's controls.
- Live statistics — view the total click count, the current session's click count, and the measured CPS.
How to use
1. Set the clicking speed. Enter a positive number in Clicks per second.
2. Choose a mouse button. Select Left, Right, or Middle.
3. Choose where to click.
   - Select Follow cursor to click at the cursor's current location.
   - Select Fixed position, then press F8 or click Capture [F8]. Move the cursor to the target while the three-second countdown runs. The captured X and Y coordinates will be displayed.
4. Configure burst mode (optional). Enable Burst mode, choose a Count (the number of clicks per burst), and set Pause in seconds. For example, a count of 10 and a pause of 0.25 creates a quarter-second pause after every ten clicks.
5. Start clicking. Press F6 or click START / TOGGLE [F6].
6. Stop clicking. Press F7 or click STOP [F7].
Keyboard shortcuts
Key	Action
F6	Start clicking, or stop if clicking is already running
F7	Stop clicking
F8	Capture the cursor position after a three-second countdown


Default settings and limits
- Clicking speed: 20 clicks per second.
- Mouse button: Left.
- Click location: Follow cursor.
- Burst mode: disabled by default.
- Burst defaults: 10 clicks and a 0.25-second pause.
- CPS must be greater than 0.
- Burst count must be a positive whole number, and burst pause must be 0 or greater.
- Fixed-position mode requires a position to be captured before clicking can start.
Click counters are kept while the application is open. The session count resets when a new clicking session starts; statistics are not saved between launches.
Important notes
- This application is for Windows and uses Windows-specific mouse input APIs.
- In fixed-position mode, the application moves the actual mouse cursor to the captured coordinates while clicking.
- Check the selected target and settings before starting. Press F7 to stop clicking promptly.
- Do not use automated clicking in applications or games where it is prohibited; follow the rules of the software you use.
- If Windows prevents input to an application running with elevated privileges, Autoclicker may need to be run with the appropriate permissions too.
Project files
- dist/Op_Autoclicker.exe — ready-to-run Windows application for users.
- op_autoclicker.py — Python source code for anyone interested in inspecting or modifying the implementation.
Regular users only need the .exe file linked in the Download section. No source-code setup is required.
License
No license file is currently included in this repository. Until a license is added, permissions to use, modify, and redistribute the source code are not explicitly granted by an open-source license.
