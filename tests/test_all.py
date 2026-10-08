import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import (
    CHAMVA_EXE_PATH,
    CHAMVA_FFMPEG_PATH,
    KRITA_EXE_PATH,
    OUTPUT_DIR,
)
from adapters.chamva_adapter import ChamVaAdapter
from adapters.krita_adapter import KritaAdapter
from orchestrator import MultiAppOrchestrator


async def run_full_diagnostics():
    print("=" * 60)
    print("EJECUTANDO BATERÍA DE PRUEBAS DE INTEGRACIÓN")
    print("=" * 60)

    # Test 1: Config & Paths
    print("\n[TEST 1] Verificación de Rutas y Binarios:")
    assert CHAMVA_EXE_PATH.exists(), f"ChamVa no existe en: {CHAMVA_EXE_PATH}"
    print(f"  [OK] ChamVa ejecutable: {CHAMVA_EXE_PATH}")

    assert CHAMVA_FFMPEG_PATH.exists(), f"FFmpeg no existe en: {CHAMVA_FFMPEG_PATH}"
    print(f"  [OK] ChamVa FFmpeg: {CHAMVA_FFMPEG_PATH}")

    assert KRITA_EXE_PATH.exists(), f"Krita no existe en: {KRITA_EXE_PATH}"
    print(f"  [OK] Krita ejecutable: {KRITA_EXE_PATH}")

    # Test 2: FFmpeg direct test
    print("\n[TEST 2] Verificación de Motor FFmpeg de ChamVa:")
    chamva = ChamVaAdapter()
    ff_res = chamva.run_ffmpeg(["-version"])
    assert ff_res["status"] == "success", "FFmpeg falló al ejecutar -version"
    first_line = ff_res["stdout"].splitlines()[0] if ff_res["stdout"] else ""
    print(f"  [OK] Motor multimedia activo: {first_line}")

    # Test 3: Krita Plugin Installation
    print("\n[TEST 3] Verificación del Plugin de Krita (PyKrita):")
    krita = KritaAdapter()
    install_res = krita.install_plugin()
    assert install_res["status"] == "success"
    assert krita.is_plugin_installed(), "El plugin no está marcado como instalado"
    print(f"  [OK] Plugin KritaBridge instalado en: {krita.pykrita_dir}")
    print(f"  [OK] Activación en kritarc: completada")

    # Test 4: MCP Server tools check
    print("\n[TEST 4] Verificación de Herramientas MCP:")
    from server import server
    tools = await server.list_tools()
    assert len(tools) >= 20, f"Se esperaban al menos 20 herramientas, encontradas: {len(tools)}"
    print(f"  [OK] Total de herramientas MCP registradas: {len(tools)}")
    
    # Test 5: ChamVa CDP Launch and UI Snapshot
    print("\n[TEST 5] Verificación de ChamVa (Lanzamiento y Conexión CDP):")
    print("  Iniciando ChamVa con CDP port 9333...")
    started = chamva.launch()
    assert started, "No se pudo iniciar ChamVa con puerto CDP"
    print("  [OK] Puerto CDP 9333 escuchando.")

    page = await chamva.get_page()
    title = await page.title()
    url = page.url
    print(f"  [OK] Conexión CDP establecida con éxito. Título: '{title}', URL: {url}")

    shot = await chamva.take_screenshot("test_validation.png")
    assert Path(shot).exists(), "No se pudo generar la captura de pantalla"
    print(f"  [OK] Captura de verificación generada: {shot}")

    # Clean up connection
    await chamva.disconnect()
    print("  [OK] Desconexión segura de Playwright completada.")

    print("\n" + "=" * 60)
    print("TODAS LAS PRUEBAS COMPLETADAS SATISFACTORIAMENTE (5/5 PASADAS)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_full_diagnostics())
