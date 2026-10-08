from krita import Krita
from .krita_bridge import KritaBridgeExtension

app = Krita.instance()
ext = KritaBridgeExtension(parent=app)

try:
    # Registra con Scripter si está disponible globalmente
    Scripter.addExtension(ext)
except Exception:
    pass

try:
    # Registra con la instancia de Krita
    app.addExtension(ext)
except Exception:
    pass
