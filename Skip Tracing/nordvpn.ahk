#NoEnv
SendMode Input
SetWorkingDir %A_ScriptDir%
SetTitleMatchMode, 2 ; Allow partial matching of window titles

; Activate the already running NordVPN window
IfWinExist, ahk_exe NordVPN.exe ; Match the NordVPN executable
{
    WinActivate ; Activate the window
    Sleep, 2000 ; Wait for 2 seconds to ensure the window is focused

    ; Use MouseClick to perform the action at specific coordinates
    CoordMode, Mouse, Client ; Ensure coordinates are relative to the active window's client area
    MouseClick, Left, 521, 166, 1 ; Click at (521, 166) with the left mouse button
}
Else
{
    MsgBox, NordVPN application not found!
}

Return
