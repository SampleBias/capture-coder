
import tkinter as tk

root = tk.Tk()
root.withdraw()  # Hide main window

def show_test_overlay():
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    overlay = tk.Toplevel(root)
    overlay.attributes('-fullscreen', True)
    overlay.attributes('-alpha', 0.3)  # Semi-transparent
    overlay.attributes('-topmost', True)
    overlay.overrideredirect(True)
    
    canvas = tk.Canvas(overlay, width=screen_width, height=screen_height, bg='black', highlightthickness=0)
    canvas.pack()
    
    # Draw a test rectangle
    canvas.create_rectangle(100, 100, 400, 300, outline='red', width=2)
    
    overlay.after(3000, overlay.destroy)  # Auto-close after 3 seconds

show_test_overlay()
root.mainloop()
