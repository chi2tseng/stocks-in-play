' SIPs dashboard auto-launcher.
'
' Runs at Windows login (via a Startup-folder shortcut) and:
'   1. Checks whether port 5510 is already serving the dashboard.
'      If yes -> skips the server step (idempotent - multiple instances
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
'
' 2026-09-02: port check now runs netstat HIDDEN (shell.Run window style 0
' + temp file) instead of shell.Exec, which flashed a cmd window at login.

Option Explicit

Dim shell, fso, tmp, f, output, alreadyRunning

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Step 1: detect existing listener on port 5510 (no visible window) ---
tmp = fso.GetSpecialFolder(2) & "\sips_port_check.txt"
shell.Run "cmd /c netstat -ano | findstr LISTENING | findstr :5510 > """ & tmp & """", 0, True
output = ""
If fso.FileExists(tmp) Then
    Set f = fso.OpenTextFile(tmp, 1)
    If Not f.AtEndOfStream Then output = f.ReadAll()
    f.Close
    fso.DeleteFile tmp
End If
alreadyRunning = (InStr(output, ":5510") > 0)

' --- Step 2: start sidecar if not running -------------------------------
If Not alreadyRunning Then
    ' pyw.exe = windowless Python launcher, picks the default 3.x install.
    ' Working dir matters - sidecar.py resolves ROOT relative to its own
    ' file path, so cd into D:\SIPs first.
    shell.CurrentDirectory = "D:\SIPs"
    shell.Run "pyw.exe ""D:\SIPs\sidecar.py""", 0, False
    ' Give the server ~1.5s to bind before pointing the browser at it.
    WScript.Sleep 1500
End If

' --- Step 3: open the dashboard in the default browser ------------------
shell.Run "http://127.0.0.1:5510/#/sips", 1, False