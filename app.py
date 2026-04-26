def recommend(df, tmin, banned, stress_value, coef):
    plan = []
    daily_count = {}
    rain_limit = ai_rain_limit(df["температура"].mean(), stress_value)

    for i in range(6, len(df) - 12):
        row = df.iloc[i]
        t = row["время"]
        day = t.date()

        if t.hour in banned:
            continue

        if 9 <= t.hour <= 18:
            continue

        if daily_count.get(day, 0) >= 2:
            continue

        temp = row["температура"]
        if temp < tmin:
            continue

        recent_rain = df.iloc[i-6:i]["дождь"].sum()
        future_rain = df.iloc[i:i+12]["дождь"].sum()

        if recent_rain > rain_limit:
            continue

        if future_rain > rain_limit * 2:
            continue

        daily_need = volume(temp, stress_value, coef)

        if daily_count.get(day, 0) == 0:
            liters = daily_need / 2
        else:
            liters = daily_need / 2

        plan.append({
            "time": t,
            "liters": round(liters, 1)
        })

        daily_count[day] = daily_count.get(day, 0) + 1

    return plan
