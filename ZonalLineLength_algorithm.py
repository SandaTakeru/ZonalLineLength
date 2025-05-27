# -*- coding: utf-8 -*-

__author__ = 'Sanda Takeru'
__date__ = '2025-05-26'
__copyright__ = '(C) 2025 by Sanda Takeru'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QVariant, QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsField,
    QgsProcessingException
)
import processing

class ZonalLineLengthAlgorithm(QgsProcessingAlgorithm):
    POLYGON = 'POLYGON'
    LINE = 'LINE'
    POLYGON_ID = 'POLYGON_ID'
    OUTPUT = 'OUTPUT'

    def tr(self, text):
        return QCoreApplication.translate('ZonalLineLengthAlgorithm', text)

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LINE,
                self.tr('Line layer to summarize'),
                [QgsProcessing.TypeVectorLine]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POLYGON,
                self.tr('Reference polygon layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.POLYGON_ID,
                self.tr('Polygon layer identifier field'),
                parentLayerParameterName=self.POLYGON,
                type=QgsProcessingParameterField.Any
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                'STATS',
                self.tr('Statistics to calculate'),
                options=[
                    self.tr('Sum'),
                    self.tr('Count'),
                    self.tr('Mean'),
                    self.tr('Median'),
                    self.tr('Minimum'),
                    self.tr('Maximum'),
                    self.tr('Standard deviation')
                ],
                allowMultiple=True,
                defaultValue=[0]  # Default: Sum
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                'LENGTH_THRESHOLD',
                self.tr('Minimum total_length to keep (set 0 or blank to keep all)'),
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                minValue=0.0,
                defaultValue=0.01
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output line layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        polygon_source = self.parameterAsSource(parameters, self.POLYGON, context)
        line_source = self.parameterAsSource(parameters, self.LINE, context)
        polygon_id_field = self.parameterAsFields(parameters, self.POLYGON_ID, context)[0]

        if polygon_source is None or line_source is None:
            raise QgsProcessingException('Could not get input layer(s)')
        if polygon_id_field is None:
            raise QgsProcessingException(self.tr('Polygon identifier field is not set or does not exist in the polygon layer.'))
        if polygon_source.featureCount() == 0:
            raise QgsProcessingException(self.tr('Polygon layer is empty. Please provide a valid polygon layer.'))
        if line_source.featureCount() == 0:
            raise QgsProcessingException(self.tr('Line layer is empty. Please provide a valid line layer.'))

        # layer validity checks
        polygon_layer = self.parameterAsVectorLayer(parameters, self.POLYGON, context)
        line_layer = self.parameterAsVectorLayer(parameters, self.LINE, context)
        if polygon_layer is None or not polygon_layer.isValid():
            raise QgsProcessingException(self.tr('Invalid polygon layer. Please check the layer.'))
        if line_layer is None or not line_layer.isValid():
            raise QgsProcessingException(self.tr('Invalid line layer. Please check the layer.'))

        # CRS check
        polygon_crs = polygon_source.sourceCrs()
        line_crs = line_source.sourceCrs()
        if not polygon_crs.isValid() or not line_crs.isValid():
            raise QgsProcessingException(self.tr('Invalid CRS for input layer(s). Please check the layers.'))
        if polygon_crs.isGeographic():
            raise QgsProcessingException(self.tr('Reference polygon layer CRS is not projected. Please use a projected CRS.'))
        if line_crs.isGeographic():
            raise QgsProcessingException(self.tr('Line layer CRS is not projected. Please use a projected CRS.'))
        if polygon_crs != line_crs:
            feedback.reportError(self.tr('Warning: The CRS of the polygon layer and the line layer are different. Processing will continue, but results may be unreliable.'))

        # polygon_id_field check
        if polygon_id_field not in polygon_source.fields().names():
            raise QgsProcessingException(self.tr('Polygon identifier field does not exist in the polygon layer. Please select a valid field.'))

        # Get ID field type
        id_field_obj = polygon_source.fields().field(polygon_id_field)
        id_field_type = id_field_obj.type()

        # 1. Intersection
        feedback.pushInfo('Extracting intersection...')
        try:
            intersection_result = processing.run(
                "native:intersection",
                {
                    'INPUT': parameters[self.LINE],
                    'OVERLAY': parameters[self.POLYGON],
                    'INPUT_FIELDS': [],
                    'OVERLAY_FIELDS': [polygon_id_field],
                    'OUTPUT': 'memory:intersected'
                },
                context=context, feedback=feedback, is_child_algorithm=True
            )
        except Exception as e:
            feedback.reportError(f"Intersection failed: {e}")
            raise QgsProcessingException(f"Intersection failed: {e}")

        # Check for intersection errors in the result
        intersected_layer = self.parameterAsVectorLayer(intersection_result, 'OUTPUT', context)
        if intersected_layer is None or intersected_layer.featureCount() == 0:
            feedback.reportError("No intersection features were created. Please check input data for geometry or attribute issues.")
            raise QgsProcessingException("No intersection features were created. Please check input data for geometry or attribute issues.")

        # Remove features outside polygons (i.e., where intersection geometry is empty or null)
        feedback.pushInfo('Filtering out features outside polygons...')
        from qgis.core import QgsVectorLayer, QgsFeature, QgsWkbTypes
        fields = intersected_layer.fields()
        crs = intersected_layer.sourceCrs()
        wkb_type = intersected_layer.wkbType()
        filtered_intersected = QgsVectorLayer(QgsWkbTypes.displayString(wkb_type) + f"?crs={crs.authid()}", "filtered_intersected", "memory")
        filtered_intersected_data = filtered_intersected.dataProvider()
        filtered_intersected_data.addAttributes(fields)
        filtered_intersected.updateFields()
        for feat in intersected_layer.getFeatures():
            geom = feat.geometry()
            if geom is not None and not geom.isEmpty():
                filtered_intersected_data.addFeature(feat)
        filtered_intersected.updateExtents()

        # Use filtered_intersected for subsequent processing
        intersected_layer = filtered_intersected

        # 2. Calculate line length
        feedback.pushInfo('Adding length field...')
        length_field = 'length_m'
        intersected_layer.startEditing()
        if length_field not in [f.name() for f in intersected_layer.fields()]:
            intersected_layer.dataProvider().addAttributes([QgsField(length_field, QVariant.Double)])
            intersected_layer.updateFields()
        idx = intersected_layer.fields().indexFromName(length_field)
        for feat in intersected_layer.getFeatures():
            geom = feat.geometry()
            feat[length_field] = geom.length()
            intersected_layer.updateFeature(feat)
        intersected_layer.commitChanges()

        # 3. Aggregate length by polygon ID
        feedback.pushInfo('Aggregating length...')
        stats_choices = parameters.get('STATS', [0])
        if isinstance(stats_choices, int):
            stats_choices = [stats_choices]
        stat_map = {
            0: ('sum', 'ZLL_SUM', 6),        # Double
            1: ('count', 'ZLL_COUNT', 2),    # Integer
            2: ('mean', 'ZLL_MEAN', 6),      # Double
            3: ('median', 'ZLL_MEDIAN', 6),  # Double
            4: ('min', 'ZLL_MIN', 6),        # Double
            5: ('max', 'ZLL_MAX', 6),        # Double
            6: ('stdev', 'ZLL_STDDEV', 6),   # Double
        }
        aggregates = []
        for idx in stats_choices:
            agg, name, typ = stat_map.get(idx, ('sum', 'ZLL_SUM', 6))
            aggregates.append({
                'aggregate': agg,
                'delimiter': ',',
                'input': length_field,
                'length': 0,
                'name': name,
                'type': typ
            })
        # Always add the polygon id field
        aggregates.append({
            'aggregate': 'first_value',
            'delimiter': ',',
            'input': polygon_id_field,
            'length': 0,
            'name': polygon_id_field,
            'type': id_field_type
        })
        aggregate_result = processing.run(
            "native:aggregate",
            {
                'INPUT': intersected_layer,
                'GROUP_BY': polygon_id_field,
                'AGGREGATES': aggregates,
                'OUTPUT': 'memory:aggregated'
            },
            context=context, feedback=feedback, is_child_algorithm=True
        )
        aggregated_layer = aggregate_result['OUTPUT']

        # Convert to layer object if necessary
        if isinstance(aggregated_layer, str):
            aggregated_layer = self.parameterAsVectorLayer(aggregate_result, 'OUTPUT', context)

        # 4. Remove ghost features with ZLL_SUM < threshold (optional)
        threshold = parameters.get('LENGTH_THRESHOLD', None)
        try:
            threshold = float(threshold) if threshold not in (None, '', ' ') else None
        except Exception:
            threshold = None

        # Use ZLL_SUM if present, otherwise use the first stat field for filtering
        stat_field_for_filter = None
        for idx in stats_choices:
            if stat_map[idx][1] == 'ZLL_SUM':
                stat_field_for_filter = 'ZLL_SUM'
                break
        if stat_field_for_filter is None and stats_choices:
            stat_field_for_filter = stat_map[stats_choices[0]][1]

        if threshold is not None and threshold > 0.0 and stat_field_for_filter:
            feedback.pushInfo(f'Removing ghost features ({stat_field_for_filter} < {threshold})...')
            from qgis.core import QgsFeature, QgsVectorLayer, QgsFields, QgsWkbTypes
            fields = aggregated_layer.fields()
            crs = aggregated_layer.sourceCrs()
            wkb_type = aggregated_layer.wkbType()
            filtered_layer = QgsVectorLayer(QgsWkbTypes.displayString(wkb_type) + f"?crs={crs.authid()}", "filtered", "memory")
            filtered_layer_data = filtered_layer.dataProvider()
            filtered_layer_data.addAttributes(fields)
            filtered_layer.updateFields()
            for feat in aggregated_layer.getFeatures():
                if feat[stat_field_for_filter] is not None and feat[stat_field_for_filter] >= threshold:
                    filtered_layer_data.addFeature(feat)
            filtered_layer.updateExtents()
            output_layer = filtered_layer
        else:
            # No filtering
            output_layer = aggregated_layer

        # 5. Join polygon attributes to line (exclude duplicate polygon_id_field)
        feedback.pushInfo('Joining attributes...')
        polygon_fields = [f.name() for f in polygon_source.fields() if f.name() != polygon_id_field]
        join_result = processing.run(
            "native:joinattributestable",
            {
                'INPUT': output_layer,
                'FIELD': polygon_id_field,
                'INPUT_2': parameters[self.POLYGON],
                'FIELD_2': polygon_id_field,
                'FIELDS_TO_COPY': polygon_fields,
                'METHOD': 1,
                'DISCARD_NONMATCHING': False,
                'OUTPUT': parameters[self.OUTPUT]
            },
            context=context, feedback=feedback, is_child_algorithm=True
        )
        return {self.OUTPUT: join_result['OUTPUT']}

    def name(self):
        return 'zonallinelength'

    def displayName(self):
        return self.tr('Zonal Line Length Algorithm')

    def shortHelpString(self):
        return self.tr(
            'Extracts the intersection of polygons and lines, summarizes the line length for each polygon, and outputs a line layer with the original polygon attributes joined without duplication.'
        )

    def createInstance(self):
        return ZonalLineLengthAlgorithm()
    
    def icon(self):
        from qgis.PyQt.QtGui import QIcon
        from pathlib import Path
        icon_path = Path(__file__).parent / "icon.svg"
        return QIcon(str(icon_path))