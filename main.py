"""
main.py
─────────────────────────────────────────────
전체 파이프라인: 데이터 로드 -> 지표 계산 -> 리포트 생성 -> 차트 렌더링

실행:
    python main.py --code 005930 --market KOSPI --name "삼성전자"

Claude 샌드박스처럼 외부망이 막힌 환경에서는 --demo 플래그로
합성(synthetic) 데이터를 생성해 파이프라인 로직을 검증할 수 있다.
"""

import argparse
import numpy as np
import pandas as pd

from indicators import compute_all_indicators
from report import generate_report
from chart import render_chart


def make_synthetic_ohlcv(n=180, start_price=70000, seed=42):
    """실제 티커 접속 없이 파이프라인을 검증하기 위한 합성 OHLCV 생성기.
    랜덤워크 + 완만한 하락 추세 + 노이즈로 구성."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)

    returns = rng.normal(loc=-0.0007, scale=0.018, size=n)
    close = start_price * np.cumprod(1 + returns)

    high = close * (1 + np.abs(rng.normal(0.006, 0.004, n)))
    low = close * (1 - np.abs(rng.normal(0.006, 0.004, n)))
    open_ = low + (high - low) * rng.random(n)
    volume = rng.integers(500_000, 3_000_000, n)

    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    df.index.name = "Date"
    return df


def run_pipeline(df, ticker_name, out_prefix="report"):
    ts, snapshot = compute_all_indicators(df)
    report_text = generate_report(snapshot, ticker_name=ticker_name)

    report_path = f"{out_prefix}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    chart_path = f"{out_prefix}.png"
    render_chart(ts, snapshot, chart_path, title=f"{ticker_name} 기술적 분석")

    return report_text, report_path, chart_path, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=str, default=None, help="종목코드 (예: 005930)")
    parser.add_argument("--market", type=str, default="KOSPI", choices=["KOSPI", "KOSDAQ"])
    parser.add_argument("--name", type=str, default="종목")
    parser.add_argument("--period", type=str, default="6mo")
    parser.add_argument("--demo", action="store_true", help="합성 데이터로 오프라인 테스트")
    parser.add_argument("--out", type=str, default="report")
    args = parser.parse_args()

    if args.demo or args.code is None:
        print("[demo 모드] 합성 데이터로 파이프라인을 검증합니다 (실거래 데이터 아님).")
        df = make_synthetic_ohlcv()
        name = args.name if args.name != "종목" else "DEMO"
    else:
        from data_loader import load_ohlcv
        df = load_ohlcv(args.code, market=args.market, period=args.period)
        name = args.name

    report_text, report_path, chart_path, snapshot = run_pipeline(df, name, out_prefix=args.out)

    print(report_text)
    print(f"\n[저장됨] 리포트: {report_path}")
    print(f"[저장됨] 차트: {chart_path}")


if __name__ == "__main__":
    main()
