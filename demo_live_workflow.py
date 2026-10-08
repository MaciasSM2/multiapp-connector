import asyncio
import time
from pathlib import Path
from PIL import Image, ImageDraw

from config import OUTPUT_DIR
from adapters.chamva_adapter import ChamVaAdapter
from adapters.krita_adapter import KritaAdapter
from orchestrator import MultiAppOrchestrator


def generate_sample_graphic() -> Path:
    """Genera un archivo de imagen de muestra para el flujo de prueba."""
    img_path = OUTPUT_DIR / "sample_character.png"
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dibujar figura estilizada (círculo y trazos)
    draw.ellipse([100, 100, 412, 412], fill=(70, 130, 240, 255), outline=(255, 255, 255, 255), width=8)
    draw.polygon([(256, 150), (350, 320), (162, 320)], fill=(255, 215, 0, 255))
    draw.rectangle([200, 350, 312, 380], fill=(240, 80, 80, 255))

    img.save(img_path)
    return img_path


async def run_live_demonstration():
    print("=" * 65)
    print("DEMOSTRACIÓN EN VIVO: FLUJO INTEGRADO MULTI-APLICATIVO")
    print("=" * 65)

    # 1. Generar activo gráfico
    sample_img = generate_sample_graphic()
    print(f"\n[PASO 1] Gráfico de prueba generado: {sample_img}")

    # 2. Inicializar adaptadores
    chamva = ChamVaAdapter()
    krita = KritaAdapter()
    orch = MultiAppOrchestrator(chamva=chamva, krita=krita)

    # 3. ChamVa: Lanzamiento y creación de diseño
    print("\n[PASO 2] Conectando con ChamVa (Tauri 2 / CDP)...")
    chamva.launch()
    print("  Creando nuevo diseño (Post de Instagram 1080x1080)...")
    design_res = await chamva.create_design(preset="instagram")
    print(f"  [OK] Lienzo creado en ChamVa: {design_res.get('status')}")

    # 4. ChamVa: Agregar texto al diseño
    print("\n[PASO 3] Insertando tipografía en el lienzo de ChamVa...")
    text_res = await chamva.add_text("Conector AI Activo")
    print(f"  [OK] Texto agregado: {text_res.get('status')}")

    # 5. Captura visual de verificación
    shot_path = await chamva.take_screenshot("demo_chamva_final.png")
    print(f"  [OK] Captura de ChamVa registrada en: {shot_path}")

    await chamva.disconnect()

    # 6. Krita: Inyección en lienzo de arte y capas
    print("\n[PASO 4] Orquestando con Krita (PyKrita)...")
    print(f"  Inyectando el activo en Krita como capa base con capa de dibujo superior...")
    krita_res = await orch.image_to_krita_canvas(
        image_path=str(sample_img),
        canvas_name="Demostración ChamVa & Krita",
        width=1080,
        height=1080,
    )
    print(f"  [OK] Estado del pipeline hacia Krita: {krita_res.get('status')}")

    print("\n" + "=" * 65)
    print("¡FLUJO DEMOSTRATIVO FINALIZADO EXITOSAMENTE!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_live_demonstration())
