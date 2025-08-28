
import os
import time
from dotenv import load_dotenv
from pynput import keyboard, mouse
from PIL import ImageGrab
import google.generativeai as genai

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("Warning: GEMINI_API_KEY not found in .env. Please add it and restart.")
genai.configure(api_key=api_key)

# Globals
response_text = ""
start_pos = None
end_pos = None
capturing = False

def on_press(key):
    global capturing
    controller = keyboard.Controller()
    if key == keyboard.KeyCode.from_char('c') and controller.shift_pressed and controller.ctrl_pressed:
        capturing = True
        mouse_listener.start()
        print("Drag mouse to select area...")

    elif key == keyboard.KeyCode.from_char('v') and controller.shift_pressed and controller.ctrl_pressed:
        if response_text:
            simulate_typing(response_text)
        else:
            print("No response available to paste.")

def on_click(x, y, button, pressed):
    global start_pos, end_pos, capturing
    if capturing:
        if pressed and button == mouse.Button.left:
            start_pos = (x, y)
        elif not pressed and button == mouse.Button.left:
            end_pos = (x, y)
            capturing = False
            capture_and_process()
            return False  # Stop listener

def capture_and_process():
    global response_text, start_pos, end_pos
    if not start_pos or not end_pos:
        print("Selection canceled.")
        return

    left = min(start_pos[0], end_pos[0])
    top = min(start_pos[1], end_pos[1])
    width = abs(end_pos[0] - start_pos[0])
    height = abs(end_pos[1] - end_pos[1])

    if width < 1 or height < 1:
        print("Invalid selection area.")
        return

    try:
        image = ImageGrab.grab(bbox=(left, top, left + width, top + height))
        image.save('temp_image.png')
    except Exception as e:
        print(f"Error capturing image: {e}")
        return

    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        with open('temp_image.png', 'rb') as img_file:
            response = model.generate_content(["Describe this image in detail", img_file])
        response_text = response.text
        print("Response from Gemini ready. Press Ctrl+Shift+V to paste it.")
    except Exception as e:
        print(f"Error with Gemini API: {e}")
    finally:
        if os.path.exists('temp_image.png'):
            os.remove('temp_image.png')

def simulate_typing(text):
    controller = keyboard.Controller()
    words = text.split()
    for i, word in enumerate(words):
        controller.type(word)
        if i < len(words) - 1:
            controller.type(' ')
        time.sleep(0.1)  # Short delay between words for streaming effect

# Setup listeners
mouse_listener = mouse.Listener(on_click=on_click)
with keyboard.Listener(on_press=on_press) as k_listener:
    print("App running. Press Ctrl+Shift+C to capture, Ctrl+Shift+V to paste response.")
    k_listener.join()
