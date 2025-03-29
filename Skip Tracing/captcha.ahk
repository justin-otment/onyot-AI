#NoEnv
SendMode Input
SetWorkingDir %A_ScriptDir%
SetTitleMatchMode, 2 ; Allow partial matching of window titles

; Activate the already running Incognito Chrome window
IfWinExist, ahk_exe chrome.exe ; Chrome window class (works for Incognito too)
{
    WinActivate ; Activate the window
    Sleep, 5000 ; Wait for 5 seconds to ensure the window is focused

    ; Use MouseClick to perform the action at specific coordinates
    CoordMode, Mouse, Client ; Ensure coordinates are relative to the active window's client area
    MouseClick, Left, 554, 330, 1 ; Click at (554, 330) with the left mouse button
}
Else
{
    MsgBox, Chrome Incognito window not found!
}

Return
