"""
chart.py
─────────────────────────────────────────────
캔들차트 + 지표 오버레이 (MA, 볼린저밴드, VWAP, 지지/저항, SMC 존)를 렌더링한다.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import mplfinance as mpf
import pandas as pd

# 한글 폰트 설정 (Noto Sans CJK KR / 나눔고딕 등 시스템에 설치된 폰트 자동 탐색)
_KR_FONT = None
for _font_name in ["Noto Sans CJK KR", "Noto Sans KR", "NanumGothic", "Malgun Gothic", "AppleGothic"]:
    if any(_font_name.lower() in f.name.lower() for f in fm.fontManager.ttflist):
        _KR_FONT = _font_name
        break
if _KR_FONT:
    plt.rcParams["font.family"] = _KR_FONT
plt.rcParams["axes.unicode_minus"] = False


def render_chart(df_with_indicators, snapshot, out_path, title="기술적 분석 차트", tail=90):
    """df_with_indicators: indicators.compute_all_indicators()가 반환한 시계열 DataFrame
    snapshot: 같은 함수가 반환한 최신 시점 요약 dict
    """
    plot_df = df_with_indicators.tail(tail).copy()

    addplots = [
        mpf.make_addplot(plot_df["MA5"], color="#e67e22", width=1.0),
        mpf.make_addplot(plot_df["MA20"], color="#2980b9", width=1.0),
        mpf.make_addplot(plot_df["BB_UPPER"], color="#95a5a6", width=0.8, linestyle="--"),
        mpf.make_addplot(plot_df["BB_LOWER"], color="#95a5a6", width=0.8, linestyle="--"),
        mpf.make_addplot(plot_df["VWAP"], color="#8e44ad", width=1.0),
        mpf.make_addplot(plot_df["RSI"], panel=2, color="#c0392b", ylabel="RSI"),
    ]

    # mpf.plot(style="yahoo")처럼 스타일명을 문자열로 넘기면 내부적으로
    # font.family rcParam이 sans-serif로 리셋되어 한글 폰트 설정이 무시된다.
    # make_mpf_style의 rc 옵션으로 폰트를 스타일 자체에 박아 넣어야 유지된다.
    rc_overrides = {"axes.unicode_minus": False}
    if _KR_FONT:
        rc_overrides["font.family"] = _KR_FONT
    chart_style = mpf.make_mpf_style(base_mpf_style="yahoo", rc=rc_overrides)

    fig, axes = mpf.plot(
        plot_df,
        type="candle",
        style=chart_style,
        addplot=addplots,
        volume=True,
        panel_ratios=(6, 2, 2),
        title=title,
        ylabel="가격",
        returnfig=True,
        figsize=(14, 9),
    )

    price_ax = axes[0]

    # 주요 레벨 수평선
    levels = {
        f"지지 S1 {snapshot['pivot_s1']:.0f}": (snapshot["pivot_s1"], "#27ae60"),
        f"저항 R1 {snapshot['pivot_r1']:.0f}": (snapshot["pivot_r1"], "#c0392b"),
        f"스윙저점 {snapshot['swing_low']:.0f}": (snapshot["swing_low"], "#16a085"),
        f"스윙고점 {snapshot['swing_high']:.0f}": (snapshot["swing_high"], "#d35400"),
    }
    # mplfinance는 x축을 실제 날짜가 아닌 정수 위치(0..N-1)로 그리므로
    # 텍스트 주석도 정수 위치를 사용해야 한다 (Timestamp를 쓰면 축이 깨짐).
    last_x = len(plot_df) - 1
    for label, (level, color) in levels.items():
        price_ax.axhline(level, color=color, linewidth=0.8, linestyle=":", alpha=0.8)
        price_ax.text(
            last_x, level, f"  {label}",
            va="center", fontsize=8, color=color,
        )
    price_ax.set_xlim(right=last_x + max(6, int(len(plot_df) * 0.08)))

    # SMC discount/premium 존 음영
    disc_low, disc_high = snapshot["discount_zone"]
    prem_low, prem_high = snapshot["premium_zone"]
    price_ax.axhspan(disc_low, disc_high, color="#2ecc71", alpha=0.06)
    price_ax.axhspan(prem_low, prem_high, color="#e74c3c", alpha=0.06)

    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path
