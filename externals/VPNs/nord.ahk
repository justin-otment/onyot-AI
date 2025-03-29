#SingleInstance force

; Wait for a second to make sure the active window is ready
Sleep, 1000

; Send CTRL+N to the active window
Send, ^n  ; ^ stands for CTRL

Sleep, 500  ; Small pause (optional)

; You can add more actions if needed after this
