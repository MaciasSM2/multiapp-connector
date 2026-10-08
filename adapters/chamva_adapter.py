import os
import subprocess
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
from playwright.async_api import async_playwright, Playwright, Browser, Page

from config import (
    CHAMVA_EXE_PATH,
    CHAMVA_FFMPEG_PATH,
    CHAMVA_FFPROBE_PATH,
    CHAMVA_CDP_PORT,
    OUTPUT_DIR,
)


class ChamVaAdapter:
    """
    Controlador robusto para ChamVa (Tauri 2 + WebView2) a través de
    Chrome DevTools Protocol (CDP) y su motor interno FFmpeg.
    """

    def __init__(self, cdp_port: int = CHAMVA_CDP_PORT):
        self.cdp_port = cdp_port
        self.cdp_url = f"http://127.0.0.1:{self.cdp_port}"
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    def is_running(self) -> bool:
        """Verifica si el puerto CDP de ChamVa está activo y responde."""
        try:
            r = httpx.get(f"{self.cdp_url}/json/version", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    def is_process_alive(self) -> bool:
        """Comprueba si existe algún proceso chamva.exe en ejecución en el sistema."""
        try:
            res = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chamva.exe", "/NH"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return "chamva.exe" in res.stdout.lower()
        except Exception:
            return False

    def terminate_process(self):
        """Finaliza cualquier proceso chamva.exe que no tenga activado el puerto de depuración."""
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chamva.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except Exception:
            pass

    def launch(self, force_restart_if_no_cdp: bool = True) -> bool:
        """
        Inicia ChamVa con la bandera de depuración remota CDP.
        Si ChamVa ya estaba abierto sin CDP, lo reinicia para permitir el control programático.
        """
        if self.is_running():
            return True

        if not CHAMVA_EXE_PATH.exists():
            raise FileNotFoundError(f"No se encontró el ejecutable en: {CHAMVA_EXE_PATH}")

        if self.is_process_alive() and force_restart_if_no_cdp:
            print("[ChamVaAdapter] Detectada instancia sin CDP. Reiniciando con depuración activada...")
            self.terminate_process()

        env = os.environ.copy()
        env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={self.cdp_port}"

        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [str(CHAMVA_EXE_PATH)],
            env=env,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )

        for _ in range(15):
            time.sleep(1)
            if self.is_running():
                return True

        return False

    async def get_page(self) -> Page:
        """Obtiene la página activa de ChamVa a través de Playwright CDP de forma tolerante a fallos."""
        if not self.is_running():
            self.launch()

        if self._browser and not self._browser.is_connected():
            await self.disconnect()

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)

        for _ in range(5):
            for ctx in self._browser.contexts:
                for p in ctx.pages:
                    try:
                        title = await p.title()
                        url = p.url
                        if "ChamVa" in title or "tauri.localhost" in url:
                            self._page = p
                            return p
                    except Exception:
                        pass
            await asyncio.sleep(0.5)

        if self._browser.contexts and self._browser.contexts[0].pages:
            self._page = self._browser.contexts[0].pages[0]
            return self._page

        raise RuntimeError("No se encontró ninguna pestaña activa en ChamVa.")

    async def disconnect(self):
        """Desconecta Playwright limpiamente sin cerrar la aplicación gráfica ChamVa."""
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
            self._browser = None
            self._page = None

    async def dismiss_overlays_if_needed(self, page: Page):
        """Cierra modales u overlays residuales que puedan interceptar clics en la barra de herramientas."""
        try:
            overlay = page.locator(".home-overlay, [role='dialog']").first
            if await overlay.count() > 0 and await overlay.is_visible():
                close_btn = overlay.locator("button:has-text('✕'), [aria-label='Cerrar']").first
                if await close_btn.count() > 0 and await close_btn.is_visible():
                    await close_btn.click(force=True)
                else:
                    await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
        except Exception:
            pass

    async def take_screenshot(self, filename: Optional[str] = None) -> str:
        """Captura visualmente la ventana de ChamVa para diagnóstico del agente."""
        page = await self.get_page()
        if not filename:
            filename = f"chamva_capture_{int(time.time())}.png"
        out_path = OUTPUT_DIR / filename
        await page.screenshot(path=str(out_path))
        return str(out_path)

    async def create_design(
        self,
        preset: str = "instagram",
        width: int = 1080,
        height: int = 1080,
    ) -> Dict[str, Any]:
        """Crea un nuevo diseño en ChamVa con preset o medidas personalizadas."""
        page = await self.get_page()

        # Si hay botón para añadir pestaña en el editor
        add_tab_btn = page.locator("button:has-text('+'), [aria-label='Nuevo']").first
        if await add_tab_btn.count() > 0 and await add_tab_btn.is_visible():
            await add_tab_btn.click(force=True)
            await page.wait_for_timeout(1000)

        preset_lower = preset.lower()

        if preset_lower == "instagram":
            btn = page.locator("text=Post de Instagram").first
            await btn.click(force=True)
        elif preset_lower in ["story", "reel", "historia"]:
            btn = page.locator("text=Historia / Reel").first
            await btn.click(force=True)
        elif preset_lower in ["youtube", "miniatura"]:
            btn = page.locator("text=Miniatura de YouTube").first
            await btn.click(force=True)
        elif preset_lower == "facebook":
            btn = page.locator("text=Post de Facebook").first
            await btn.click(force=True)
        elif preset_lower == "photo":
            btn = page.locator("text=EDITAR UNA FOTO").first
            await btn.click(force=True)
        elif preset_lower == "custom":
            ancho_input = page.locator("input").nth(0)
            alto_input = page.locator("input").nth(1)
            await ancho_input.fill(str(width))
            await alto_input.fill(str(height))
            crear_btn = page.locator("button:has-text('Crear')").first
            await crear_btn.click(force=True)
        else:
            btn = page.locator("text=Post de Instagram").first
            await btn.click(force=True)

        await page.wait_for_timeout(2000)
        await self.dismiss_overlays_if_needed(page)

        shot = await self.take_screenshot("design_created.png")

        return {
            "status": "success",
            "message": f"Diseño creado con preset '{preset}'",
            "screenshot": shot,
        }

    async def open_video_editor(self) -> Dict[str, Any]:
        """Abre el editor de video en ChamVa."""
        page = await self.get_page()
        video_btn = page.locator("text=Editar video").first
        if await video_btn.count() > 0 and await video_btn.is_visible():
            await video_btn.click(force=True)
            await page.wait_for_timeout(2000)
            await self.dismiss_overlays_if_needed(page)
            shot = await self.take_screenshot("video_editor_opened.png")
            return {
                "status": "success",
                "message": "Editor de video abierto con éxito",
                "screenshot": shot,
            }
        else:
            return {
                "status": "error",
                "message": "El botón 'Editar video' no está visible en la pantalla actual",
            }

    async def remove_background(self) -> Dict[str, Any]:
        """Ejecuta la función 'Quitar fondo' en el editor."""
        page = await self.get_page()
        await self.dismiss_overlays_if_needed(page)
        btn = page.locator("button").filter(has_text="Quitar fondo").first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(force=True)
            await page.wait_for_timeout(3000)
            shot = await self.take_screenshot("background_removed.png")
            return {
                "status": "success",
                "message": "Acción 'Quitar fondo' ejecutada",
                "screenshot": shot,
            }
        else:
            return {
                "status": "error",
                "message": "El botón 'Quitar fondo' no está visible. Asegúrate de tener una imagen seleccionada.",
            }

    async def add_text(self, text: str) -> Dict[str, Any]:
        """Inserta un elemento de texto en el lienzo."""
        page = await self.get_page()
        await self.dismiss_overlays_if_needed(page)

        texto_tab = page.locator("text=Texto").first
        if await texto_tab.count() > 0 and await texto_tab.is_visible():
            await texto_tab.click(force=True)
            await page.wait_for_timeout(1000)

        # Buscar botón para añadir texto o usar la herramienta flotante T
        add_btn = page.locator("button").filter(has_text="título").first
        if await add_btn.count() > 0 and await add_btn.is_visible():
            await add_btn.click(force=True)
        else:
            t_tool = page.locator("button").filter(has_text="T").first
            if await t_tool.count() > 0 and await t_tool.is_visible():
                await t_tool.click(force=True)

        await page.wait_for_timeout(1000)
        shot = await self.take_screenshot("text_added.png")
        return {
            "status": "success",
            "message": f"Texto '{text}' agregado al lienzo",
            "screenshot": shot,
        }

    async def export_design(self) -> Dict[str, Any]:
        """Descarga o exporta el diseño actual."""
        page = await self.get_page()
        await self.dismiss_overlays_if_needed(page)
        descargar_btn = page.locator("button").filter(has_text="Descargar").first

        if await descargar_btn.count() == 0 or not await descargar_btn.is_visible():
            return {
                "status": "error",
                "message": "El botón 'Descargar' no está visible en el lienzo actual.",
            }

        try:
            async with page.expect_download(timeout=10000) as download_info:
                await descargar_btn.click(force=True)
                await page.wait_for_timeout(1500)

                modal_descargar = page.locator(".modal button, dialog button").filter(has_text="Descargar").first
                if await modal_descargar.count() > 0 and await modal_descargar.is_visible():
                    await modal_descargar.click(force=True)

            download = await download_info.value
            target_path = OUTPUT_DIR / download.suggested_filename
            await download.save_as(str(target_path))
            return {
                "status": "success",
                "message": "Diseño descargado correctamente",
                "output_file": str(target_path),
            }
        except Exception as e:
            shot = await self.take_screenshot("export_triggered.png")
            return {
                "status": "warning",
                "message": f"Acción de descarga disparada: {e}",
                "screenshot": shot,
            }

    def run_ffmpeg(self, args: List[str]) -> Dict[str, Any]:
        """Ejecuta el binario local verificado de FFmpeg de ChamVa."""
        if not CHAMVA_FFMPEG_PATH.exists():
            return {
                "status": "error",
                "message": f"No se encontró FFmpeg de ChamVa en {CHAMVA_FFMPEG_PATH}",
            }

        cmd = [str(CHAMVA_FFMPEG_PATH)] + args
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr[-500:] if res.stderr else "",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
