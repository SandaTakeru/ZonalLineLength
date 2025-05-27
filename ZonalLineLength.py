# -*- coding: utf-8 -*-

__author__ = 'Sanda Takeru'
__date__ = '2025-05-26'
__copyright__ = '(C) 2025 by Sanda Takeru'
__revision__ = '$Format:%H$'

import os
import sys
import inspect

from qgis.core import QgsProcessingAlgorithm, QgsApplication
from .ZonalLineLength_provider import ZonalLineLengthProvider

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

class ZonalLineLength(object):

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = ZonalLineLengthProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        
    def unloadGui(self):
        """Unload the GUI components."""
        self.unload()
        self.provider = None
