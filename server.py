from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import csv
import json
from pathlib import Path
import requests

app = FastAPI()

# Serve static files from the public directory
app.mount("/", StaticFiles(directory="public", html=True), name="static")


@app.post("/update-airports")
def update_airports():
    """Download airport data from OpenFlights and update airports.json."""
    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    resp = requests.get(url)
    resp.raise_for_status()
    reader = csv.reader(resp.text.splitlines())
    airports = []
    for row in reader:
        try:
            lat = float(row[6])
            lon = float(row[7])
        except (ValueError, IndexError):
            continue
        airports.append({
            "name": row[1],
            "lat": lat,
            "lon": lon
        })

    out_file = Path("public") / "airports.json"
    out_file.write_text(json.dumps(airports, indent=2))
    return {"count": len(airports)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
