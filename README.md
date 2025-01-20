# Remote Worker Control

## Project Overview
Remote Worker Control is an AI-powered application designed to monitor remote workers using YOLOv8 for real-time object detection. It detects behaviors like drowsiness, smoking, phone usage, eating, and multiple persons present or absence from the scene. Alerts are sent through visual warnings and Telegram messages.

![Poster](poster.jpg)

---

## Features
- **Real-Time Detection**: Monitors behaviors and alerts for the following classes:
  - Drowsiness
  - Smoking
  - Phone Usage
  - Eating
  - Absence of a person
  - Presence of multiple persons
- **Face Authentication**: Users can sign up and log in using face recognition.
- **Telegram Integration**: Alerts are sent to a designated manager via Telegram.
- **CSV Logging**: Detection events are logged with timestamps and reasons.
- **GUI Application**: A Tkinter-based graphical interface for ease of use.
- **Screenshot and Video Processing**: Supports live webcam input, video uploads, and screenshot-based detection.

---

## Installation

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd remote-worker-control
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download YOLOv8 model weights:
   - Place the `yolov8n.pt` file under the appropriate directory (e.g., `runs/train/bitirme/weights`).

4. Set up your Telegram bot:
   - Replace `TELEGRAM_BOT_TOKEN` and `MANAGER_CHAT_ID` in the `app.py` file with your bot's token and chat ID.

---

## Project Structure
```
remote-worker-control/
├── runs/train/bitirme/
│   └── weights/
│       ├── best.pt         # Trained YOLOv8 weights
├── app.py                  # Main application source code
├── script.ipynb            # Model training and validation script
├── requirements.txt        # Required Python packages
├── data.yaml               # Dataset configuration for YOLOv8
├── icon.png                # Application icon
├── poster.jpg              # Project poster
├── short_alert.wav         # Alert sound
├── README.md               # Project documentation
```

---

## Training the Model
To train the YOLOv8 model, follow these steps:

1. Configure the dataset in `data.yaml`.
2. Open the `script.ipynb` file and run the cells to:
   - Initialize YOLOv8 model with `yolov8n.pt`.
   - Train the model using your dataset.
   - Validate the trained model.

3. The best-trained weights will be saved in the `runs/train/bitirme/weights` directory.

---

## Running the Application

### Windows:
1. Execute the app:
   ```bash
   run.bat
   ```
   
## Demo Video
[Watch the Demo](https://www.youtube.com/watch?v=O9Q77JRDaxQ)

---

## Key Dependencies
- `ultralytics`
- `opencv-python`
- `face_recognition`
- `pygame`
- `tkinter`
- `matplotlib`
- `requests`

---


## Authors
- Abdullah Enes Patır
- Yasir Şekerci

## Supervisor
- Salih Sarp
