"""
batch_main.py
─────────────────────────────────────────────
KOSPI200 전 종목에 대해 main.run_pipeline()(데이터 로드 → 지표 계산 → 리포트 →
차트)을 반복 실행하고, Herencia 웹앱이 바로 fetch해서 쓸 수 있는
output/manifest.json을 생성한다.

실행:
    python batch_main.py                      # KOSPI200 전 종목
    python batch_main.py --limit 10           # 앞 10종목만 (테스트용)
    python batch_main.py --refresh-universe   # KOSPI200 구성종목 캐시를 새로 받기
    python batch_main.py --demo --limit 5     # 네트워크 없이 합성 데이터로 배치 로직만 검증

Claude 샌드박스처럼 외부망(Yahoo Finance/KRX)이 막힌 환경에서는 --demo로 로직만
검증하고, 실제 200종목 실행은 로컬 환경에서 해주세요 (README 참고).
"""

import argparse
import json
import os
import re
import time

import pandas as pd

from main import make_synthetic_ohlcv, run_pipeline
from report import classify_trend, classify_momentum, entry_opinion
from export import build_stock_entry
from universe import load_kospi200


def _safe_filename(name):
    """종목명에 파일명으로 못 쓰는 문자가 섞여 있어도 안전하게 치환."""
    return re.sub(r'[\\/:*?"<>|]', "_", str(name))


def _demo_universe(n=5):
    """네트워크 없이 배치 로직을 검증하기 위한 소규모 합성 유니버스."""
    return pd.DataFrame({
        "code": [f"{i:06d}" for i in range(1, n + 1)],
        "name": [f"DEMO{i}" for i in range(1, n + 1)],
    })


def run_batch(universe_df, out_dir="output", period="6mo", sleep_sec=1.0, demo=False):
    """유니버스 DataFrame(columns: code, name)을 순회하며 종목별 리포트/차트를 생성하고
    output/manifest.json에 결과를 모아 저장한다. 개별 종목 실패는 건너뛰고 계속 진행한다."""
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    failures = []
    total = len(universe_df)

    for i, row in enumerate(universe_df.itertuples(index=False), start=1):
        code, name = str(row.code), str(row.name)
        # os.path.join 대신 "/"를 직접 씀: report_path/chart_path가 그대로 API의
        # 정적 파일 URL(/output/...)로도 쓰이므로 Windows에서도 슬래시로 통일해야 함.
        prefix = f"{out_dir}/{code}_{_safe_filename(name)}"
        print(f"[{i}/{total}] {code} {name} 처리 중...")

        try:
            if demo:
                df = make_synthetic_ohlcv(seed=abs(hash(code)) % (2**32))
            else:
                from data_loader import load_ohlcv
                df = load_ohlcv(code, market="KOSPI", period=period)

            _, report_path, chart_path, snapshot = run_pipeline(df, name, out_prefix=prefix)

            entry = build_stock_entry(
                code=code,
                name=name,
                market="KOSPI",
                snapshot=snapshot,
                opinion=entry_opinion(snapshot),
                trend=classify_trend(snapshot),
                momentum=classify_momentum(snapshot),
                report_path=report_path,
                chart_path=chart_path,
            )
            manifest.append(entry)

        except Exception as e:
            print(f"  -> 실패: {e}")
            failures.append({"code": code, "name": name, "error": str(e)})

        # yfinance 과호출로 인한 일시 차단을 피하기 위한 종목 간 대기 (demo 모드는 생략)
        if not demo and sleep_sec > 0 and i < total:
            time.sleep(sleep_sec)

    manifest_path = os.path.join(out_dir, "manifest.json")
    payload = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe": "KOSPI200",
        "count": len(manifest),
        "failed_count": len(failures),
        "failed": failures,
        "stocks": manifest,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {len(manifest)}종목 성공, {len(failures)}종목 실패")
    print(f"[저장됨] manifest: {manifest_path}")
    return manifest, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="처리할 종목 수 제한 (테스트용)")
    parser.add_argument("--period", type=str, default="6mo")
    parser.add_argument("--out-dir", type=str, default="output")
    parser.add_argument("--sleep", type=float, default=1.0, help="종목 간 대기 시간(초), yfinance 과호출 방지")
    parser.add_argument("--refresh-universe", action="store_true", help="KOSPI200 구성종목 캐시를 새로 받기")
    parser.add_argument("--demo", action="store_true", help="합성 데이터로 오프라인 배치 로직 검증")
    args = parser.parse_args()

    if args.demo:
        print("[demo 모드] 합성 데이터로 배치 파이프라인 로직을 검증합니다 (실거래 데이터 아님).")
        universe_df = _demo_universe(args.limit or 5)
    else:
        universe_df = load_kospi200(refresh=args.refresh_universe)
        if args.limit:
            universe_df = universe_df.head(args.limit)

    run_batch(
        universe_df,
        out_dir=args.out_dir,
        period=args.period,
        sleep_sec=args.sleep,
        demo=args.demo,
    )


if __name__ == "__main__":
    main()
