from typing import Tuple
import pandas as pd
from datetime import datetime, timedelta
from src.db import getDbConnection
from src.utils.dateUtils import compressDateList, getOperatingMinutesWithoutReport
from src.utils.trackingUtils import getTrackingChannelsMap

class MonthlyReportService:

    @staticmethod
    def getMonthlyRecordingStatus(daysBack: int = 30) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        now = datetime.now()
        # devCt: generacion de ventana movil exacta de ultimos n dias (d-30 a hoy)
        targetDates = [(now.date() - timedelta(days=i)) for i in range(daysBack - 1, -1, -1)]
        requiredMonths = sorted(list(set(d.strftime("%Y-%m") for d in targetDates)))

        query = """
        WITH latest_status AS (
            SELECT DISTINCT ON (store_ceco, channel)
                store_ceco,
                channel,
                is_online,
                is_recording,
                captured_at_utc
            FROM sch_cctv.tbl_dvr_recording_status
            WHERE captured_at_utc >= NOW() - INTERVAL '7 days'
            ORDER BY store_ceco, channel, captured_at_utc DESC
        )
        SELECT 
            cal.store_ceco,
            s.name AS store_name,
            cal.channel,
            cal.camera_name,
            cal.year_month,
            cal.day_mask,
            COALESCE(ls.is_recording, false) AS is_recording,
            COALESCE(ls.is_online, false) AS is_online,
            ls.captured_at_utc
        FROM sch_cctv.tbl_dvr_recording_calendar cal
        JOIN sch_cctv.tbl_store s ON s.ceco = cal.store_ceco AND s.status = 1 AND s.delete_at IS NULL
        LEFT JOIN latest_status ls ON ls.store_ceco = cal.store_ceco AND ls.channel = cal.channel
        WHERE cal.year_month = ANY(%s)
        ORDER BY s.name, cal.channel;
        """

        activeStoresQuery = """
        SELECT ceco, name 
        FROM sch_cctv.tbl_store 
        WHERE status = 1 AND delete_at IS NULL 
        ORDER BY ceco;
        """

        with getDbConnection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (requiredMonths,))
                rows = cursor.fetchall()

                cursor.execute(activeStoresQuery)
                activeStores = cursor.fetchall()

        # organizar mascaras por camara y mes
        cameraMap = {}
        for row in rows:
            storeCeco, storeName, channel, cameraName, yearMonth, dayMask, isRecording, isOnline, capturedAt = row
            cameraKey = (storeCeco, channel)
            
            if cameraKey not in cameraMap:
                cameraMap[cameraKey] = {
                    "ceco": storeCeco,
                    "tienda": storeName,
                    "canal": channel,
                    "camara": cameraName or f"Canal {channel}",
                    "masks": {},
                    "isRecording": isRecording,
                    "isOnline": isOnline,
                    "capturedAt": capturedAt
                }
            cameraMap[cameraKey]["masks"][yearMonth] = dayMask or ""

        processedRows = []
        for (storeCeco, channel), data in cameraMap.items():
            missingDates = []
            
            # evaluar cada fecha dentro de la ventana de 30 dias
            for targetDate in targetDates:
                ym = targetDate.strftime("%Y-%m")
                dayIndex = targetDate.day - 1
                mask = data["masks"].get(ym, "")
                
                if dayIndex < len(mask):
                    if mask[dayIndex] == "0":
                        missingDates.append(targetDate)
                else:
                    missingDates.append(targetDate)

            accumulatedDays = len(missingDates)
            isRecording = data["isRecording"]
            isOnline = data["isOnline"]
            capturedAt = data["capturedAt"]
            opMinutes = getOperatingMinutesWithoutReport(capturedAt, now)

            # devCt: clasificar estado actual considerando ventana operativa (09:00 a 22:00) y umbral de 60 min
            if capturedAt is None or opMinutes > 60:
                if opMinutes > 780:
                    currentState = "OFFLINE / SIN REPORTE (>24H)"
                else:
                    currentState = "SIN REPORTE (>60 MIN)"
            elif isRecording is True:
                currentState = "GRABANDO"
            elif isRecording is False and isOnline is True:
                currentState = "ONLINE NO GRABA"
            elif isOnline is False:
                currentState = "OFFLINE"
            else:
                currentState = "SIN REPORTE (>60 MIN)"

            processedRows.append({
                "ceco": storeCeco,
                "tienda": data["tienda"],
                "canal": channel,
                "camara": data["camara"],
                "dias sin grabacion acumulado": accumulatedDays,
                "dias en los que dejo de grabar": compressDateList(missingDates),
                "estado actual": currentState
            })

        cameraDf = pd.DataFrame(processedRows)

        # devCt: generacion de hoja resumen historico agrupada por tienda/ceco
        storeSummaryList = []
        for ceco, group in cameraDf.groupby("ceco"):
            storeName = group["tienda"].iloc[0]
            totalCams = len(group)
            observedCams = group[(group["dias sin grabacion acumulado"] > 0) | (group["estado actual"] != "GRABANDO")]
            
            affectedChannels = ", ".join(str(ch) for ch in observedCams["canal"].tolist()) if len(observedCams) > 0 else "Ninguno"
            maxDays = int(observedCams["dias sin grabacion acumulado"].max()) if len(observedCams) > 0 else 0
            
            states = set(group["estado actual"].unique())
            if states == {"GRABANDO"} and maxDays == 0:
                dvrState = "OPERATIVO"
                detailText = "todas las camaras grabando de forma continua sin perdidas"
            elif any("SIN REPORTE" in s or "OFFLINE" in s for s in states):
                dvrState = "CRITICO / OBSERVADO"
                detailText = f"{len(observedCams)} de {totalCams} camaras observadas. canales con falla: {affectedChannels}"
            else:
                dvrState = "HISTORICO OBSERVADO"
                detailText = f"{len(observedCams)} de {totalCams} camaras con hasta {maxDays} dias sin grabacion en los ultimos 30 dias"

            storeSummaryList.append({
                "ceco": ceco,
                "tienda": storeName,
                "total camaras": totalCams,
                "camaras observadas": len(observedCams),
                "canales observados": affectedChannels,
                "max dias sin grabacion": maxDays,
                "estado dvr": dvrState,
                "detalle": detailText
            })

        summaryDf = pd.DataFrame(storeSummaryList).sort_values(
            by=["max dias sin grabacion", "camaras observadas"], 
            ascending=[False, False]
        )

        # devCt: generacion de hoja comparativa con listado maestro de tracking (solo tiendas activas)
        trackingMap = getTrackingChannelsMap()
        cameraGroupByCeco = dict(tuple(cameraDf.groupby("ceco"))) if len(cameraDf) > 0 else {}
        comparisonList = []

        for storeCeco, storeName in activeStores:
            if storeCeco in cameraGroupByCeco:
                group = cameraGroupByCeco[storeCeco]
                totalCams = len(group)
                activeCams = len(group[group["estado actual"] == "GRABANDO"])
                inactiveCams = totalCams - activeCams
            else:
                totalCams = 0
                activeCams = 0
                inactiveCams = 0

            # devCt: calculo de discrepancias frente al tracking maestro (col f menos col d: listado menos camaras activas)
            if storeCeco in trackingMap:
                trackingVal = trackingMap[storeCeco]
                trackingDisplay = trackingVal
                diff = trackingVal - activeCams
                if diff == 0:
                    discrepancyText = "Sin discrepancias"
                else:
                    discrepancyText = f"Discrepancia ({diff})"
            else:
                trackingDisplay = "Sin informacion segun listado"
                discrepancyText = "Sin informacion segun listado"

            comparisonList.append({
                "ceco": storeCeco,
                "tienda": storeName,
                "total de camaras": totalCams,
                "total de camaras activas": activeCams,
                "total de camaras inactivas": inactiveCams,
                "total de camaras segun el listado": trackingDisplay,
                "discrepancias": discrepancyText
            })

        comparisonDf = pd.DataFrame(comparisonList).sort_values("ceco")

        return cameraDf, summaryDf, comparisonDf
