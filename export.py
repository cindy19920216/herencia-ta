"""
export.py
─────────────────────────────────────────────
indicators.compute_all_indicators()가 만든 snapshot(dict)을 JSON 직렬화 가능한
형태로 변환하고, Herencia 웹앱(React/Next.js)이 바로 fetch해서 쓸 수 있는
종목별 매니페스트 엔트리를 만든다.

숫자 계산(indicators.py)과 표현(report.py, chart.py)에 이어, "데이터 반출 포맷"도
별도 모듈로 분리해서 Herencia 편입 시 이 파일만 보고 스키마를 파악할 수 있게 한다.
"""

import numpy as np
import pandas as pd


def _to_native(v):
    """numpy/pandas 스칼라 및 중첩 tuple/dict를 JSON 직렬화 가능한 파이썬 기본 타입으로 변환."""
    if isinstance(v, np.floating):
        v = float(v)
        return None if np.isnan(v) else v
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, (tuple, list)):
        return [_to_native(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_native(x) for k, x in v.items()}
    return v


def serialize_snapshot(snapshot):
    """indicators.compute_all_indicators()가 반환한 snapshot dict를
    JSON 직렬화 가능한 dict로 변환한다 (numpy/Timestamp 타입 제거)."""
    return {k: _to_native(v) for k, v in snapshot.items()}


_HISTORY_COLUMNS = [
    "Open", "High", "Low", "Close", "Volume",
    "MA5", "MA20", "MA60",
    "BB_UPPER", "BB_LOWER",
    "VWAP",
    "RSI",
    "MACD_HIST",
]


def serialize_history(ts, tail=180):
    """indicators.compute_all_indicators()가 반환한 시계열 DataFrame(ts)에서
    차트 렌더링에 필요한 컬럼만 추려 JSON 직렬화 가능한 레코드 리스트로 변환한다.

    프론트엔드의 인터랙티브 캔들차트(가격 오버레이 MA/BB/VWAP + RSI/MACD 서브패널)가
    바로 소비할 수 있는 형태. STOCH/ADX/ATR/DONCHIAN/SQZ/PIVOT 등 나머지 지표는
    시계열로 내보내지 않고 스냅샷(snapshot)에만 남긴다 — 상세 화면의 접이식
    "상세 지표" 섹션은 지금처럼 스냅샷 스칼라 값으로 충분하기 때문.
    """
    cols = [c for c in _HISTORY_COLUMNS if c in ts.columns]
    trimmed = ts.tail(tail)[cols]
    records = []
    for date, row in trimmed.iterrows():
        rec = {"date": date.strftime("%Y-%m-%d")}
        for c in cols:
            key = c.lower()
            v = _to_native(row[c])
            if isinstance(v, float):
                v = round(v, 1 if key in ("rsi", "macd_hist") else 2)
            rec[key] = v
        records.append(rec)
    return records


def build_stock_entry(code, name, market, snapshot, opinion, trend, momentum,
                       report_path=None, chart_path=None, history_path=None,
                       market_cap_100m=None):
    """Herencia manifest.json에 들어갈 종목별 엔트리 하나를 생성한다.

    market_cap_100m: 시가총액 (단위: 억원). 한투 종목마스터 기준 스냅샷 값이라
    실시간이 아니며, KOSPI200 외 종목(개별 실행)은 None일 수 있다.
    """
    return {
        "code": code,
        "name": name,
        "market": market,
        "as_of": _to_native(snapshot.get("date")),
        "market_cap_100m": _to_native(market_cap_100m),
        "trend": trend,
        "momentum": momentum,
        "entry_opinion": opinion,
        "indicators": serialize_snapshot(snapshot),
        "report_path": report_path,
        "chart_path": chart_path,
        "history_path": history_path,
    }
