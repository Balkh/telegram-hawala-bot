from datetime import date


def _div(a, b):
    return a // b


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400)
    g_day_no += g_d_m[gm2] + gd2
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = _div(j_day_no, 12053)
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * _div(j_day_no, 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += _div(j_day_no - 1, 365)
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + _div(j_day_no, 31)
        jd = 1 + (j_day_no % 31)
    else:
        jm = 7 + _div(j_day_no - 186, 30)
        jd = 1 + ((j_day_no - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy2 = jy - 979
    jm2 = jm - 1
    jd2 = jd - 1
    j_day_no = 365 * jy2 + _div(jy2, 33) * 8 + _div(jy2 % 33 + 3, 4)
    j_day_no += 186 if jm2 >= 6 else jm2 * 31
    if jm2 >= 6:
        j_day_no += (jm2 - 6) * 30
    j_day_no += jd2
    g_day_no = j_day_no + 79
    gy = 1600 + 400 * _div(g_day_no, 146097)
    g_day_no %= 146097
    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * _div(g_day_no, 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False
    gy += 4 * _div(g_day_no, 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += _div(g_day_no, 365)
        g_day_no %= 365
    g_md = [0, 31, 28 + int(leap), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and g_day_no >= g_md[gm]:
        g_day_no -= g_md[gm]
        gm += 1
    gd = g_day_no + 1
    return gy, gm, gd


def gregorian_to_jalali_str(date_str):
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError("invalid date")
    gy, gm, gd = map(int, parts)
    jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def jalali_to_gregorian_str(date_str):
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError("invalid date")
    jy, jm, jd = map(int, parts)
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return f"{gy:04d}-{gm:02d}-{gd:02d}"


def today_gregorian_str():
    t = date.today()
    return t.strftime("%Y-%m-%d")


def today_jalali_str():
    t = date.today()
    jy, jm, jd = gregorian_to_jalali(t.year, t.month, t.day)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"

