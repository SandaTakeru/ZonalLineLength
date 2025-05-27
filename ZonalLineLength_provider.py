# -*- coding: utf-8 -*-

__author__ = 'Sanda Takeru'
__date__ = '2025-05-26'
__copyright__ = '(C) 2025 by Sanda Takeru'
__revision__ = '$Format:%H$'

from pathlib import Path
from PyQt5.QtGui import QIcon
from qgis.core import QgsProcessingProvider
from .ZonalLineLength_algorithm import ZonalLineLengthAlgorithm


class ZonalLineLengthProvider(QgsProcessingProvider):

    def __init__(self):
        QgsProcessingProvider.__init__(self)

    def unload(self):
        pass

    def loadAlgorithms(self):
        self.addAlgorithm(ZonalLineLengthAlgorithm())

    def id(self):
        return 'Zonal Line Length'

    def name(self):
        return self.tr('Zonal Line Length')

    def icon(self):
        path = (Path(__file__).parent / "icon.svg").resolve()
        return QIcon(str(path))

    def longName(self):
        return self.name()
