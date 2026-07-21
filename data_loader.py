"""
data_loader.py
─────────────────────────────────────────────
KOSPI/KOSDAQ 종목 OHLCV 데이터를 yfinance로 가져온다.

* KOSPI 종목  -> 티커 뒤에 '.KS' (예: 삼성전자 005930.KS)
* KOSDAQ 종목 -> 티커 뒤에 '.KQ' (예: 에코프로 086520.KQ)

주의: 이 함수는 실제 네트워크(Yahoo Finance)에 접속해야 동작합니다.
Claude 샌드박스 환경에서는 외부망이 PyPI 등 패키지 저장소로만 열려 있어
이 함수를 직접 실행할 수 없습니다 — 로컬 환경(VS Code 등)에서 실행하세요.
"""

import yfinance as yf
import pandas as pd


MARKET_SUFFIX = {
    "KOSPI": ".KS",
    "KOSDAQ": ".KQ",
}


def normalize_ticker(code, market="KOSPI"):
    """'005930' + KOSPI -> '005930.KS' 형태로 변환. 이미 접미사가 있으면 그대로 반환."""
    code = str(code).strip()
    if code.endswith(".KS") or code.endswith(".KQ"):
        return code
    suffix = MARKET_SUFFIX.get(market.upper(), ".KS")
    return f"{code}{suffix}"


def load_ohlcv(code, market="KOSPI", period="6mo", interval="1d"):
    """yfinance로 OHLCV를 받아 표준 컬럼(Open, High, Low, Close, Volume)의
    DataFrame으로 정규화해서 반환한다."""
    ticker = normalize_ticker(code, market)
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)

    if df.empty:
        raise ValueError(f"'{ticker}' 데이터를 가져오지 못했습니다. 티커/기간을 확인하세요.")

    # yfinance가 멀티인덱스 컬럼을 반환하는 경우 정리
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index.name = "Date"
    return df
