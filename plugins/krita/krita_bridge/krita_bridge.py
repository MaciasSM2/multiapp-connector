import os
from krita import Extension, Krita, InfoObject

try:
    from PyQt5.QtCore import QTimer
    from PyQt5.QtGui import QImage
except ImportError:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QImage

from .server import KritaDaemonServer, TASK_QUEUE, RESPONSE_MAP


class KritaBridgeExtension(Extension):
    """
    Extensión PyKrita para conectar Krita con Antigravity y OpenCode.
    Ejecuta un servidor daemon HTTP y despacha los comandos en el hilo principal de Qt.
    """

    def __init__(self, parent):
        super(KritaBridgeExtension, self).__init__(parent)
        self.server = None
        self.timer = None

    def setup(self):
        # Iniciar servidor daemon
        self.server = KritaDaemonServer(host="127.0.0.1", port=52150)
        self.server.start()

        # Iniciar QTimer periódico en el hilo principal de Qt para atender tareas
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_queue)
        self.timer.start(50)  # Cada 50 ms
        print("[KritaBridge] Plugin inicializado con éxito en Krita.")

    def createActions(self, window):
        # No se necesitan botones obligatorios en la barra de herramientas, pero registramos la extensión
        pass

    def _process_queue(self):
        """Procesa peticiones de la cola dentro del hilo principal de Qt de Krita."""
        while not TASK_QUEUE.empty():
            try:
                task = TASK_QUEUE.get_nowait()
                req_id = task["id"]
                action = task["action"]
                params = task.get("params", {})

                result = self._execute_action(action, params)

                if req_id in RESPONSE_MAP:
                    RESPONSE_MAP[req_id].put(result)
            except Exception as e:
                print(f"[KritaBridge] Error al procesar tarea de cola: {e}")

    def _execute_action(self, action: str, params: dict) -> dict:
        app = Krita.instance()

        if action == "get_status":
            doc = app.activeDocument()
            return {
                "status": "success",
                "krita_version": app.version(),
                "has_active_document": doc is not None,
                "document_name": doc.name() if doc else None,
            }

        elif action == "get_document_info":
            doc = app.activeDocument()
            if not doc:
                return {"status": "error", "message": "No hay documento activo abierto en Krita"}

            layers = []
            for node in doc.topLevelNodes():
                layers.append({
                    "name": node.name(),
                    "type": node.type(),
                    "visible": node.visible(),
                    "opacity": node.opacity(),
                })

            return {
                "status": "success",
                "name": doc.name(),
                "width": doc.width(),
                "height": doc.height(),
                "resolution": doc.resolution(),
                "color_model": doc.colorModel(),
                "color_depth": doc.colorDepth(),
                "layers": layers,
            }

        elif action == "create_document":
            w = int(params.get("width", 1920))
            h = int(params.get("height", 1080))
            name = params.get("name", "Nuevo Dibujo AI")
            dpi = int(params.get("dpi", 300))
            color_model = params.get("color_model", "RGBA")
            color_depth = params.get("color_depth", "U8")

            doc = app.createDocument(w, h, name, color_model, color_depth, "", dpi)
            if not doc:
                return {"status": "error", "message": "No se pudo crear el documento en Krita"}

            win = app.activeWindow()
            if win:
                win.addView(doc)

            return {
                "status": "success",
                "message": f"Documento '{name}' creado ({w}x{h} px @ {dpi} DPI)",
                "width": w,
                "height": h,
            }

        elif action == "add_layer":
            doc = app.activeDocument()
            if not doc:
                return {"status": "error", "message": "No hay documento activo"}

            layer_name = params.get("name", "Capa AI")
            layer_type = params.get("type", "paintLayer")
            node = doc.createNode(layer_name, layer_type)
            doc.rootNode().addChildNode(node, None)
            doc.refreshProjection()

            return {"status": "success", "message": f"Capa '{layer_name}' añadida con éxito"}

        elif action == "import_layer":
            doc = app.activeDocument()
            if not doc:
                return {"status": "error", "message": "No hay documento activo en Krita para importar la capa"}

            file_path = params.get("file_path")
            layer_name = params.get("layer_name", os.path.basename(file_path))

            if not file_path or not os.path.exists(file_path):
                return {"status": "error", "message": f"Archivo no encontrado: {file_path}"}

            # Importar como FileLayer o insertar datos de imagen
            file_layer = doc.createFileLayer(layer_name, file_path, "None")
            if not file_layer:
                return {"status": "error", "message": "No se pudo instanciar la capa desde el archivo"}

            doc.rootNode().addChildNode(file_layer, None)
            doc.refreshProjection()

            return {
                "status": "success",
                "message": f"Capa '{layer_name}' importada correctamente desde {file_path}",
            }

        elif action == "export_canvas":
            doc = app.activeDocument()
            if not doc:
                return {"status": "error", "message": "No hay documento activo para exportar"}

            output_path = params.get("output_path")
            if not output_path:
                return {"status": "error", "message": "Se requiere 'output_path'"}

            doc.setBatchmode(True)
            doc.refreshProjection()
            doc.waitForDone()

            export_info = InfoObject()
            ok = doc.exportImage(output_path, export_info)
            if ok:
                return {"status": "success", "output_path": output_path, "message": "Lienzo exportado con éxito"}
            else:
                return {"status": "error", "message": f"Krita no pudo exportar la imagen a {output_path}"}

        elif action == "trigger_action":
            act_name = params.get("action_name")
            act = app.action(act_name)
            if not act:
                return {"status": "error", "message": f"Acción de Krita no encontrada: '{act_name}'"}

            act.trigger()
            return {"status": "success", "message": f"Acción '{act_name}' disparada con éxito"}

        return {"status": "error", "message": f"Acción desconocida: '{action}'"}
