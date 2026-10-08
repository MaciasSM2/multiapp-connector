import asyncio
import json
from typing import Optional, List
from mcp.server.mcpserver import MCPServer
from config import (
    SERVER_NAME,
    SERVER_VERSION,
    CHAMVA_EXE_PATH,
    CHAMVA_FFMPEG_PATH,
    KRITA_EXE_PATH,
    OUTPUT_DIR,
)
from adapters.chamva_adapter import ChamVaAdapter
from adapters.krita_adapter import KritaAdapter
from adapters.canva_adapter import CanvaAdapter
from orchestrator import MultiAppOrchestrator

# Inicializar servidor MCP y adaptadores
server = MCPServer(SERVER_NAME)
chamva = ChamVaAdapter()
krita = KritaAdapter()
canva = CanvaAdapter()
orchestrator = MultiAppOrchestrator(chamva=chamva, krita=krita)


# ==========================================
# 1. DIAGNÓSTICO Y ESTADO DEL SISTEMA
# ==========================================

@server.tool()
async def system_diagnostics() -> str:
    """Realiza un diagnóstico de las aplicaciones conectadas en el equipo (ChamVa, Krita, FFmpeg)."""
    chamva_installed = CHAMVA_EXE_PATH.exists()
    chamva_running = chamva.is_running()
    ffmpeg_installed = CHAMVA_FFMPEG_PATH.exists()
    krita_installed = KRITA_EXE_PATH.exists()
    krita_plugin_installed = krita.is_plugin_installed()
    krita_running = krita.is_running()

    diag = {
        "server": f"{SERVER_NAME} v{SERVER_VERSION}",
        "output_dir": str(OUTPUT_DIR),
        "apps": {
            "chamva": {
                "installed": chamva_installed,
                "path": str(CHAMVA_EXE_PATH),
                "running_cdp": chamva_running,
                "cdp_port": chamva.cdp_port,
            },
            "chamva_ffmpeg": {
                "installed": ffmpeg_installed,
                "path": str(CHAMVA_FFMPEG_PATH),
            },
            "krita": {
                "installed": krita_installed,
                "path": str(KRITA_EXE_PATH),
                "plugin_installed": krita_plugin_installed,
                "running_bridge": krita_running,
                "bridge_port": krita.port,
            },
        },
    }
    return json.dumps(diag, indent=2, ensure_ascii=False)


# ==========================================
# 2. HERRAMIENTAS DE CHAMVA
# ==========================================

@server.tool()
async def chamva_status() -> str:
    """Verifica si ChamVa está abierto y disponible para recibir comandos automáticos vía CDP."""
    running = chamva.is_running()
    return json.dumps({
        "running": running,
        "cdp_url": chamva.cdp_url,
        "message": "ChamVa está activo y listo para operar" if running else "ChamVa no está iniciado con CDP. Usa chamva_launch.",
    }, indent=2)


@server.tool()
async def chamva_launch() -> str:
    """Inicia ChamVa en segundo plano con el puerto de depuración remota CDP activado."""
    try:
        ok = chamva.launch()
        return json.dumps({
            "status": "success" if ok else "failed",
            "message": "ChamVa iniciado con depuración CDP" if ok else "No se pudo iniciar ChamVa",
            "cdp_url": chamva.cdp_url,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_screenshot() -> str:
    """Toma una captura de pantalla de la interfaz de ChamVa para verificar visualmente el estado actual."""
    try:
        shot_path = await chamva.take_screenshot()
        return json.dumps({
            "status": "success",
            "screenshot_path": shot_path,
            "message": "Captura guardada en el directorio de salida",
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_create_design(
    preset: str = "instagram",
    width: int = 1080,
    height: int = 1080,
) -> str:
    """
    Crea un nuevo diseño en ChamVa.
    - preset: 'instagram', 'story', 'reel', 'youtube', 'facebook', 'custom' o 'photo'.
    - width y height: Medidas en píxeles si se usa el preset 'custom'.
    """
    try:
        res = await chamva.create_design(preset=preset, width=width, height=height)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_open_video_editor() -> str:
    """Abre el editor de video en ChamVa."""
    try:
        res = await chamva.open_video_editor()
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_remove_background() -> str:
    """Ejecuta la herramienta nativa 'Quitar fondo' en el diseño activo de ChamVa."""
    try:
        res = await chamva.remove_background()
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_add_text(text: str) -> str:
    """Inserta un bloque de texto en el lienzo activo de ChamVa."""
    try:
        res = await chamva.add_text(text=text)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_export_design() -> str:
    """Descarga o exporta el diseño actual de ChamVa al disco local."""
    try:
        res = await chamva.export_design()
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def chamva_ffmpeg_execute(args: List[str]) -> str:
    """
    Ejecuta el motor FFmpeg verificado propio de ChamVa con argumentos en lista.
    Ejemplo de args: ["-i", "input.mp4", "-vn", "-acodec", "copy", "output.aac"]
    """
    try:
        res = chamva.run_ffmpeg(args)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ==========================================
# 3. HERRAMIENTAS DE KRITA
# ==========================================

@server.tool()
async def krita_status() -> str:
    """Verifica si Krita está abierto y si el plugin de comunicación KritaBridge está respondiendo."""
    running = krita.is_running()
    installed = krita.is_installed()
    plugin_installed = krita.is_plugin_installed()

    if running:
        info = krita.get_status()
        return json.dumps({
            "running": True,
            "bridge_url": krita.base_url,
            "details": info,
        }, indent=2, ensure_ascii=False)
    else:
        return json.dumps({
            "running": False,
            "krita_installed": installed,
            "plugin_installed": plugin_installed,
            "message": "Krita no está activo o no responde en el puerto 52150. Usa krita_launch.",
        }, indent=2, ensure_ascii=False)


@server.tool()
async def krita_launch() -> str:
    """Inicia Krita en segundo plano con el puente KritaBridge activo."""
    try:
        ok = krita.launch()
        return json.dumps({
            "status": "success" if ok else "failed",
            "message": "Krita iniciado y puente conectado" if ok else "No se pudo conectar con Krita tras el inicio",
            "bridge_url": krita.base_url,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@server.tool()
async def krita_document_info() -> str:
    """Obtiene información detallada del documento activo en Krita (capas, dimensiones, resolución)."""
    res = krita.get_document_info()
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
async def krita_create_document(
    width: int = 1920,
    height: int = 1080,
    name: str = "Lienzo AI",
    dpi: int = 300,
    color_model: str = "RGBA",
) -> str:
    """
    Crea un nuevo documento de dibujo en Krita.
    - width: Ancho en píxeles.
    - height: Alto en píxeles.
    - name: Nombre del documento.
    - dpi: Resolución en DPI.
    """
    res = krita.create_document(width=width, height=height, name=name, dpi=dpi, color_model=color_model)
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
async def krita_import_layer(file_path: str, layer_name: Optional[str] = None) -> str:
    """Importa un archivo de imagen existente como nueva capa dentro del documento activo en Krita."""
    res = krita.import_layer(file_path=file_path, layer_name=layer_name)
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
async def krita_add_layer(name: str = "Capa AI", layer_type: str = "paintLayer") -> str:
    """Añade una nueva capa vacía en el documento activo en Krita."""
    res = krita.add_layer(name=name, layer_type=layer_type)
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
async def krita_export_canvas(output_path: Optional[str] = None) -> str:
    """Exporta el lienzo activo de Krita a un archivo PNG, JPG o PSD en disco."""
    res = krita.export_canvas(output_path=output_path)
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
async def krita_trigger_action(action_name: str) -> str:
    """Dispara una acción nativa interna de Krita (ej: 'edit_undo', 'edit_redo', 'clear')."""
    res = krita.trigger_action(action_name=action_name)
    return json.dumps(res, indent=2, ensure_ascii=False)


# ==========================================
# 4. HERRAMIENTAS DE CANVA (CLOUD / WEB)
# ==========================================

@server.tool()
async def canva_open_session(url: str = "https://www.canva.com") -> str:
    """Abre Canva en el navegador con perfil persistente para diseño y maquetación web."""
    res = await canva.open_canva(url=url)
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
async def canva_upload_asset(file_path: str) -> str:
    """Sube un archivo multimedia local a la biblioteca de Canva."""
    res = await canva.upload_asset(file_path=file_path)
    return json.dumps(res, indent=2, ensure_ascii=False)


# ==========================================
# 5. PIPELINES Y FLUJOS CRUZADOS (MULTI-APP)
# ==========================================

@server.tool()
async def pipeline_image_to_krita(
    image_path: str,
    canvas_name: str = "Proyecto AI Integrado",
    width: int = 1920,
    height: int = 1080,
) -> str:
    """
    Flujo compuesto: Toma una imagen local, asegura Krita, crea un lienzo si no existe,
    e inyecta la imagen como capa base dejando una capa lista para dibujar encima.
    """
    res = await orchestrator.image_to_krita_canvas(
        image_path=image_path,
        canvas_name=canvas_name,
        width=width,
        height=height,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
def pipeline_video_trim(
    video_path: str,
    start_time: str = "00:00:00",
    duration: str = "00:00:10",
    output_filename: Optional[str] = None,
) -> str:
    """
    Flujo compuesto: Recorta un video a velocidad máxima sin pérdida de calidad
    empleando el motor FFmpeg verificado de ChamVa.
    """
    res = orchestrator.trim_video_fast(
        video_path=video_path,
        start_time=start_time,
        duration=duration,
        output_name=output_filename,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@server.tool()
def pipeline_video_frame_to_krita(
    video_path: str,
    timestamp: str = "00:00:01",
    send_to_krita: bool = True,
) -> str:
    """
    Flujo compuesto: Extrae un fotograma clave de video con ChamVa FFmpeg y lo envía
    automáticamente a Krita como capa de referencia para dibujo artístico.
    """
    res = orchestrator.extract_frame_for_drawing(
        video_path=video_path,
        timestamp=timestamp,
        send_to_krita=send_to_krita,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    server.run()
