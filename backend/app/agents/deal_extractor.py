"""Deal Extractor agent: photo of a printed deal contract -> structured deal JSON.

Designed for OpenAI-compatible vision endpoints such as Gemini. The model is asked for a strict
JSON object in plain content and the result is parsed defensively.
Prompt rules encode DEAL_TABLE.md §5.
"""
import base64
import copy
import json
import re
from datetime import date, datetime
from typing import Any

try:
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional runtime dependency for scan preprocessing
    cv2 = None
    np = None

from app.llm.client import LLMClient

_SYSTEM = """You are a vehicle deal-contract extraction assistant for a car dealership CRM.
You will receive a photo of a printed deal worksheet / purchase contract (lease, finance, or cash).
Extract the fields below and respond with ONLY a single JSON object — no prose, no markdown fences.

Extraction rules (follow exactly):
1. deal_type: decide from the section title on the sheet ("Lease" -> "lease", "Finance" -> "finance").
   If neither appears and there are no financing terms, use "cash".
2. Dates: contract_date must come ONLY from the Contract Date in the Customer block.
   delivery_date from the Delivery Date row; first_payment_date from Payment Date row.
   IGNORE the print date in the page header/corner (a reprinted contract shows today's date there).
   The contract is usually from the vehicle model year era (a 2022 vehicle -> dates in 2022, not 2023+).
   Output all dates as "YYYY-MM-DD".
3. model_year: read from the vehicle line (e.g. "2022 VOLKSWAGEN TIGUAN" -> 2022). Must match the
   printed model year, NOT the print/reprint year in the page header.
4. Amounts: plain numbers without "$" or thousands commas. Amounts printed in
   parentheses are NEGATIVE: "(300.00)" -> -300.00, "($221.70)" -> -221.70.
5. Trim: split the vehicle trim into trim_base (the catalog trim level, e.g. "Comfortline")
   and trim_package (appearance/option package, e.g. "R-Line Black Edition").
   If you cannot split it confidently, put the whole string in trim_base and lower confidence.
6. Shorthand like "72 @ 0%" means term=72 AND rate_pct=0. An explicitly printed 0%
   rate MUST be output as 0 (a number). Use null for rate_pct ONLY when no rate appears at all.
7. Lease / Finance terms block: read ONLY the row labels inside the "Lease" or "Finance" table
   (mid-page). Extract into TOP-LEVEL JSON keys — never nest in a sub-object:
   - Lender -> lender (e.g. "VW Credit Canada Inc.")
   - Rate -> rate_pct (e.g. 5.99 — the APR/interest rate, NOT the Residual %)
   - Term -> term (e.g. 48 — NOT the payment count)
   - Payment Frequency -> payment_frequency ("Bi-Weekly" / "BiWeekly" -> "biweekly")
   - Number of Payments -> num_payments (TOTAL PAYMENT COUNT, e.g. 104 — a separate row from Term)
   - Base Pmt / Base Pmt (pre-tax) -> base_payment (pre-tax amount, e.g. 220.25)
   - Payment / Payment (total amount) -> payment_amount (tax-included per payment, e.g. 253.29)
   CRITICAL — term and num_payments are ALMOST NEVER equal on Canadian lease sheets:
   a 48-month bi-weekly lease has term=48 but num_payments=104. Read each row separately.
   Do NOT copy Term into num_payments. Do NOT default frequency to "monthly" on lease sheets.
   Do NOT compute payment_amount from selling_price ÷ term — read the printed Payment line.
   Bi-weekly lease payments are typically $200–400; values above $500 are almost always wrong.
   base_payment must be LESS than payment_amount (HST adds ~15%). Never set both to the same number.
   For lease sheets also read KPY Allowed / KM/Y Allowed -> km_per_year, Residual % -> residual_pct
   (as 47, not 0.47), Residual value -> residual_value, Res. MSRP -> residual_msrp,
   Buy Option -> buy_option_price.
   These fields are REQUIRED for lease/finance deals — do not skip them when the table is visible.
8. Pricing column (left fee breakdown on O'Regan / VW sheets): read ONLY printed row labels.
   - MSRP / List Price -> base_price (optional; may differ from Selling Price)
   - Selling Price -> selling_price (vehicle sale price BEFORE fees; e.g. 42340.00 — NOT MSRP+options)
   - Discount -> discount (negative; e.g. -250 or -300 from parenthesized amount)
   - Each fee row -> line_items (Admin Fee, Air Tax, Tire Levy, etc.) with positive amounts
   - Sub-Total / Capital Cost -> capital_cost (e.g. 44119.45 — BEFORE cap reduction; NOT Net Lease)
   - Cash Down / Cap Reduction -> cash_down AND cap_reduction (same amount, e.g. 8781.75)
   - Net Lease -> NOT capital_cost; it equals capital_cost minus cap_reduction (~35337.70)
   - Total Balance Due / Drive Off -> drive_off_total (e.g. 11000.00 — NOT Net Lease)
   NEVER invent round placeholder numbers (1000, 2500, 5000, 40715). Use null when unreadable.
   capital_cost must be GREATER than selling_price (fees add on). drive_off_total is typically $8k–$15k on leases.
9. line_items: copy every fee/discount line verbatim into line_items with its signed amount
   (fees positive, discounts negative, e.g. "Discount in lieu of PPM" -> -700).
   category must be one of: admin, gov_levy, protection, registration, discount, other.
   Do not invent categories; when unsure use "other". Discount lines always get "discount".
9. trades: if the sheet has a Trade block (trade-in vehicle), output one entry per traded
   vehicle with its description, VIN, mileage, allocation (trade value) and lien_payout.
   The Trade-block Lien and the right-column "Payout Lien Amount" are the same fact — use one
   consistent value.
10. Occlusion: the photo may have covered/illegible areas. Output null for any field you cannot
   read and lower confidence. NEVER guess or fabricate values.
11. Lease-only fields (residual_msrp, residual_pct, residual_value, buy_option_price,
    km_per_year, excess_km_rate, security_deposit) must be null unless deal_type is "lease".
12. Highlighter marks on the sheet carry no meaning — they are just manual annotations.
13. customer: the buyer's name/phone/email from the Customer block (null when unreadable).
    Map printed "Cell" / "Mobile" to customer.phone and "Email" to customer.email.
    Put all three fields ONLY inside the customer object — not at the top level.
14. confidence: your overall extraction confidence from 0 to 1.

Output JSON shape (use null for anything not present on the sheet):
{
  "deal_type": "cash" | "finance" | "lease",
  "contract_date": "YYYY-MM-DD", "delivery_date": ..., "first_payment_date": ...,
  "dealership": ..., "rep_name_raw": ...,
  "make": ..., "model": ..., "model_year": 2022, "trim_base": ..., "trim_package": ...,
  "model_code": ..., "vin": ..., "stock_number": ...,
  "condition": "new" | "used" | "demo" | "cpo",
  "odometer_at_deal": ..., "exterior_color": ..., "engine": ..., "transmission": ..., "drivetrain": ...,
  "base_price": ..., "options_adjustment": ..., "selling_price": ..., "discount": ...,
  "fees_total": ..., "tax_total": ..., "capital_cost": ..., "total_with_tax": ...,
  "cash_down": ..., "trade_equity": ..., "cap_reduction": ..., "drive_off_total": ...,
  "lender": ..., "rate_pct": ..., "term": ..., "payment_frequency": "weekly" | "biweekly" | "semimonthly" | "monthly",
  "num_payments": ..., "base_payment": ..., "payment_amount": ...,
  "residual_msrp": ..., "residual_pct": ..., "residual_value": ..., "buy_option_price": ...,
  "km_per_year": ..., "excess_km_rate": ..., "security_deposit": ...,
  "line_items": [{"item_name": "Air Tax", "category": "gov_levy", "amount": 100.00}, ...],
  "trades": [{"make": ..., "model": ..., "model_year": ..., "trim_base": ..., "vin": ...,
              "mileage": ..., "exterior_color": ..., "allocation": ..., "lien_payout": ...}],
  "customer": {"name": ..., "phone": ..., "email": ...},
  "confidence": 0.9
}"""

_DEAL_TYPES = frozenset({"cash", "finance", "lease"})
_CONDITIONS = frozenset({"new", "used", "demo", "cpo"})
_FREQUENCIES = frozenset({"weekly", "biweekly", "semimonthly", "monthly"})
_CATEGORIES = frozenset({"admin", "gov_levy", "protection", "registration", "discount", "other"})

_MONEY_FIELDS = (
    "base_price", "options_adjustment", "selling_price", "discount", "fees_total",
    "tax_total", "capital_cost", "total_with_tax", "cash_down", "trade_equity",
    "cap_reduction", "drive_off_total", "rate_pct", "base_payment", "payment_amount",
    "residual_msrp", "residual_pct", "residual_value", "buy_option_price",
    "excess_km_rate", "security_deposit",
)
_INT_FIELDS = ("model_year", "odometer_at_deal", "term", "num_payments", "km_per_year")
_DATE_FIELDS = ("contract_date", "delivery_date", "first_payment_date")
_LEASE_ONLY_FIELDS = (
    "residual_msrp", "residual_pct", "residual_value", "buy_option_price",
    "km_per_year", "excess_km_rate", "security_deposit",
)
_TEXT_FIELDS = (
    "dealership", "rep_name_raw", "make", "model", "trim_base", "trim_package",
    "model_code", "vin", "stock_number", "exterior_color", "engine",
    "transmission", "drivetrain", "lender",
)

# Vision models sometimes flatten contact fields to the root object or use
# dealer-form labels (Cell, Email) instead of the nested customer block we ask for.
_CUSTOMER_NAME_KEYS = ("name", "full_name", "customer_name", "buyer_name")
_CUSTOMER_PHONE_KEYS = ("phone", "cell", "mobile", "telephone", "phone_number")
_CUSTOMER_EMAIL_KEYS = ("email", "email_address")
_CUSTOMER_PHONE_ROOT_KEYS = _CUSTOMER_PHONE_KEYS + ("customer_phone",)
_CUSTOMER_EMAIL_ROOT_KEYS = _CUSTOMER_EMAIL_KEYS + ("customer_email",)

# Vision models often nest lease/finance terms or use dealer-form column labels.
_NESTED_TERM_BLOCKS = (
    "lease", "terms", "financing", "finance", "lease_terms", "finance_terms", "payment_terms",
    "pricing", "price_breakdown", "vehicle_pricing", "fees", "fee_breakdown",
)
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "lender": ("leasing_company", "finance_company", "bank", "creditor"),
    "rate_pct": ("rate", "interest_rate", "apr", "lease_rate", "finance_rate"),
    "term": ("term_months", "lease_term", "finance_term", "term_in_months"),
    "payment_frequency": ("frequency", "payment_freq", "pay_frequency", "pmt_frequency"),
    "num_payments": ("number_of_payments", "payments", "num_pays", "no_of_payments", "payment_count"),
    "base_payment": ("base_pmt", "base_payment_pre_tax", "payment_before_tax", "pre_tax_payment"),
    "payment_amount": ("payment", "total_payment", "pmt_amount", "payment_total", "lease_payment"),
    "km_per_year": ("kpy_allowed", "kilometers_per_year", "annual_km", "km_allowed", "km_y_allowed"),
    "residual_pct": ("residual_percent", "residual_percentage", "residual"),
    "residual_value": ("residual_amount",),
    "residual_msrp": ("res_msrp", "residual_msrp_amount"),
    "selling_price": ("sale_price", "sales_price", "vehicle_price"),
    "base_price": ("msrp", "list_price", "retail_price"),
    "capital_cost": ("sub_total", "subtotal", "amount_to_finance", "balance_to_finance", "capitalized_cost"),
    "cash_down": ("cash_down_payment", "down_payment"),
    "cap_reduction": ("cap_cost_reduction", "capital_cost_reduction"),
    "drive_off_total": ("drive_off", "total_balance_due", "amount_due", "total_due", "drive_away"),
    "discount": ("customer_discount", "dealer_discount", "rebate"),
    "fees_total": ("fees", "total_fees"),
    "tax_total": ("tax", "total_tax", "hst", "gst"),
    "total_with_tax": ("total_incl_tax", "total_including_tax"),
    "trade_equity": ("trade_value", "trade_allowance", "trade_in_value"),
    "vin": ("vehicle_vin", "vin_number"),
    "stock_number": ("stock", "stock_no", "stock_num", "stock#"),
    "odometer_at_deal": ("odometer", "mileage", "kms", "km"),
}


_PAYMENTS_PER_YEAR = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12}
_NUM_PAYMENT_KEYS = frozenset({
    "num_payments", "number_of_payments", "payments", "num_pays",
    "no_of_payments", "payment_count", "numberofpayments",
})
_TERM_KEY_NAMES = frozenset({
    "term", "termmonths", "lease_term", "finance_term", "terminmonths",
})
_PAYMENT_AMOUNT_KEYS = frozenset({
    "payment_amount", "payment", "total_payment", "pmt_amount",
    "payment_total", "lease_payment", "base_payment", "base_pmt",
})
_LEASE_TABLE_FIELDS = (
    "lender", "rate_pct", "term", "payment_frequency", "num_payments",
    "base_payment", "payment_amount", "capital_cost", "cash_down", "cap_reduction",
    "drive_off_total", "residual_msrp", "residual_pct", "residual_value",
    "buy_option_price", "km_per_year", "excess_km_rate", "security_deposit",
)

_PRICING_FIELDS = (
    "base_price", "selling_price", "discount", "fees_total", "tax_total",
    "capital_cost", "total_with_tax", "cash_down", "cap_reduction",
    "drive_off_total", "trade_equity", "options_adjustment",
)

_PRICING_KEY_HINTS: dict[str, frozenset[str]] = {
    "selling_price": frozenset({"sellingprice", "saleprice", "salesprice", "vehicleprice"}),
    "base_price": frozenset({"baseprice", "msrp", "listprice", "retailprice"}),
    "capital_cost": frozenset({"capitalcost", "subtotal", "subtotalcapitalcost", "amounttobefinance", "balancetofinance"}),
    "cash_down": frozenset({"cashdown", "downpayment", "cashdownpayment"}),
    "cap_reduction": frozenset({"capreduction", "capcostreduction", "capitalcostreduction"}),
    "drive_off_total": frozenset({"driveoff", "driveofftotal", "totalbalancedue", "amountdue", "totaldue", "driveaway"}),
    "discount": frozenset({"discount", "customerdiscount", "dealerdiscount", "rebate"}),
    "net_lease": frozenset({"netlease", "netcapitalcost", "netcapcost"}),
}

# Round placeholders vision models invent when they cannot read the sheet.
_PLACEHOLDER_AMOUNTS = frozenset({500, 1000, 1500, 2000, 2500, 3000, 5000, 6800, 10000})

_LEASE_TABLE_SYSTEM = """You are reading ONLY the Lease or Finance terms table on a dealership deal worksheet.
Ignore vehicle, customer, and fee sections. Return ONLY one JSON object — no markdown.

Read each printed row label in the table exactly. Do NOT calculate or infer values.
{
  "deal_type": "lease" | "finance",
  "lender": string,
  "rate_pct": number,
  "term": number,
  "payment_frequency": "weekly" | "biweekly" | "semimonthly" | "monthly",
  "num_payments": number,
  "base_payment": number,
  "payment_amount": number,
  "capital_cost": number,
  "cash_down": number,
  "cap_reduction": number,
  "drive_off_total": number,
  "residual_msrp": number,
  "residual_pct": number,
  "residual_value": number,
  "buy_option_price": number,
  "km_per_year": number,
  "excess_km_rate": number,
  "security_deposit": number
}

Row mapping (Canadian O'Regan / VW-style sheets):
- "Term" row -> term (e.g. 48). NOT the same as Number of Payments.
- "Payment Frequency" row -> payment_frequency ("Bi-Weekly" -> "biweekly").
- "Number of Payments" row -> num_payments (e.g. 104 on a 48-month bi-weekly lease).
- "Payment" / "Total Payment" row -> payment_amount (per-payment total incl tax, e.g. 253.29).
  NEVER compute payment from selling price ÷ term — bi-weekly lease payments are typically $200–400.
  If you see 639.99 or similar, that is WRONG — re-read the highlighted Payment line near the bottom.
- "Base Pmt" / "Base Pmt (pre-tax)" -> base_payment (e.g. 220.25). Must be LESS than payment_amount.
  base_payment × ~1.15 ≈ payment_amount (15% HST). Do NOT copy the same value into both fields.
- "Rate" -> rate_pct (NOT Residual %). Rate is usually 0–10, not hundreds.
- "KM Allowed" / "KPY Allowed" -> km_per_year (e.g. 20000). "Residual 47%" -> residual_pct as 47.
- "Res. MSRP" -> residual_msrp. "Cash Down / Cap Reduction" -> both cash_down and cap_reduction.
"""

_PRICING_SYSTEM = """You are reading ONLY the vehicle pricing / fee breakdown column on a dealership deal worksheet.
Ignore lease terms, customer info, and payment tables. Return ONLY one JSON object — no markdown.

Read each printed row label in the left pricing column exactly. Do NOT calculate or infer totals.
{
  "base_price": number,
  "selling_price": number,
  "discount": number,
  "fees_total": number,
  "tax_total": number,
  "capital_cost": number,
  "cash_down": number,
  "cap_reduction": number,
  "drive_off_total": number,
  "line_items": [{"item_name": "Air Tax", "category": "gov_levy", "amount": 100.00}]
}

Row mapping (Canadian O'Regan / VW-style sheets):
- "MSRP" / list price -> base_price (optional)
- "Selling Price" -> selling_price (e.g. 42340.00 — vehicle price before fees)
- "Discount" -> discount (negative; e.g. -250 from parenthesized amount)
- Each fee line -> line_items with positive amount (Admin Fee, Air Tax, Tire Levy, etc.)
- "Sub-Total" / "Capital Cost" -> capital_cost (e.g. 44119.45 — BEFORE cap reduction)
- "Cash Down / Cap Reduction" -> cash_down AND cap_reduction (same value, e.g. 8781.75)
- "Net Lease" is NOT capital_cost — it is capital_cost minus cap_reduction (~35337.70)
- "Total Balance Due" / "Drive Off" -> drive_off_total (e.g. 11000.00 — amount due today)
NEVER output round placeholder guesses (1000, 2500, 5000). Use null when a row is illegible.
capital_cost must exceed selling_price. drive_off_total is typically $8k–$15k on leases, not $40k.
"""


def _order_points(pts: Any) -> Any:
    points = np.array(pts, dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    return np.array(
        [
            points[np.argmin(sums)],
            points[np.argmin(diffs)],
            points[np.argmax(sums)],
            points[np.argmax(diffs)],
        ],
        dtype=np.float32,
    )


def _find_quad_from_contours(
    contours: list[Any], width: int, height: int, min_area_ratio: float
) -> Any:
    min_area = width * height * min_area_ratio
    best = None
    best_area = 0.0
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        for eps in (0.01, 0.015, 0.02, 0.025, 0.03, 0.04):
            approx = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(approx) == 4 and area > best_area:
                best = approx.reshape(4, 2)
                best_area = area
    return best


def _find_quad_color(image: Any) -> tuple[Any, float]:
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 120), (180, 80, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=1
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    quad = _find_quad_from_contours(contours, w, h, 0.10)
    if quad is None:
        full = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
        return full, 1.0
    return quad, cv2.contourArea(quad.astype(np.int32)) / (w * h)


def _find_quad_edge(gray: Any) -> tuple[Any, float]:
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    best = None
    best_area = 0.0
    for lo, hi in ((30, 100), (50, 150), (75, 200)):
        edges = cv2.Canny(blur, lo, hi)
        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
            iterations=2,
        )
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        quad = _find_quad_from_contours(contours, w, h, 0.15)
        if quad is not None:
            area = cv2.contourArea(quad.astype(np.int32))
            if area > best_area:
                best = quad
                best_area = area
    if best is None:
        full = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
        return full, 1.0
    return best, best_area / (w * h)


def _warp_perspective(image: Any, corners: Any) -> Any:
    rect = _order_points(corners)
    tl, tr, br, bl = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width <= 0 or height <= 0:
        return image
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC)


def _upscale(image: Any, min_long: int = 1800) -> Any:
    h, w = image.shape[:2]
    long_edge = max(h, w)
    if long_edge >= min_long:
        return image
    scale = min_long / long_edge
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def _binarize(warped: Any, block_size: int = 31, c: int = 10) -> Any:
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 8, 7, 21)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _soften_for_ocr(warped: Any) -> Any:
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 6, 7, 21)
    gray = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _encode_png(image: Any) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Failed to encode pseudo-scan image")
    return bytes(buf.tobytes())


def _build_pseudo_scans(image_bytes: bytes) -> list[tuple[str, bytes, str]]:
    """Return pseudo-scans for retrying hard OCR pages.

    Output tuples are: (scan_name, png_bytes, mime).
    """
    if cv2 is None or np is None:
        return []
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    color_corners, _color_ratio = _find_quad_color(image)
    edge_corners, _edge_ratio = _find_quad_edge(gray)

    color_warp = _binarize(_upscale(_warp_perspective(image, color_corners)))
    edge_warp = _binarize(_upscale(_warp_perspective(image, edge_corners)))
    edge_soft = _soften_for_ocr(_upscale(_warp_perspective(image, edge_corners)))

    scans: list[tuple[str, bytes, str]] = []
    h_color = color_warp.shape[0]
    color_header = color_warp[: int(h_color * 0.60), :]
    scans.append(("color_header", _encode_png(color_header), "image/png"))
    scans.append(("edge_lease", _encode_png(edge_warp), "image/png"))
    right_start = int(edge_warp.shape[1] * 0.52)
    scans.append(("edge_amounts", _encode_png(edge_warp[:, right_start:]), "image/png"))
    scans.append(("edge_soft", _encode_png(edge_soft), "image/png"))
    return scans


async def _extract_primary_pass(
    image_bytes: bytes,
    mime: str,
    llm: LLMClient,
) -> dict[str, Any]:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = await llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract this deal contract. Respond with ONLY the JSON object. "
                            "In the Lease table read each row separately: Term (e.g. 48), "
                            "Payment Frequency (e.g. Bi-Weekly), Number of Payments (e.g. 104), "
                            "and the printed Payment amount (e.g. 253.29). "
                            "Never set num_payments equal to term unless the sheet shows that."
                        ),
                    },
                ],
            },
        ],
        timeout=300,
        temperature=0.0,
        max_tokens=16384,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    message = response["choices"][0]["message"]
    return _parse_model_message(message)


def _score_extraction_candidate(extracted: dict[str, Any], parsed: dict[str, Any]) -> int:
    score = 0
    if extracted.get("deal_type") in _DEAL_TYPES:
        score += 10
    for field in ("make", "model", "model_year", "selling_price", "contract_date"):
        if extracted.get(field) not in (None, ""):
            score += 4
    if extracted.get("deal_type") == "lease":
        for field in ("term", "num_payments", "payment_frequency", "payment_amount", "rate_pct"):
            if extracted.get(field) not in (None, ""):
                score += 5
    if extracted.get("line_items"):
        score += min(10, len(extracted["line_items"]) * 2)
    if extracted.get("vin"):
        score += 12
    if extracted.get("stock_number"):
        score += 5
    if extracted.get("trades"):
        score += 12
    if extracted.get("confidence") is not None:
        score += int(float(extracted["confidence"]) * 10)
    if _terms_look_suspicious(extracted, parsed):
        score -= 18
    if _pricing_looks_suspicious(extracted):
        score -= 14
    return score


def _walk_dict(obj: Any) -> list[tuple[str, Any]]:
    """Depth-first (key, value) pairs from nested dicts/lists."""
    found: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.append((key, value))
            found.extend(_walk_dict(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_dict(item))
    return found


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "").replace(" ", "").replace("_", "")


def _scan_frequency_from_raw(parsed: dict[str, Any]) -> str | None:
    """Find bi-weekly / monthly hints anywhere in model output."""
    for _key, value in _walk_dict(parsed):
        if not isinstance(value, str):
            continue
        norm = value.strip().lower().replace("-", "").replace(" ", "").replace("_", "")
        if "biweek" in norm or norm in {"biwk", "biweekly", "biweekly"}:
            return "biweekly"
        if "semimonth" in norm or "twiceamonth" in norm:
            return "semimonthly"
        if "monthly" in norm or (norm == "month"):
            return "monthly"
        if norm == "weekly" or (norm.endswith("weekly") and "bi" not in norm):
            return "weekly"
    return None


def _scan_term_candidates(parsed: dict[str, Any]) -> list[int]:
    """Collect term_months candidates from keys labeled Term (not payment count)."""
    candidates: list[int] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm in _NUM_PAYMENT_KEYS or "payment" in norm and "term" not in norm:
            continue
        if norm not in _TERM_KEY_NAMES and not norm.endswith("term"):
            continue
        n = _to_int(value)
        if n is not None and 24 <= n <= 96:
            candidates.append(n)
    return sorted(set(candidates))


def _scan_large_payment_counts(parsed: dict[str, Any]) -> list[int]:
    """Ints that look like total payment counts (> term, typical bi-weekly lease)."""
    candidates: list[int] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm in _NUM_PAYMENT_KEYS or "payment" in norm and "amount" not in norm:
            n = _to_int(value)
            if n is not None and 50 <= n <= 250:
                candidates.append(n)
    return sorted(set(candidates))


def _looks_computed_payment(
    payment: float | None,
    selling_price: float | None,
    capital_cost: float | None,
    term_months: int | None,
) -> bool:
    if payment is None:
        return False
    if term_months and term_months > 0:
        for price in (selling_price, capital_cost):
            if price and abs(payment - price / term_months) < 80:
                return True
    # Bi-weekly lease per-payment amounts are rarely above ~$500 on passenger sheets.
    return payment > 800


def _max_plausible_payment(frequency: str | None, deal_type: str | None) -> float:
    """Upper bound for a per-period payment before we treat it as a hallucination."""
    if deal_type == "lease" and frequency == "biweekly":
        return 500.0
    if deal_type == "lease" and frequency == "weekly":
        return 350.0
    if frequency == "monthly":
        return 2500.0
    return 800.0


def _payment_pair_looks_valid(base: float | None, total: float | None) -> bool:
    """Canadian lease sheets show base (pre-tax) and total (incl. ~15% HST) on separate rows."""
    if base is None or total is None or base <= 0 or total <= 0:
        return False
    if total <= base:
        return False
    ratio = total / base
    return 1.05 <= ratio <= 1.25


def _collect_payment_candidates(parsed: dict[str, Any]) -> list[float]:
    """All payment-sized dollar amounts anywhere in model output."""
    candidates: list[float] = []
    for _key, value in _walk_dict(parsed):
        n = _to_number(value)
        if n is not None and 50 <= n <= 800:
            candidates.append(n)
    return sorted(set(candidates))


def _find_hst_payment_pair(parsed: dict[str, Any]) -> tuple[float | None, float | None]:
    """Prefer a base/total pair whose ratio matches printed HST (~15%)."""
    amounts = _collect_payment_candidates(parsed)
    best: tuple[float | None, float | None] = (None, None)
    best_ratio_delta = 999.0
    for base in amounts:
        for total in amounts:
            if total <= base:
                continue
            ratio = total / base
            if not (1.05 <= ratio <= 1.25):
                continue
            delta = abs(ratio - 1.15)
            if delta < best_ratio_delta:
                best_ratio_delta = delta
                best = (base, total)
    return best


def _payments_look_suspicious(out: dict[str, Any]) -> bool:
    """Heuristics for model-computed or mis-read payment rows."""
    deal_type = out.get("deal_type")
    freq = out.get("payment_frequency")
    base = out.get("base_payment")
    payment = out.get("payment_amount")
    if payment is None:
        return False
    cap = _max_plausible_payment(freq if isinstance(freq, str) else None, deal_type)
    if payment > cap:
        return True
    if base is not None and abs(base - payment) < 0.02:
        # Real sheets always show pre-tax base below tax-included total.
        return deal_type == "lease"
    if deal_type == "lease" and base is not None and not _payment_pair_looks_valid(base, payment):
        return True
    if (
        deal_type == "finance"
        and out.get("rate_pct") == 0
        and freq == "monthly"
        and out.get("term") == out.get("num_payments")
    ):
        return False
    return _looks_computed_payment(
        payment, out.get("selling_price"), out.get("capital_cost"), out.get("term")
    )


def _fix_swapped_term_and_payment_count(out: dict[str, Any]) -> None:
    """Bi-weekly leases often mis-place term (48) into num_payments, then infer term=22."""
    freq = out.get("payment_frequency")
    num = out.get("num_payments")
    term = out.get("term")
    if num is None or freq != "biweekly":
        return
    if num in _COMMON_TERM_MONTHS:
        expected = _expected_num_payments(num, "biweekly")
        if expected != num:
            out["term"] = num
            out["num_payments"] = expected
            return
    if (
        term is not None
        and num in _COMMON_TERM_MONTHS
        and term not in _COMMON_TERM_MONTHS
        and _payment_term_mismatch(term, "biweekly", num) <= 1
    ):
        out["term"] = num
        out["num_payments"] = _expected_num_payments(num, "biweekly")


def _scan_rate_candidates(parsed: dict[str, Any]) -> list[float]:
    candidates: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm not in _RATE_KEYS and not (norm.endswith("rate") and "payment" not in norm):
            continue
        if any(x in norm for x in ("payment", "residual", "excess", "km")):
            continue
        n = _to_number(value)
        if n is not None and 0.01 <= n <= 25:
            candidates.append(n)
    return candidates


def _payment_looks_like_rate(payment: float | None, rate: float | None) -> bool:
    if payment is None or rate is None:
        return False
    return abs(payment - rate) < 0.05 or abs(payment - rate * 100) < 2


def _pick_best_base_payment(parsed: dict[str, Any]) -> float | None:
    bases: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm not in {"basepayment", "basepmt", "paymentbeforetax", "pretaxpayment"} and "base" not in norm:
            continue
        n = _to_number(value)
        if n is not None and 50 <= n <= 800:
            bases.append(n)
    return min(bases) if bases else None


def _reconcile_payment_pair(out: dict[str, Any], parsed: dict[str, Any]) -> None:
    """Fix equal/wrong base+total using HST-linked pairs from raw model output."""
    # Finance sheets show one monthly payment, not lease-style pre/post-HST
    # payment rows. Searching all dollar values for an HST ratio can mistake
    # an admin fee for the payment total.
    if out.get("deal_type") != "lease":
        return
    pair_base, pair_total = _find_hst_payment_pair(parsed)
    if pair_total is None:
        return

    base = out.get("base_payment")
    payment = out.get("payment_amount")
    current_valid = _payment_pair_looks_valid(base, payment)
    if current_valid and not _payments_look_suspicious(out):
        return

    out["payment_amount"] = pair_total
    out["base_payment"] = pair_base


def _reconcile_rate_and_payments(out: dict[str, Any], parsed: dict[str, Any]) -> None:
    rates = _scan_rate_candidates(parsed)
    if rates:
        current = out.get("rate_pct")
        if current in (None, 0):
            out["rate_pct"] = min(rates, key=lambda r: abs(r - 5.99)) if len(rates) > 1 else rates[0]

    _reconcile_payment_pair(out, parsed)

    rate = out.get("rate_pct")
    payment = out.get("payment_amount")
    freq = out.get("payment_frequency")
    deal_type = out.get("deal_type")
    if _payment_looks_like_rate(payment, rate) or _payments_look_suspicious(out):
        alt = _pick_best_payment_amount(
            parsed,
            out.get("selling_price"),
            out.get("term"),
            frequency=freq if isinstance(freq, str) else None,
            deal_type=deal_type if isinstance(deal_type, str) else None,
        )
        if alt is not None:
            out["payment_amount"] = alt
    base = out.get("base_payment")
    if (
        _payment_looks_like_rate(base, rate)
        or (base is not None and base > _max_plausible_payment(
            freq if isinstance(freq, str) else None,
            deal_type if isinstance(deal_type, str) else None,
        ))
        or (base is not None and out.get("payment_amount") is not None and abs(base - out["payment_amount"]) < 0.02)
    ):
        out["base_payment"] = _pick_best_base_payment(parsed)
        pair_base, _pair_total = _find_hst_payment_pair(parsed)
        if pair_base is not None:
            out["base_payment"] = pair_base


def _null_zero_placeholders(out: dict[str, Any]) -> None:
    """Vision models use 0 for 'not read' — treat as null for optional fields."""
    for field in _ZERO_MEANS_UNKNOWN:
        if out.get(field) == 0:
            out[field] = None


def _scan_dates_for_field(parsed: dict[str, Any], field: str) -> list[str]:
    hints = _DATE_KEY_HINTS.get(field, frozenset())
    found: list[str] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm not in hints and not any(norm == _normalize_key(h) for h in hints):
            continue
        iso = _to_date(value)
        if iso:
            found.append(iso)
    return found


def _reconcile_dates_and_year(out: dict[str, Any], parsed: dict[str, Any]) -> None:
    make = str(out.get("make") or parsed.get("make") or "").lower()
    model = str(out.get("model") or parsed.get("model") or "").lower()
    vehicle_years: list[int] = []
    other_years: list[int] = []
    for key, value in _walk_dict(parsed):
        if not isinstance(value, str):
            continue
        norm = _normalize_key(key)
        vl = value.lower()
        for match in re.finditer(r"\b(20\d{2})\b", value):
            y = int(match.group(1))
            if not (2010 <= y <= 2035):
                continue
            if (
                (make and make in vl)
                or (model and model in vl)
                or norm in {"make", "model", "vehicle", "description", "modelyear"}
            ):
                vehicle_years.append(y)
            else:
                other_years.append(y)
    if vehicle_years:
        out["model_year"] = min(vehicle_years)
    elif other_years and not out.get("model_year"):
        out["model_year"] = min(other_years)

    model_year = out.get("model_year")
    if not model_year:
        return

    for field in _DATE_FIELDS:
        alts = _scan_dates_for_field(parsed, field)
        if not alts:
            continue
        best = min(alts, key=lambda d: abs(int(d[:4]) - model_year))
        current = out.get(field)
        if not current:
            out[field] = best
            continue
        if abs(int(current[:4]) - model_year) > abs(int(best[:4]) - model_year):
            out[field] = best


def _collect_int_candidates(parsed: dict[str, Any], key_names: frozenset[str]) -> list[int]:
    """Gather integer candidates for a field from all nested keys."""
    candidates: list[int] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm not in key_names and not any(norm == _normalize_key(k) for k in key_names):
            continue
        n = _to_int(value)
        if n is not None and n > 0:
            candidates.append(n)
    return candidates


def _expected_num_payments(term_months: int, frequency: str) -> int:
    return round(term_months * _PAYMENTS_PER_YEAR[frequency] / 12)


def _infer_term_months(num_payments: int, frequency: str) -> int:
    return round(num_payments * 12 / _PAYMENTS_PER_YEAR[frequency])


_COMMON_TERM_MONTHS = frozenset({24, 36, 39, 42, 48, 51, 54, 60, 72, 84})
_FREQ_PREFERENCE = {"biweekly": 0, "monthly": 1, "semimonthly": 2, "weekly": 3}
_RATE_KEYS = frozenset({"ratepct", "rate", "interestrate", "apr", "leaserate", "financerate"})
_ZERO_MEANS_UNKNOWN = (
    "odometer_at_deal", "km_per_year", "residual_value", "buy_option_price",
    "security_deposit", "cap_reduction", "trade_equity", "residual_msrp",
)
_DATE_KEY_HINTS = {
    "contract_date": frozenset({"contractdate", "contract_date"}),
    "delivery_date": frozenset({"deliverydate", "delivery_date"}),
    "first_payment_date": frozenset({"firstpaymentdate", "first_payment_date", "paymentdate", "payment_date"}),
}


def _payment_term_mismatch(term_months: int | None, frequency: str | None, num_payments: int | None) -> int:
    """Return absolute diff between expected and actual payment count (0 = perfect)."""
    if term_months is None or frequency is None or num_payments is None:
        return 999
    return abs(_expected_num_payments(term_months, frequency) - num_payments)


def _combo_sort_key(
    term_months: int,
    frequency: str,
    num_payments: int,
    deal_type: str | None,
) -> tuple[int, int, int, int]:
    """Lower is better: mismatch, non-standard term, frequency preference, term distance from 48."""
    mismatch = _payment_term_mismatch(term_months, frequency, num_payments)
    standard_penalty = 0 if term_months in _COMMON_TERM_MONTHS else 1
    freq_rank = _FREQ_PREFERENCE.get(frequency, 9)
    if deal_type == "lease" and frequency == "monthly":
        freq_rank += 5
    if deal_type == "lease" and frequency == "biweekly":
        freq_rank -= 2
    term_penalty = abs(term_months - 48)
    return (mismatch, standard_penalty, freq_rank, term_penalty)


def _pick_best_num_payments(parsed: dict[str, Any], term_months: int | None) -> int | None:
    """When the model duplicates term into num_payments, recover the real count from raw JSON."""
    candidates = _collect_int_candidates(parsed, _NUM_PAYMENT_KEYS)
    candidates.extend(_scan_large_payment_counts(parsed))
    if not candidates and term_months is not None:
        # Scan for payment-count-sized ints that exceed term (bi-weekly lease pattern).
        for _key, value in _walk_dict(parsed):
            n = _to_int(value)
            if n is None or n <= term_months or n > 250:
                continue
            if any(abs(_expected_num_payments(t, f) - n) <= 1 for t in (36, 39, 42, 48, 51, 54, 60, 72) for f in _FREQUENCIES):
                candidates.append(n)

    if not candidates:
        return None
    unique = sorted(set(candidates))
    if term_months is not None:
        scored = sorted(
            unique,
            key=lambda n: (
                0 if n > term_months else 1,
                min(_payment_term_mismatch(term_months, f, n) for f in _FREQUENCIES),
            ),
        )
        return scored[0]
    return max(unique)


def _pick_best_payment_amount(
    parsed: dict[str, Any],
    selling_price: float | None,
    term_months: int | None,
    *,
    frequency: str | None = None,
    deal_type: str | None = None,
) -> float | None:
    """Prefer the printed total Payment row; ignore base_pmt and price÷term hallucinations."""
    pair_base, pair_total = _find_hst_payment_pair(parsed)
    if pair_total is not None:
        return pair_total

    total_keys = frozenset({
        "paymentamount", "payment", "totalpayment", "pmtamount",
        "paymenttotal", "leasepayment",
    })
    base_keys = frozenset({"basepayment", "basepmt", "paymentbeforetax", "pretaxpayment"})

    totals: list[float] = []
    bases: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        n = _to_number(value)
        if n is None or n <= 0 or n > 5000:
            continue
        if norm in total_keys or (norm.endswith("payment") and "base" not in norm):
            totals.append(n)
        elif norm in base_keys or "base" in norm:
            bases.append(n)

    candidates = totals or bases
    if not candidates:
        return None

    cap = _max_plausible_payment(frequency, deal_type)

    def _filter_computed(vals: list[float]) -> list[float]:
        if term_months is None or term_months <= 0:
            return vals
        filtered = [
            c for c in vals
            if selling_price is None or abs(c - selling_price / term_months) >= 80
        ]
        return filtered or vals

    filtered = _filter_computed(candidates)
    reasonable = [c for c in filtered if 50 <= c <= cap]
    pool = reasonable if reasonable else [c for c in filtered if c <= cap] or filtered
    return min(pool) if totals else min(pool)


def _reconcile_payment_terms(out: dict[str, Any], parsed: dict[str, Any]) -> None:
    """Fix common vision-model errors: wrong term/freq/num triples and computed payments."""
    _fix_swapped_term_and_payment_count(out)
    deal_type = out.get("deal_type")
    raw_freq = _scan_frequency_from_raw(parsed)

    selling = out.get("selling_price")
    capital = out.get("capital_cost")
    term = out.get("term")
    payment = out.get("payment_amount")

    if _payments_look_suspicious(out):
        alt_payment = _pick_best_payment_amount(
            parsed, selling, term,
            frequency=out.get("payment_frequency"),
            deal_type=deal_type if isinstance(deal_type, str) else None,
        )
        if alt_payment is not None:
            out["payment_amount"] = alt_payment
            payment = alt_payment
        pair_base, pair_total = (
            _find_hst_payment_pair(parsed) if deal_type == "lease" else (None, None)
        )
        if pair_total is not None:
            out["payment_amount"] = pair_total
            out["base_payment"] = pair_base
            payment = pair_total
        elif out.get("base_payment") and _looks_computed_payment(
            out.get("base_payment"), selling, capital, term
        ):
            out["base_payment"] = None

    term_candidates = _scan_term_candidates(parsed)
    num_candidates = _scan_large_payment_counts(parsed) or _collect_int_candidates(parsed, _NUM_PAYMENT_KEYS)

    if term_candidates:
        out["term"] = term_candidates[-1] if len(term_candidates) == 1 else max(
            term_candidates,
            key=lambda t: (
                0 if t in _COMMON_TERM_MONTHS else 1,
                abs(t - 48),
            ),
        )

    alt_num = _pick_best_num_payments(parsed, out.get("term"))
    if alt_num is not None:
        current_num = out.get("num_payments")
        if current_num is None or (
            out.get("term") is not None
            and current_num <= out["term"]
            and alt_num > out["term"]
        ):
            out["num_payments"] = alt_num

    if raw_freq:
        out["payment_frequency"] = raw_freq

    term = out.get("term")
    num = out.get("num_payments")
    if num is None:
        return

    current_freq = out.get("payment_frequency") or "monthly"
    original_key = _combo_sort_key(term or 0, current_freq, num, deal_type)
    if original_key[0] == 0 and deal_type != "lease":
        return  # finance/cash combo already consistent — do not swap math alternatives

    freqs_to_try: list[str | None] = []
    if raw_freq:
        freqs_to_try.append(raw_freq)
    if out.get("payment_frequency"):
        freqs_to_try.append(out["payment_frequency"])
    freqs_to_try.extend(_FREQUENCIES)

    terms_to_try: list[int | None] = list(term_candidates)
    if term is not None:
        terms_to_try.append(term)
    nums_to_try = sorted(set(num_candidates + ([num] if num else [])))

    best_combo = (term, out.get("payment_frequency"), num)
    best_key = _combo_sort_key(
        term or 0,
        out.get("payment_frequency") or "monthly",
        num,
        deal_type if isinstance(deal_type, str) else None,
    )

    seen_freqs: set[str | None] = set()
    for candidate_freq in freqs_to_try:
        if candidate_freq in seen_freqs:
            continue
        seen_freqs.add(candidate_freq)
        for candidate_term in terms_to_try:
            if candidate_term is None or not (12 <= candidate_term <= 96):
                continue
            for candidate_num in nums_to_try:
                key = _combo_sort_key(
                    candidate_term, candidate_freq or "monthly", candidate_num, deal_type
                )
                if key < best_key:
                    best_key = key
                    best_combo = (candidate_term, candidate_freq, candidate_num)

    best_term, best_freq, best_num = best_combo
    if best_key[0] <= 1 and best_term and best_num and best_freq:
        out["term"] = best_term
        out["payment_frequency"] = best_freq
        out["num_payments"] = best_num

    # Canadian leases are bi-weekly unless the sheet explicitly says otherwise.
    if deal_type == "lease":
        if out.get("payment_frequency") == "semimonthly" and raw_freq != "semimonthly":
            out["payment_frequency"] = raw_freq or "biweekly"
        if (
            out.get("num_payments")
            and out.get("term")
            and out["num_payments"] > out["term"]
            and out.get("payment_frequency") in (None, "monthly", "semimonthly")
        ):
            out["payment_frequency"] = "biweekly"
            inferred = _infer_term_months(out["num_payments"], "biweekly")
            if 12 <= inferred <= 96:
                out["term"] = inferred

    # Anchor on plausible per-payment amount when combo still looks wrong.
    payment = out.get("payment_amount")
    if payment and 50 <= payment <= 800 and out.get("num_payments"):
        for candidate_freq in ("biweekly", "monthly", "semimonthly", "weekly"):
            inferred_term = _infer_term_months(out["num_payments"], candidate_freq)
            if 12 <= inferred_term <= 96 and _payment_term_mismatch(
                inferred_term, candidate_freq, out["num_payments"]
            ) <= 1:
                if deal_type == "lease" and candidate_freq == "monthly" and raw_freq != "monthly":
                    continue
                out["term"] = inferred_term
                out["payment_frequency"] = candidate_freq
                break

    _fix_swapped_term_and_payment_count(out)


def _normalize_percentage_fields(out: dict[str, Any]) -> None:
    """Models sometimes output 47% as 0.47 or 47/100."""
    if out.get("deal_type") != "lease":
        return
    pct = out.get("residual_pct")
    if pct is not None and 0 < pct < 1:
        out["residual_pct"] = round(pct * 100, 4)


def _reconcile_lease_fields(out: dict[str, Any], parsed: dict[str, Any]) -> None:
    if out.get("deal_type") != "lease":
        return

    pct_candidates: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if "residual" in norm and "msrp" not in norm and "value" not in norm and "amount" not in norm:
            n = _to_number(value)
            if n is not None and 0 < n <= 100:
                pct_candidates.append(n if n > 1 else n * 100)
    if pct_candidates:
        reasonable = [p for p in pct_candidates if 35 <= p <= 65]
        if reasonable:
            out["residual_pct"] = min(reasonable, key=lambda p: abs(p - 47))

    km_candidates: list[int] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if "km" in norm or "kpy" in norm or norm == "kmallowed":
            n = _to_int(value)
            if n is not None and 8000 <= n <= 30000:
                km_candidates.append(n)
    if km_candidates:
        out["km_per_year"] = max(km_candidates)

    value_candidates: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm in {"residualvalue", "residualamount", "buyoptionprice", "buyoption"} or (
            "residual" in norm and ("value" in norm or norm == "residual")
        ):
            n = _to_number(value)
            if n is not None and n >= 1000:
                value_candidates.append(n)
    if value_candidates:
        best = max(value_candidates)
        if out.get("residual_value") in (None, 0):
            out["residual_value"] = best
        if out.get("buy_option_price") in (None, 0):
            out["buy_option_price"] = best

    msrp_candidates: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if "residual" in norm and "msrp" in norm:
            n = _to_number(value)
            if n is not None and n >= 1000:
                msrp_candidates.append(n)
    if msrp_candidates and out.get("residual_msrp") in (None, 0):
        out["residual_msrp"] = max(msrp_candidates)

    for field, lo, hi in (("excess_km_rate", 0.05, 0.30),):
        val = out.get(field)
        if val is not None and val > hi:
            for _key, raw in _walk_dict(parsed):
                n = _to_number(raw)
                if n is not None and lo <= n <= hi:
                    out[field] = n
                    break

    deposit_candidates: list[float] = []
    for key, value in _walk_dict(parsed):
        if "deposit" in _normalize_key(key):
            n = _to_number(value)
            if n is not None and 0 < n <= 2000:
                deposit_candidates.append(n)
    if deposit_candidates and (out.get("security_deposit") in (None, 0)):
        out["security_deposit"] = min(deposit_candidates)


def _scan_pricing_candidates(parsed: dict[str, Any], field: str) -> list[float]:
    """Collect dollar amounts from keys that match a pricing field label."""
    hints = _PRICING_KEY_HINTS.get(field, frozenset())
    aliases = _FIELD_ALIASES.get(field, ())
    extra = frozenset(_normalize_key(a) for a in aliases)
    all_keys = hints | extra | frozenset({_normalize_key(field)})
    candidates: list[float] = []
    for key, value in _walk_dict(parsed):
        norm = _normalize_key(key)
        if norm not in all_keys and not any(norm.endswith(h) for h in hints):
            continue
        n = _to_number(value)
        if n is not None:
            candidates.append(n)
    return candidates


def _looks_placeholder_amount(value: float | None) -> bool:
    if value is None:
        return False
    rounded = round(abs(value), 2)
    return rounded in _PLACEHOLDER_AMOUNTS or (rounded >= 1000 and rounded % 500 == 0)


def _pricing_looks_suspicious(out: dict[str, Any]) -> bool:
    """Detect invented or mis-mapped pricing on lease/finance sheets."""
    if out.get("deal_type") not in ("lease", "finance"):
        return False
    selling = out.get("selling_price")
    capital = out.get("capital_cost")
    cash = out.get("cash_down") or out.get("cap_reduction")
    drive = out.get("drive_off_total")
    discount = out.get("discount")

    if selling is not None and selling > 50000:
        return True
    if (
        capital is not None
        and selling is not None
        and capital < selling
        and out.get("deal_type") == "lease"
    ):
        return True
    if capital is not None and capital < 35000 and out.get("deal_type") == "lease":
        return True
    if cash is not None and 0 < cash < 3000 and out.get("deal_type") == "lease":
        return True
    if drive is not None and drive > 25000 and out.get("deal_type") == "lease":
        return True
    if discount is not None and discount < -3000:
        return True
    for field in ("selling_price", "capital_cost", "cash_down", "cap_reduction", "drive_off_total"):
        if _looks_placeholder_amount(out.get(field)):
            return True
    return False


def _pick_best_pricing_value(
    parsed: dict[str, Any],
    field: str,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
) -> float | None:
    """Choose the most plausible amount for a pricing field from raw JSON."""
    candidates = _scan_pricing_candidates(parsed, field)
    if not candidates:
        return None
    filtered = candidates
    if min_val is not None:
        filtered = [c for c in filtered if c >= min_val]
    if max_val is not None:
        filtered = [c for c in filtered if c <= max_val]
    if not filtered:
        filtered = candidates
    # Drop obvious placeholders when better options exist.
    non_placeholders = [c for c in filtered if not _looks_placeholder_amount(c)]
    pool = non_placeholders if non_placeholders else filtered

    if field == "selling_price":
        return min(pool, key=lambda v: abs(v - 43000)) if pool else None
    if field == "capital_cost":
        return max(pool) if pool else None
    if field in ("cash_down", "cap_reduction"):
        return max(pool) if pool else None
    if field == "drive_off_total":
        reasonable = [c for c in pool if 5000 <= c <= 20000]
        return min(reasonable, key=lambda v: abs(v - 11000)) if reasonable else None
    if field == "discount":
        negatives = [c for c in pool if c < 0]
        return max(negatives) if negatives else None  # closest to zero
    return pool[0] if pool else None


def _reconcile_pricing_fields(out: dict[str, Any], parsed: dict[str, Any]) -> None:
    """Fix mis-read pricing using labeled rows and lease-sheet arithmetic."""
    if out.get("deal_type") not in ("lease", "finance"):
        return

    # Lift line_items from nested pricing blocks if top-level list is empty.
    if not out.get("line_items"):
        for block_key in ("pricing", "price_breakdown", "fees", "fee_breakdown"):
            block = parsed.get(block_key)
            if isinstance(block, dict) and block.get("line_items"):
                parsed = {**parsed, "line_items": block["line_items"]}
                break

    if _pricing_looks_suspicious(out):
        selling_alt = _pick_best_pricing_value(parsed, "selling_price", min_val=30000, max_val=50000)
        if selling_alt is not None:
            out["selling_price"] = selling_alt

        capital_alt = _pick_best_pricing_value(parsed, "capital_cost", min_val=out.get("selling_price") or 35000)
        if capital_alt is not None:
            out["capital_cost"] = capital_alt

        cash_alt = _pick_best_pricing_value(parsed, "cash_down", min_val=2000)
        cap_alt = _pick_best_pricing_value(parsed, "cap_reduction", min_val=2000)
        if cash_alt is not None:
            out["cash_down"] = cash_alt
        if cap_alt is not None:
            out["cap_reduction"] = cap_alt
        elif cash_alt is not None:
            out["cap_reduction"] = cash_alt

        drive_alt = _pick_best_pricing_value(parsed, "drive_off_total", max_val=25000)
        if drive_alt is not None:
            out["drive_off_total"] = drive_alt

        discount_alt = _pick_best_pricing_value(parsed, "discount", max_val=0)
        if discount_alt is not None and discount_alt > -3000:
            out["discount"] = discount_alt

    # Net lease = capital_cost - cap_reduction (O'Regan sheets print this explicitly).
    net_candidates = _scan_pricing_candidates(parsed, "net_lease")
    capital = out.get("capital_cost")
    cap_red = out.get("cap_reduction") or out.get("cash_down")
    if capital is not None and cap_red is not None:
        expected_net = capital - cap_red
        if net_candidates:
            best_net = min(net_candidates, key=lambda n: abs(n - expected_net))
            if abs(best_net - expected_net) > 500:
                # Cap reduction likely wrong — recover from net lease row.
                implied_cap_red = capital - best_net
                if implied_cap_red > 2000:
                    out["cap_reduction"] = implied_cap_red
                    out["cash_down"] = implied_cap_red

    # Sum line_items into fees_total when individual fees were extracted.
    items = out.get("line_items") or []
    if items:
        fee_sum = sum(
            item["amount"] for item in items
            if item.get("amount", 0) > 0 and item.get("category") != "discount"
        )
        discount_sum = sum(
            item["amount"] for item in items
            if item.get("category") == "discount" or item.get("amount", 0) < 0
        )
        if fee_sum > 0:
            out["fees_total"] = round(fee_sum, 2)
        if discount_sum < 0:
            out["discount"] = round(discount_sum, 2)

    if out.get("deal_type") == "finance":
        selling = out.get("selling_price")
        discount = out.get("discount")
        fees = out.get("fees_total")
        tax = out.get("tax_total")
        trade = out.get("trade_equity")
        if trade in (None, 0) and out.get("trades"):
            trade = sum(
                (item.get("allocation") or 0) - (item.get("lien_payout") or 0)
                for item in out["trades"]
            )
        cash_down = out.get("cash_down")
        if (
            selling is not None
            and discount is not None
            and fees is not None
            and tax is not None
            and trade is not None
            and cash_down is not None
        ):
            total_with_tax = selling + discount + fees - trade + tax
            amount_financed = total_with_tax - cash_down
            if total_with_tax > 0 and amount_financed > 0:
                out["trade_equity"] = round(trade, 2)
                out["total_with_tax"] = round(total_with_tax, 2)
                out["capital_cost"] = round(amount_financed, 2)
                out["drive_off_total"] = round(total_with_tax, 2)

    # selling_price required for save — if still suspicious, keep best effort from capital/fees.
    if out.get("selling_price") is None or (
        out.get("capital_cost") and out["selling_price"] > out["capital_cost"]
    ):
        alt = _pick_best_pricing_value(parsed, "selling_price", min_val=25000, max_val=55000)
        if alt is not None:
            out["selling_price"] = alt


def _terms_look_suspicious(out: dict[str, Any], parsed: dict[str, Any]) -> bool:
    if out.get("deal_type") not in ("lease", "finance"):
        return False
    if _payments_look_suspicious(out):
        return True
    payment = out.get("payment_amount")
    if _looks_computed_payment(
        payment, out.get("selling_price"), out.get("capital_cost"), out.get("term")
    ) and not (
        out.get("deal_type") == "finance"
        and out.get("rate_pct") == 0
        and out.get("payment_frequency") == "monthly"
        and out.get("term") == out.get("num_payments")
    ):
        return True
    if out.get("deal_type") == "lease" and out.get("payment_frequency") == "semimonthly":
        if _scan_frequency_from_raw(parsed) != "semimonthly":
            return True
    raw_freq = _scan_frequency_from_raw(parsed)
    if raw_freq and out.get("payment_frequency") != raw_freq:
        return True
    term_cands = _scan_term_candidates(parsed)
    if term_cands and out.get("term") not in term_cands:
        return True
    num_cands = _scan_large_payment_counts(parsed)
    if num_cands and out.get("num_payments") not in num_cands:
        return True
    if out.get("deal_type") == "lease":
        pct = out.get("residual_pct")
        if pct is not None and pct > 65:
            return True
    if out.get("rate_pct") == 0 and _scan_rate_candidates(parsed):
        return True
    if _payment_looks_like_rate(out.get("payment_amount"), out.get("rate_pct")):
        return True
    if (
        out.get("deal_type") == "lease"
        and out.get("payment_frequency") == "biweekly"
        and out.get("num_payments") in _COMMON_TERM_MONTHS
    ):
        return True
    if out.get("term") is not None and out["term"] not in _COMMON_TERM_MONTHS:
        return True
    if _pricing_looks_suspicious(out):
        return True
    return False


def _merge_parsed(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for field in _LEASE_TABLE_FIELDS + _PRICING_FIELDS:
        value = overlay.get(field)
        if value is not None and str(value).strip() != "":
            merged[field] = value
    if overlay.get("line_items"):
        merged["line_items"] = overlay["line_items"]
    overlay_type = str(overlay.get("deal_type") or "").strip().lower()
    if overlay_type in _DEAL_TYPES:
        merged["deal_type"] = overlay_type
    return merged


def _merge_pricing_pass(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Add focused pricing evidence without replacing reliable full-page fields."""
    merged = copy.deepcopy(base)
    for field in _PRICING_FIELDS:
        value = overlay.get(field)
        if merged.get(field) in (None, "") and value not in (None, ""):
            merged[field] = value

    items = list(merged.get("line_items") or [])
    seen = {
        (_normalize_key(str(item.get("item_name") or item.get("name") or "")), _to_number(item.get("amount")))
        for item in items
        if isinstance(item, dict)
    }
    for item in overlay.get("line_items") or []:
        if not isinstance(item, dict):
            continue
        key = (
            _normalize_key(str(item.get("item_name") or item.get("name") or "")),
            _to_number(item.get("amount")),
        )
        if key not in seen:
            items.append(item)
            seen.add(key)

    overlay_discount = _to_number(overlay.get("discount"))
    discount_amounts = {
        _to_number(item.get("amount"))
        for item in items
        if isinstance(item, dict)
        and (
            item.get("category") == "discount"
            or (_to_number(item.get("amount")) or 0) < 0
        )
    }
    if overlay_discount is not None and overlay_discount < 0 and overlay_discount not in discount_amounts:
        items.append(
            {"item_name": "Discount", "category": "discount", "amount": overlay_discount}
        )
    if items:
        merged["line_items"] = items
    return merged


async def _extract_lease_table(
    image_bytes: bytes, mime: str, llm: LLMClient
) -> dict[str, Any]:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = await llm.chat(
        [
            {"role": "system", "content": _LEASE_TABLE_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Read ONLY the Lease or Finance table. "
                            "Return ONLY the JSON object. "
                            "Term and Number of Payments are separate rows."
                        ),
                    },
                ],
            },
        ],
        timeout=300,
        temperature=0.0,
        max_tokens=8192,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    return _parse_model_message(response["choices"][0]["message"])


async def _extract_pricing_block(
    image_bytes: bytes, mime: str, llm: LLMClient
) -> dict[str, Any]:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = await llm.chat(
        [
            {"role": "system", "content": _PRICING_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Read ONLY the pricing / fee breakdown column. "
                            "Return ONLY the JSON object. "
                            "Capital Cost is Sub-Total BEFORE cap reduction; "
                            "Drive Off is NOT Net Lease."
                        ),
                    },
                ],
            },
        ],
        timeout=300,
        temperature=0.0,
        max_tokens=8192,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    return _parse_model_message(response["choices"][0]["message"])


def _to_number(value: Any) -> float | None:
    """Coerce '42,340.00', '(700)', '($221.70)', 394.12 -> signed float; None on failure."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").replace("%", "").strip()
    if s.startswith("-"):
        negative = True
        s = s[1:]
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if negative else n


def _to_int(value: Any) -> int | None:
    n = _to_number(value)
    return int(n) if n is not None else None


def _to_date(value: Any) -> str | None:
    """Normalize to ISO YYYY-MM-DD; accepts MM/DD/YYYY as printed on contracts."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _first_text(source: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _to_text(source.get(key))
        if value is not None:
            return value
    return None


def _first_value(source: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _flatten_term_blocks(parsed: dict[str, Any]) -> dict[str, Any]:
    """Lift nested lease/finance blocks and alias keys to canonical top-level names."""
    out = dict(parsed)
    sources: list[dict[str, Any]] = [parsed]
    for block_key in _NESTED_TERM_BLOCKS:
        block = parsed.get(block_key)
        if isinstance(block, dict):
            sources.append(block)
            for key, value in block.items():
                if out.get(key) in (None, "") and value not in (None, ""):
                    out[key] = value

    for canonical, aliases in _FIELD_ALIASES.items():
        if out.get(canonical) not in (None, ""):
            continue
        for source in sources:
            value = _first_value(source, (canonical, *aliases))
            if value is not None:
                out[canonical] = value
                break

    # Pricing blocks often nest under "pricing" with different key names.
    for field, hints in _PRICING_KEY_HINTS.items():
        if out.get(field) not in (None, ""):
            continue
        for key, value in _walk_dict(parsed):
            norm = _normalize_key(key)
            if norm in hints:
                v = _to_number(value) if field != "net_lease" else _to_number(value)
                if v is not None:
                    out[field] = v
                    break

    deal_type = str(out.get("deal_type") or "").strip().lower()
    if deal_type not in _DEAL_TYPES:
        if isinstance(parsed.get("lease"), dict) or _first_value(out, ("km_per_year", *_FIELD_ALIASES["km_per_year"])):
            out["deal_type"] = "lease"
        elif any(
            _first_value(out, (canonical, *_FIELD_ALIASES.get(canonical, ())))
            for canonical in ("lender", "rate_pct", "term", "payment_amount")
        ):
            out["deal_type"] = "finance"

    return out


def _normalize_customer(parsed: dict[str, Any]) -> dict[str, str | None]:
    """Map customer contact fields from nested or flattened model output."""
    raw = parsed.get("customer")
    if isinstance(raw, str):
        cust: dict[str, Any] = {"name": raw}
    elif isinstance(raw, dict):
        cust = raw
    else:
        cust = {}

    return {
        "name": _first_text(cust, _CUSTOMER_NAME_KEYS) or _first_text(parsed, _CUSTOMER_NAME_KEYS),
        "phone": _first_text(cust, _CUSTOMER_PHONE_KEYS) or _first_text(parsed, _CUSTOMER_PHONE_ROOT_KEYS),
        "email": _first_text(cust, _CUSTOMER_EMAIL_KEYS) or _first_text(parsed, _CUSTOMER_EMAIL_ROOT_KEYS),
    }


def _clean(parsed: dict[str, Any]) -> dict[str, Any]:
    parsed = _flatten_term_blocks(parsed)
    out: dict[str, Any] = {}

    deal_type = str(parsed.get("deal_type") or "").strip().lower()
    out["deal_type"] = deal_type if deal_type in _DEAL_TYPES else None

    condition = str(parsed.get("condition") or "").strip().lower()
    out["condition"] = condition if condition in _CONDITIONS else "new"

    freq = str(parsed.get("payment_frequency") or "").strip().lower().replace("-", "").replace(" ", "").replace("_", "")
    if freq in ("biweekly", "biwkly", "biweek"):
        freq = "biweekly"
    elif freq in ("semimonthly", "semimonth", "twicemonthly"):
        freq = "semimonthly"
    out["payment_frequency"] = freq if freq in _FREQUENCIES else None

    for f in _TEXT_FIELDS:
        out[f] = _to_text(parsed.get(f))
    for f in _DATE_FIELDS:
        out[f] = _to_date(parsed.get(f))
    for f in _INT_FIELDS:
        out[f] = _to_int(parsed.get(f))
    for f in _MONEY_FIELDS:
        out[f] = _to_number(parsed.get(f))

    # Lease-only columns must be NULL for non-lease deals (DB CHECK constraint)
    if out["deal_type"] != "lease":
        for f in _LEASE_ONLY_FIELDS:
            out[f] = None

    line_items = []
    for item in parsed.get("line_items") or []:
        if not isinstance(item, dict):
            continue
        name = _to_text(item.get("item_name") or item.get("name"))
        amount = _to_number(item.get("amount"))
        if name is None or amount is None:
            continue
        category = str(item.get("category") or "").strip().lower()
        if category not in _CATEGORIES:
            category = "discount" if amount < 0 else "other"
        line_items.append({"item_name": name, "category": category, "amount": amount})
    out["line_items"] = line_items

    trades = []
    for tr in parsed.get("trades") or []:
        if not isinstance(tr, dict):
            continue
        trade = {
            "make": _to_text(tr.get("make")),
            "model": _to_text(tr.get("model")),
            "model_year": _to_int(tr.get("model_year") or tr.get("year")),
            "trim_base": _to_text(tr.get("trim_base") or tr.get("trim")),
            "vin": _to_text(tr.get("vin")),
            "mileage": _to_int(tr.get("mileage")),
            "exterior_color": _to_text(tr.get("exterior_color") or tr.get("color")),
            "allocation": _to_number(tr.get("allocation")),
            "lien_payout": _to_number(tr.get("lien_payout")) or 0,
        }
        if any(v is not None for v in trade.values()):
            trades.append(trade)
    out["trades"] = trades

    out["customer"] = _normalize_customer(parsed)

    confidence = _to_number(parsed.get("confidence"))
    out["confidence"] = max(0.0, min(1.0, confidence)) if confidence is not None else None

    _null_zero_placeholders(out)
    _normalize_percentage_fields(out)
    _reconcile_rate_and_payments(out, parsed)
    _reconcile_payment_terms(out, parsed)
    _reconcile_lease_fields(out, parsed)
    _reconcile_pricing_fields(out, parsed)
    _reconcile_dates_and_year(out, parsed)

    # Drop computed/hallucinated payments we could not correct from raw JSON.
    if _payments_look_suspicious(out):
        pair_base, pair_total = _find_hst_payment_pair(parsed)
        if pair_total is not None:
            out["payment_amount"] = pair_total
            out["base_payment"] = pair_base
        else:
            out["payment_amount"] = None
            out["base_payment"] = None

    return out


def _strip_reasoning(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Some reasoning models emit JSON after a closing think tag.
    think_close = "</" + "think>"
    if think_close in text:
        _, _, tail = text.partition(think_close)
        text = tail if tail.strip() else re.sub(r"<" + "think>.*?" + think_close, "", text, flags=re.DOTALL)
    return re.sub(r"```(?:json)?", "", text).strip()


def _parse_json_content(content: str) -> dict[str, Any]:
    """Parse the first JSON object from model text.

    Models sometimes append a second JSON blob or trailing prose after the
    deal object; greedy ``\\{.*\\}`` + ``json.loads`` then raises "Extra data".
    """
    clean = _strip_reasoning(content)
    start = clean.find("{")
    if start == -1:
        raise ValueError("Deal extractor did not produce a JSON result.")
    try:
        obj, _end = json.JSONDecoder().raw_decode(clean, start)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Deal extractor returned invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("Deal extractor returned a non-object JSON result.")
    return obj


def _parse_model_message(message: dict[str, Any]) -> dict[str, Any]:
    """Parse deal JSON from assistant message fields."""
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        args = tool_calls[0]["function"]["arguments"]
        if isinstance(args, str):
            return _parse_json_content(args)
        if isinstance(args, dict):
            return args
        raise ValueError("Deal extractor tool call had invalid arguments.")

    chunks: list[str] = []
    for key in ("content", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            chunks.append(value)

    if not chunks:
        raise ValueError("Deal extractor did not produce a JSON result.")

    last_error: ValueError | None = None
    for text in chunks + ["\n".join(chunks)]:
        try:
            return _parse_json_content(text)
        except ValueError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


async def run_deal_extractor(image_bytes: bytes, mime: str, llm: LLMClient) -> dict[str, Any]:
    """Returns {"extracted": <cleaned fields>, "raw": <full parsed model output>}."""
    parsed = await _extract_primary_pass(image_bytes, mime, llm)
    extracted = _clean(parsed)
    best_name = "original"
    best_score = _score_extraction_candidate(extracted, parsed)
    confidence = float(extracted.get("confidence") or 0)
    terms_suspicious = _terms_look_suspicious(extracted, parsed)
    identity_confident = confidence >= 0.9 and all(
        extracted.get(field) not in (None, "")
        for field in ("make", "model", "model_year", "vin")
    )

    # Retry with pseudo-scan variants only when primary extraction looks weak.
    if not identity_confident and (terms_suspicious or _pricing_looks_suspicious(extracted)):
        for scan_name, scan_bytes, scan_mime in _build_pseudo_scans(image_bytes):
            try:
                scan_parsed = await _extract_primary_pass(scan_bytes, scan_mime, llm)
                scan_extracted = _clean(scan_parsed)
                scan_score = _score_extraction_candidate(scan_extracted, scan_parsed)
            except Exception:
                continue
            if scan_score > best_score:
                parsed = scan_parsed
                extracted = scan_extracted
                best_score = scan_score
                best_name = scan_name

    parsed["image_pass"] = best_name

    deal_type = extracted.get("deal_type")
    needs_focused_pass = deal_type in ("lease", "finance") and (
        extracted.get("payment_amount") is None
        or _terms_look_suspicious(extracted, parsed)
    )
    if needs_focused_pass:
        try:
            focused = await _extract_lease_table(image_bytes, mime, llm)
            parsed = _merge_parsed(parsed, focused)
            parsed["lease_table_pass"] = focused
            extracted = _clean(parsed)
        except Exception:
            pass

    # Second focused pass when payments still look computed (common on O'Regan lease sheets).
    if deal_type == "lease" and _terms_look_suspicious(extracted, parsed):
        try:
            focused = await _extract_lease_table(image_bytes, mime, llm)
            parsed = _merge_parsed(parsed, focused)
            parsed["lease_table_pass_retry"] = focused
            extracted = _clean(parsed)
        except Exception:
            pass

    # A focused pricing pass can reveal a second discount or fee hidden in the
    # dense column. Merge it conservatively so it cannot replace vehicle/trade
    # identity or the focused finance terms.
    if deal_type in ("lease", "finance"):
        try:
            pricing = await _extract_pricing_block(image_bytes, mime, llm)
            parsed = _merge_pricing_pass(parsed, pricing)
            parsed["pricing_pass"] = pricing
            extracted = _clean(parsed)
        except Exception:
            pass

    return {"extracted": extracted, "raw": copy.deepcopy(parsed)}
