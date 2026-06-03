' SIPs dashboard auto-launcher.
'
' Runs at Windows login (via a Startup-folder shortcut) and:
'   1. Checks whether port 5510 is already serving the dashboard.
'      If yes -> skips the server step (idempotent — multiple instances
'      would race on the same port and one would crash).
'   2. If no listener -> starts sidecar.py with pyw.exe so there's no
'      flashing console window. Sidecar serves D:\SIPs\dashboard\ on
'      http://127.0.0.1:5510 AND provides the Studies write endpoints.
'   3. Opens the dashboard in the default browser.
'
' To disable: delete the shortcut from
'   shell:startup  (= %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup)
'
' To run manually without restarting Windows:
'   wscript D:\SIPs\auto_start_dashboard.vbs

Option Explicit

Dim shell, exec, output, alreadyRunning

Set shell = CreateObject("WScript.Shell")

' --- Step 1: detect existing listener on port 5510 ----------------------
Set exec = shell.Exec("cmd /c netstat -ano | findstr LISTENING | findstr :5510")
output = exec.StdOut.ReadAll()
alreadyRunning = (InStr(output, ":5510") > 0)

' --- Step 2: start sidecar if not running -------------------------------
If Not alreadyRunning Then
    ' pyw.exe = windowless Python launcher, picks the default 3.x install.
    ' Working dir matters — sidecar.py resolves ROOT relative to its own
    ' file path, so cd into D:\SIPs first.
    shell.CurrentDirectory = "D:\SIPs"
    shell.Run "pyw.exe ""D:\SIPs\sidecar.py""", 0, False
    ' Give the server ~1.5s to bind before pointing the browser at it.
    WScript.Sleep 1500
End If

' --- Step 3: open the dashboard in the default browser ------------------
shell.Run "http://127.0.0.1:5510/#/sips", 1, False
