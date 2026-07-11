"""
Export propagation studies (link / coverage) as PDF, KMZ and GeoJSON.

The planner posts the study snapshot it already holds (parameters +
results); rendering is stateless. The PDF carries the calibration footer
(held-out RMSE) and the engineering disclaimer.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date

ACCENT = (0x0D / 255, 0x94 / 255, 0x88 / 255)
INK = (0.12, 0.16, 0.2)
MUTED = (0.45, 0.5, 0.55)


def _calibration_footer() -> str:
    try:
        from python.api.services.calibration import calibration_summary

        s = calibration_summary()
        cal = s.get("calibrated", {})
        urban = cal.get("urban", {})
        if urban:
            return (
                f"Modelo calibrado contra {s.get('residuals_scored', 0):,} medições Anatel — "
                f"RMSE urbano {urban.get('rmse_after_db')} dB (held-out, n={urban.get('n_test'):,})."
            ).replace(",", ".")
    except Exception:
        pass
    return "Modelo físico ITU-R/3GPP sobre terreno 30 m."


def study_pdf(study: dict) -> bytes:
    """Render a link or coverage study as a one-page branded PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    kind = study.get("kind", "enlace")
    params = study.get("params", {})
    y = H - 20 * mm

    def text(x, yy, s, size=9, bold=False, color=INK):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColorRGB(*color)
        c.drawString(x, yy, s)

    # Header
    c.setFillColorRGB(*ACCENT)
    c.rect(0, H - 12 * mm, W, 12 * mm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(15 * mm, H - 8.2 * mm, "ENLACE — Estudo de Propagação RF")
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 15 * mm, H - 8.2 * mm, date.today().strftime("%d/%m/%Y"))

    title = "Enlace ponto-a-ponto" if kind == "enlace" else "Cobertura de torre"
    text(15 * mm, y, title, 15, bold=True)
    y -= 8 * mm

    # Parameters block
    text(15 * mm, y, "PARÂMETROS", 8, bold=True, color=MUTED)
    y -= 5 * mm
    rows = [
        ("Frequência", f"{params.get('freqMhz', '—')} MHz"),
        ("Superfície", str(params.get('surface', 'dsm')).upper()),
    ]
    if kind == "enlace":
        tx, rx = study.get("tx") or {}, study.get("rx") or {}
        rows += [
            ("TX", f"{tx.get('lat', 0):.5f}, {tx.get('lng', 0):.5f} · h {params.get('txHeight', '—')} m"),
            ("RX", f"{rx.get('lat', 0):.5f}, {rx.get('lng', 0):.5f} · h {params.get('rxHeight', '—')} m"),
            ("Edifícios 0,5 m", "sim" if params.get("useBuildings") else "não"),
        ]
    else:
        tx = study.get("tx") or {}
        rows += [
            ("Torre", f"{tx.get('lat', 0):.5f}, {tx.get('lng', 0):.5f} · h {params.get('txHeight', '—')} m"),
            ("Potência / ganho", f"{params.get('txPower', '—')} dBm / {params.get('antGain', '—')} dBi"),
            ("Raio / grade", f"{params.get('radiusM', '—')} m / {params.get('gridRes', '—')} m"),
        ]
    for k, v in rows:
        text(15 * mm, y, k, 9, color=MUTED)
        text(60 * mm, y, str(v), 9)
        y -= 5 * mm
    y -= 4 * mm

    # Results block
    text(15 * mm, y, "RESULTADOS", 8, bold=True, color=MUTED)
    y -= 5 * mm
    if kind == "enlace":
        prof = study.get("profile") or {}
        la = prof.get("link_analysis") or {}
        lb = study.get("linkBudget") or {}
        res = [
            ("Distância", f"{(prof.get('total_distance_m', 0) / 1000):.2f} km"),
            ("Linha de visada", "LIVRE" if la.get("line_of_sight") else "OBSTRUÍDA"),
            ("1ª zona de Fresnel", "≥60% livre" if la.get("fresnel_clear")
             else f"{(la.get('worst_clearance_ratio', 0) * 100):.0f}% no pior ponto"),
            ("Elevação mín–máx", f"{prof.get('min_elevation_m', 0):.0f} – {prof.get('max_elevation_m', 0):.0f} m"),
        ]
        if lb:
            res += [
                ("Rx previsto", f"{lb.get('received_power_dbm', 0):.1f} dBm"),
                ("Margem de fade", f"{lb.get('fade_margin_db', 0):.1f} dB"),
                ("Disponibilidade", f"{lb.get('availability_pct', 0):.3f} %"),
                ("Chuva (P.837)", f"{lb.get('rain_rate_mmh', '—')} mm/h"),
            ]
        cs = prof.get("clutter_summary") or {}
        if cs.get("environment"):
            res.append(("Ambiente (MapBiomas)", cs["environment"]))
    else:
        cov = study.get("coverage") or {}
        res = [
            ("Cobertura P50", f"{cov.get('coverage_pct', 0):.1f} %"),
            ("Cobertura P90", f"{cov.get('coverage_pct_p90', 0) or 0:.1f} % (σ {cov.get('sigma_db', 0) or 0:.1f} dB)"),
            ("Área coberta", f"{cov.get('coverage_area_km2', 0):.1f} km²"),
            ("Sinal médio", f"{cov.get('avg_signal_dbm', 0):.1f} dBm"),
            ("Ambiente", str(cov.get("environment", "—"))),
        ]
    for k, v in res:
        text(15 * mm, y, k, 9, color=MUTED)
        text(60 * mm, y, str(v), 9, bold=(k in ("Linha de visada", "Cobertura P50")))
        y -= 5 * mm
    y -= 4 * mm

    # Simple profile sketch for link studies
    prof = study.get("profile") or {}
    pts = prof.get("points") or []
    if kind == "enlace" and len(pts) > 2:
        text(15 * mm, y, "PERFIL DO TERRENO", 8, bold=True, color=MUTED)
        y -= 3 * mm
        cw, ch = W - 30 * mm, 40 * mm
        x0, y0 = 15 * mm, y - ch
        elevs = [p.get("curved_elevation_m", p.get("elevation_m", 0)) for p in pts]
        lo, hi = min(elevs), max(elevs)
        span = max(1.0, hi - lo)
        c.setFillColorRGB(0.95, 0.94, 0.92)
        c.rect(x0, y0, cw, ch, stroke=0, fill=1)
        c.setStrokeColorRGB(*ACCENT)
        c.setLineWidth(1.2)
        path = c.beginPath()
        for i, e in enumerate(elevs):
            px = x0 + cw * i / (len(elevs) - 1)
            py = y0 + ch * (e - lo) / span * 0.9 + ch * 0.05
            (path.moveTo if i == 0 else path.lineTo)(px, py)
        c.drawPath(path)
        la = prof.get("link_analysis") or {}
        fr = la.get("fresnel") or []
        if len(fr) == len(pts):
            c.setStrokeColorRGB(0.49, 0.23, 0.93)
            c.setLineWidth(0.8)
            p2 = c.beginPath()
            for i, f in enumerate(fr):
                px = x0 + cw * i / (len(fr) - 1)
                py = y0 + ch * (f.get("los_m", 0) - lo) / span * 0.9 + ch * 0.05
                (p2.moveTo if i == 0 else p2.lineTo)(px, py)
            c.drawPath(p2)
        y = y0 - 6 * mm

    # Footer: calibration + disclaimer
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(*MUTED)
    c.drawString(15 * mm, 18 * mm, _calibration_footer())
    c.drawString(
        15 * mm, 14 * mm,
        "Estimativa por modelos ITU-R/3GPP sobre dados abertos (SRTM, Copernicus, ANADEM, MapBiomas, Open Buildings)."
    )
    c.drawString(
        15 * mm, 10 * mm,
        "Não substitui projeto técnico assinado por profissional habilitado (Lei 5.194/66) nem site survey.",
    )
    c.setFillColorRGB(*ACCENT)
    c.drawRightString(W - 15 * mm, 10 * mm, "enlace.network")
    c.showPage()
    c.save()
    return buf.getvalue()


def study_geojson(study: dict) -> dict:
    """GeoJSON FeatureCollection for a study."""
    feats = []
    kind = study.get("kind", "enlace")
    tx = study.get("tx") or {}
    if tx:
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [tx.get("lng"), tx.get("lat")]},
            "properties": {"role": "tx" if kind == "enlace" else "tower"},
        })
    if kind == "enlace":
        rx = study.get("rx") or {}
        if rx:
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [rx.get("lng"), rx.get("lat")]},
                "properties": {"role": "rx"},
            })
            la = (study.get("profile") or {}).get("link_analysis") or {}
            feats.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[tx.get("lng"), tx.get("lat")],
                                             [rx.get("lng"), rx.get("lat")]]},
                "properties": {
                    "line_of_sight": la.get("line_of_sight"),
                    "fresnel_clear": la.get("fresnel_clear"),
                },
            })
    else:
        grid = (study.get("coverage") or {}).get("grid") or []
        for p in grid[:5000]:
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.get("lon"), p.get("lat")]},
                "properties": {"signal_dbm": round(p.get("signal_dbm", 0), 1)},
            })
    return {"type": "FeatureCollection", "features": feats}


def study_kmz(study: dict) -> bytes:
    """KMZ (zipped KML) for Google Earth."""
    kind = study.get("kind", "enlace")
    tx = study.get("tx") or {}
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        "<name>Enlace — Estudo de Propagação</name>",
        '<Style id="ok"><LineStyle><color>ff88940d</color><width>3</width></LineStyle></Style>',
        '<Style id="bad"><LineStyle><color>ff4444ee</color><width>3</width></LineStyle></Style>',
    ]
    if kind == "enlace":
        rx = study.get("rx") or {}
        la = (study.get("profile") or {}).get("link_analysis") or {}
        style = "ok" if la.get("line_of_sight") else "bad"
        parts.append(
            f"<Placemark><name>TX</name><Point><coordinates>{tx.get('lng')},{tx.get('lat')},0</coordinates></Point></Placemark>"
        )
        parts.append(
            f"<Placemark><name>RX</name><Point><coordinates>{rx.get('lng')},{rx.get('lat')},0</coordinates></Point></Placemark>"
        )
        parts.append(
            f'<Placemark><name>Enlace ({"LOS livre" if la.get("line_of_sight") else "obstruído"})</name>'
            f"<styleUrl>#{style}</styleUrl><LineString><tessellate>1</tessellate>"
            f"<coordinates>{tx.get('lng')},{tx.get('lat')},0 {rx.get('lng')},{rx.get('lat')},0</coordinates>"
            "</LineString></Placemark>"
        )
    else:
        cov = study.get("coverage") or {}
        parts.append(
            f"<Placemark><name>Torre</name><Point><coordinates>{tx.get('lng')},{tx.get('lat')},0</coordinates></Point></Placemark>"
        )
        for p in (cov.get("grid") or [])[:2000]:
            s = p.get("signal_dbm", -120)
            color = "ff29b981" if s >= -70 else "ff08b3ea" if s >= -85 else "ff1673f9" if s >= -95 else "ff4444ee"
            parts.append(
                f'<Placemark><Style><IconStyle><color>{color}</color><scale>0.4</scale>'
                '<Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon></IconStyle></Style>'
                f"<Point><coordinates>{p.get('lon')},{p.get('lat')},0</coordinates></Point></Placemark>"
            )
    parts.append("</Document></kml>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", "\n".join(parts))
    return buf.getvalue()
