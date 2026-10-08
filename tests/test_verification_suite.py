import asyncio
import os
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

# Add workspace to path
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from config import (
    CHAMVA_EXE_PATH,
    CHAMVA_FFMPEG_PATH,
    KRITA_EXE_PATH,
    OUTPUT_DIR,
)
from adapters.chamva_adapter import ChamVaAdapter
from adapters.krita_adapter import KritaAdapter
from adapters.canva_adapter import CanvaAdapter
from orchestrator import MultiAppOrchestrator
from server import server


async def run_audit():
    print("=" * 70)
    print("AUDITORÍA INTEGRAL DE VERIFICACIÓN Y PRUEBAS EN VIVO")
    print("=" * 70)

    results = {}

    # -------------------------------------------------------------
    # 1. VERIFICACIÓN DE CHAMVA
    # -------------------------------------------------------------
    print("\n[MÓDULO 1] Verificación de ChamVa (Tauri 2 / WebView2 + FFmpeg)...")
    chamva = ChamVaAdapter()
    
    # 1.1 Existencia binarios
    b_ok = CHAMVA_EXE_PATH.exists() and CHAMVA_FFMPEG_PATH.exists()
    results["chamva_binaries"] = b_ok
    print(f"  1.1 Binarios locales presentes: {'PASS' if b_ok else 'FAIL'}")

    # 1.2 FFmpeg propio
    ff_res = chamva.run_ffmpeg(["-version"])
    ff_ok = ff_res.get("status") == "success" and "chamva" in ff_res.get("stdout", "").lower()
    results["chamva_ffmpeg"] = ff_ok
    print(f"  1.2 Motor multimedia verificado FFmpeg: {'PASS' if ff_ok else 'FAIL'}")

    # 1.3 Lanzamiento y CDP
    started = chamva.launch()
    results["chamva_launch_cdp"] = started
    print(f"  1.3 Lanzamiento y canal CDP (puerto 9333): {'PASS' if started else 'FAIL'}")

    # 1.4 Creación de diseño
    design_res = await chamva.create_design("instagram")
    d_ok = design_res.get("status") == "success"
    results["chamva_create_design"] = d_ok
    print(f"  1.4 Creación de lienzo Instagram (1080x1080): {'PASS' if d_ok else 'FAIL'}")

    # 1.5 Inserción de texto
    text_res = await chamva.add_text("Auditoria Antigravity")
    t_ok = text_res.get("status") == "success"
    results["chamva_add_text"] = t_ok
    print(f"  1.5 Inserción de elemento tipográfico: {'PASS' if t_ok else 'FAIL'}")

    # 1.6 Captura de pantalla
    shot = await chamva.take_screenshot("audit_chamva_screen.png")
    shot_ok = Path(shot).exists() and Path(shot).stat().st_size > 1000
    results["chamva_screenshot"] = shot_ok
    print(f"  1.6 Captura visual de pantalla: {'PASS' if shot_ok else 'FAIL'} ({Path(shot).stat().st_size} bytes)")

    await chamva.disconnect()

    # -------------------------------------------------------------
    # 2. VERIFICACIÓN DE KRITA
    # -------------------------------------------------------------
    print("\n[MÓDULO 2] Verificación de Krita (Desktop & PyKrita)...")
    krita = KritaAdapter()

    k_inst = krita.is_installed()
    results["krita_installed"] = k_inst
    print(f"  2.1 Binario Krita 5.3 presente: {'PASS' if k_inst else 'FAIL'}")

    p_inst = krita.is_plugin_installed()
    results["krita_plugin_installed"] = p_inst
    print(f"  2.2 Plugin KritaBridge en PyKrita (%APPDATA%): {'PASS' if p_inst else 'FAIL'}")

    # Verificar sintaxis del plugin
    plugin_path = krita.pykrita_dir / "krita_bridge" / "krita_bridge.py"
    try:
        compile(plugin_path.read_text(encoding="utf-8"), str(plugin_path), "exec")
        p_syntax = True
    except Exception as e:
        p_syntax = False
        print(f"      Error de compilación en plugin: {e}")
    results["krita_plugin_syntax"] = p_syntax
    print(f"  2.3 Sintaxis y compilación del plugin: {'PASS' if p_syntax else 'FAIL'}")

    # -------------------------------------------------------------
    # 3. VERIFICACIÓN DE PIPELINES MULTI-APP
    # -------------------------------------------------------------
    print("\n[MÓDULO 3] Verificación de Pipelines Cruzados y FFmpeg...")
    orch = MultiAppOrchestrator(chamva=chamva, krita=krita)

    # 3.1 Generar video de prueba sintético con FFmpeg de ChamVa (usando MediaFoundation h264_mf)
    test_video_path = OUTPUT_DIR / "test_synthetic.mp4"
    gen_video_args = [
        "-f", "lavfi",
        "-i", "testsrc=duration=3:size=640x360:rate=30",
        "-c:v", "h264_mf",
        "-pix_fmt", "yuv420p",
        "-y",
        str(test_video_path)
    ]
    gen_res = chamva.run_ffmpeg(gen_video_args)
    v_created = test_video_path.exists() and test_video_path.stat().st_size > 500
    results["pipeline_create_test_video"] = v_created
    print(f"  3.1 Generación de video de prueba con FFmpeg: {'PASS' if v_created else 'FAIL'}")

    # 3.2 Recorte rápido de video (pipeline_video_trim)
    trim_res = orch.trim_video_fast(str(test_video_path), start_time="00:00:00", duration="00:00:01", output_name="test_trimmed.mp4")
    trim_ok = trim_res.get("status") == "success" and Path(trim_res.get("output_video", "")).exists()
    results["pipeline_video_trim"] = trim_ok
    print(f"  3.2 Recorte de video ultrarrápido (stream-copy): {'PASS' if trim_ok else 'FAIL'}")

    # 3.3 Extracción de fotograma para dibujo
    frame_res = orch.extract_frame_for_drawing(str(test_video_path), timestamp="00:00:01", output_name="test_extracted_frame.png", send_to_krita=False)
    frame_ok = frame_res.get("status") == "success" and Path(frame_res.get("frame_path", "")).exists()
    results["pipeline_frame_extraction"] = frame_ok
    print(f"  3.3 Extracción de fotograma como referencia: {'PASS' if frame_ok else 'FAIL'}")

    # -------------------------------------------------------------
    # 4. VERIFICACIÓN DEL SERVIDOR MCP
    # -------------------------------------------------------------
    print("\n[MÓDULO 4] Verificación de Servidor MCP (Protocolo 2.x)...")
    tools = await server.list_tools()
    tool_count = len(tools)
    mcp_ok = tool_count >= 20
    results["mcp_tools_registered"] = mcp_ok
    print(f"  4.1 Catálogo de herramientas registradas: {'PASS' if mcp_ok else 'FAIL'} ({tool_count} herramientas)")

    # Test tool call: system_diagnostics
    from server import system_diagnostics
    diag_json = await system_diagnostics()
    diag_ok = "multiapp-connector" in diag_json
    results["mcp_tool_execution"] = diag_ok
    print(f"  4.2 Ejecución de herramienta nativa (system_diagnostics): {'PASS' if diag_ok else 'FAIL'}")

    # -------------------------------------------------------------
    # 5. RESUMEN GLOBAL
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("RESUMEN DE RESULTADOS DE AUDITORÍA:")
    print("=" * 70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for k, v in results.items():
        status_str = "PASS [OK]" if v else "FAIL [XX]"
        print(f"  - {k.ljust(35)}: {status_str}")

    print("-" * 70)
    print(f"TOTAL: {passed}/{total} PRUEBAS EXITOSAS ({int(passed/total*100)}%)")
    print("=" * 70)

    return results


if __name__ == "__main__":
    asyncio.run(run_audit())
