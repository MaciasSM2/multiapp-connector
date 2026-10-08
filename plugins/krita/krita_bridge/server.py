import json
import os
import queue
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Any, Dict

TASK_QUEUE = queue.Queue()
RESPONSE_MAP: Dict[str, queue.Queue] = {}


class KritaRequestHandler(BaseHTTPRequestHandler):
    """Manejador HTTP para recibir comandos hacia Krita de forma concurrente."""

    def log_message(self, format, *args):
        # Silenciar logs ruidosos en la terminal de Krita
        pass

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status" or self.path == "/api/ping":
            self._dispatch_command("get_status", {})
        elif self.path == "/api/document_info":
            self._dispatch_command("get_document_info", {})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        endpoint = self.path.split("?")[0]

        if endpoint == "/api/create_document":
            self._dispatch_command("create_document", payload)
        elif endpoint == "/api/import_layer":
            self._dispatch_command("import_layer", payload)
        elif endpoint == "/api/export":
            self._dispatch_command("export_canvas", payload)
        elif endpoint == "/api/trigger_action":
            self._dispatch_command("trigger_action", payload)
        elif endpoint == "/api/add_layer":
            self._dispatch_command("add_layer", payload)
        elif endpoint == "/api/set_layer_visible":
            self._dispatch_command("set_layer_visible", payload)
        else:
            self._send_json(404, {"error": f"Unknown action: {endpoint}"})

    def _dispatch_command(self, action: str, params: dict):
        req_id = os.urandom(8).hex()
        resp_q = queue.Queue()
        RESPONSE_MAP[req_id] = resp_q

        TASK_QUEUE.put({"id": req_id, "action": action, "params": params})

        try:
            result = resp_q.get(timeout=15.0)
            status_code = 200 if result.get("status") == "success" else 400
            self._send_json(status_code, result)
        except queue.Empty:
            self._send_json(504, {"status": "error", "message": "Command timeout in Krita main thread"})
        finally:
            RESPONSE_MAP.pop(req_id, None)


class KritaDaemonServer:
    """Servidor HTTP en hilo daemon que escucha en 127.0.0.1:52150."""

    def __init__(self, host: str = "127.0.0.1", port: int = 52150):
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        try:
            self.httpd = HTTPServer((self.host, self.port), KritaRequestHandler)
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            print(f"[KritaBridge] Servidor escuchando en http://{self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[KritaBridge] Error al iniciar servidor: {e}")
            return False

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
