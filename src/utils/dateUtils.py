from typing import List, Optional
from datetime import datetime, date

def formatDuration(minutes: Optional[int]) -> str:
    if minutes is None:
        return "mas de 48 horas sin reporte"
    if minutes < 1:
        return "menos de 1 min"
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 1440:
        hours = minutes // 60
        remainingMinutes = minutes % 60
        return f"{hours} h {remainingMinutes} m" if remainingMinutes > 0 else f"{hours} h"
    
    days = minutes // 1440
    remainingHours = (minutes % 1440) // 60
    return f"{days} d {remainingHours} h" if remainingHours > 0 else f"{days} d"

# devCt: agrupa dias consecutivos de fechas en rangos legibles (ej: 01/10-05/10)
def compressDateList(dateList: List[date]) -> str:
    if not dateList:
        return "ninguno"
    
    sortedDates = sorted(list(set(dateList)))
    ranges = []
    start = sortedDates[0]
    prev = sortedDates[0]
    
    for currentDate in sortedDates[1:]:
        if (currentDate - prev).days == 1:
            prev = currentDate
        else:
            if start == prev:
                ranges.append(start.strftime("%d/%m"))
            else:
                ranges.append(f"{start.strftime('%d/%m')}-{prev.strftime('%d/%m')}")
            start = currentDate
            prev = currentDate

    if start == prev:
        ranges.append(start.strftime("%d/%m"))
    else:
        ranges.append(f"{start.strftime('%d/%m')}-{prev.strftime('%d/%m')}")
        
    return ", ".join(ranges)

def compressDayList(days: List[int]) -> str:
    if not days:
        return "ninguno"
    
    sortedDays = sorted(list(set(days)))
    ranges = []
    start = sortedDays[0]
    prev = sortedDays[0]
    
    for day in sortedDays[1:]:
        if day == prev + 1:
            prev = day
        else:
            ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = day
            prev = day
    ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
    
    return ", ".join(ranges)

# devCt: calcula minutos transcurridos en horario operativo (09:00 a 22:00 lima)
def getOperatingMinutesWithoutReport(dtStart: Optional[datetime], dtEnd: Optional[datetime] = None) -> int:
    if dtStart is None:
        return 999999
        
    import zoneinfo
    from datetime import time, timedelta
    
    limaTz = zoneinfo.ZoneInfo("America/Lima")
    if dtEnd is None:
        dtEnd = datetime.now(limaTz)
        
    if dtStart.tzinfo is None:
        dtStart = dtStart.replace(tzinfo=limaTz)
    else:
        dtStart = dtStart.astimezone(limaTz)
        
    if dtEnd.tzinfo is None:
        dtEnd = dtEnd.replace(tzinfo=limaTz)
    else:
        dtEnd = dtEnd.astimezone(limaTz)

    if dtStart >= dtEnd:
        return 0

    totalSeconds = 0.0
    currDate = dtStart.date()
    endDate = dtEnd.date()

    while currDate <= endDate:
        openTime = datetime.combine(currDate, time(9, 0), tzinfo=limaTz)
        closeTime = datetime.combine(currDate, time(22, 0), tzinfo=limaTz)

        dayStart = max(dtStart, openTime)
        dayEnd = min(dtEnd, closeTime)

        if dayStart < dayEnd:
            totalSeconds += (dayEnd - dayStart).total_seconds()

        currDate += timedelta(days=1)

    return int(totalSeconds // 60)

