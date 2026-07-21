"""
universe.py
─────────────────────────────────────────────
KOSPI200 구성종목(종목코드+종목명) 리스트를 가져온다.

우선순위:
1. 로컬 캐시 CSV(data/kospi200.csv)가 있으면 그대로 사용 (네트워크 없이 반복 실행 가능).
2. 캐시가 없거나 --refresh-universe로 강제 갱신을 요청하면 한국투자증권이 공개
   배포하는 종목마스터 파일(kospi_code.mst)에서 최신 구성종목을 받아와 캐시에 저장한다.

이 마스터 파일은 로그인/API 키 없이 받을 수 있는 정적 zip 파일이다.
(참고: pykrx의 get_index_portfolio_deposit_file()은 2026-05 릴리스부터 KRX 회원
로그인이 필요해져서, 로그인 없이 동작하는 이 방식으로 대체했다.)
"""

import io
import os
import zipfile

import pandas as pd
import requests

DEFAULT_CACHE_PATH = os.path.join("data", "kospi200.csv")
KIS_MASTER_URL = "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip"

# kospi_code.mst 레코드 뒤쪽 228자(2번째 파트)에서 'KOSPI200섹터업종' 필드 위치.
# '0'이면 미편입, 그 외(1~9/A/B 섹터코드)면 KOSPI200 편입.
# 주의: 한국투자증권이 공개한 공식 파서는 파일을 텍스트 모드로 줄 단위로 읽으면서
# 각 줄 끝의 개행문자(\n)까지 rf2 = row[-228:]에 포함시키는 버릇이 있어, 그 파서 기준
# 필드 폭 합(=18)과 실제 데이터 오프셋(=19)이 한 칸 어긋난다. 여기서는 개행 없는
# 깨끗한 줄(splitlines() 결과)을 쓰므로 실측으로 검증된 오프셋 19를 그대로 사용한다.
_KOSPI200_SECTOR_OFFSET = 19
_KOSPI200_SECTOR_LEN = 1


def fetch_kospi200_from_kis():
    """한국투자증권 공개 종목마스터 파일에서 KOSPI200 구성종목(코드+종목명)을 받아온다.

    마스터 파일 한 줄은 [앞부분: 단축코드(9)+표준코드(12)+한글명] + [뒷부분 228자 고정폭 필드]
    구조이며, 뒷부분의 'KOSPI200섹터업종' 필드로 편입 여부를 가린다.
    """
    resp = requests.get(KIS_MASTER_URL, timeout=30)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        raw = zf.read("kospi_code.mst").decode("cp949")

    rows = []
    for line in raw.splitlines():
        if not line:
            continue
        head, tail = line[:-228], line[-228:]
        code = head[0:9].strip()
        name = head[21:].strip()
        sector = tail[_KOSPI200_SECTOR_OFFSET:_KOSPI200_SECTOR_OFFSET + _KOSPI200_SECTOR_LEN]
        if sector != "0":
            rows.append({"code": code.zfill(6), "name": name})

    df = pd.DataFrame(rows, columns=["code", "name"]).sort_values("code").reset_index(drop=True)
    if df.empty:
        raise ValueError(
            "종목마스터 파일에서 KOSPI200 구성종목을 찾지 못했습니다. "
            "kospi_code.mst의 필드 구조가 바뀌었을 수 있습니다."
        )
    return df


def load_kospi200(cache_path=DEFAULT_CACHE_PATH, refresh=False):
    """KOSPI200 구성종목 DataFrame(columns: code, name)을 반환한다.

    캐시가 있고 refresh=False면 캐시를 그대로 읽는다.
    그 외에는 한국투자증권 종목마스터 파일에서 새로 받아와 캐시 파일을 갱신한다.
    """
    if not refresh and os.path.exists(cache_path):
        return pd.read_csv(cache_path, dtype={"code": str})

    df = fetch_kospi200_from_kis()
    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    df.to_csv(cache_path, index=False, encoding="utf-8-sig")
    return df
