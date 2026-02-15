import time
import threading

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class Webcam:
    """
    Real webcam capture using OpenCV.
    Captures frames from USB webcam at specified FPS.
    """

    def __init__(self, device_index=0, width=640, height=480, fps=10):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self._frame = None
        self._frame_lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._cap = None

    def start(self):
        if self.running:
            return
        if not HAS_CV2:
            print("[WEBC] OpenCV not available, cannot start webcam")
            return

        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            print(f"[WEBC] Failed to open webcam device {self.device_index}")
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[WEBC] Webcam started (device {self.device_index}, {self.width}x{self.height})")

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()
        print("[WEBC] Webcam stopped")

    def get_frame(self):
        """Get the latest JPEG-encoded frame bytes."""
        with self._frame_lock:
            return self._frame

    def _capture_loop(self):
        """Continuously capture frames from the webcam."""
        while not self._stop_event.is_set():
            ret, frame = self._cap.read()
            if ret:
                # Encode as JPEG
                _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                with self._frame_lock:
                    self._frame = jpeg.tobytes()
            time.sleep(1.0 / self.fps)
