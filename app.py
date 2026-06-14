import cv2
import numpy as np
import pygame
import os
import glob
import time
import threading
import base64
from flask import Flask, send_file, jsonify, request

# --- CONFIGURATION & PATHS ---
DATASET_PATH = r"D:\project file\New folder (3)\color_160_samples"
IMAGE_FOLDER = r"D:\project file\New folder (3)\New folder"
SQUARE_SIZE = 500      
BASE_DURATION = 0.25  
SAMPLE_RATE = 44100

app = Flask(__name__)

# --- GLOBAL STATE ---
class ScannerState:
    def __init__(self):
        self.is_playing = False
        self.is_scanning = False
        self.current_idx = 0
        self.img_files = []
        self.color_dataset = []
        self.current_frame_b64 = ""
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.scan_progress = 0
        self.scan_speed = 1.0
        self.image_resolution = "0x0"

state = ScannerState()

# --- INITIALIZATION ---
def init_pygame():
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()

def get_color_dataset():
    mapping = []
    if not os.path.exists(DATASET_PATH):
        return mapping
    folders = [f for f in os.listdir(DATASET_PATH) if os.path.isdir(os.path.join(DATASET_PATH, f))]
    for folder in folders:
        if folder.startswith("rgb_"):
            try:
                parts = folder.split("_")
                r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
                folder_path = os.path.join(DATASET_PATH, folder)
                files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(".wav")]
                if files:
                    mapping.append({"color": (r, g, b), "files": files})
            except: continue
    return mapping

def find_closest_sound(target_rgb, dataset):
    if not dataset: return None
    target = np.array(target_rgb)
    best_dist = float('inf')
    best_files = None
    for entry in dataset:
        dist = np.linalg.norm(target - np.array(entry["color"]))
        if dist < best_dist:
            best_dist = dist
            best_files = entry["files"]
    return best_files

def update_image_resolution(img_path):
    image = cv2.imread(img_path)
    if image is not None:
        h, w, _ = image.shape
        state.image_resolution = f"{w}x{h}"

# --- SCANNING CORE ---
def scan_worker():
    global state
    init_pygame()
    
    while not state.stop_event.is_set():
        with state.lock:
            if not state.is_playing or state.current_idx >= len(state.img_files) or state.current_idx < 0:
                state.is_scanning = False
                time.sleep(0.1)
                continue
            
            img_path = state.img_files[state.current_idx]
            
        image = cv2.imread(img_path)
        if image is None: 
            with state.lock:
                state.is_playing = False
                state.is_scanning = False
            continue

        h, w, _ = image.shape
        state.image_resolution = f"{w}x{h}"
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        total_squares = ((h // SQUARE_SIZE) + (1 if h % SQUARE_SIZE else 0)) * \
                       ((w // SQUARE_SIZE) + (1 if w % SQUARE_SIZE else 0))
        scanned_squares = 0
        
        with state.lock:
            state.is_scanning = True
        
        for y in range(0, h, SQUARE_SIZE):
            for x in range(0, w, SQUARE_SIZE):
                with state.lock:
                    if not state.is_playing or state.stop_event.is_set():
                        state.is_scanning = False
                        pygame.mixer.stop()
                        break
                
                roi = image_rgb[y:y+SQUARE_SIZE, x:x+SQUARE_SIZE]
                if roi.size == 0: 
                    scanned_squares += 1
                    continue

                avg_rgb = np.mean(roi, axis=(0, 1))
                r, g, b = int(avg_rgb[0]), int(avg_rgb[1]), int(avg_rgb[2])
                sound_files = find_closest_sound((r, g, b), state.color_dataset)

                temp_img = image.copy()
                cv2.rectangle(temp_img, (x, y), (x + SQUARE_SIZE, y + SQUARE_SIZE), (0, 255, 0), 3)
                _, buffer = cv2.imencode('.jpg', temp_img)
                
                with state.lock:
                    state.current_frame_b64 = base64.b64encode(buffer).decode('utf-8')
                    scanned_squares += 1
                    if total_squares > 0:
                        state.scan_progress = int((scanned_squares / total_squares) * 100)

                if sound_files:
                    try:
                        sound = pygame.mixer.Sound(sound_files[0])
                        sound.play(maxtime=250)
                        time.sleep(BASE_DURATION / state.scan_speed)
                        pygame.mixer.stop()
                    except: pass
            
            with state.lock:
                if not state.is_playing:
                    state.is_scanning = False
                    pygame.mixer.stop()
                    break
        
        with state.lock:
            state.is_playing = False
            state.is_scanning = False
            state.scan_progress = 0

# --- WEB INTERFACE ---
@app.route('/')
def index():
    # Serve the index.html file from the same directory
    return send_file('index.html')

@app.route('/api/frame')
def get_frame():
    return jsonify({"frame": state.current_frame_b64})

@app.route('/api/image_info')
def get_image_info():
    with state.lock:
        current_image = ""
        if state.current_idx < len(state.img_files):
            current_image = os.path.basename(state.img_files[state.current_idx])
        
        dataset_size = len(state.color_dataset)
        dataset_status = f"{dataset_size} color-sound mappings"
        if dataset_size == 0:
            dataset_status = "No dataset loaded"
        
        return jsonify({
            "current_image": current_image,
            "current_index": state.current_idx,
            "total_images": len(state.img_files),
            "is_playing": state.is_playing,
            "is_scanning": state.is_scanning,
            "scan_progress": state.scan_progress,
            "dataset_status": dataset_status,
            "image_resolution": state.image_resolution,
            "scan_speed": state.scan_speed
        })

@app.route('/api/control', methods=['POST'])
def handle_control():
    data = request.json
    action = data.get('action')
    msg = ""
    
    with state.lock:
        if action == 'play':
            if state.current_idx >= len(state.img_files):
                msg = "No images available"
            else:
                state.is_playing = True
                state.scan_progress = 0
                msg = f"Playing image: {os.path.basename(state.img_files[state.current_idx])}"
                
        elif action == 'pause':
            state.is_playing = False
            state.is_scanning = False
            pygame.mixer.stop()
            msg = "Paused"
            
        elif action == 'next':
            state.is_playing = False
            state.is_scanning = False
            pygame.mixer.stop()
            
            if state.img_files:
                state.current_idx = (state.current_idx + 1) % len(state.img_files)
                state.scan_progress = 0
                
                img_path = state.img_files[state.current_idx]
                image = cv2.imread(img_path)
                if image is not None:
                    _, buffer = cv2.imencode('.jpg', image)
                    state.current_frame_b64 = base64.b64encode(buffer).decode('utf-8')
                    update_image_resolution(img_path)
                
                msg = f"Next image: {os.path.basename(state.img_files[state.current_idx])}"
            else:
                msg = "No images available"
            
        elif action == 'prev':
            state.is_playing = False
            state.is_scanning = False
            pygame.mixer.stop()
            
            if state.img_files:
                state.current_idx = (state.current_idx - 1) % len(state.img_files)
                state.scan_progress = 0
                
                img_path = state.img_files[state.current_idx]
                image = cv2.imread(img_path)
                if image is not None:
                    _, buffer = cv2.imencode('.jpg', image)
                    state.current_frame_b64 = base64.b64encode(buffer).decode('utf-8')
                    update_image_resolution(img_path)
                
                msg = f"Previous image: {os.path.basename(state.img_files[state.current_idx])}"
            else:
                msg = "No images available"
    
    return jsonify({"message": msg})

if __name__ == '__main__':
    # Initialize State
    state.color_dataset = get_color_dataset()
    for ext in ['*.jpg', '*.png', '*.jpeg', '*.bmp', '*.tiff']:
        state.img_files.extend(glob.glob(os.path.join(IMAGE_FOLDER, ext)))
    
    state.img_files.sort()
    
    if state.img_files:
        img_path = state.img_files[0]
        image = cv2.imread(img_path)
        if image is not None:
            _, buffer = cv2.imencode('.jpg', image)
            state.current_frame_b64 = base64.b64encode(buffer).decode('utf-8')
            update_image_resolution(img_path)
    
    # Check if index.html exists
    if not os.path.exists('index.html'):
        print("WARNING: index.html not found in current directory!")
        print("Please make sure index.html is in the same folder as app.py")
        print("Creating a placeholder index.html file...")
        
        # Create a simple index.html file
        simple_html = """<!DOCTYPE html>
<html>
<head>
    <title>Drum Image Scanner</title>
</head>
<body>
    <h1>Drum Image Scanner</h1>
    <p>Please place your index.html file in the same directory as app.py</p>
    <p>The server is running, but the UI file is missing.</p>
</body>
</html>"""
        
        with open('index.html', 'w') as f:
            f.write(simple_html)
    
    # Start background scanner
    state.thread = threading.Thread(target=scan_worker, daemon=True)
    state.thread.start()
    
    print("Starting Drum Image Scanner...")
    print(f"Loaded {len(state.img_files)} images")
    print(f"Loaded {len(state.color_dataset)} color-sound mappings")
    print("Open http://localhost:5000 in your browser")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
