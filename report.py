"""
report.py
─────────────────────────────────────────────
indicators.compute_all_indicators()가 만든 snapshot(dict)을 받아
샘플 리포트(MU 예시)와 유사한 구조의 한국어 분석 텍스트를 생성한다.

핵심 설계: 숫자 계산과 문구 생성을 분리해서,
숫자가 바뀌면 문구도 규칙 기반으로 자동으로 따라가게 만든다.
"""

import numpy as np


def _fmt(x, decimals=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"{x:,.{decimals}f}"


def _pct(a, b):
    if b == 0 or b is None or (isinstance(b, float) and np.isnan(b)):
        return None
    return (a - b) / b * 100


# ─────────────────────────────────────────────
# 규칙 기반 판정 로직
# ─────────────────────────────────────────────

def classify_trend(snap):
    close, ma5, ma20 = snap["close"], snap["ma5"], snap["ma20"]
    if np.isnan(ma5) or np.isnan(ma20):
        return "중립"
    if close > ma5 > ma20:
        return "강세"
    if close < ma5 < ma20:
        return "약세"
    return "혼조"


def classify_momentum(snap):
    rsi = snap["rsi"]
    if np.isnan(rsi):
        return "중립"
    if rsi >= 70:
        return "과매수"
    if rsi <= 30:
        return "과매도"
    return "중립"


def entry_opinion(snap):
    """진입 의견: 매수 / 매도 / 관망 3단 규칙.
    - 지지구간 근접 + RSI 과매도 + 반등 조짐(스토캐스틱 저점) -> '매수 관심'
    - 저항구간 근접 + RSI 과매수 -> '매도/차익실현 관심'
    - 그 외 -> '관망'

    단, 엘더 임펄스 시스템(EMA13 기울기 + MACD 히스토그램 기울기)이 방향성 모멘텀을
    명확히 반대로 확인해주는 상태(적색=신규 매수 자제, 녹색=신규 매도 자제)일 때는
    지지/저항 근접 조건만으로 반대 방향 진입 의견을 내지 않는다.
    (예: 지지구간+RSI 과매도라도 엘더 임펄스가 적색이면 하락 모멘텀이 아직
    꺾이지 않은 것이므로 '매수 관심' 대신 '관망'으로 낮춘다.)
    이 로직은 참고용 휴리스틱이며 투자 조언이 아님.
    """
    close = snap["close"]
    disc_low, disc_high = snap["discount_zone"]
    prem_low, prem_high = snap["premium_zone"]
    rsi = snap["rsi"]
    elder = snap["elder_impulse"]

    near_support = close <= disc_high and close >= snap["swing_low"] * 0.98
    near_resistance = close >= prem_low

    if near_support and rsi <= 45:
        if elder == "red":
            return "관망(지지 구간 근접이나 엘더 임펄스 적색으로 하락 모멘텀 진행 중 - 반전 확인 전 신규 매수 자제)"
        return "매수 관심(지지 구간 반등 확인 후 진입)"
    if near_resistance and rsi >= 60:
        if elder == "green":
            return "관망(저항 구간 근접이나 엘더 임펄스 녹색으로 상승 모멘텀 진행 중 - 신규 매도 자제)"
        return "매도/차익실현 관심"
    return "관망"


def elder_impulse_kr(color):
    mapping = {
        "green": "녹색(강세, 매수 우호)",
        "red": "적색(약세, 신규 매수 자제)",
        "blue": "청색(중립, 양방향 허용)",
    }
    return mapping.get(color, "N/A")


# ─────────────────────────────────────────────
# 리포트 본문 생성
# ─────────────────────────────────────────────

def generate_report(snap, ticker_name="종목"):
    close = snap["close"]
    prev_close = snap["prev_close"]
    chg_pct = _pct(close, prev_close)

    trend = classify_trend(snap)
    momentum = classify_momentum(snap)
    opinion = entry_opinion(snap)

    sqz_txt = "스퀴즈 ON(변동성 수축 국면)" if snap["sqz_on"] else "스퀴즈 OFF(변동성 확장/일반 국면)"
    elder_txt = elder_impulse_kr(snap["elder_impulse"])

    disc_low, disc_high = snap["discount_zone"]
    prem_low, prem_high = snap["premium_zone"]

    lines = []
    lines.append(f"## {ticker_name} 기술적 분석 리포트\n")
    lines.append(
        f"{ticker_name} 주가는 분석 시점 종가 {_fmt(close)}을 기록했습니다"
        + (f" (전일 대비 {chg_pct:+.2f}%)." if chg_pct is not None else ".")
    )
    lines.append(
        f"단기 이동평균선 기준 추세는 **{trend}** 흐름이며, "
        f"MA5({_fmt(snap['ma5'])}) / MA20({_fmt(snap['ma20'])}) 대비 "
        f"현재가는 {'상단' if close > snap['ma5'] else '하단'}에 위치합니다."
    )
    lines.append(
        f"RSI({_fmt(snap['rsi'], 2)})는 **{momentum}** 구간이며, "
        f"스토캐스틱 %K({_fmt(snap['stoch_k'], 2)})/%D({_fmt(snap['stoch_d'], 2)})도 함께 참고할 때 "
        f"단기 반전 가능성을 {'주시할 필요가 있습니다' if momentum != '중립' else '아직 논하기 이릅니다'}."
    )
    lines.append(
        f"ADX({_fmt(snap['adx'], 2)})는 "
        f"{'추세 신뢰도가 높은 편' if snap['adx'] >= 25 else '뚜렷한 추세보다는 변동성 장세에 가까운 편'}입니다."
    )
    lines.append(
        f"볼린저 밴드는 상단 {_fmt(snap['bb_upper'])} / 중심 {_fmt(snap['bb_mid'])} / "
        f"하단 {_fmt(snap['bb_lower'])}이며, {sqz_txt}입니다."
    )
    lines.append(
        f"엘더 임펄스 시스템은 {elder_txt} 상태입니다."
    )

    lines.append("\n### 스마트 머니 컨셉(SMC) & 구조 분석")
    lines.append(
        f"현재가는 디스카운트 존({_fmt(disc_low)}~{_fmt(disc_high)}) "
        f"{'내부' if disc_low <= close <= disc_high else '외부'}에 위치합니다 "
        f"(프리미엄 존: {_fmt(prem_low)}~{_fmt(prem_high)})."
    )
    if snap["choch"] == "bullish":
        lines.append(f"최근 구간에서 상승 전환 CHoCH가 감지되었습니다 (돌파 레벨 {_fmt(snap['choch_level'])}).")
    elif snap["choch"] == "bearish":
        lines.append(f"최근 구간에서 하락 전환 CHoCH가 감지되었습니다 (붕괴 레벨 {_fmt(snap['choch_level'])}).")
    else:
        lines.append("뚜렷한 구조적 전환(CHoCH) 신호는 아직 확인되지 않았습니다.")
    lines.append(
        f"거래량 프로파일 POC는 {_fmt(snap['poc'])} 부근이며, "
        f"최근 20봉 매수 우위 비율은 {_fmt(snap['buy_volume_ratio'], 1)}%입니다."
    )

    lines.append("\n### 진입 의견")
    lines.append(f"**{opinion}**")

    lines.append("\n### 주요 레벨")
    lines.append(f"- 저항: VWAP {_fmt(snap['vwap'])} / 피벗 R1 {_fmt(snap['pivot_r1'])} / R2 {_fmt(snap['pivot_r2'])}")
    lines.append(f"- 지지: 돈치안 하단 {_fmt(snap['donchian_lower'])} / 피벗 S1 {_fmt(snap['pivot_s1'])} / S2 {_fmt(snap['pivot_s2'])}")
    lines.append(f"- 스윙 고점 {_fmt(snap['swing_high'])} / 스윙 저점 {_fmt(snap['swing_low'])}")

    lines.append("\n### 리스크 관리")
    lines.append(
        f"ATR({_fmt(snap['atr'])}) 기준 변동성을 고려해 손절 폭을 넓게 설정하는 것을 권장합니다. "
        f"예시 손절가: 볼린저 밴드 하단({_fmt(snap['bb_lower'])}) 이탈 시."
    )

    lines.append(
        "\n> 본 리포트는 규칙 기반 지표 계산 결과를 요약한 참고 자료이며, 투자 권유가 아닙니다."
    )

    return "\n".join(lines)
