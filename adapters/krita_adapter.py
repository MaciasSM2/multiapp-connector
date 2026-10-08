import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx

from config import KRITA_EXE_PATH, KRITA_PORT, OUTPUT_DIR, WORKSPACE_DIR


class KritaAdapter:
    """
    Controlador para Krita mediante la extensión local PyKrita KritaBridge en http://127.0.0.1:52150.
    """

    def __init__(self, port: int = KRITA_PORT):
        self.port = port
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.pykrita_dir = Path(os.environ.get("APPDATA", "")) / "krita" / "pykrita"
        self.kritarc_path = Path(os.environ.get("LOCALAPPDATA", "")) / "kritarc"
        self.temp_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp"

    def is_installed(self) -> bool:
        """Verifica si el binario de Krita existe en el sistema."""
        return KRITA_EXE_PATH.exists()

    def is_plugin_installed(self) -> bool:
        """Comprueba si el plugin KritaBridge está copiado en la carpeta pykrita de Krita."""
        desktop_file = self.pykrita_dir / "kritapykrita_krita_bridge.desktop"
        pkg_dir = self.pykrita_dir / "krita_bridge"
        return desktop_file.exists() and pkg_dir.exists()

    def install_plugin(self) -> Dict[str, Any]:
        """
        Instala automáticamente el plugin KritaBridge en el directorio de usuario de Krita
        y lo activa en la configuración kritarc.
        """
        source_dir = WORKSPACE_DIR / "plugins" / "krita"
        if not source_dir.exists():
            return {"status": "error", "message": f"Carpeta fuente no encontrada: {source_dir}"}

        self.pykrita_dir.mkdir(parents=True, exist_ok=True)

        # 1. Copiar .desktop según la convención kritapykrita_
        src_desktop = source_dir / "kritapykrita_krita_bridge.desktop"
        if not src_desktop.exists():
            src_desktop = source_dir / "krita_bridge.desktop"
        dest_desktop = self.pykrita_dir / "kritapykrita_krita_bridge.desktop"
        shutil.copy2(src_desktop, dest_desktop)

        # 2. Copiar carpeta de módulo
        src_pkg = source_dir / "krita_bridge"
        dest_pkg = self.pykrita_dir / "krita_bridge"
        if dest_pkg.exists():
            shutil.rmtree(dest_pkg)
        shutil.copytree(src_pkg, dest_pkg)

        # 3. Asegurar activación en kritarc
        self._enable_in_kritarc()

        return {
            "status": "success",
            "message": "Plugin KritaBridge instalado y configurado correctamente en PyKrita.",
            "pykrita_dir": str(self.pykrita_dir),
        }

    def _enable_in_kritarc(self):
        """Agrega las secciones [python] y [PythonPlugin] en kritarc para activar krita_bridge."""
        if not self.kritarc_path.exists():
            return

        try:
            content = self.kritarc_path.read_text(encoding="utf-8", errors="ignore")
            # Configurar sección [python] (estándar Krita 5)
            if "[python]" in content:
                if "krita_bridge=true" not in content:
                    content = content.replace(
                        "[python]",
                        "[python]\nkrita_bridge=true\nkritapykrita_krita_bridge=true\nenable_krita_bridge=true"
                    )
            else:
                content += "\n[python]\nkrita_bridge=true\nkritapykrita_krita_bridge=true\nenable_krita_bridge=true\n"

            # Compatibilidad adicional con [PythonPlugin]
            if "[PythonPlugin]" in content:
                if "krita_bridge=true" not in content:
                    content = content.replace(
                        "[PythonPlugin]",
                        "[PythonPlugin]\nkrita_bridge=true\nkritapykrita_krita_bridge=true"
                    )
            else:
                content += "\n[PythonPlugin]\nkrita_bridge=true\nkritapykrita_krita_bridge=true\n"

            self.kritarc_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[KritaAdapter] Advertencia al actualizar kritarc: {e}")

    def clean_stale_locks(self):
        """Elimina archivos lockfile huérfanos de QtSingleApplication que impiden abrir Krita."""
        try:
            for lock in self.temp_dir.glob("qtsingleapp-Krita*-lockfile"):
                lock.unlink(missing_ok=True)
        except Exception:
            pass

    def is_running(self) -> bool:
        """Verifica si el servidor daemon de Krita está activo y responde."""
        try:
            r = httpx.get(f"{self.base_url}/api/status", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    def launch(self) -> bool:
        """Inicia Krita en segundo plano."""
        if self.is_running():
            return True

        if not self.is_plugin_installed():
            self.install_plugin()

        if not KRITA_EXE_PATH.exists():
            raise FileNotFoundError(f"Krita no encontrado en: {KRITA_EXE_PATH}")

        # Limpiar bloqueos residuales de sesiones anteriores cerradas incorrectamente
        self.clean_stale_locks()

        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [str(KRITA_EXE_PATH)],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )

        # Krita puede tardar 10-25 segundos en inicializar la interfaz gráfica y los plugins
        for _ in range(35):
            time.sleep(1)
            if self.is_running():
                return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Consulta el estado del motor Krita y si tiene un lienzo abierto."""
        try:
            r = httpx.get(f"{self.base_url}/api/status", timeout=3.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": f"Krita no responde en {self.base_url}: {e}"}

    def get_document_info(self) -> Dict[str, Any]:
        """Obtiene detalles completos del lienzo activo (medidas, capas, resolución)."""
        try:
            r = httpx.get(f"{self.base_url}/api/document_info", timeout=3.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": f"Error al consultar documento: {e}"}

    def create_document(
        self,
        width: int = 1920,
        height: int = 1080,
        name: str = "Lienzo AI",
        dpi: int = 300,
        color_model: str = "RGBA",
    ) -> Dict[str, Any]:
        """Crea un nuevo documento de dibujo en blanco en Krita."""
        payload = {
            "width": width,
            "height": height,
            "name": name,
            "dpi": dpi,
            "color_model": color_model,
        }
        try:
            r = httpx.post(f"{self.base_url}/api/create_document", json=payload, timeout=5.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_layer(self, file_path: str, layer_name: Optional[str] = None) -> Dict[str, Any]:
        """Importa una imagen externa como nueva capa en Krita."""
        payload = {
            "file_path": str(Path(file_path).resolve()),
            "layer_name": layer_name or Path(file_path).name,
        }
        try:
            r = httpx.post(f"{self.base_url}/api/import_layer", json=payload, timeout=5.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def add_layer(self, name: str = "Capa AI", layer_type: str = "paintLayer") -> Dict[str, Any]:
        """Añade una nueva capa vacía en el documento activo."""
        payload = {"name": name, "type": layer_type}
        try:
            r = httpx.post(f"{self.base_url}/api/add_layer", json=payload, timeout=5.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def export_canvas(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Exporta el lienzo activo de Krita a disco (PNG, JPG, PSD)."""
        if not output_path:
            output_path = str(OUTPUT_DIR / f"krita_export_{int(time.time())}.png")

        payload = {"output_path": str(Path(output_path).resolve())}
        try:
            r = httpx.post(f"{self.base_url}/api/export", json=payload, timeout=10.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def trigger_action(self, action_name: str) -> Dict[str, Any]:
        """Dispara una acción nativa de Krita (deshacer, rehacer, invertir, etc.)."""
        payload = {"action_name": action_name}
        try:
            r = httpx.post(f"{self.base_url}/api/trigger_action", json=payload, timeout=5.0)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
