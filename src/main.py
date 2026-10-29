import sys
import time
from datetime import datetime
from src.config import Config
from src.services.MonthlyReportService import MonthlyReportService
from src.services.DailyAlertService import DailyAlertService
from src.services.ExcelExportService import ExcelExportService
from src.utils.mailUtils import sendMailOffice365

def buildHtmlSummary(monthlyDf, cameraDf, summaryDf, runTimestamp: str) -> str:
    totalCameras = len(monthlyDf)
    camerasWithGaps = len(monthlyDf[(monthlyDf["dias sin grabacion acumulado"] > 0) | (monthlyDf["estado actual"] != "GRABANDO")])
    totalDailyCameraAlerts = len(cameraDf)
    totalDvrAlerts = len(summaryDf)
    
    # extraer top 8 de alertas detalladas por camara para vista previa en correo
    previewRowsHtml = ""
    for _, row in cameraDf.head(8).iterrows():
        previewRowsHtml += f"""
        <tr>
            <td style="padding: 7px; border: 1px solid #ddd;">{row['ceco']}</td>
            <td style="padding: 7px; border: 1px solid #ddd;">{row['tienda']}</td>
            <td style="padding: 7px; border: 1px solid #ddd; text-align: center;">{row['canal']}</td>
            <td style="padding: 7px; border: 1px solid #ddd;">{row['camara']}</td>
            <td style="padding: 7px; border: 1px solid #ddd; color: #c00000; font-weight: bold;">{row['tiempo sin grabacion']}</td>
            <td style="padding: 7px; border: 1px solid #ddd;">{row['estado actual']}</td>
            <td style="padding: 7px; border: 1px solid #ddd; font-size: 11px; color: #555;">{row['detalle']}</td>
        </tr>
        """
        
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.5; }}
            .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #1F4E79; color: white; padding: 15px 20px; border-radius: 6px 6px 0 0; }}
            .card-container {{ display: flex; gap: 12px; margin: 20px 0; }}
            .card {{ flex: 1; padding: 14px 12px; border-radius: 4px; background-color: #f8fafc; border: 1px solid #e2e8f0; text-align: center; }}
            .card-title {{ font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: bold; }}
            .card-value {{ font-size: 22px; font-weight: bold; margin-top: 5px; color: #1e293b; }}
            .card-value-critical {{ font-size: 22px; font-weight: bold; margin-top: 5px; color: #b91c1c; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 12px; }}
            th {{ background-color: #1F4E79; color: white; padding: 8px; border: 1px solid #ddd; text-align: left; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #777; border-top: 1px solid #ddd; padding-top: 10px; }}
            .legend-box {{ background-color: #f1f5f9; padding: 12px; border-radius: 6px; margin-top: 15px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0;">Reporte de Monitoreo CCTV - Grabaciones DVR</h2>
                <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">Fecha de ejecucion: {runTimestamp}</div>
            </div>
            
            <div class="card-container">
                <div class="card">
                    <div class="card-title">Camaras Monitoreadas</div>
                    <div class="card-value">{totalCameras}</div>
                </div>
                <div class="card">
                    <div class="card-title">Camaras con Falla/Perdida Mes</div>
                    <div class="card-value-critical">{camerasWithGaps}</div>
                </div>
                <div class="card">
                    <div class="card-title">DVRs Alerta (>30m)</div>
                    <div class="card-value-critical">{totalDvrAlerts}</div>
                </div>
                <div class="card">
                    <div class="card-title">Camaras en Alerta (>30m)</div>
                    <div class="card-value-critical">{totalDailyCameraAlerts}</div>
                </div>
            </div>

            <h3 style="margin-bottom: 5px;">Vista Previa: Detalle de Camaras sin Grabacion Activa</h3>
            <table>
                <thead>
                    <tr>
                        <th>CECO</th>
                        <th>Tienda</th>
                        <th>Canal</th>
                        <th>Camara</th>
                        <th>Tiempo sin Grabacion</th>
                        <th>Estado Actual</th>
                        <th>Detalle</th>
                    </tr>
                </thead>
                <tbody>
                    {previewRowsHtml}
                </tbody>
            </table>

            <div class="legend-box">
                <b>Nota:</b> Ambos archivos Excel adjuntos incluyen una pestana <b>"Leyenda de Estados"</b> con la definicion tecnica, criticidad y accion recomendada para cada valor de la columna 'Estado Actual'.
            </div>

            <p style="margin-top: 15px;">
                Se adjuntan los 2 reportes detallados en formato Excel:
                <ul>
                    <li><b>Historico del mes (-30 dias):</b> Pestanas con Camaras Observadas, Detalle General y Leyenda de Estados.</li>
                    <li><b>Alertas del dia (D-1 a hoy):</b> Pestanas con Alertas por Camara, Resumen por DVR y Leyenda de Estados.</li>
                </ul>
            </p>

            <div class="footer">
                Sistema Automatizado de Control de Camaras CCTV - Servidor Interno.
            </div>
        </div>
    </body>
    </html>
    """
    return html

def executeMonitoringJob():
    now = datetime.now()
    runTimestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    dateStamp = now.strftime("%Y%m%d_%H%M")
    
    print(f"[info] iniciando ciclo de monitoreo cctv - {runTimestamp}")
    
    try:
        # 1. extraer datos
        print("[info] consultando reporte mensual de camaras (30 dias)...")
        monthlyCameraDf, monthlySummaryDf = MonthlyReportService.getMonthlyRecordingStatus(30)
        
        print("[info] consultando alertas urgentes de dvrs y detalle de camaras (ultimas 24-48h)...")
        cameraDf, summaryDf = DailyAlertService.getDailyAlerts(48)
        
        # 2. generar libros excel
        print("[info] generando archivos excel con pestana de resumen, leyenda y detalle por camara...")
        monthlyExcelBytes = ExcelExportService.createMonthlyExcel(monthlyCameraDf, monthlySummaryDf)
        dailyExcelBytes = ExcelExportService.createDailyAlertsExcel(cameraDf, summaryDf)
        
        monthlyFileName = f"reporte_historico_camaras_mes_{dateStamp}.xlsx"
        dailyFileName = f"reporte_alertas_dvr_dia_{dateStamp}.xlsx"
        
        # 3. construir cuerpo html
        htmlContent = buildHtmlSummary(monthlyCameraDf, cameraDf, summaryDf, runTimestamp)
        
        # 4. enviar por correo mediante microsoft graph api
        recipients = [email.strip() for email in Config.EMAIL_RECEPTOR.split(",") if email.strip()]
        subject = f"Alerta y Reporte CCTV DVRs - {runTimestamp}"
        
        attachments = [
            (monthlyFileName, monthlyExcelBytes),
            (dailyFileName, dailyExcelBytes)
        ]
        
        print(f"[info] enviando correo a: {recipients}...")
        sentOk = sendMailOffice365(
            sender=Config.EMAIL_EMISOR,
            subject=subject,
            messageBody=htmlContent,
            recipients=recipients,
            attachments=attachments
        )
        
        if sentOk:
            print("[ok] ciclo de monitoreo completado exitosamente")
        else:
            print("[error] no se pudo enviar el correo de monitoreo")
            
    except Exception as error:
        print(f"[error] error durante ejecucion del job de monitoreo: {str(error)}")

def main():
    # devCt: ejecucion inmediata si se pasa --run-once o ejecucion continua en servidor
    isRunOnce = "--run-once" in sys.argv
    
    if isRunOnce:
        executeMonitoringJob()
        return

    print("[info] servicio daemon de monitoreo cctv iniciado")
    executeMonitoringJob()
    
    while True:
        try:
            # devCt: calculo del tiempo restante hasta el inicio de la siguiente hora
            now = datetime.now()
            sleepSeconds = 3600 - (now.minute * 60 + now.second)
            print(f"[info] proxima ejecucion en {sleepSeconds} segundos ({round(sleepSeconds/60)} minutos)")
            time.sleep(sleepSeconds)
            executeMonitoringJob()
        except KeyboardInterrupt:
            print("[info] servicio daemon detenido por usuario")
            break
        except Exception as loopError:
            print(f"[error] error en ciclo principal: {str(loopError)}")
            time.sleep(60)

if __name__ == "__main__":
    main()
