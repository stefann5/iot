import time
import threading
import struct
import random


class WebcamSimulator:
    """
    Simulates a webcam by generating simple JPEG-like frames.
    In simulation mode, generates a colored test pattern frame.
    The frame changes color periodically to show it's live.
    """

    def __init__(self, width=640, height=480, fps=10):
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self._frame = None
        self._frame_lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._generate_frames, daemon=True)
        self._thread.start()
        print(f"[WEBC Simulator] Webcam started ({self.width}x{self.height} @ {self.fps}fps)")

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        print("[WEBC Simulator] Webcam stopped")

    def get_frame(self):
        """Get the latest JPEG frame bytes."""
        with self._frame_lock:
            return self._frame

    def _generate_frames(self):
        """Generate simple BMP frames encoded as JPEG-compatible data."""
        colors = [
            (0, 100, 200),   # Blue
            (0, 180, 100),   # Green
            (200, 100, 0),   # Orange
            (150, 0, 150),   # Purple
            (200, 200, 0),   # Yellow
        ]
        color_idx = 0
        frame_count = 0

        while not self._stop_event.is_set():
            # Create a simple BMP image
            r, g, b = colors[color_idx % len(colors)]

            # Create a minimal valid JPEG-like BMP frame
            frame = self._create_bmp_frame(r, g, b, frame_count)

            with self._frame_lock:
                self._frame = frame

            frame_count += 1
            if frame_count % (self.fps * 3) == 0:  # Change color every 3 seconds
                color_idx += 1

            time.sleep(1.0 / self.fps)

    def _create_bmp_frame(self, r, g, b, frame_num):
        """Create a minimal BMP image with a color and frame counter text area."""
        w, h = 320, 240  # Smaller for simulation
        row_size = (w * 3 + 3) & ~3  # Row padding to 4 bytes
        pixel_data_size = row_size * h
        file_size = 54 + pixel_data_size

        # BMP Header
        header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 54)
        # DIB Header
        dib = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0,
                          pixel_data_size, 2835, 2835, 0, 0)

        # Pixel data (BGR format, bottom-up)
        rows = []
        for y in range(h):
            row = bytearray()
            for x in range(w):
                # Add a simple grid pattern
                if (x // 40 + y // 40) % 2 == 0:
                    row.extend([b, g, r])
                else:
                    row.extend([b // 2, g // 2, r // 2])
            # Pad row to 4-byte boundary
            while len(row) % 4 != 0:
                row.append(0)
            rows.append(bytes(row))

        return header + dib + b''.join(rows)
