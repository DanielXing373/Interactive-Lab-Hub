import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ok:
                continue
            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
    def log_message(self, *args):
        pass

print("Open http://PI_IP:8080 in a browser. Ctrl-C to stop.")
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
