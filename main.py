import os
import time
import threading
import subprocess
from queue import Queue
from dataclasses import dataclass
from typing import Optional, Tuple
from contextlib import contextmanager

from dotenv import load_dotenv
from pynput import keyboard, mouse
from PIL import ImageGrab, Image
import google.generativeai as genai
import tkinter as tk
from tkinter import Canvas
import io
import Quartz

# Load environment variables
load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

genai.configure(api_key=API_KEY)

@dataclass
class AppState:
    """Centralized state management"""
    response_text: str = ""
    start_pos: Optional[Tuple[int, int]] = None
    end_pos: Optional[Tuple[int, int]] = None
    capturing: bool = False
    ctrl_pressed: bool = False
    shift_pressed: bool = False
    overlay: Optional[tk.Toplevel] = None
    canvas: Optional[Canvas] = None
    rect: Optional[int] = None
    last_clipboard_hash: Optional[int] = None
    clipboard_monitoring: bool = True
    processing_queue: Queue = None
    
    def __post_init__(self):
        self.processing_queue = Queue()

class ScreenCapture:
    """Handles screen capture operations"""
    
    @staticmethod
    def get_active_window_bounds() -> Optional[Tuple[int, int, int, int]]:
        """Get bounds of active window using Quartz"""
        try:
            windows = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | 
                Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID
            )
            
            if windows and len(windows) > 0:
                # Get frontmost window
                for window in windows:
                    if window.get('kCGWindowLayer', 0) == 0:
                        bounds = window.get('kCGWindowBounds', {})
                        if bounds:
                            return (
                                int(bounds.get('X', 0)),
                                int(bounds.get('Y', 0)),
                                int(bounds.get('Width', 0)),
                                int(bounds.get('Height', 0))
                            )
        except Exception:
            pass
        return None
    
    @staticmethod
    def capture_window() -> Optional[Image.Image]:
        """Capture active window"""
        bounds = ScreenCapture.get_active_window_bounds()
        if not bounds:
            return None
        
        x, y, width, height = bounds
        try:
            # Use direct bbox capture for efficiency
            return ImageGrab.grab(bbox=(x, y, x + width, y + height))
        except Exception:
            return None
    
    @staticmethod
    def capture_area(start: Tuple[int, int], end: Tuple[int, int]) -> Optional[Image.Image]:
        """Capture specific area"""
        left = min(start[0], end[0])
        top = min(start[1], end[1])
        right = max(start[0], end[0])
        bottom = max(start[1], end[1])
        
        if right - left < 1 or bottom - top < 1:
            return None
        
        try:
            return ImageGrab.grab(bbox=(left, top, right, bottom))
        except Exception:
            return None
    
    @staticmethod
    def to_clipboard(image: Image.Image) -> bool:
        """Put image on clipboard"""
        try:
            output = io.BytesIO()
            image.save(output, 'PNG')
            subprocess.run(
                ['osascript', '-e', 
                 'set the clipboard to (read (POSIX file "/dev/stdin") as PNG picture)'],
                input=output.getvalue(),
                capture_output=True,
                check=False
            )
            return True
        except Exception:
            return False

class GeminiProcessor:
    """Handles Gemini API interactions"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    def process_image(self, image: Image.Image, prompt: str = "Describe this image in detail") -> Optional[str]:
        """Process image with Gemini"""
        try:
            # Convert RGBA to RGB if necessary to avoid JPEG conversion issues
            if image.mode == 'RGBA':
                # Create a white background
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = rgb_image
            
            response = self.model.generate_content([prompt, image])
            return response.text
        except Exception as e:
            print(f"✗ Gemini API error: {e}")
            return None

class UIManager:
    """Manages UI overlay for selection"""
    
    def __init__(self, state: AppState):
        self.state = state
        self.root = None
    
    @contextmanager
    def overlay_context(self):
        """Context manager for overlay creation and cleanup"""
        try:
            self.create_overlay()
            yield
        finally:
            self.destroy_overlay()
    
    def create_overlay(self):
        """Create selection overlay"""
        self.root = tk.Tk()
        self.root.withdraw()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        self.state.overlay = tk.Toplevel(self.root)
        self.state.overlay.attributes('-fullscreen', True)
        self.state.overlay.attributes('-alpha', 0.3)
        self.state.overlay.attributes('-topmost', True)
        self.state.overlay.overrideredirect(True)
        
        self.state.canvas = Canvas(
            self.state.overlay,
            width=screen_width,
            height=screen_height,
            bg='black',
            highlightthickness=0
        )
        self.state.canvas.pack()
    
    def destroy_overlay(self):
        """Clean up overlay"""
        if self.state.overlay:
            self.state.overlay.destroy()
            self.state.overlay = None
            self.state.canvas = None
        if self.root:
            self.root.destroy()
            self.root = None
    
    def update_selection(self, x: int, y: int):
        """Update selection rectangle"""
        if not self.state.canvas or not self.state.start_pos:
            return
        
        if self.state.rect:
            self.state.canvas.delete(self.state.rect)
        
        x1, y1 = self.state.start_pos
        self.state.rect = self.state.canvas.create_rectangle(
            min(x1, x), min(y1, y),
            max(x1, x), max(y1, y),
            outline='red', width=3, fill=''
        )

class ClipboardMonitor:
    """Monitors clipboard for images"""
    
    def __init__(self, state: AppState, processor: GeminiProcessor):
        self.state = state
        self.processor = processor
        self.thread = None
    
    def start(self):
        """Start monitoring"""
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.state.clipboard_monitoring:
            try:
                image = ImageGrab.grabclipboard()
                if isinstance(image, Image.Image):
                    # Use hash for efficient comparison
                    img_hash = hash(image.tobytes())
                    if img_hash != self.state.last_clipboard_hash:
                        self.state.last_clipboard_hash = img_hash
                        self.state.processing_queue.put(('clipboard', image))
            except Exception:
                pass
            time.sleep(0.5)

class HotkeyHandler:
    """Handles keyboard and mouse events"""
    
    def __init__(self, state: AppState, ui: UIManager):
        self.state = state
        self.ui = ui
        self.kb_controller = keyboard.Controller()
    
    def on_key_press(self, key):
        """Handle key press events"""
        try:
            if key == keyboard.Key.ctrl:
                self.state.ctrl_pressed = True
            elif key == keyboard.Key.shift:
                self.state.shift_pressed = True
            elif self.state.ctrl_pressed and self.state.shift_pressed:
                if hasattr(key, 'char'):
                    if key.char == 'c':
                        self._start_area_capture()
                    elif key.char == 'w':
                        self._capture_window()
                    elif key.char == 'v':
                        self._paste_response()
        except AttributeError:
            pass
    
    def on_key_release(self, key):
        """Handle key release events"""
        if key == keyboard.Key.ctrl:
            self.state.ctrl_pressed = False
        elif key == keyboard.Key.shift:
            self.state.shift_pressed = False
    
    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse clicks during capture"""
        if not self.state.capturing:
            return
        
        if button == mouse.Button.left:
            if pressed:
                self.state.start_pos = (x, y)
                self.state.rect = None
            else:
                self.state.end_pos = (x, y)
                self.state.capturing = False
                self.state.processing_queue.put(('area', None))
                return False
    
    def on_mouse_move(self, x, y):
        """Handle mouse movement during capture"""
        if self.state.capturing and self.state.start_pos:
            self.ui.update_selection(x, y)
    
    def _start_area_capture(self):
        """Initialize area capture mode"""
        self.state.capturing = True
        self.ui.create_overlay()
        
        # Start mouse listener
        mouse_thread = threading.Thread(
            target=lambda: mouse.Listener(
                on_click=self.on_mouse_click,
                on_move=self.on_mouse_move
            ).join(),
            daemon=True
        )
        mouse_thread.start()
        
        print("=== CAPTURE MODE ===")
        print("Click and drag to select area")
    
    def _capture_window(self):
        """Capture current window"""
        image = ScreenCapture.capture_window()
        if image:
            ScreenCapture.to_clipboard(image)
            self.state.processing_queue.put(('window', image))
    
    def _paste_response(self):
        """Paste the stored response"""
        if self.state.response_text:
            print("=== PASTING ===")
            # Use chunked typing for better performance
            text = self.state.response_text
            chunk_size = 10  # Type 10 chars at a time
            for i in range(0, len(text), chunk_size):
                self.kb_controller.type(text[i:i+chunk_size])
                if i + chunk_size < len(text):
                    time.sleep(0.01)  # Minimal delay
            print("✓ Pasted")
        else:
            print("No response available")

class ScreenCaptureApp:
    """Main application controller"""
    
    def __init__(self):
        self.state = AppState()
        self.processor = GeminiProcessor()
        self.ui = UIManager(self.state)
        self.hotkeys = HotkeyHandler(self.state, self.ui)
        self.clipboard = ClipboardMonitor(self.state, self.processor)
        self.processing_thread = None
    
    def start(self):
        """Start the application"""
        print("=== SCREEN CAPTURE GEMINI ===")
        print("Ctrl+Shift+C: Capture area")
        print("Ctrl+Shift+W: Capture window")
        print("Ctrl+Shift+V: Paste response")
        print("Clipboard monitoring: ACTIVE")
        print("=" * 40)
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
        
        # Start clipboard monitor
        self.clipboard.start()
        
        # Start keyboard listener (blocking)
        with keyboard.Listener(
            on_press=self.hotkeys.on_key_press,
            on_release=self.hotkeys.on_key_release
        ) as listener:
            listener.join()
    
    def _process_queue(self):
        """Process queued capture requests"""
        while True:
            try:
                capture_type, image = self.state.processing_queue.get()
                
                if capture_type == 'area':
                    # Clean up overlay first
                    self.ui.destroy_overlay()
                    
                    # Capture the selected area
                    if self.state.start_pos and self.state.end_pos:
                        image = ScreenCapture.capture_area(
                            self.state.start_pos,
                            self.state.end_pos
                        )
                
                if image:
                    print(f"Processing {capture_type} capture...")
                    response = self.processor.process_image(image)
                    if response:
                        self.state.response_text = response
                        print("✓ Ready to paste (Ctrl+Shift+V)")
                    else:
                        print("✗ Processing failed")
                
            except Exception as e:
                print(f"Processing error: {e}")

if __name__ == "__main__":
    try:
        app = ScreenCaptureApp()
        app.start()
    except KeyboardInterrupt:
        print("\n=== APP TERMINATED ===")
    except Exception as e:
        print(f"Fatal error: {e}")
