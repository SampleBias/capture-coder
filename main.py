import os
import sys
import time
import threading
import subprocess
from queue import Queue
from dataclasses import dataclass
from typing import Optional, Tuple, List
from contextlib import contextmanager
import logging
import random
import re

from dotenv import load_dotenv
from pynput import keyboard, mouse
from PIL import ImageGrab, Image
import google.generativeai as genai
import tkinter as tk
from tkinter import Canvas
import io
import Quartz

# Suppress gRPC fork warnings
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'

# Suppress absl logging warnings
logging.getLogger('absl').setLevel(logging.ERROR)

# Load environment variables
load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

genai.configure(api_key=API_KEY)

# Expert coder prompts for iterative refinement
INITIAL_ANALYSIS_PROMPT = """You are an expert competitive programmer and software engineer. Analyze this coding problem carefully.

First, identify:
1. Problem type (array manipulation, dynamic programming, graph, etc.)
2. Key constraints and edge cases
3. Expected time/space complexity
4. Optimal approach/algorithm

Then provide a solution following these rules:
- Output ONLY Python code
- Use the most efficient algorithm
- Handle ALL edge cases
- Include brief # comments for complex logic
- NO markdown formatting, NO explanations outside code
- Start with necessary imports
- Use clear, concise variable names"""

REFINEMENT_PROMPT = """Review this solution for the given problem. Check for:
1. Correctness - does it solve all cases?
2. Efficiency - is this optimal O(n) complexity?
3. Edge cases - empty inputs, single elements, maximums?
4. Code quality - can it be more concise/Pythonic?
5. Bug fixes - any logical errors?

Output ONLY the improved Python code. NO explanations outside # comments."""

FINAL_OPTIMIZATION_PROMPT = """Final pass - make this solution production-ready:
1. Optimize any remaining inefficiencies
2. Ensure clean, Pythonic code style
3. Remove redundant operations
4. Verify all test cases would pass

Output ONLY the final optimized Python code."""

USER_FEEDBACK_PROMPT = """The user has provided feedback about the code:
{feedback}

Incorporate this feedback and fix the code accordingly.
Output ONLY the corrected Python code."""

@dataclass
class AppState:
    """Centralized state management"""
    response_text: str = ""
    problem_image: Optional[Image.Image] = None
    iteration_history: List[str] = None
    start_pos: Optional[Tuple[int, int]] = None
    end_pos: Optional[Tuple[int, int]] = None
    capturing: bool = False
    ctrl_pressed: bool = False
    shift_pressed: bool = False
    alt_pressed: bool = False
    overlay: Optional[tk.Toplevel] = None
    canvas: Optional[Canvas] = None
    rect: Optional[int] = None
    last_clipboard_hash: Optional[int] = None
    clipboard_monitoring: bool = True
    processing_queue: Queue = None
    is_typing: bool = False
    feedback_mode: bool = False
    feedback_text: str = ""
    
    def __post_init__(self):
        self.processing_queue = Queue()
        self.iteration_history = []

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
                stderr=subprocess.DEVNULL,
                check=False
            )
            return True
        except Exception:
            return False

class ExpertCoder:
    """Expert coding assistant with iterative refinement"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        
    def clean_code(self, text: str) -> str:
        """Remove markdown formatting and clean code"""
        code = text.strip()
        
        # Remove markdown code blocks
        if '```' in code:
            lines = code.split('\n')
            code_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith('```'):
                    in_block = not in_block
                    continue
                if in_block or (not line.strip().startswith('```') and not in_block):
                    if not line.strip().startswith('```'):
                        code_lines.append(line)
            code = '\n'.join(code_lines)
        
        return code.strip()
    
    def extract_feedback(self, text: str) -> Optional[str]:
        """Extract feedback from markdown comments"""
        feedback_lines = []
        for line in text.split('\n'):
            if line.strip().startswith('#'):
                # Look for feedback indicators
                if any(word in line.lower() for word in ['fix', 'change', 'update', 'improve', 'wrong', 'error', 'bug']):
                    feedback_lines.append(line.strip('#').strip())
        
        return ' '.join(feedback_lines) if feedback_lines else None
    
    def solve_with_iterations(self, image: Image.Image, max_iterations: int = 3) -> Tuple[str, List[str]]:
        """Solve problem with iterative refinement"""
        iterations = []
        
        try:
            # Convert RGBA to RGB if necessary
            if image.mode == 'RGBA':
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1])
                image = rgb_image
            
            print("# Step 1: Initial analysis and solution...")
            
            # Initial solution
            response = self.model.generate_content([INITIAL_ANALYSIS_PROMPT, image])
            solution = self.clean_code(response.text)
            iterations.append(solution)
            
            if max_iterations > 1:
                print("# Step 2: Reviewing for correctness and efficiency...")
                
                # First refinement - correctness and efficiency
                refinement_prompt = f"{REFINEMENT_PROMPT}\n\nCurrent solution:\n{solution}"
                response = self.model.generate_content([refinement_prompt, image])
                solution = self.clean_code(response.text)
                iterations.append(solution)
            
            if max_iterations > 2:
                print("# Step 3: Final optimization pass...")
                
                # Final optimization
                optimization_prompt = f"{FINAL_OPTIMIZATION_PROMPT}\n\nCurrent solution:\n{solution}"
                response = self.model.generate_content([optimization_prompt, image])
                solution = self.clean_code(response.text)
                iterations.append(solution)
            
            print(f"# Solution refined through {len(iterations)} iterations")
            return solution, iterations
            
        except Exception as e:
            print(f"# Error during solving: {e}")
            return None, []
    
    def apply_user_feedback(self, image: Image.Image, current_code: str, feedback: str) -> Optional[str]:
        """Apply user feedback to improve the solution"""
        try:
            print(f"# Applying feedback: {feedback[:50]}...")
            
            prompt = USER_FEEDBACK_PROMPT.format(feedback=feedback)
            prompt += f"\n\nCurrent code:\n{current_code}"
            
            response = self.model.generate_content([prompt, image])
            improved_code = self.clean_code(response.text)
            
            print("# Feedback incorporated")
            return improved_code
            
        except Exception as e:
            print(f"# Error applying feedback: {e}")
            return None

class UIManager:
    """Manages UI overlay for selection"""
    
    def __init__(self, state: AppState):
        self.state = state
        self.root = None
    
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
    """Monitors clipboard for images and feedback"""
    
    def __init__(self, state: AppState, coder: ExpertCoder):
        self.state = state
        self.coder = coder
        self.thread = None
    
    def start(self):
        """Start monitoring"""
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.state.clipboard_monitoring:
            try:
                # Check for images
                image = ImageGrab.grabclipboard()
                if isinstance(image, Image.Image):
                    img_hash = hash(image.tobytes())
                    if img_hash != self.state.last_clipboard_hash:
                        self.state.last_clipboard_hash = img_hash
                        self.state.processing_queue.put(('clipboard', image))
                
                # Check for text feedback (markdown comments)
                try:
                    clipboard_text = subprocess.check_output(
                        ['pbpaste'], 
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8')
                    
                    if clipboard_text and clipboard_text.startswith('#'):
                        feedback = self.coder.extract_feedback(clipboard_text)
                        if feedback and feedback != self.state.feedback_text:
                            self.state.feedback_text = feedback
                            self.state.processing_queue.put(('feedback', feedback))
                except:
                    pass
                    
            except Exception:
                pass
            time.sleep(0.5)

class NaturalTyping:
    """Handles natural typing simulation"""
    
    def __init__(self, kb_controller):
        self.kb_controller = kb_controller
        self.base_delay = 0.04
        self.word_pause = 0.12
        self.line_pause = 0.25
        self.think_pause = 0.4
    
    def type_naturally(self, text: str, speed_multiplier: float = 1.0):
        """Type text with natural human-like delays"""
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            # Thinking pause for complex lines
            if any(keyword in line for keyword in ['import', 'def ', 'class ', 'return', 'for ', 'while ']):
                time.sleep(self.think_pause * speed_multiplier)
            
            words = line.split(' ')
            for word_idx, word in enumerate(words):
                for char in word:
                    self.kb_controller.type(char)
                    delay = (self.base_delay + random.uniform(-0.015, 0.02)) * speed_multiplier
                    time.sleep(max(0.01, delay))
                
                if word_idx < len(words) - 1:
                    self.kb_controller.type(' ')
                    time.sleep((self.word_pause + random.uniform(-0.03, 0.03)) * speed_multiplier)
            
            if line_idx < len(lines) - 1:
                self.kb_controller.press(keyboard.Key.enter)
                self.kb_controller.release(keyboard.Key.enter)
                time.sleep(self.line_pause * speed_multiplier)

class HotkeyHandler:
    """Handles keyboard and mouse events"""
    
    def __init__(self, state: AppState, ui: UIManager, coder: ExpertCoder):
        self.state = state
        self.ui = ui
        self.coder = coder
        self.kb_controller = keyboard.Controller()
        self.natural_typing = NaturalTyping(self.kb_controller)
    
    def on_key_press(self, key):
        """Handle key press events"""
        try:
            if key == keyboard.Key.ctrl:
                self.state.ctrl_pressed = True
            elif key == keyboard.Key.shift:
                self.state.shift_pressed = True
            elif key == keyboard.Key.alt:
                self.state.alt_pressed = True
            elif self.state.ctrl_pressed and self.state.shift_pressed:
                if hasattr(key, 'char'):
                    if key.char == 'c':
                        self._start_area_capture()
                    elif key.char == 'w':
                        self._capture_window()
                    elif key.char == 'v':
                        self._paste_response()
                    elif key.char == 'f':
                        self._paste_fast()
                    elif key.char == 'x':
                        self.state.is_typing = False
                        print("# Typing stopped")
                    elif key.char == 'r':
                        self._refine_solution()
                    elif key.char == 'h':
                        self._show_iteration_history()
        except AttributeError:
            pass
    
    def on_key_release(self, key):
        """Handle key release events"""
        if key == keyboard.Key.ctrl:
            self.state.ctrl_pressed = False
        elif key == keyboard.Key.shift:
            self.state.shift_pressed = False
        elif key == keyboard.Key.alt:
            self.state.alt_pressed = False
    
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
        
        mouse_thread = threading.Thread(
            target=lambda: mouse.Listener(
                on_click=self.on_mouse_click,
                on_move=self.on_mouse_move
            ).join(),
            daemon=True
        )
        mouse_thread.start()
        
        print("# Selecting problem area...")
    
    def _capture_window(self):
        """Capture current window"""
        image = ScreenCapture.capture_window()
        if image:
            ScreenCapture.to_clipboard(image)
            self.state.processing_queue.put(('window', image))
    
    def _paste_response(self):
        """Paste with natural typing speed"""
        if self.state.response_text and not self.state.is_typing:
            print("# Typing solution (natural speed)...")
            self._type_code(speed=1.0)
    
    def _paste_fast(self):
        """Paste with fast typing speed"""
        if self.state.response_text and not self.state.is_typing:
            print("# Typing solution (fast)...")
            self._type_code(speed=0.3)
    
    def _type_code(self, speed: float = 1.0):
        """Type code at specified speed"""
        self.state.is_typing = True
        
        def type_worker():
            try:
                self.natural_typing.type_naturally(self.state.response_text, speed)
                print("# Solution typed")
            except Exception as e:
                print(f"# Typing error: {e}")
            finally:
                self.state.is_typing = False
        
        threading.Thread(target=type_worker, daemon=True).start()
    
    def _refine_solution(self):
        """Trigger refinement of current solution"""
        if self.state.problem_image and self.state.response_text:
            print("# Refining solution...")
            self.state.processing_queue.put(('refine', None))
    
    def _show_iteration_history(self):
        """Show iteration history"""
        if self.state.iteration_history:
            print(f"# Iteration history: {len(self.state.iteration_history)} versions")
            for i, code in enumerate(self.state.iteration_history, 1):
                print(f"# Version {i}: {len(code.split(chr(10)))} lines")

class ExpertSolverApp:
    """Main application controller"""
    
    def __init__(self):
        self.state = AppState()
        self.coder = ExpertCoder()
        self.ui = UIManager(self.state)
        self.hotkeys = HotkeyHandler(self.state, self.ui, self.coder)
        self.clipboard = ClipboardMonitor(self.state, self.coder)
        self.processing_thread = None
    
    def start(self):
        """Start the application"""
        print("# EXPERT CODE SOLVER v2.0")
        print("#" * 40)
        print("# CAPTURE:")
        print("#   Ctrl+Shift+C: Select problem area")
        print("#   Ctrl+Shift+W: Capture window")
        print("# OUTPUT:")
        print("#   Ctrl+Shift+V: Type solution (natural)")
        print("#   Ctrl+Shift+F: Type solution (fast)")
        print("#   Ctrl+Shift+X: Stop typing")
        print("# REFINEMENT:")
        print("#   Ctrl+Shift+R: Refine solution")
        print("#   Ctrl+Shift+H: Show history")
        print("# FEEDBACK:")
        print("#   Copy '# fix: ...' to clipboard")
        print("#" * 40)
        
        self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
        
        self.clipboard.start()
        
        with keyboard.Listener(
            on_press=self.hotkeys.on_key_press,
            on_release=self.hotkeys.on_key_release
        ) as listener:
            listener.join()
    
    def _process_queue(self):
        """Process queued requests"""
        while True:
            try:
                action_type, data = self.state.processing_queue.get()
                
                if action_type == 'area':
                    self.ui.destroy_overlay()
                    if self.state.start_pos and self.state.end_pos:
                        image = ScreenCapture.capture_area(
                            self.state.start_pos,
                            self.state.end_pos
                        )
                        if image:
                            self._process_problem(image)
                
                elif action_type in ['window', 'clipboard']:
                    if action_type == 'clipboard':
                        image = data
                    else:
                        image = data
                    if image:
                        self._process_problem(image)
                
                elif action_type == 'refine':
                    if self.state.problem_image and self.state.response_text:
                        improved = self.coder.apply_user_feedback(
                            self.state.problem_image,
                            self.state.response_text,
                            "Optimize further and ensure all edge cases are handled"
                        )
                        if improved:
                            self.state.response_text = improved
                            self.state.iteration_history.append(improved)
                            print("# Solution refined")
                
                elif action_type == 'feedback':
                    feedback = data
                    if self.state.problem_image and self.state.response_text:
                        improved = self.coder.apply_user_feedback(
                            self.state.problem_image,
                            self.state.response_text,
                            feedback
                        )
                        if improved:
                            self.state.response_text = improved
                            self.state.iteration_history.append(improved)
                            print(f"# Feedback applied")
                
            except Exception as e:
                print(f"# Processing error: {e}")
    
    def _process_problem(self, image: Image.Image):
        """Process a problem image"""
        print("# Analyzing problem with expert solver...")
        self.state.problem_image = image
        
        solution, iterations = self.coder.solve_with_iterations(image, max_iterations=3)
        
        if solution:
            self.state.response_text = solution
            self.state.iteration_history = iterations
            print(f"# Expert solution ready (refined {len(iterations)}x)")
            print("# Press Ctrl+Shift+V to type")
        else:
            print("# Failed to generate solution")

if __name__ == "__main__":
    try:
        app = ExpertSolverApp()
        app.start()
    except KeyboardInterrupt:
        print("\n# TERMINATED")
    except Exception as e:
        print(f"# Fatal: {e}")