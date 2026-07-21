# Herencia 기술적 분석 파이프라인 (프로토타입)

## 진행 상황 (다음에 이어서 하기) — 2026-07-21 기준

**여기까지 한 것**
1. KOSPI200 전 종목 일괄 실행용 `universe.py`/`export.py`/`batch_main.py` 추가 (2026-07-20).
2. `universe.py` 데이터 소스 교체: pykrx의 KOSPI200 구성종목 조회가 2026-05 릴리스부터 KRX
   회원 로그인을 요구하게 되어(공급망 공격 아님 — PyPI 정식 배포본 해시 대조로 확인 완료),
   로그인이 필요 없는 한국투자증권 공개 종목마스터 파일(`kospi_code.mst`) 기반으로 교체.
   `requirements.txt`에서 `pykrx` 제거, `requests` 추가.
3. KOSPI200 200종목 전체 배치 실행 완료 — `output/manifest.json` (count=200, failed_count=0).
   추세: 약세 118 · 혼조 56 · 강세 26 / 진입의견: 관망 125 · 매수 관심 70 · 매도·차익실현 관심 5.
4. Herencia 연동 방식 결정 (사용자 선택: **서버리스 브리지**) → `api.py` (FastAPI) 추가.
   로컬에서 `/health`, `/api/manifest`, `/api/stocks`, `/api/stocks/{code}`, 정적 파일
   서빙(`/output/*`) 전부 curl로 동작 확인 완료. 배포용 `Procfile` 추가.

**다음에 할 것 (미완료)**
1. 실제 Render/Railway 등에 `api.py` 배포 (아래 "Herencia 편입 시 참고" 참고).
   이 저장소는 아직 git 저장소가 아니라서, 배포 전에 git init + GitHub 연동이 먼저 필요할 수 있음.
2. Herencia(Vercel) 쪽에서 배포된 API URL로 fetch하는 연동 코드 작성.
3. CORS `allow_origins`를 현재 `["*"]`(전체 허용, 프로토타입용)에서 Herencia 실제 배포 도메인으로 좁히기.
4. `output/manifest.json` 갱신 주기 정하기 — 지금은 로컬에서 `python batch_main.py`를
   수동 실행해야 갱신됨. 크론(예: GitHub Actions 스케줄) 등으로 자동화할지 결정 필요.

---

KOSPI/KOSDAQ 종목에 대해 **데이터 수집 → 지표 계산 → 한국어 리포트 생성 → 차트 렌더링**까지
한 번에 처리하는 프로토타입입니다. 나중에 Herencia 대시보드에 API/컴포넌트로 편입하는 것을 염두에 두고
로직(지표 계산, 텍스트 생성)과 표현(차트)을 분리해서 구성했습니다.

## 구성

```
herencia-ta/
├── data_loader.py   # yfinance로 KOSPI/KOSDAQ OHLCV 가져오기 (.KS/.KQ 접미사 자동 처리)
├── indicators.py     # MA/RSI/스토캐스틱/ADX/ATR/볼린저/VWAP/돈치안/MACD/
│                      # 스퀴즈모멘텀/엘더임펄스/피벗/SMC존/CHoCH/POC/매수우위비율
├── report.py          # 지표 스냅샷 → 한국어 서술형 리포트 (규칙 기반 진입의견 포함)
├── chart.py            # 캔들차트 + MA/BB/VWAP 오버레이 + RSI/거래량 패널 + 지지/저항선
├── main.py               # 단일 종목 파이프라인 실행 진입점
├── universe.py           # KOSPI200 구성종목 리스트 (한투 종목마스터 조회 + data/kospi200.csv 캐시)
├── export.py             # snapshot → JSON 직렬화, Herencia manifest 엔트리 생성
├── batch_main.py         # KOSPI200 전 종목 일괄 실행 + output/manifest.json 생성
├── api.py                # FastAPI 브리지: manifest.json/차트/리포트를 HTTP API로 노출
├── Procfile              # 배포용 시작 명령 (Render/Railway 등)
└── requirements.txt
```

## 로컬 실행 방법

Claude 샌드박스는 Yahoo Finance API로 접속이 막혀 있어서, **실제 데이터 실행은 로컬 환경에서** 해주셔야 해요.

```bash
pip install -r requirements.txt

# 삼성전자(KOSPI, 005930) 최근 6개월 분석
python main.py --code 005930 --market KOSPI --name "삼성전자"

# 코스닥 종목 예시 (에코프로 086520)
python main.py --code 086520 --market KOSDAQ --name "에코프로"

# 네트워크 없이 로직만 검증하고 싶을 때 (합성 데이터)
python main.py --demo
```

실행하면 `report.md`(텍스트 리포트)와 `report.png`(차트)가 생성됩니다.

## KOSPI200 전 종목 일괄 실행 (Herencia 연동용)

`batch_main.py`는 KOSPI200 구성종목 전체에 대해 위 파이프라인을 반복 실행하고,
Herencia 웹앱이 바로 fetch해서 쓸 수 있는 `output/manifest.json`을 만들어줍니다.

```bash
# 최초 1회: KOSPI200 구성종목을 KRX에서 받아 data/kospi200.csv에 캐시
# (이후 실행에서는 캐시를 재사용하므로 매번 다시 받지 않음)
python batch_main.py --refresh-universe --limit 5   # 우선 5종목만 테스트

# 본 실행: KOSPI200 200종목 전체 (종목당 yfinance 호출 1회 + 1초 대기)
python batch_main.py

# 옵션
python batch_main.py --limit 20              # 앞 20종목만
python batch_main.py --sleep 2                # 종목 간 대기시간 늘리기 (과호출 방지)
python batch_main.py --out-dir output/2026-07-20   # 실행일자별로 결과 분리 저장
python batch_main.py --as-of 20260717         # 휴장일 등으로 구성종목 기준일을 지정해야 할 때

# 네트워크 없이 배치 로직만 검증 (합성 데이터 5종목)
python batch_main.py --demo --limit 5
```

종목별로 `output/{종목코드}_{종목명}.md`, `.png`가 생성되고, 전체 결과 요약은
`output/manifest.json` 하나로 모입니다. 종목 중 데이터 조회 실패(상장폐지, 티커 불일치 등)가
있어도 배치 전체가 중단되지 않고 `manifest.json`의 `failed` 배열에 사유와 함께 기록된 채
나머지 종목 처리가 계속됩니다.

`manifest.json` 구조:

```json
{
  "generated_at": "2026-07-20 17:36:10",
  "universe": "KOSPI200",
  "count": 198,
  "failed_count": 2,
  "failed": [{"code": "005935", "name": "삼성전자우", "error": "..."}],
  "stocks": [
    {
      "code": "005930",
      "name": "삼성전자",
      "market": "KOSPI",
      "as_of": "2026-07-20",
      "trend": "강세",
      "momentum": "중립",
      "entry_opinion": "관망",
      "indicators": { "close": 71200.0, "rsi": 55.3, "...": "..." },
      "report_path": "output/005930_삼성전자.md",
      "chart_path": "output/005930_삼성전자.png"
    }
  ]
}
```

Herencia 쪽에서는 이 JSON 하나를 정적 파일로 서빙하거나(아래 "Herencia 편입 시 참고"의
서버리스 브리지 뒤에 두고) fetch하면, 종목 리스트/트렌드/진입의견 뱃지 UI를
바로 만들 수 있습니다.

## 지금 버전이 하는 것 / 안 하는 것

**하는 것**
- MU 예시 리포트와 유사한 구조: 개요 → SMC/구조분석 → 진입의견 → 주요레벨 → 리스크관리
- 진입의견은 지지/저항 근접도 + RSI 임계값 기반의 **단순 룰 3단 분류** (매수관심/매도관심/관망)
- CHoCH는 최근 구간을 절반으로 나눠 스윙 고점/저점 돌파 여부를 보는 **단순화된 버전**입니다.
  실제 SMC 방법론의 정밀한 스윙 구조 인식(BOS/CHoCH/OB) 대비 근사치예요.
- VWAP은 일봉 데이터라 "당일 VWAP"이 아니라 **최근 N봉 rolling VWAP**으로 구현했습니다.

**아직 안 하는 것 (다음 단계 후보)**
- 엘리어트 파동, 피보나치 확장(현재는 되돌림 레벨 함수만 존재)
- 차트 패턴 자동 인식(헤드앤숄더, 삼각수렴 등)
- 다중 시간대(일/주/월) 통합 분석
- 실시간/장중 데이터, 호가창 기반 지표

## 변경 이력

### 2026-07-21
- **`universe.py` — KOSPI200 데이터 소스 교체 (pykrx → 한투 종목마스터)**
  `python batch_main.py --refresh-universe`가 "KRX 로그인 실패: KRX_ID 또는 KRX_PW
  환경변수가 설정되지 않았습니다"로 실패. 처음엔 로컬 pykrx 패키지가 변조된 공급망
  공격으로 의심했으나, PyPI에서 pykrx 1.2.8 sdist를 받아 SHA256을 대조한 결과 정식
  배포본과 완전히 일치 확인 (업로더: 실제 메인테이너 Jonghun Yoo, 2026-05-04 업로드).
  즉 KRX가 최근 해당 데이터 API에 회원 로그인을 요구하도록 정책을 바꾼 것이었음.
  실계정 자격증명을 스크립트에 넣는 대신, 로그인이 필요 없는 한국투자증권 공개
  종목마스터 파일(`kospi_code.mst.zip`)로 `fetch_kospi200_from_kis()`를 새로 작성해
  대체. 파일의 `KOSPI200섹터업종` 필드(228자 고정폭 파트, 오프셋 19)가 '0'이면
  미편입/그 외면 편입 — 실측 오프셋 검증(삼성전자 vs 동화약품 대조) 후 반영, 정확히
  200종목 필터링 확인. `requirements.txt`에서 `pykrx` 제거, `requests` 추가.
- **KOSPI200 200종목 전체 배치 실행** — `output/manifest.json` (count=200, failed=0).
- **`api.py` 추가 — FastAPI 서버리스 브리지**
  Herencia 연동 방식으로 서버리스 브리지를 선택 (JS 포팅 대비 로직 이중 관리 회피).
  `output/manifest.json`과 종목별 리포트/차트를 읽어 서빙하는 HTTP API
  (`/health`, `/api/manifest`, `/api/stocks`, `/api/stocks/{code}`, 정적 파일
  `/output/*`). 로컬에서 curl로 전 엔드포인트 동작 확인. 배포용 `Procfile` 추가.
  `batch_main.py`가 만드는 `report_path`/`chart_path`가 Windows에서 백슬래시로
  생성되어 정적 파일 URL과 안 맞는 문제도 같이 수정 (`os.path.join` 대신 `/` 직접 사용).

### 2026-07-20
- **KOSPI200 일괄 실행 + Herencia 연동용 매니페스트 추가**
  기존에는 종목 1개(`main.py --code ...`)만 처리할 수 있었는데, KOSPI200 전체를
  Herencia에 태우려면 (1) 구성종목 리스트, (2) 다종목 반복 실행, (3) 웹앱이 바로
  fetch할 수 있는 정형 데이터가 필요해서 세 파일을 추가함.
  - `universe.py`: pykrx로 KRX에서 KOSPI200 구성종목(코드+종목명)을 가져와
    `data/kospi200.csv`에 캐시. 캐시가 있으면 재조회 없이 그대로 사용.
  - `export.py`: `indicators.py`의 snapshot(numpy/Timestamp 포함)을 JSON
    직렬화 가능한 순수 파이썬 타입으로 변환하는 `serialize_snapshot()`과,
    종목별 매니페스트 엔트리를 만드는 `build_stock_entry()`.
  - `batch_main.py`: 유니버스를 순회하며 `main.run_pipeline()`을 반복 호출,
    종목별 `report.md`/`report.png`를 `output/`에 저장하고 전체 결과를
    `output/manifest.json`으로 모음. 종목 1개 실패해도 배치 전체가 멈추지 않고
    `manifest.json`의 `failed` 배열에 기록한 뒤 계속 진행. yfinance 과호출 방지를
    위해 종목 간 기본 1초 대기(`--sleep`로 조절).
  - `--demo --limit N`으로 네트워크 없이 배치 로직 자체는 검증 완료
    (합성 데이터 5종목 실행 → `manifest.json`/개별 `.md`/`.png` 정상 생성 확인).
    실제 KOSPI200 200종목 실행과 KRX 유니버스 조회(`--refresh-universe`)는
    네트워크가 열린 로컬 환경에서 실행해서 확인해주세요.

### 2026-07-16
- **`report.py` — 진입의견 로직 버그 수정**
  `entry_opinion()`이 디스카운트 존(스윙 60봉 하위 50%) 근접 + RSI≤45 조건만 보고 "매수 관심"을
  판정해서, 하락 모멘텀이 아직 안 꺾인 상태(엘더 임펄스 적색 = 신규 매수 자제)에서도 매수 신호가
  나오는 모순이 있었음. 실제로 삼성전자(005930) 급락 구간(-8.77%)에서 재현됨.
  → `entry_opinion()`에 `elder_impulse` 체크 추가: 지지구간+RSI 조건을 만족해도 엘더 임펄스가
  적색이면 "매수 관심" 대신 "관망(하락 모멘텀 진행 중 — 반전 확인 전 자제)"으로 낮추도록 수정
  (저항구간+RSI 과매수 상황에서 엘더 임펄스 녹색일 때도 대칭 적용).
- **`chart.py` — 차트 한글 폰트 깨짐 수정**
  import 시점에 `plt.rcParams["font.family"]`를 Malgun Gothic 등으로 설정해도, 실제로는
  `mpf.plot(..., style="yahoo")` 호출이 내부적으로 `font.family`를 `sans-serif`로 리셋해버려서
  제목/레벨 라벨의 한글이 계속 □(tofu)로 깨졌음.
  → `mpf.make_mpf_style(base_mpf_style="yahoo", rc={...})`로 스타일 객체 자체에 폰트를 박아
  넣도록 수정. 재실행 후 차트 한글 정상 표시 확인.
- 위 두 수정 모두 `python main.py --code 005930 --market KOSPI --name "삼성전자"`로 재검증 완료
  (`report.md`, `report.png` 정상 생성, 진입의견/엘더임펄스 모순 해소).

## Herencia 편입 시 참고

**결정됨 (2026-07-21): 서버리스 브리지 방식.** 지표 계산 로직(`indicators.py` 등)을 TypeScript로
다시 짜지 않고, FastAPI(`api.py`)로 감싸서 그대로 재사용한다. 프로토타입 단계라 지표를 자주
손볼 가능성이 높아서, JS 포팅 시 생기는 "로직 이중 관리" 리스크를 피하는 쪽을 택함.

### api.py 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `GET /health` | 헬스체크 |
| `GET /api/manifest` | `output/manifest.json` 전체 (요약 통계 + 종목별 지표 스냅샷) |
| `GET /api/stocks` | 종목 리스트만 가볍게 (지표 상세 제외, 목록/뱃지 UI용) |
| `GET /api/stocks/{code}` | 종목 하나의 상세 결과 (없으면 404) |
| `GET /output/{파일명}` | 종목별 리포트(.md)/차트(.png) 정적 파일 |

로컬 실행: `uvicorn api:app --reload` (localhost:8000)

### 배포 (Render/Railway 등)

`Procfile`에 시작 명령이 정의되어 있음 (`web: uvicorn api:app --host 0.0.0.0 --port $PORT`).
이 저장소가 아직 git 저장소가 아니므로, 배포 전에 git init 후 GitHub에 올리고 Render/Railway에서
그 저장소를 연결하는 절차가 필요함. 배포되면 Herencia(Vercel) 쪽에서 그 URL로 fetch하면 됨.

CORS는 현재 `allow_origins=["*"]`(프로토타입용 전체 허용)로 되어 있음 — 실제 배포 시
`api.py`에서 Herencia 배포 도메인으로 좁혀야 함.

**주의**: API 서버 자체는 `batch_main.py`를 실행하지 않는다 — 이미 생성된 `output/manifest.json`을
읽어 서빙만 한다. 종목 결과를 최신으로 유지하려면 `batch_main.py`를 별도로 (로컬/크론 등에서)
주기적으로 돌려서 `output/`을 갱신해야 함.

데이터 소스도 참고할 점: yfinance는 KOSPI/KOSDAQ 커버리지가 완벽하지 않을 수 있어서
(간혹 결측/지연), 실서비스로 갈 땐 KRX 공식 API나 QuantiWise 쪽 데이터로 교체하는 걸 권장해요.
