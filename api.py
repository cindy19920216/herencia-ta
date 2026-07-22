"""
api.py
─────────────────────────────────────────────
FastAPI 서버리스 브리지: batch_main.py가 만든 output/manifest.json과 종목별
리포트(.md)/차트(.png)를, Herencia(Vercel) 웹앱이 fetch로 가져다 쓸 수 있는
HTTP API로 노출한다. 지표 계산 로직은 다시 짜지 않고 기존 파이썬 코드를 그대로 재사용한다.

로컬 실행:
    uvicorn api:app --reload
    curl http://127.0.0.1:8000/api/manifest

배포(Render/Railway 등):
    시작 명령 예시: uvicorn api:app --host 0.0.0.0 --port $PORT
    (Procfile에 동일하게 정의되어 있음)

주의: output/manifest.json은 batch_main.py를 별도로 (로컬/크론 등에서) 실행해야
갱신된다. 이 API 서버 자체는 batch_main.py를 실행하지 않고, 이미 생성된 결과만 읽어 서빙한다.
"""

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

OUTPUT_DIR = "output"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "manifest.json")

app = FastAPI(title="Herencia 기술적 분석 API")

app.add_middleware(
    CORSMiddleware,
    # TODO: 실제 배포 시 Herencia 도메인으로 좁히기 (예: ["https://herencia.example.com"])
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

if os.path.isdir(OUTPUT_DIR):
    app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


def _load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        raise HTTPException(
            status_code=503,
            detail="output/manifest.json이 아직 없습니다. batch_main.py를 먼저 실행하세요.",
        )
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/manifest")
def get_manifest():
    """KOSPI200 배치 결과 전체 (요약 통계 + 종목별 엔트리 + 지표 스냅샷)."""
    return _load_manifest()


@app.get("/api/stocks")
def list_stocks():
    """종목 리스트만 가볍게 (indicators 상세 제외, 목록/뱃지 UI용)."""
    manifest = _load_manifest()
    fields = ("code", "name", "market", "as_of", "market_cap_100m", "trend", "momentum", "entry_opinion")
    return [{k: s.get(k) for k in fields} for s in manifest["stocks"]]


@app.get("/api/stocks/{code}")
def get_stock(code: str):
    """종목 하나의 상세 결과 (지표 스냅샷 포함)."""
    manifest = _load_manifest()
    for s in manifest["stocks"]:
        if s["code"] == code:
            return s
    raise HTTPException(
        status_code=404,
        detail=f"{code} 종목을 찾을 수 없습니다 (최근 KOSPI200 배치 결과에 없음).",
    )


@app.get("/api/stocks/{code}/history")
def get_stock_history(code: str):
    """종목 하나의 캔들차트용 시계열 히스토리 (OHLCV + MA/BB/VWAP/RSI/MACD_HIST)."""
    manifest = _load_manifest()
    for s in manifest["stocks"]:
        if s["code"] == code:
            history_path = s.get("history_path")
            if not history_path or not os.path.exists(history_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"{code} 종목의 히스토리 파일이 없습니다.",
                )
            with open(history_path, encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(
        status_code=404,
        detail=f"{code} 종목을 찾을 수 없습니다 (최근 KOSPI200 배치 결과에 없음).",
    )
