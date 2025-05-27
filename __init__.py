# -*- coding: utf-8 -*-
__author__ = 'Sanda Takeru'
__date__ = '2025-05-26'
__copyright__ = '(C) 2025 by Sanda Takeru'

import os
from qgis.PyQt.QtCore import QCoreApplication, QTranslator

def classFactory(iface):
    from .ZonalLineLength import ZonalLineLength
    # --- Fix translation loader for QGIS 3.x ---
    app = QCoreApplication.instance()
    locale = app.property("locale") if app is not None else None
    if locale is None:
        locale = "en"
    else:
        locale = str(locale)
    plugin_dir = os.path.dirname(__file__)
    i18n_path = os.path.join(plugin_dir, 'i18n', f'ZonalLineLength_{locale}.qm')
    if os.path.exists(i18n_path):
        translator = QTranslator()
        translator.load(i18n_path)
        QCoreApplication.installTranslator(translator)
    # --- End translation loader ---
    return ZonalLineLength(iface)
