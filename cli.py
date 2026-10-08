import argparse
import asyncio
import json
import sys
from pathlib import Path

from config import OUTPUT_DIR
from adapters.chamva_adapter import ChamVaAdapter
from adapters.krita_adapter import KritaAdapter
from orchestrator import MultiAppOrchestrator


async def main_async():
    parser = argparse.ArgumentParser(
        description="CLI de control directo para el Conector Multi-Aplicativos (ChamVa, Krita, Canva)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Status
    subparsers.add_parser("status", help="Muestra el diagnóstico de ChamVa, Krita y FFmpeg")

    # ChamVa commands
    subparsers.add_parser("chamva-launch", help="Inicia ChamVa con el puerto de depuración CDP")
    subparsers.add_parser("chamva-shot", help="Captura la pantalla de ChamVa y guarda el archivo PNG")

    chamva_design = subparsers.add_parser("chamva-design", help="Crea un nuevo diseño en ChamVa")
    chamva_design.add_argument("--preset", default="instagram", help="instagram, story, youtube, custom, etc.")
    chamva_design.add_argument("--width", type=int, default=1080, help="Ancho si se usa custom")
    chamva_design.add_argument("--height", type=int, default=1080, help="Alto si se usa custom")

    chamva_text = subparsers.add_parser("chamva-text", help="Inserta un texto en el lienzo de ChamVa")
    chamva_text.add_argument("text", help="Contenido del texto")

    subparsers.add_parser("chamva-video", help="Abre el editor de video en ChamVa")

    # Krita commands
    subparsers.add_parser("krita-install-plugin", help="Instala y activa el plugin KritaBridge en PyKrita")
    subparsers.add_parser("krita-launch", help="Inicia Krita con el puente activo")

    krita_canvas = subparsers.add_parser("krita-canvas", help="Crea un nuevo lienzo de dibujo en Krita")
    krita_canvas.add_argument("--name", default="Lienzo AI", help="Nombre del lienzo")
    krita_canvas.add_argument("--width", type=int, default=1920, help="Ancho en px")
    krita_canvas.add_argument("--height", type=int, default=1080, help="Alto en px")
    krita_canvas.add_argument("--dpi", type=int, default=300, help="Resolución en DPI")

    krita_import = subparsers.add_parser("krita-import", help="Importa una imagen como capa en Krita")
    krita_import.add_argument("image_path", help="Ruta de la imagen")
    krita_import.add_argument("--layer-name", default=None, help="Nombre de la capa")

    # Pipeline commands
    pipe_to_krita = subparsers.add_parser("pipe-to-krita", help="Prepara lienzo e inyecta imagen en Krita")
    pipe_to_krita.add_argument("image_path", help="Ruta de la imagen a inyectar")

    pipe_trim = subparsers.add_parser("video-trim", help="Recorta video ultrarrápido con FFmpeg de ChamVa")
    pipe_trim.add_argument("video_path", help="Ruta del video")
    pipe_trim.add_argument("--start", default="00:00:00", help="Tiempo de inicio (HH:MM:SS)")
    pipe_trim.add_argument("--duration", default="00:00:10", help="Duración (HH:MM:SS)")

    args = parser.parse_args()

    chamva = ChamVaAdapter()
    krita = KritaAdapter()
    orch = MultiAppOrchestrator(chamva=chamva, krita=krita)

    if args.command == "status":
        from config import CHAMVA_EXE_PATH
        info = {
            "chamva": {
                "installed": CHAMVA_EXE_PATH.exists(),
                "running": chamva.is_process_alive(),
                "running_cdp": chamva.is_running(),
            },
            "krita": {
                "installed": krita.is_installed(),
                "plugin_installed": krita.is_plugin_installed(),
                "running": krita.is_running(),
            },
        }
        print(json.dumps(info, indent=2, ensure_ascii=False))

    elif args.command == "chamva-launch":
        ok = chamva.launch()
        print("ChamVa lanzado con éxito." if ok else "Error al iniciar ChamVa.")

    elif args.command == "chamva-shot":
        shot = await chamva.take_screenshot()
        print(f"Captura guardada en: {shot}")

    elif args.command == "chamva-design":
        res = await chamva.create_design(preset=args.preset, width=args.width, height=args.height)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "chamva-text":
        res = await chamva.add_text(args.text)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "chamva-video":
        res = await chamva.open_video_editor()
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "krita-install-plugin":
        res = krita.install_plugin()
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "krita-launch":
        ok = krita.launch()
        print("Krita lanzado con éxito." if ok else "Error al iniciar Krita.")

    elif args.command == "krita-canvas":
        res = krita.create_document(width=args.width, height=args.height, name=args.name, dpi=args.dpi)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "krita-import":
        res = krita.import_layer(file_path=args.image_path, layer_name=args.layer_name)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "pipe-to-krita":
        res = await orch.image_to_krita_canvas(image_path=args.image_path)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "video-trim":
        res = orch.trim_video_fast(video_path=args.video_path, start_time=args.start, duration=args.duration)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    else:
        parser.print_help()

    await chamva.disconnect()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
