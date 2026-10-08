import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

from config import OUTPUT_DIR
from adapters.chamva_adapter import ChamVaAdapter
from adapters.krita_adapter import KritaAdapter


class MultiAppOrchestrator:
    """
    Orquestador de flujos de trabajo cruzados entre ChamVa, Krita y Canva.
    Permite automatizar tareas compuestas donde múltiples herramientas colaboran en una misma obra.
    """

    def __init__(self, chamva: ChamVaAdapter, krita: KritaAdapter):
        self.chamva = chamva
        self.krita = krita

    async def image_to_krita_canvas(
        self,
        image_path: str,
        canvas_name: str = "Lienzo AI Compuesto",
        width: int = 1920,
        height: int = 1080,
        add_drawing_layer: bool = True,
    ) -> Dict[str, Any]:
        """
        Toma una imagen (por ejemplo generada o editada), asegura que Krita esté listo,
        crea un lienzo de dibujo y la inyecta como capa base con una capa de dibujo superior.
        """
        img = Path(image_path).resolve()
        if not img.exists():
            return {"status": "error", "message": f"Imagen no encontrada: {image_path}"}

        # 1. Asegurar Krita en ejecución
        if not self.krita.is_running():
            ok = self.krita.launch()
            if not ok:
                return {"status": "error", "message": "No se pudo iniciar Krita"}

        # 2. Verificar o crear documento en Krita
        doc_info = self.krita.get_document_info()
        if doc_info.get("status") != "success":
            create_res = self.krita.create_document(
                width=width,
                height=height,
                name=canvas_name,
                dpi=300,
            )
            if create_res.get("status") != "success":
                return {"status": "error", "message": f"Error al crear lienzo: {create_res}"}

        # 3. Importar la imagen como capa
        import_res = self.krita.import_layer(
            file_path=str(img),
            layer_name=f"Base_{img.stem}",
        )

        # 4. Crear capa transparente superior para dibujo
        if add_drawing_layer:
            self.krita.add_layer(name="Detalles y Pinceladas AI", layer_type="paintLayer")

        return {
            "status": "success",
            "message": "Imagen inyectada con éxito en el lienzo de Krita con capa de dibujo preparada",
            "image": str(img),
            "krita_import": import_res,
        }

    def trim_video_fast(
        self,
        video_path: str,
        start_time: str = "00:00:00",
        duration: str = "00:00:10",
        output_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recorta un video a velocidad máxima sin pérdida de calidad (stream copy)
        utilizando el motor FFmpeg verificado de ChamVa.
        """
        src = Path(video_path).resolve()
        if not src.exists():
            return {"status": "error", "message": f"Video no encontrado: {video_path}"}

        if not output_name:
            output_name = f"trim_{src.stem}_{int(time.time())}{src.suffix}"

        out_file = OUTPUT_DIR / output_name

        args = [
            "-ss", start_time,
            "-i", str(src),
            "-t", duration,
            "-c", "copy",
            "-y",
            str(out_file),
        ]

        res = self.chamva.run_ffmpeg(args)
        if res.get("status") == "success":
            return {
                "status": "success",
                "output_video": str(out_file),
                "message": f"Video recortado con éxito en {out_file.name}",
            }
        else:
            return {"status": "error", "message": f"FFmpeg falló: {res.get('stderr')}"}

    def extract_frame_for_drawing(
        self,
        video_path: str,
        timestamp: str = "00:00:01",
        output_name: Optional[str] = None,
        send_to_krita: bool = True,
    ) -> Dict[str, Any]:
        """
        Extrae un fotograma clave de un video con el motor de ChamVa y
        opcionalmente lo inyecta directo en Krita como referencia de dibujo.
        """
        src = Path(video_path).resolve()
        if not src.exists():
            return {"status": "error", "message": f"Video no encontrado: {video_path}"}

        if not output_name:
            output_name = f"frame_{src.stem}_{int(time.time())}.png"

        frame_file = OUTPUT_DIR / output_name

        args = [
            "-ss", timestamp,
            "-i", str(src),
            "-vframes", "1",
            "-q:v", "2",
            "-y",
            str(frame_file),
        ]

        res = self.chamva.run_ffmpeg(args)
        if res.get("status") != "success":
            return {"status": "error", "message": f"Error al extraer fotograma: {res.get('stderr')}"}

        krita_info = None
        if send_to_krita:
            # Si Krita está disponible, inyectarlo como capa de referencia
            if not self.krita.is_running():
                self.krita.launch()

            doc_info = self.krita.get_document_info()
            if doc_info.get("status") != "success":
                self.krita.create_document(name=f"Referencia_{src.stem}")

            krita_info = self.krita.import_layer(
                file_path=str(frame_file),
                layer_name=f"Referencia_Video_{timestamp}",
            )
            self.krita.add_layer(name="Boceto y Lineart")

        return {
            "status": "success",
            "frame_path": str(frame_file),
            "sent_to_krita": send_to_krita,
            "krita_result": krita_info,
        }
