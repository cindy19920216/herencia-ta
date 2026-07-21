"""
indicators.py
─────────────────────────────────────────────
KOSPI/KOSDAQ 기술적 분석 리포트용 지표 계산 엔진.

입력: OHLCV DataFrame (columns: Open, High, Low, Close, Volume / DatetimeIndex)
출력: dict 형태의 계산된 지표 스냅샷 (최신 시점 기준) + 시계열 컬럼이 추가된 DataFrame

의존성: pandas, numpy
"""

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
# 기본 이동평균 / 오실레이터
# ─────────────────────────────────────────────

def add_moving_averages(df, windows=(5, 20, 60)):
    out = df.copy()
    for w in windows:
        out[f"MA{w}"] = out["Close"].rolling(w).mean()
    return out


def add_rsi(df, period=14):
    out = df.copy()
    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))
    out["RSI"] = out["RSI"].fillna(50)
    return out


def add_stochastic(df, k_period=14, k_smooth=3, d_smooth=3):
    out = df.copy()
    low_min = out["Low"].rolling(k_period).min()
    high_max = out["High"].rolling(k_period).max()
    raw_k = 100 * (out["Close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    out["STOCH_K"] = raw_k.rolling(k_smooth).mean()
    out["STOCH_D"] = out["STOCH_K"].rolling(d_smooth).mean()
    return out


def add_adx(df, period=14):
    out = df.copy()
    high, low, close = out["High"], out["Low"], out["Close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    out["ADX"] = dx.ewm(alpha=1 / period, adjust=False).mean()
    out["PLUS_DI"] = plus_di
    out["MINUS_DI"] = minus_di
    return out


def add_atr(df, period=14):
    out = df.copy()
    high, low, close = out["High"], out["Low"], out["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    out["ATR"] = tr.ewm(alpha=1 / period, adjust=False).mean()
    return out


def add_bollinger(df, period=20, num_std=2):
    out = df.copy()
    mid = out["Close"].rolling(period).mean()
    std = out["Close"].rolling(period).std()
    out["BB_MID"] = mid
    out["BB_UPPER"] = mid + num_std * std
    out["BB_LOWER"] = mid - num_std * std
    return out


def add_vwap(df, window=20):
    """일반적인 VWAP은 하루 내(intraday) 계산이지만, 일봉 스윙 분석용으로
    최근 N봉 누적 거래대금 기반 rolling VWAP을 사용한다."""
    out = df.copy()
    typical_price = (out["High"] + out["Low"] + out["Close"]) / 3
    pv = typical_price * out["Volume"]
    out["VWAP"] = pv.rolling(window).sum() / out["Volume"].rolling(window).sum()
    return out


def add_donchian(df, period=20):
    out = df.copy()
    out["DONCHIAN_UPPER"] = out["High"].rolling(period).max()
    out["DONCHIAN_LOWER"] = out["Low"].rolling(period).min()
    return out


def add_macd(df, fast=12, slow=26, signal=9):
    out = df.copy()
    ema_fast = out["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = out["Close"].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    out["MACD"] = macd
    out["MACD_SIGNAL"] = macd_signal
    out["MACD_HIST"] = macd - macd_signal
    return out


# ─────────────────────────────────────────────
# 고급/합성 지표
# ─────────────────────────────────────────────

def add_squeeze_momentum(df, bb_period=20, bb_std=2, kc_period=20, kc_mult=1.5):
    """LazyBear 스타일 Squeeze Momentum.
    - Squeeze ON: 볼린저 밴드가 켈트너 채널 안에 들어감 (변동성 수축)
    - Momentum: 최근 kc_period 구간 중심선 대비 종가의 선형회귀 값
    """
    out = df.copy()
    mid = out["Close"].rolling(bb_period).mean()
    std = out["Close"].rolling(bb_period).std()
    bb_upper = mid + bb_std * std
    bb_lower = mid - bb_std * std

    tr = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - out["Close"].shift()).abs(),
        (out["Low"] - out["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr_kc = tr.rolling(kc_period).mean()
    kc_mid = out["Close"].rolling(kc_period).mean()
    kc_upper = kc_mid + kc_mult * atr_kc
    kc_lower = kc_mid - kc_mult * atr_kc

    out["SQZ_ON"] = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    highest_high = out["High"].rolling(kc_period).max()
    lowest_low = out["Low"].rolling(kc_period).min()
    sma_close = out["Close"].rolling(kc_period).mean()
    avg_val = (highest_high + lowest_low) / 2
    avg_val = (avg_val + sma_close) / 2
    diff = out["Close"] - avg_val

    def _linreg_last(series):
        y = series.values
        x = np.arange(len(y))
        if np.any(np.isnan(y)):
            return np.nan
        slope, intercept = np.polyfit(x, y, 1)
        return slope * (len(y) - 1) + intercept

    out["SQZ_MOM"] = diff.rolling(kc_period).apply(_linreg_last, raw=False)
    return out


def add_elder_impulse(df, ema_period=13):
    """Elder Impulse System: EMA13 기울기 + MACD 히스토그램 기울기 조합.
    - green(강세, 매수 가능): EMA↑ & MACD_HIST↑
    - red(약세, 매도 금지=신규 매수 자제): EMA↓ & MACD_HIST↓
    - blue(중립, 양방향 허용): 그 외
    """
    out = df.copy()
    if "MACD_HIST" not in out.columns:
        out = add_macd(out)
    ema = out["Close"].ewm(span=ema_period, adjust=False).mean()
    out["EMA13"] = ema
    ema_up = ema.diff() > 0
    hist_up = out["MACD_HIST"].diff() > 0

    color = pd.Series("blue", index=out.index)
    color[(ema_up) & (hist_up)] = "green"
    color[(~ema_up) & (~hist_up)] = "red"
    out["ELDER_IMPULSE"] = color
    return out


def add_pivot_points(df):
    """전일(직전봉) 고가/저가/종가 기반 클래식 피벗포인트."""
    out = df.copy()
    prev_high = out["High"].shift(1)
    prev_low = out["Low"].shift(1)
    prev_close = out["Close"].shift(1)

    pp = (prev_high + prev_low + prev_close) / 3
    out["PIVOT_PP"] = pp
    out["PIVOT_R1"] = 2 * pp - prev_low
    out["PIVOT_S1"] = 2 * pp - prev_high
    out["PIVOT_R2"] = pp + (prev_high - prev_low)
    out["PIVOT_S2"] = pp - (prev_high - prev_low)
    out["PIVOT_R3"] = prev_high + 2 * (pp - prev_low)
    out["PIVOT_S3"] = prev_low - 2 * (prev_high - pp)
    return out


def fibonacci_levels(swing_high, swing_low, direction="down"):
    """direction='down' -> 고점에서 저점으로 하락 후 되돌림 레벨(저항 후보)
       direction='up'   -> 저점에서 고점으로 상승 후 되돌림 레벨(지지 후보)
    """
    diff = swing_high - swing_low
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels = {}
    for r in ratios:
        if direction == "down":
            levels[r] = swing_high - diff * r
        else:
            levels[r] = swing_low + diff * r
    # 확장(extension) 레벨도 함께 제공
    levels["ext_100"] = swing_low - diff * (0.0)  # placeholder, overwritten below
    return levels


def find_recent_swing(df, lookback=60):
    """최근 lookback 구간 내 스윙 고점/저점과 그 위치를 반환."""
    window = df.tail(lookback)
    swing_high = window["High"].max()
    swing_high_idx = window["High"].idxmax()
    swing_low = window["Low"].min()
    swing_low_idx = window["Low"].idxmin()
    return {
        "swing_high": swing_high,
        "swing_high_idx": swing_high_idx,
        "swing_low": swing_low,
        "swing_low_idx": swing_low_idx,
    }


def smc_zone(swing_high, swing_low):
    """스마트 머니 컨셉(SMC) Premium/Discount/Equilibrium 존 계산.
    - Discount zone: 0% ~ 50% (저점 근처, 매수 관심 구역)
    - Premium zone : 50% ~ 100% (고점 근처, 매도/차익실현 구역)
    """
    mid = (swing_high + swing_low) / 2
    return {
        "discount_zone": (swing_low, mid),
        "premium_zone": (mid, swing_high),
        "equilibrium": mid,
    }


def detect_choch(df, lookback=30):
    """CHoCH(Change of Character) 단순 탐지:
    직전 추세가 하락(고점 갱신 실패, 저점 하향)이다가
    최근 N봉 내 최근 스윙 고점을 상향 돌파하면 상승 전환 CHoCH,
    반대면 하락 전환 CHoCH로 판정하는 단순 룰 기반 버전.
    실거래 신호가 아닌 '참고용 구조 신호'임에 유의.
    """
    window = df.tail(lookback)
    closes = window["Close"]
    highs = window["High"]
    lows = window["Low"]

    # 최근 절반 구간의 스윙포인트 대비 마지막 종가 비교
    mid_point = len(window) // 2
    prior_high = highs.iloc[:mid_point].max()
    prior_low = lows.iloc[:mid_point].min()
    last_close = closes.iloc[-1]

    if last_close > prior_high:
        return {"choch": "bullish", "level": prior_high}
    elif last_close < prior_low:
        return {"choch": "bearish", "level": prior_low}
    else:
        return {"choch": None, "level": None}


def volume_profile_poc(df, bins=24, lookback=120):
    """거래량 프로파일 POC(Point of Control) 근사 계산.
    가격 구간을 bins개로 나누고 각 구간에 배분된 거래량을 합산,
    최대 거래량 구간의 중심가를 POC로 반환.
    """
    window = df.tail(lookback)
    price_min = window["Low"].min()
    price_max = window["High"].max()
    if price_max == price_min:
        return {"poc": price_min, "bins": None}

    bin_edges = np.linspace(price_min, price_max, bins + 1)
    volume_per_bin = np.zeros(bins)

    for _, row in window.iterrows():
        # 각 봉의 거래량을 해당 봉의 고저 범위에 걸친 bin들에 균등 배분
        low, high, vol = row["Low"], row["High"], row["Volume"]
        if high == low:
            idx = np.searchsorted(bin_edges, low, side="right") - 1
            idx = np.clip(idx, 0, bins - 1)
            volume_per_bin[idx] += vol
            continue
        overlap_start = np.clip(np.searchsorted(bin_edges, low, side="left") - 1, 0, bins - 1)
        overlap_end = np.clip(np.searchsorted(bin_edges, high, side="right") - 1, 0, bins - 1)
        span = max(overlap_end - overlap_start + 1, 1)
        for b in range(overlap_start, overlap_end + 1):
            volume_per_bin[b] += vol / span

    poc_idx = int(np.argmax(volume_per_bin))
    poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
    return {"poc": poc_price, "bin_edges": bin_edges, "volume_per_bin": volume_per_bin}


def buy_sell_volume_ratio(df, lookback=20):
    """상승봉(Close>Open) 거래량 vs 전체 거래량 비율로 매수 우위/매도 우위 근사."""
    window = df.tail(lookback)
    up_vol = window.loc[window["Close"] >= window["Open"], "Volume"].sum()
    total_vol = window["Volume"].sum()
    if total_vol == 0:
        return 50.0
    return 100 * up_vol / total_vol


# ─────────────────────────────────────────────
# 전체 파이프라인
# ─────────────────────────────────────────────

def compute_all_indicators(df, swing_lookback=60):
    """OHLCV DataFrame을 받아 모든 지표를 계산하고,
    (시계열 DataFrame, 최신 시점 스냅샷 dict) 튜플을 반환한다."""
    out = df.copy()
    out = add_moving_averages(out)
    out = add_rsi(out)
    out = add_stochastic(out)
    out = add_adx(out)
    out = add_atr(out)
    out = add_bollinger(out)
    out = add_vwap(out)
    out = add_donchian(out)
    out = add_macd(out)
    out = add_squeeze_momentum(out)
    out = add_elder_impulse(out)
    out = add_pivot_points(out)

    swing = find_recent_swing(out, lookback=swing_lookback)
    zones = smc_zone(swing["swing_high"], swing["swing_low"])
    choch = detect_choch(out, lookback=swing_lookback // 2)
    poc_info = volume_profile_poc(out, lookback=swing_lookback * 2)
    buy_ratio = buy_sell_volume_ratio(out, lookback=20)

    last = out.iloc[-1]
    snapshot = {
        "date": out.index[-1],
        "close": last["Close"],
        "prev_close": out["Close"].iloc[-2] if len(out) > 1 else last["Close"],
        "ma5": last["MA5"],
        "ma20": last["MA20"],
        "ma60": last.get("MA60", np.nan),
        "rsi": last["RSI"],
        "stoch_k": last["STOCH_K"],
        "stoch_d": last["STOCH_D"],
        "adx": last["ADX"],
        "atr": last["ATR"],
        "bb_upper": last["BB_UPPER"],
        "bb_mid": last["BB_MID"],
        "bb_lower": last["BB_LOWER"],
        "vwap": last["VWAP"],
        "donchian_upper": last["DONCHIAN_UPPER"],
        "donchian_lower": last["DONCHIAN_LOWER"],
        "macd_hist": last["MACD_HIST"],
        "sqz_on": bool(last["SQZ_ON"]) if not pd.isna(last["SQZ_ON"]) else None,
        "sqz_mom": last["SQZ_MOM"],
        "elder_impulse": last["ELDER_IMPULSE"],
        "pivot_pp": last["PIVOT_PP"],
        "pivot_r1": last["PIVOT_R1"],
        "pivot_r2": last["PIVOT_R2"],
        "pivot_s1": last["PIVOT_S1"],
        "pivot_s2": last["PIVOT_S2"],
        "swing_high": swing["swing_high"],
        "swing_low": swing["swing_low"],
        "discount_zone": zones["discount_zone"],
        "premium_zone": zones["premium_zone"],
        "equilibrium": zones["equilibrium"],
        "choch": choch["choch"],
        "choch_level": choch["level"],
        "poc": poc_info["poc"],
        "buy_volume_ratio": buy_ratio,
        "high_52w": out["High"].tail(252).max() if len(out) >= 5 else out["High"].max(),
    }
    return out, snapshot
