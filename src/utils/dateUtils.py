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
