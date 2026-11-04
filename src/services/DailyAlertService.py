from typing import Tuple
import pandas as pd
from src.db import getDbConnection
from src.utils.dateUtils import formatDuration
from src.utils.trackingUtils import getTrackingChannelsMap

class DailyAlertService:

    @staticmethod
    def getDailyAlerts(hoursInterval: int = 48) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        # devCt: consulta combinada de estado general de dvr y detalle de cada camara
        query = """
        WITH latest_camera_status AS (
            SELECT DISTINCT ON (store_ceco, channel)
                store_ceco,
                channel,
                camera_name,
                is_online,
                is_recording,
                last_recording_utc,
                captured_at_utc
            FROM sch_cctv.tbl_dvr_recording_status
            WHERE captured_at_utc >= NOW() - INTERVAL '72 hours'
            ORDER BY store_ceco, channel, captured_at_utc DESC
        ),
        dvr_summary AS (
            SELECT 
                s.ceco,
                s.name AS store_name,
                d.minutes_since_last_report,
                d.last_report_at,
                d.reported_channels,
                d.recording_channels,
                d.not_recording_channels,
                d.offline_channels,
                d.all_cameras_recording
            FROM sch_cctv.tbl_store s
            JOIN sch_cctv.fn_getstoredvrmonitoringsummary(%s) d ON d.store_ceco = s.ceco
            WHERE s.status = 1 AND s.delete_at IS NULL
        )
        SELECT 
            d.ceco,
            d.store_name,
            COALESCE(lc.channel, 0) AS canal,
            COALESCE(lc.camera_name, 'TODAS LAS CAMARAS') AS camara,
            d.minutes_since_last_report,
            lc.is_online,
            lc.is_recording,
            lc.last_recording_utc,
            d.reported_channels,
            d.recording_channels,
            d.not_recording_channels
        FROM dvr_summary d
        LEFT JOIN latest_camera_status lc ON lc.store_ceco = d.ceco
        WHERE (
            d.minutes_since_last_report > 30 
            OR d.minutes_since_last_report IS NULL 
            OR d.all_cameras_recording = FALSE
            OR COALESCE(lc.is_recording, false) = FALSE
        )
        ORDER BY d.minutes_since_last_report DESC NULLS FIRST, d.store_name, lc.channel;
        """

        comparisonQuery = """
        SELECT 
            s.ceco,
            s.name AS store_name,
            COALESCE(d.reported_channels, 0) AS reported_channels,
            COALESCE(d.recording_channels, 0) AS recording_channels
        FROM sch_cctv.tbl_store s
        LEFT JOIN sch_cctv.fn_getstoredvrmonitoringsummary(%s) d ON d.store_ceco = s.ceco
        WHERE s.status = 1 AND s.delete_at IS NULL
        ORDER BY s.ceco;
        """

        trackingMap = getTrackingChannelsMap()

        with getDbConnection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (hoursInterval,))
                rows = cursor.fetchall()

                cursor.execute(comparisonQuery, (hoursInterval,))
                compDbRows = cursor.fetchall()

        cameraRows = []
        storeMap = {}

        for row in rows:
            ceco, storeName, minutesSinceReport, channel, cameraName, isOnline, isRecording, lastRecUtc, repCh, recCh, notRecCh = (
                row[0], row[1], row[4], row[2], row[3], row[5], row[6], row[7], row[8], row[9], row[10]
            )

            # clasificar estado actual y descripcion de detalle por camara
            if minutesSinceReport is None or minutesSinceReport > 1440:
                currentState = "OFFLINE / SIN REPORTE (>24H)"
                detailText = "dvr sin comunicacion con agente central hace mas de 24 horas"
            elif minutesSinceReport > 30:
                currentState = "SIN REPORTE (>30 MIN)"
                detailText = f"dvr sin reporte reciente hace {formatDuration(minutesSinceReport)}"
            elif isOnline is False:
                currentState = "CAMARA OFFLINE"
                detailText = "camara sin senal de video o cable de red/energia desconectado"
            elif isRecording is False:
                currentState = "ONLINE NO GRABA"
                detailText = "camara en linea pero grabacion detenida en disco"
            elif recCh == 0:
                currentState = "NO GRABA NINGUN CANAL"
                detailText = "el dvr no tiene ningun canal grabando (posible disco dañado o lleno)"
            else:
                currentState = "OBSERVADO"
                detailText = "canal en observacion por corte intermitente"

            cameraRows.append({
                "ceco": ceco,
                "tienda": storeName,
                "canal": channel if channel > 0 else "General",
                "camara": cameraName,
                "tiempo sin grabacion": formatDuration(minutesSinceReport),
                "estado actual": currentState,
                "detalle": detailText
            })

            # agrupar para resumen a nivel de dvr / tienda
            if ceco not in storeMap:
                storeMap[ceco] = {
                    "ceco": ceco,
                    "tienda": storeName,
                    "channels": [],
                    "minutes": minutesSinceReport,
                    "repCh": repCh,
                    "recCh": recCh,
                    "state": currentState,
                    "detail": detailText
                }
            if channel > 0:
                storeMap[ceco]["channels"].append(str(channel))

        # construir resumen por tienda
        storeSummaryRows = []
        for ceco, info in storeMap.items():
            affectedChannels = ", ".join(info["channels"]) if info["channels"] else "Todos"
            storeSummaryRows.append({
                "ceco": info["ceco"],
                "tienda": info["tienda"],
                "canales afectados": f"Canales: {affectedChannels}",
                "tiempo sin grabacion": formatDuration(info["minutes"]),
                "estado actual": info["state"],
                "detalle": info["detail"]
            })

        # devCt: generacion de comparativo de canales diario con el listado maestro de tracking (solo tiendas activas)
        comparisonRows = []
        for r in compDbRows:
            storeCeco, storeName, reportedCh, recordingCh = r
            inactiveCh = max(0, reportedCh - recordingCh)

            # devCt: calculo de discrepancias frente al tracking maestro (col f menos col d: listado menos camaras activas)
            if storeCeco in trackingMap:
                trackingVal = trackingMap[storeCeco]
                trackingDisplay = trackingVal
                diff = trackingVal - recordingCh
                if diff == 0:
                    discrepancyText = "Sin discrepancias"
                else:
                    discrepancyText = f"Discrepancia ({diff})"
            else:
                trackingDisplay = "Sin informacion segun listado"
                discrepancyText = "Sin informacion segun listado"

            comparisonRows.append({
                "ceco": storeCeco,
                "tienda": storeName,
                "total de camaras": reportedCh,
                "total de camaras activas": recordingCh,
                "total de camaras inactivas": inactiveCh,
                "total de camaras segun el listado": trackingDisplay,
                "discrepancias": discrepancyText
            })

        cameraDf = pd.DataFrame(cameraRows)
        summaryDf = pd.DataFrame(storeSummaryRows)
        comparisonDf = pd.DataFrame(comparisonRows).sort_values("ceco")
        return cameraDf, summaryDf, comparisonDf
