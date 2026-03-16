"""Watch for Windows file dialog and paste a file path into it."""
import sys
import time
import win32gui
import win32con
import win32api

def watch_and_fill(path, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.4)
        hwnd = None
        def find_dialog(h, results):
            cls = win32gui.GetClassName(h)
            title = win32gui.GetWindowText(h)
            if cls == '#32770' and not title:  # file dialog has no title
                results.append(h)
            return True
        results = []
        win32gui.EnumWindows(find_dialog, results)
        if results:
            hwnd = results[0]
            edits = []
            def enum_children(child, data):
                if win32gui.GetClassName(child) == 'Edit':
                    data.append(child)
                return True
            win32gui.EnumChildWindows(hwnd, enum_children, edits)
            if edits:
                edit = edits[-1]
                import ctypes
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
                win32api.SendMessage(edit, win32con.WM_SETTEXT, 0, path)
                time.sleep(0.3)
                btns = []
                def find_open(child, data):
                    if win32gui.GetWindowText(child) in ('&Open', 'Open'):
                        data.append(child)
                    return True
                win32gui.EnumChildWindows(hwnd, find_open, btns)
                if btns:
                    win32api.PostMessage(btns[0], win32con.BM_CLICK, 0, 0)
                    print(f"SUCCESS: submitted {path}", flush=True)
                    return True
                else:
                    # Try pressing Enter as fallback
                    import win32com.client
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.SendKeys("{ENTER}")
                    print(f"SUCCESS (Enter): submitted {path}", flush=True)
                    return True
    print("TIMEOUT", flush=True)
    return False

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\resume.pdf"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    watch_and_fill(path, timeout)
