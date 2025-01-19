import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from ultralytics import YOLO
import cv2
from PIL import Image, ImageTk, ImageGrab
import os
import time  # For timing detection intervals
import csv  # Import csv module for logging
import pygame
import face_recognition
import requests

# For Windows screenshot capturing
try:
    import win32gui
except ImportError:
    win32gui = None  # Will handle in the screenshot method

# Constants
LOG_FILE = "detections_log.csv"
USERS_DIR = "users"
MAX_ENTRIES = 100  # Maximum number of log entries to display
REFRESH_INTERVAL = 5000  # Auto-refresh interval in milliseconds (5 seconds)

# Telegram Configuration
# It's recommended to load these from environment variables for security
TELEGRAM_BOT_TOKEN = '7694868786:AAEEir3nMZA4IMDUNFAxV-f_p--n9AygzYw'  # Replace with your new bot's token
MANAGER_CHAT_ID = '1989750249'  # Replace with the manager's chat ID

# Ensure USERS_DIR exists
if not os.path.exists(USERS_DIR):
    os.makedirs(USERS_DIR)

class ObjectDetectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Remote Worker Control")
        
        # Make the main window fullscreen or maximized
        self.root.state('zoomed')

        # Initialize current user as None
        self.current_user = None

        # Sound flags for each class
        self.sound_played = {
            "cigaratte": False,
            "phone": False,
            "drowsy": False,
            "food": False,
            "person_absent": False,  # For absence detection
            "multiple_person": False  # For multiple person detection
        }

        # Timer for tracking multiple person detection
        self.multiple_person_start_time = None

        # Set background color
        self.root.configure(bg="#343541")

        # Initialize references for any warning windows to avoid duplicates
        self.warning_window = None
        self.person_absent_warning_window = None  # For absence alerts

        # Application icon
        icon_path = "icon.png"
        if os.path.exists(icon_path):
            try:
                icon = ImageTk.PhotoImage(file=icon_path)
                self.root.iconphoto(False, icon)
            except Exception as e:
                print(f"Error loading icon: {e}")
        else:
            print(f"Icon file not found: {icon_path}")

        # Style configuration (modern / custom theme)
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Use a consistent theme
        self.style.configure(
            "TButton",
            font=("Helvetica", 14),
            padding=10,
            background="white",
            foreground="black",
            borderwidth=1
        )
        # Optional: tweak how the button looks when active
        self.style.map("TButton",
                       background=[("active", "#E6E6E6")])

        # Initialize pygame mixer for sounds
        pygame.mixer.init()

        # Ensure the screenshots directory exists
        self.screenshots_dir = "screenshots"
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)

        # Create frames
        self.create_frames()

        # Initialize Login/Signup Frame
        self.init_login_frame()

        # Initialize Main Application Frame (hidden initially)
        self.init_main_frame()

        # Flag to stop video-processing thread
        self.stop = False

        # Classes of interest for warnings
        self.classes_of_interest = ["cigaratte", "phone", "drowsy", "food"]

        # Track detection start times (None if not detected yet)
        self.detection_start_times = {
            "cigaratte": None,
            "phone": None,
            "drowsy": None,
            "food": None
        }

        # Variables for tracking person absence
        self.last_person_detected_time = time.time()
        self.person_absent_alert_played = False

        # Start auto-refresh for the side panel
        self.start_auto_refresh()

        # Frame sayacı ve başlangıç zamanı için yapı
        self.frame_counters = {
            "cigaratte": 0,
            "phone": 0,
            "drowsy": 0,
            "food": 0,
            "no_person": 0,
            "multiple_person": 0
        }
        self.start_times = {
            "cigaratte": time.time(),
            "phone": time.time(),
            "drowsy": time.time(),
            "food": time.time(),
            "no_person": time.time(),
            "multiple_person": time.time()
        }

        self.alert_threshold = 200  # 1 dakika içinde 200 frame
        self.reset_interval = 60    # Sayaçları sıfırlamak için 1 dakika

    def create_frames(self):
        """Create frames for login/signup and main application."""
        # Frame for Login/Signup
        self.login_frame = tk.Frame(self.root, bg="#343541")
        
        # Frame for Main Application
        self.main_frame = tk.Frame(self.root, bg="#343541")

    def init_login_frame(self):
        """Initialize the Login/Signup frame with Signup and Login buttons."""
        # Clear any existing widgets in login_frame
        for widget in self.login_frame.winfo_children():
            widget.destroy()

        # Title Label
        title_label = tk.Label(
            self.login_frame,
            text="Login or Signup",
            font=("Bodoni", 28, "bold"),
            bg="#343541",
            fg="white"
        )
        title_label.pack(pady=50)

        # Signup Button
        self.signup_button = ttk.Button(
            self.login_frame,
            text="Sign Up",
            width=20,
            command=self.signup_user
        )
        self.signup_button.pack(pady=20)

        # Login Button
        self.login_button = ttk.Button(
            self.login_frame,
            text="Login",
            width=20,
            command=self.login_user
        )
        self.login_button.pack(pady=20)

        # Pack the login_frame
        self.login_frame.pack(expand=True)

    def init_main_frame(self):
        """Initialize the Main Application frame with all functionalities."""
        # Clear any existing widgets in main_frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Configure grid layout for main_frame
        self.main_frame.grid_rowconfigure(0, weight=1)  # Header row
        self.main_frame.grid_rowconfigure(1, weight=1)  # Title row
        self.main_frame.grid_rowconfigure(2, weight=1)  # Buttons row (Center-aligned)
        self.main_frame.grid_rowconfigure(3, weight=1)  # Footer row

        self.main_frame.grid_columnconfigure(0, weight=1)  # Main content
        self.main_frame.grid_columnconfigure(1, weight=0)  # Side panel

        # --- Header Frame for User Info ---
        header_frame = tk.Frame(self.main_frame, bg="#343541")
        header_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="w")

        # User Label (Initially empty)
        self.user_label = tk.Label(
            header_frame,
            text="",  # To be updated upon login
            font=("Helvetica", 12, "bold"),
            bg="#343541",
            fg="white"
        )
        self.user_label.pack(side="left")

        # --- Title Label ---
        title_label = tk.Label(
            self.main_frame,
            text="Remote Worker Control",
            font=("Bodoni", 28, "bold"),
            bg="#343541",
            fg="white"
        )
        # Reduced top padding from 20 to 10 to lift the title slightly
        title_label.grid(row=1, column=0, columnspan=2, padx=20, pady=(10, 10), sticky="n")

        # --- Frame to hold main buttons ---
        button_frame = tk.Frame(self.main_frame, bg="#343541")
        # Reduced vertical padding from 40 to 10 to lift the buttons upwards
        button_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=(20, 20), sticky="n")


        # --- Main Buttons (3 Rows x 2 Columns) ---
        self.start_video_button = ttk.Button(
            button_frame,
            text="Start Video",
            width=20,
            command=self.start_video_detection
        )
        self.start_video_button.grid(row=0, column=0, padx=20, pady=10)

        self.capture_photo_button = ttk.Button(
            button_frame,
            text="Capture Photo",
            width=20,
            command=self.capture_and_save_result
        )
        self.capture_photo_button.grid(row=0, column=1, padx=20, pady=10)

        self.upload_photo_button = ttk.Button(
            button_frame,
            text="Upload Photo",
            width=20,
            command=self.upload_and_process_photo
        )
        self.upload_photo_button.grid(row=1, column=0, padx=20, pady=10)

        self.upload_video_button = ttk.Button(
            button_frame,
            text="Upload Video",
            width=20,
            command=self.upload_and_process_video
        )
        self.upload_video_button.grid(row=1, column=1, padx=20, pady=10)

        self.toggle_panel_button = ttk.Button(
            button_frame,
            text="Detection History",
            width=20,
            command=self.toggle_side_panel
        )
        self.toggle_panel_button.grid(row=2, column=0, padx=20, pady=10)

        self.logout_button = ttk.Button(
            button_frame,
            text="Sign Out",
            width=20,
            command=self.confirm_logout
        )
        self.logout_button.grid(row=2, column=1, padx=20, pady=10)

        # --- Footer Label ---
        footer_label = tk.Label(
            self.main_frame,
            text="© 2024 Remote Worker Control",
            bg="#343541",
            fg="white",
            font=("Helvetica", 10)
        )
        footer_label.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="s")

        # --- Side Panel (initially hidden) ---
        self.side_panel = tk.Frame(self.main_frame, bg="#454545", width=300)
        self.side_panel.grid_rowconfigure(0, weight=1)
        self.side_panel.grid_columnconfigure(0, weight=1)
        self.side_panel_visible = False  # start hidden

        # Add a Treeview to display CSV logs
        self.log_tree = ttk.Treeview(self.side_panel, columns=("time_detected", "warning_cause", "name"), show="headings")
        self.log_tree.heading("time_detected", text="Time Detected")
        self.log_tree.heading("warning_cause", text="Warning Cause")
        self.log_tree.heading("name", text="Name")
        self.log_tree.column("time_detected", anchor="center", width=150)
        self.log_tree.column("warning_cause", anchor="center", width=200)
        self.log_tree.column("name", anchor="center", width=100)
        self.log_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # A scrollbar for the Treeview
        scroll_y = ttk.Scrollbar(self.side_panel, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.grid(row=0, column=1, sticky='ns')

        # Status label for the side panel
        self.status_label = tk.Label(
            self.side_panel,
            text="Loaded 0 entries",
            bg="#454545",
            fg="white",
            font=("Helvetica", 10)
        )
        self.status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10))

        # --- Clear CSV Button (Initially hidden) ---
        self.clear_csv_button = ttk.Button(
            self.side_panel,
            text="Clear CSV",
            command=self.clear_csv,
            width=15
        )
        # Place the button below the status label
        self.clear_csv_button.grid(row=2, column=0, columnspan=2, pady=(0, 10))

        # Initially hide the Clear CSV button
        self.clear_csv_button.grid_remove()

    def confirm_logout(self):
        """Asks the user to confirm logout."""
        answer = messagebox.askyesno("Confirm Logout", "Are you sure you want to sign out?")
        if answer:
            self.logout_user()

    def toggle_side_panel(self):
        """Show/hide the side panel and load the CSV data when shown."""
        if self.side_panel_visible:
            # Hide the panel
            self.side_panel.grid_remove()
            self.side_panel_visible = False
            # Hide the Clear CSV button
            self.clear_csv_button.grid_remove()
        else:
            # Show the panel
            self.side_panel.grid(row=0, column=1, rowspan=4, padx=20, pady=20, sticky="nsew")
            self.side_panel_visible = True
            # Show the Clear CSV button
            self.clear_csv_button.grid()
            # Load or refresh the CSV log data
            self.load_csv_data()

    def load_csv_data(self):
        """Read the CSV file and populate the Treeview with the latest detections."""
        log_file = LOG_FILE

        # Clear any existing rows
        for row in self.log_tree.get_children():
            self.log_tree.delete(row)

        # If the file doesn't exist yet, do nothing
        if not os.path.exists(log_file):
            print(f"Log file {log_file} does not exist.")
            self.status_label.config(text="Log file does not exist.")
            return

        with open(log_file, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            try:
                header = next(reader)
                # Normalize header for comparison
                header_normalized = [h.strip().lower() for h in header]
                expected_header = ["time detected", "warning cause", "name"]
                if header_normalized != expected_header:
                    print("Header does not match expected format. Including the first row as data.")
                    # The first row is not a header; include it
                    file.seek(0)
                    reader = csv.reader(file)
            except StopIteration:
                # Empty file
                print("Log file is empty.")
                self.status_label.config(text="Log file is empty.")
                return

            rows = []
            for row in reader:
                if len(row) >= 3:
                    time_detected, warning_cause, name = row[0], row[1], row[2]
                    rows.append((time_detected, warning_cause, name))
                else:
                    print(f"Skipping malformed row: {row}")

            # Sort rows by timestamp
            try:
                rows.sort(key=lambda x: time.strptime(x[0], "%Y-%m-%d %H:%M:%S"))
            except Exception as e:
                print(f"Error sorting rows: {e}")

            # Limit to the most recent MAX_ENTRIES
            rows = rows[-MAX_ENTRIES:]

            # Insert into Treeview
            for row in rows:
                self.log_tree.insert("", "end", values=row)

            entry_count = len(rows)
            self.status_label.config(text=f"Loaded {entry_count} entries.")

            print(f"Loaded {entry_count} rows into the log tree.")

    def start_auto_refresh(self):
        """Start the auto-refresh mechanism for the side panel."""
        if self.side_panel_visible:
            self.load_csv_data()
        # Refresh every REFRESH_INTERVAL milliseconds
        self.root.after(REFRESH_INTERVAL, self.start_auto_refresh)

    def start_video_detection(self):
        """Starts a new thread to detect objects in the live video feed."""
        if hasattr(self, 'thread') and self.thread.is_alive():
            messagebox.showwarning("Warning", "Video processing is already running.")
            return

        self.stop = False
        self.thread = threading.Thread(target=self.detect_objects_in_video, daemon=True)
        self.thread.start()

    # def detect_objects_in_video(self):
    #     """Continuously read from webcam, run YOLO, and display results."""
    #     model_path = 'runs/train/bitirme/weights/best.pt'
    #     if not os.path.exists(model_path):
    #         messagebox.showerror("Error", f"Model file not found: {model_path}")
    #         return

    #     model = YOLO(model_path)
    #     cap = cv2.VideoCapture(0)
        
    #     if not cap.isOpened():
    #         messagebox.showerror("Error", "Camera could not be opened.")
    #         return

    #     while not self.stop and cap.isOpened():
    #         ret, frame = cap.read()
    #         if not ret:
    #             print("Frame could not be captured.")
    #             break
            
    #         # Run YOLO prediction
    #         results = model.predict(source=frame, show=False)
    #         annotated_frame = results[0].plot()

    #         current_time = time.time()

    #         # Check if there's any detection for classes_of_interest with conf >= 0.45
    #         active_classes = set()
    #         detected_classes = [model.names[int(box.cls[0])] for box in results[0].boxes]
    #         for box in results[0].boxes:
    #             cls_id = int(box.cls[0])
    #             conf = float(box.conf[0])  # Confidence score [0..1]
    #             cls_name = model.names.get(cls_id, "unknown")
                
    #             if cls_name in self.classes_of_interest and conf >= 0.45:
    #                 active_classes.add(cls_name)

    #         # --- New Feature: Detecting Absence of a Person ---
    #         # Check for "person" class
    #         person_detected = "person" in detected_classes

    #         if person_detected:
    #             self.last_person_detected_time = current_time
    #             self.person_absent_alert_played = False  # Reset alert flag
    #         else:
    #             if (current_time - self.last_person_detected_time) > 20 and not self.person_absent_alert_played:
    #                 self.play_alert_sound()
    #                 self.log_detection_to_csv("person_absent")
    #                 self.show_person_absent_warning()
    #                 self.person_absent_alert_played = True

    #         # --- Yeni Özellik: Aynı anda 2 veya daha fazla 'person' tespit edilirse ---
    #         person_count = detected_classes.count("person")
    #         if person_count >= 2:
    #             if self.multiple_person_start_time is None:
    #                 self.multiple_person_start_time = current_time
    #             else:
    #                 elapsed_multiple = current_time - self.multiple_person_start_time
    #                 if elapsed_multiple >= 3 and not self.sound_played["multiple_person"]:
    #                     self.play_alert_sound()
    #                     self.log_detection_to_csv("multiple_person")
    #                     # Kullanıcıya uyarı göstermek için mevcut show_warning fonksiyonunu kullanabiliriz
    #                     self.show_warning("multiple_person")
    #                     self.sound_played["multiple_person"] = True
    #         else:
    #             # Eğer person sayısı 2'nin altına düşerse, zamanlayıcıyı sıfırla
    #             self.multiple_person_start_time = None
    #             self.sound_played["multiple_person"] = False

    #         # --- Existing Feature: Handling Classes of Interest ---
    #         # Update timers and handle warnings
    #         for cls_name in self.classes_of_interest:
    #             if cls_name in active_classes:
    #                 if self.detection_start_times[cls_name] is None:
    #                     self.detection_start_times[cls_name] = current_time
    #                 else:
    #                     elapsed = current_time - self.detection_start_times[cls_name]
    #                     # If actively detected for >= 3 seconds, show a warning
    #                     if elapsed >= 3:
    #                         # Play sound only if we haven't already
    #                         if not self.sound_played[cls_name]:
    #                             self.play_alert_sound()
    #                             self.sound_played[cls_name] = True
    #                             self.log_detection_to_csv(cls_name)

    #                         self.show_warning(cls_name)
    #             else:
    #                 # Reset if not detected this frame
    #                 self.detection_start_times[cls_name] = None
    #                 self.sound_played[cls_name] = False  # Reset sound flag

    #         cv2.imshow("Video Processing", annotated_frame)

    #         if cv2.waitKey(1) & 0xFF == ord('q'):
    #             self.stop = True
    #             break
        
    #     cap.release()
    #     cv2.destroyAllWindows()

    def detect_objects_in_video(self):
        """Continuously read from webcam, run YOLO, and display results."""
        model_path = 'runs/train/bitirme/weights/best.pt'
        if not os.path.exists(model_path):
            messagebox.showerror("Error", f"Model file not found: {model_path}")
            return

        model = YOLO(model_path)
        cap = cv2.VideoCapture(0)
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"Camera FPS: {fps}")
        
        if not cap.isOpened():
            messagebox.showerror("Error", "Camera could not be opened.")
            return

        while not self.stop and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Frame could not be captured.")
                break
            
            # Run YOLO prediction
            results = model.predict(source=frame, show=False)
            detected_classes = []

            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])  # Confidence score [0..1]
                cls_name = model.names.get(cls_id, "unknown")
                if conf >= 0.45:  # Sadece confidence skoru 0.45 üzerindeki sınıfları al
                    detected_classes.append(cls_name)
            
            current_time = time.time()
            
            # İnsan tespiti sayacı ve zamanı güncelleme
            if "person" not in detected_classes:
              if self.frame_counters["no_person"] == 0:
                self.start_times["no_person"] = current_time       
              self.frame_counters["no_person"] += 1

            if self.frame_counters["no_person"] != 0:
              elapsed_time = current_time - self.start_times["no_person"]
              if elapsed_time >= self.reset_interval:
                  self.frame_counters["no_person"] = 0

            if self.frame_counters["no_person"] >= self.alert_threshold:
              self.play_alert_sound()
              self.log_detection_to_csv("person_absent")
              self.show_person_absent_warning()
              self.frame_counters["no_person"] = 0  # Uyarı verdikten sonra sıfırla
    
            # Eğer birden fazla kişi tespit edilirse
            person_count = detected_classes.count("person")
            if person_count > 1:
              if self.frame_counters["multiple_person"] == 0:
                self.start_times["multiple_person"] = current_time       
              self.frame_counters["multiple_person"] += 1

              if self.frame_counters["multiple_person"] != 0:
                elapsed_time = current_time - self.start_times["multiple_person"]
                if elapsed_time >= self.reset_interval:
                    self.frame_counters["multiple_person"] = 0

              if self.frame_counters["multiple_person"] >= self.alert_threshold:
                self.play_alert_sound()
                self.log_detection_to_csv("multiple_person")
                self.show_warning("multiple_person")
                self.frame_counters["multiple_person"] = 0  # Uyarı verdikten sonra sıfırla

            # Her sınıf için frame sayısını güncelle
            for cls_name in self.classes_of_interest:
                if cls_name in detected_classes:
                  if self.frame_counters[cls_name] == 0:
                    self.start_times[cls_name] = current_time       
                  self.frame_counters[cls_name] += 1
                  
                if self.frame_counters[cls_name] != 0:
                  # Eğer 1 dakika geçmişse sayaçları sıfırla
                  elapsed_time = current_time - self.start_times[cls_name]
                  if elapsed_time >= self.reset_interval:
                      self.frame_counters[cls_name] = 0

                # Eğer frame sayısı eşik değeri geçerse uyarı ver
                if self.frame_counters[cls_name] >= self.alert_threshold:
                    self.play_alert_sound()
                    self.log_detection_to_csv(cls_name)
                    self.show_warning(cls_name)
                    self.frame_counters[cls_name] = 0  # Uyarı verdikten sonra sıfırla

            annotated_frame = results[0].plot()
            cv2.imshow("Video Processing", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.stop = True
                break

        cap.release()
        cv2.destroyAllWindows()

    def play_alert_sound(self):
        """Plays the alert sound once."""
        sound_file = "short_alert.wav"  # Replace with your sound file path
        if os.path.exists(sound_file):
            try:
                pygame.mixer.music.load(sound_file)
                pygame.mixer.music.play(loops=0)  # Play the file once
            except pygame.error as e:
                print(f"Error playing sound: {e}")
        else:
            print(f"Sound file not found: {sound_file}")

    def show_warning(self, cls_name):
        """Displays a warning pop-up for specific classes of interest."""
        warning_messages = {
            'cigaratte':  "Smoking is prohibited!",
            'phone':      "Phone usage detected!",
            'drowsy':     "Drowsy condition detected!",
            'food':       "Eating detected!",
            'multiple_person': "Multiple persons detected!"
        }

        # Avoid multiple stacked windows by checking if the existing one is open
        if self.warning_window is None or not tk.Toplevel.winfo_exists(self.warning_window):
            self.warning_window = tk.Toplevel(self.root)
            self.warning_window.title("Warning!")
            self.warning_window.geometry("400x200")
            self.warning_window.configure(bg="red")

            # Bring window to front immediately
            self.warning_window.lift()
            self.warning_window.attributes("-topmost", True)
            self.warning_window.after_idle(
                lambda: self.warning_window.attributes("-topmost", False)
            )

            def on_close():
                # Reset the timer and sound flag for this class
                self.detection_start_times[cls_name] = None
                self.sound_played[cls_name] = False
                self.warning_window.destroy()
                self.warning_window = None

            self.warning_window.protocol("WM_DELETE_WINDOW", on_close)

            message_text = warning_messages.get(cls_name, "Unknown warning!")
            warning_label = tk.Label(
                self.warning_window,
                text=message_text,
                font=("Helvetica", 16, "bold"),
                bg="red",
                fg="white",
                wraplength=350
            )
            warning_label.pack(expand=True)

            close_button = ttk.Button(
                self.warning_window,
                text="OK",
                command=on_close
            )
            close_button.pack(pady=20)

    def show_person_absent_warning(self):
        """Displays a warning pop-up when no person is detected for 20 seconds."""
        warning_text = "Person not present!"

        # Avoid multiple stacked windows by checking if the existing one is open
        if self.person_absent_warning_window is None or not tk.Toplevel.winfo_exists(self.person_absent_warning_window):
            self.person_absent_warning_window = tk.Toplevel(self.root)
            self.person_absent_warning_window.title("Alert!")
            self.person_absent_warning_window.geometry("400x200")
            self.person_absent_warning_window.configure(bg="orange")

            # Bring window to front immediately
            self.person_absent_warning_window.lift()
            self.person_absent_warning_window.attributes("-topmost", True)
            self.person_absent_warning_window.after_idle(
                lambda: self.person_absent_warning_window.attributes("-topmost", False)
            )

            def on_close():
                # Reset the alert played flag
                self.person_absent_alert_played = False
                self.person_absent_warning_window.destroy()
                self.person_absent_warning_window = None

            self.person_absent_warning_window.protocol("WM_DELETE_WINDOW", on_close)

            warning_label = tk.Label(
                self.person_absent_warning_window,
                text=warning_text,
                font=("Helvetica", 16, "bold"),
                bg="orange",
                fg="white",
                wraplength=350
            )
            warning_label.pack(expand=True)

            close_button = ttk.Button(self.person_absent_warning_window, text="OK", command=on_close)
            close_button.pack(pady=20)

    def log_detection_to_csv(self, cls_name):
        """
        Logs the detection event to a CSV file with the class type, timestamp, and user name.
        Also sends a single Telegram message with both text and image.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # Mapping from class_name to warning messages
        warning_messages = {
            "cigaratte": "Smoking is prohibited!",
            "phone": "Phone usage detected!",
            "drowsy": "Drowsy condition detected!",
            "food": "Eating detected!",
            "person_absent": "Person not present!",
            "multiple_person": "Multiple Persons Detected"
        }

        warning_cause = warning_messages.get(cls_name, "Unknown warning!")

        entry = [timestamp, warning_cause, self.current_user if self.current_user else "Unknown"]

        # Check if the file exists. If not, create it and write the header.
        file_exists = os.path.exists(LOG_FILE)

        try:
            with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                if not file_exists:
                    # Write the header if the file is new
                    writer.writerow(["Time Detected", "Warning Cause", "Name"])
                # Write the detection details
                writer.writerow(entry)
            print(f"Logged detection: {warning_cause} at {timestamp} by {self.current_user}")
        except Exception as e:
            print(f"Error logging detection to CSV: {e}")

        # Prepare the Telegram message
        telegram_message = f"**Message From Remote Controller Bot**\n**Warning Triggered:**\nTime: {timestamp}\nCause: {warning_cause}\nUser: {self.current_user if self.current_user else 'Unknown'}"

        # Start a thread to capture screenshot and send Telegram message with image and caption
        threading.Thread(target=self.capture_screenshot_and_send_single_message, args=(warning_cause, timestamp, telegram_message), daemon=True).start()

        # If the side panel is visible, update the Treeview in real-time
        if self.side_panel_visible:
            try:
                self.log_tree.insert("", "end", values=entry)
                # Sort the Treeview
                self.sort_treeview()

                # Limit the number of entries
                current_entries = len(self.log_tree.get_children())
                if current_entries > MAX_ENTRIES:
                    for _ in range(current_entries - MAX_ENTRIES):
                        first_child = self.log_tree.get_children()[0]
                        self.log_tree.delete(first_child)

                # Update status label
                self.status_label.config(text=f"Loaded {min(current_entries, MAX_ENTRIES)} entries.")

                # Scroll to the latest entry
                self.log_tree.yview_moveto(1)
            except Exception as e:
                print(f"Error updating Treeview: {e}")

    def sort_treeview(self):
        """Sort the Treeview entries by timestamp."""
        try:
            entries = [(self.log_tree.set(k, "time_detected"), k) for k in self.log_tree.get_children('')]
            entries.sort(key=lambda x: time.strptime(x[0], "%Y-%m-%d %H:%M:%S"))
            for index, (val, k) in enumerate(entries):
                self.log_tree.move(k, '', index)
        except Exception as e:
            print(f"Error sorting Treeview: {e}")

    def clear_csv(self):
        """Clears the CSV log file and the Treeview."""
        answer = messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the CSV log?")
        if answer:
            try:
                # Truncate the CSV file
                with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Time Detected", "Warning Cause", "Name"])  # Write header
                print("CSV log has been cleared.")

                # Clear the Treeview
                for row in self.log_tree.get_children():
                    self.log_tree.delete(row)

                # Update status label
                self.status_label.config(text="Loaded 0 entries.")

                messagebox.showinfo("Success", "CSV log has been cleared.")
            except Exception as e:
                print(f"Error clearing CSV log: {e}")
                messagebox.showerror("Error", f"An error occurred while clearing the CSV log: {e}")

    def send_telegram_message(self, message):
        """Send a text message to the manager via Telegram using direct HTTP requests."""
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': MANAGER_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'  # Optional: for formatting
        }
        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                print("Telegram message sent successfully.")
            else:
                print(f"Failed to send Telegram message: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Exception occurred while sending Telegram message: {e}")

    def send_telegram_image(self, image_path, message):
        """Send an image with a caption to the manager via Telegram using direct HTTP requests."""
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
        payload = {
            'chat_id': MANAGER_CHAT_ID,
            'caption': message,
            'parse_mode': 'Markdown'  # Optional: for formatting
        }
        try:
            with open(image_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                response = requests.post(url, data=payload, files=files)
                if response.status_code == 200:
                    print("Telegram image sent successfully.")
                else:
                    print(f"Failed to send Telegram image: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Exception occurred while sending Telegram image: {e}")

    def capture_screenshot_and_send_single_message(self, warning_cause, timestamp, telegram_message):
        """
        Captures a screenshot and sends it along with the Telegram message in one single message.
        """
        # Define the window title to capture
        window_title = "Video Processing"

        # Allow a short delay to ensure the window is updated
        time.sleep(1)

        # Find the window's coordinates (Windows-specific)
        if win32gui:
            try:
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd == 0:
                    print(f"Window titled '{window_title}' not found.")
                    return

                # Get the window's bounding rectangle
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bottom - top

                # Capture the screenshot
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
                screenshot_filename = f"{self.screenshots_dir}/screenshot_{int(time.time())}.png"
                screenshot.save(screenshot_filename)
                print(f"Screenshot saved: {screenshot_filename}")

                # Send the screenshot with the message as a caption
                self.send_telegram_image(screenshot_filename, telegram_message)
            except Exception as e:
                print(f"Error capturing screenshot: {e}")
        else:
            print("win32gui not available. Screenshot functionality is disabled on this platform.")

    def signup_user(self):
        """Handles the signup process: captures user's face and saves it."""
        # Prompt for user's name
        user_name = simpledialog.askstring("Signup", "Please enter your name:")
        if not user_name:
            messagebox.showwarning("Warning", "Username cannot be empty.")
            return

        # Check if user already exists
        user_image_path = os.path.join(USERS_DIR, f"{user_name}.jpg")
        if os.path.exists(user_image_path):
            messagebox.showwarning("Warning", "This username already exists.")
            return

        # Notify user to position their face in the webcam
        messagebox.showinfo("Information", "Please position your face in front of the camera and press 'e'.")

        # Capture image from webcam
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            messagebox.showerror("Error", "Camera could not be opened.")
            return

        captured_image = None
        while True:
            ret, frame = cap.read()
            if not ret:
                messagebox.showerror("Error", "Frame could not be captured.")
                break

            cv2.imshow("Signup - Show Your Face", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('e'):
                captured_image = frame
                break
            elif key == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if captured_image is None:
            messagebox.showwarning("Warning", "Photo could not be taken.")
            return

        # Convert the image from BGR (OpenCV) to RGB (face_recognition)
        rgb_image = cv2.cvtColor(captured_image, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image)
        if len(face_locations) != 1:
            messagebox.showerror("Error", "Please show exactly one face.")
            return

        # Save the image
        try:
            cv2.imwrite(user_image_path, captured_image)
            messagebox.showinfo("Success", f"User '{user_name}' has been successfully registered.")
            print(f"User {user_name} signed up with image at {user_image_path}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the photo: {e}")

    def login_user(self):
        """Handles the login process: captures current face and verifies it."""
        # Notify user to position their face in the webcam
        messagebox.showinfo("Information", "Please position your face in front of the camera and press 'e'.")

        # Capture image from webcam
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            messagebox.showerror("Error", "Camera could not be opened.")
            return

        captured_image = None
        while True:
            ret, frame = cap.read()
            if not ret:
                messagebox.showerror("Error", "Frame could not be captured.")
                break

            cv2.imshow("Login - Show Your Face", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('e'):
                captured_image = frame
                break
            elif key == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if captured_image is None:
            messagebox.showwarning("Warning", "Photo could not be taken.")
            return

        # Convert the image from BGR (OpenCV) to RGB (face_recognition)
        rgb_image = cv2.cvtColor(captured_image, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image)
        if len(face_locations) != 1:
            messagebox.showerror("Error", "Please show exactly one face.")
            return

        # Encode the captured face
        captured_encoding = face_recognition.face_encodings(rgb_image, face_locations)[0]

        # Initialize variables for matching
        matches = []
        matched_user = None

        # Iterate over stored user images
        for user_image_file in os.listdir(USERS_DIR):
            if not user_image_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue

            user_name = os.path.splitext(user_image_file)[0]
            user_image_path = os.path.join(USERS_DIR, user_image_file)

            # Load user image
            user_image = face_recognition.load_image_file(user_image_path)
            user_face_locations = face_recognition.face_locations(user_image)
            if len(user_face_locations) != 1:
                print(f"User {user_name} has {len(user_face_locations)} faces in the image. Skipping.")
                continue

            # Encode user face
            user_encoding = face_recognition.face_encodings(user_image, user_face_locations)[0]

            # Compare faces
            distance = face_recognition.face_distance([user_encoding], captured_encoding)[0]
            tolerance = 0.6  # Lower is stricter
            if distance < tolerance:
                matches.append((user_name, distance))

        if matches:
            # Find the best match
            matches.sort(key=lambda x: x[1])  # Sort by distance
            matched_user = matches[0][0]
            messagebox.showinfo("Success", f"Welcome, {matched_user}!")
            print(f"User {matched_user} logged in successfully.")

            # Set the current user
            self.current_user = matched_user

            # Update the user label
            self.user_label.config(text=f"Welcome, {self.current_user}")

            # Hide the login_frame
            self.login_frame.pack_forget()

            # Show the main_frame
            self.main_frame.pack(fill='both', expand=True)
        else:
            messagebox.showerror("Error", "Authentication failed.")
            print("Login failed: No matching user found.")

    def logout_user(self):
        """Handles the logout process: hides main_frame and shows login_frame."""
        # Reset the current user
        self.current_user = None

        # Clear the user label
        self.user_label.config(text="")

        # Hide the main_frame
        self.main_frame.pack_forget()

        # Show the login_frame
        self.init_login_frame()

    def generate_unique_filename(self, base_name, extension):
        """Generate a unique filename by appending an increasing counter if needed."""
        counter = 0
        while True:
            filename = f"{base_name}_{counter}{extension}" if counter > 0 else f"{base_name}{extension}"
            if not os.path.exists(filename):
                return filename
            counter += 1

    def capture_and_save_result(self):
        """Capture a single image from the webcam, run YOLO, and show the result."""
        model_path = 'runs/train/bitirme/weights/best.pt'
        if not os.path.exists(model_path):
            messagebox.showerror("Error", f"Model file not found: {model_path}")
            return

        model = YOLO(model_path)
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            messagebox.showerror("Error", "Camera could not be opened.")
            return

        print("Press 'q' to capture a photo.")
        captured_image = None
        while True:
            ret, frame = cap.read()
            if not ret: 
                print("Frame could not be captured.")
                break

            cv2.imshow("Camera", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                captured_image = frame
                break

        cap.release()
        cv2.destroyAllWindows()

        if captured_image is None:
            messagebox.showwarning("Warning", "Photo could not be taken.")
            return  # No image captured

        # Save captured image
        temp_image_path = self.generate_unique_filename("captured_image", ".jpg")
        try:
            cv2.imwrite(temp_image_path, captured_image)
            print(f"Photo saved: {temp_image_path}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the photo: {e}")
            return

        # Process the image with YOLO
        try:
            results = model.predict(source=temp_image_path, show=False)
            annotated_frame = results[0].plot()
            result_image_path = self.generate_unique_filename("result", ".jpg")
            cv2.imwrite(result_image_path, annotated_frame)
            print(f"Result image saved: {result_image_path}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while processing the image: {e}")
            return

        # Display the result image
        self.display_image(result_image_path)

    def display_image(self, image_path):
        """Display any image in a new Tkinter Toplevel window."""
        if not os.path.exists(image_path):
            print(f"Image file not found: {image_path}")
            messagebox.showerror("Error", f"Image not found: {image_path}")
            return

        new_window = tk.Toplevel(self.root)
        new_window.title("Result Image")

        try:
            image = Image.open(image_path)
            # Resize image for consistent display
            image = image.resize((600, 400), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
        except Exception as e:
            print(f"Error loading image: {e}")
            messagebox.showerror("Error", f"An error occurred while loading the image: {e}")
            new_window.destroy()
            return

        image_label = tk.Label(new_window, image=photo)
        image_label.image = photo  # Keep reference to avoid garbage collection
        image_label.pack()

        close_button = ttk.Button(new_window, text="Close", command=new_window.destroy)
        close_button.pack(pady=10)

    def upload_and_process_photo(self):
        """Prompt user to select a photo, run YOLO, and display the result."""
        model_path = 'runs/train/bitirme/weights/best.pt'
        if not os.path.exists(model_path):
            messagebox.showerror("Error", f"Model file not found: {model_path}")
            return

        model = YOLO(model_path)
        input_image_path = filedialog.askopenfilename(
            title="Select a Photo",
            filetypes=(("Image Files", "*.jpg *.jpeg *.png"), ("All Files", "*.*"))
        )

        if not input_image_path:
            print("No photo selected.")
            return

        print(f"Uploaded photo: {input_image_path}")
        result_image_path = self.generate_unique_filename("result", ".jpg")

        # Process the image
        try:
            results = model.predict(source=input_image_path, show=False)
            annotated_frame = results[0].plot()
            cv2.imwrite(result_image_path, annotated_frame)
            print(f"Result image saved: {result_image_path}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while processing the image: {e}")
            return

        self.display_image(result_image_path)

    def upload_and_process_video(self):
        """Prompt user to select a video, run YOLO on it, and save the annotated output."""
        model_path = 'runs/train/bitirme/weights/best.pt'
        if not os.path.exists(model_path):
            messagebox.showerror("Error", f"Model file not found: {model_path}")
            return

        model = YOLO(model_path)
        input_video_path = filedialog.askopenfilename(
            title="Select a Video",
            filetypes=(("Video Files", "*.mp4 *.avi *.mov"), ("All Files", "*.*"))
        )

        if not input_video_path:
            print("No video selected.")
            return

        print(f"Uploaded video: {input_video_path}")
        result_video_path = self.generate_unique_filename("vid_result", ".mp4")

        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            messagebox.showerror("Error", "Video could not be opened.")
            return

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps = fps if fps > 0 else 25  # Default to 25 if FPS is not available
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(result_video_path, fourcc, fps, (width, height))

        print("Processing video. Press 'q' to exit.")
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            try:
                results = model.predict(source=frame, show=False)
                annotated_frame = results[0].plot()
                out.write(annotated_frame)
                cv2.imshow("Video Processing", annotated_frame)
            except Exception as e:
                print(f"Error processing video frame with YOLO: {e}")
                break

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        out.release()
        cv2.destroyAllWindows()
        print(f"Result video saved: {result_video_path}")
        messagebox.showinfo("Information", f"Result video saved: {result_video_path}")

# Main Application
if __name__ == "__main__":
    root = tk.Tk()
    app = ObjectDetectionApp(root)
    root.mainloop()
