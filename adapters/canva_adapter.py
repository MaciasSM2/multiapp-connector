import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page

from config import OUTPUT_DIR, WORKSPACE_DIR


class CanvaAdapter:
    """
    Controlador para Canva Web utilizando Playwright con soporte para perfil persistente.
    Permite abrir diseños, interactuar con el editor y descargar composiciones.
    """

    def __init__(self, user_data_dir: Optional[Path] = None):
        self.user_data_dir = user_data_dir or (WORKSPACE_DIR / ".canva_profile")
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def get_page(self) -> Page:
        """Inicia o reutiliza la sesión del navegador para Canva."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._context is None:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            )

        if not self._context.pages:
            self._page = await self._context.new_page()
        else:
            self._page = self._context.pages[0]

        return self._page

    async def open_canva(self, url: str = "https://www.canva.com") -> Dict[str, Any]:
        """Abre Canva o una URL específica de un diseño."""
        try:
            page = await self.get_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            title = await page.title()

            shot_path = OUTPUT_DIR / "canva_session.png"
            await page.screenshot(path=str(shot_path))

            return {
                "status": "success",
                "title": title,
                "url": page.url,
                "screenshot": str(shot_path),
            }
        except Exception as e:
            return {"status": "error", "message": f"Error al abrir Canva: {e}"}

    async def upload_asset(self, file_path: str) -> Dict[str, Any]:
        """Sube un archivo de imagen o video al panel de subidos de Canva."""
        path_obj = Path(file_path).resolve()
        if not path_obj.exists():
            return {"status": "error", "message": f"Archivo no encontrado: {file_path}"}

        try:
            page = await self.get_page()
            # Buscar botón o pestaña de subidos en Canva
            upload_tab = page.locator("[data-testid='side-nav-uploads-button'], button:has-text('Subidos'), button:has-text('Uploads')").first
            if await upload_tab.is_visible():
                await upload_tab.click()
                await page.wait_for_timeout(1000)

            # Usar selector de archivos
            file_input = page.locator("input[type='file']").first
            if await file_input.count() > 0:
                await file_input.set_input_files(str(path_obj))
                await page.wait_for_timeout(3000)
                return {"status": "success", "message": f"Archivo {path_obj.name} cargado en Canva"}
            else:
                return {"status": "warning", "message": "No se localizó el input de subida de archivos en Canva"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def close_session(self):
        """Cierra el navegador de Canva."""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
