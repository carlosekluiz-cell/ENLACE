"""
ITU-R P.2109-2 building entry loss (BEL).

Implements Annex 1 equations (1)-(10) with Table 1 coefficients, verified
against the published Recommendation (Aug 2023 edition). Gives the loss
not exceeded with probability P for a terminal inside a building —
the missing term when the CPE is indoors rather than roof-mounted.

Median checks (P = 0.5, horizontal): traditional @1 GHz = 14.3 dB,
thermally-efficient @1 GHz = 31.0 dB.
"""

from __future__ import annotations

import math

from statistics import NormalDist

# Table 1 — Model coefficients (ITU-R P.2109-2)
_COEFFS = {
    #                     r      s      t     u     v     w     x     y     z
    "traditional": (12.64, 3.72, 0.96, 9.6, 2.0, 9.1, -3.0, 4.5, -2.0),
    "thermally_efficient": (28.19, -3.00, 8.48, 13.5, 3.8, 27.8, -2.9, 9.4, -2.1),
}

BUILDING_CLASSES = tuple(_COEFFS)


def building_entry_loss_db(
    frequency_ghz: float,
    probability: float = 0.5,
    elevation_deg: float = 0.0,
    building_class: str = "traditional",
) -> float:
    """Building entry loss (dB) not exceeded with the given probability.

    Args:
        frequency_ghz: 0.08-100 GHz.
        probability: 0 < P < 1 (validated empirically for 0.01-0.99).
        elevation_deg: elevation angle of the path at the facade.
        building_class: "traditional" or "thermally_efficient".
    """
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be in (0, 1)")
    if not 0.08 <= frequency_ghz <= 100.0:
        raise ValueError("frequency outside P.2109 range (0.08-100 GHz)")
    try:
        r, s, t, u, v, w, x, y, z = _COEFFS[building_class]
    except KeyError:
        raise ValueError(
            f"unknown building_class {building_class!r} (expected {BUILDING_CLASSES})"
        )

    logf = math.log10(frequency_ghz)
    l_h = r + s * logf + t * logf * logf  # eq. (9): median horizontal loss
    l_e = 0.212 * abs(elevation_deg)  # eq. (10)
    mu1 = l_h + l_e  # eq. (5)
    mu2 = w + x * logf  # eq. (6)
    sigma1 = u + v * logf  # eq. (7)
    sigma2 = y + z * logf  # eq. (8)

    finv = NormalDist().inv_cdf(probability)
    a = finv * sigma1 + mu1  # eq. (2)
    b = finv * sigma2 + mu2  # eq. (3)
    c = -3.0  # eq. (4)
    # eq. (1): soft combination of the two lognormal populations
    return 10.0 * math.log10(10 ** (0.1 * a) + 10 ** (0.1 * b) + 10 ** (0.1 * c))
