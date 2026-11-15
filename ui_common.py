# -*- coding: utf-8 -*-
"""
ニュース推薦・分身AI アプリ共通UIモジュール。
デザインテーマ（白基調、#4F46E5アクセント、モダンUI）の共通CSSや
共通ヘッダー・ステップ表示を提供する。
"""

import streamlit as st


# 共通カスタムCSSをページに注入する関数
def inject_custom_css():
    """
    アプリ全体で統一感のあるモダンなWebデザインを適用するCSS。
    - 白基調 (#F8FAFF / #FFFFFF)
    - メインアクセント (#4F46E5, #4338CA)
    - 高コントラストテキスト (#1F2937, #374151, #475569)
    - ボタン文字色の確実な適用
    - 横スクロール防止とレスポンシブ配置
    """
    css_content = """
    <style>
    /* 全要素のボックスサイズ初期化 */
    *, *::before, *::after {
        box-sizing: border-box !important;
    }

    /* ページ全体の基本設定と横スクロール防止 */
    html, body, .stApp {
        overflow-x: hidden !important;
        background-color: #F8FAFF !important;
        color: #1F2937 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Kaku Gothic ProN", "BIZ UDPGothic", Meiryo, sans-serif !important;
    }

    /* コンテンツ領域の最大幅と中央揃え */
    .block-container {
        max-width: 1140px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        overflow-x: hidden !important;
    }

    /* 既存Streamlitヘッダーの整理 */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* テキストの行間・基本色・改行処理 */
    p, span, label, div {
        line-height: 1.6;
        color: #374151;
        overflow-wrap: break-word;
        word-break: break-word;
    }

    /* 見出し文字 */
    h1, h2, h3, h4, h5, h6 {
        color: #1F2937 !important;
        overflow-wrap: break-word;
        word-break: break-word;
    }

    /* ========================================================= */
    /* プライマリボタン（背景 #4F46E5 / 文字色 #FFFFFF 強制適用） */
    /* ========================================================= */
    button[kind="primary"],
    div.stButton > button[kind="primary"],
    button[kind="primary"] *,
    div.stButton > button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    button[kind="primary"],
    div.stButton > button[kind="primary"] {
        background-color: #4F46E5 !important;
        background-image: none !important;
        border: none !important;
        border-radius: 10px !important;
        min-height: 44px !important;
        padding: 0.6rem 1.4rem !important;
        font-size: 15px !important;
        letter-spacing: 0.02em !important;
        box-shadow: 0 2px 6px rgba(79, 70, 229, 0.25) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    button[kind="primary"]:hover,
    div.stButton > button[kind="primary"]:hover {
        background-color: #4338CA !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35) !important;
    }

    button[kind="primary"]:hover *,
    div.stButton > button[kind="primary"]:hover * {
        color: #FFFFFF !important;
    }

    button[kind="primary"]:active,
    div.stButton > button[kind="primary"]:active {
        transform: translateY(0) !important;
        box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2) !important;
    }

    /* ========================================================= */
    /* セカンダリボタン（白背景＋枠線＋濃い青紫文字 #3730A3） */
    /* ========================================================= */
    button[kind="secondary"],
    div.stButton > button[kind="secondary"],
    div.stButton > button:not([kind="primary"]),
    button[kind="secondary"] *,
    div.stButton > button[kind="secondary"] *,
    div.stButton > button:not([kind="primary"]) * {
        color: #3730A3 !important;
        font-weight: 600 !important;
    }

    button[kind="secondary"],
    div.stButton > button[kind="secondary"],
    div.stButton > button:not([kind="primary"]) {
        background-color: #FFFFFF !important;
        background-image: none !important;
        border: 1px solid #A5B4FC !important;
        border-radius: 10px !important;
        min-height: 42px !important;
        padding: 0.5rem 1.2rem !important;
        font-size: 14px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease !important;
    }

    button[kind="secondary"]:hover,
    div.stButton > button[kind="secondary"]:hover,
    div.stButton > button:not([kind="primary"]):hover {
        border-color: #4F46E5 !important;
        background-color: #EEF2FF !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 3px 8px rgba(79, 70, 229, 0.15) !important;
    }

    button[kind="secondary"]:hover *,
    div.stButton > button[kind="secondary"]:hover *,
    div.stButton > button:not([kind="primary"]):hover * {
        color: #4F46E5 !important;
    }

    /* 入力フォーム（Textarea, Input）のスタイル */
    textarea, div[data-baseweb="textarea"] textarea {
        border-radius: 10px !important;
        border: 1px solid #D1D5DB !important;
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        font-size: 14.5px !important;
        line-height: 1.6 !important;
        padding: 10px 14px !important;
        transition: all 0.2s ease !important;
    }

    div[data-baseweb="textarea"]:focus-within {
        border-color: #4F46E5 !important;
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15) !important;
    }

    /* Streamlitのコンテナカード（border=True）の上書き */
    div[data-testid="stVerticalBlock"] > div[style*="border:"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
        padding: 20px !important;
        box-shadow: 0 2px 8px rgba(31, 41, 55, 0.04) !important;
        overflow-wrap: break-word !important;
    }

    /* ラジオボタンの余白とデザイン */
    div[data-testid="stRadio"] > label {
        font-weight: 600 !important;
        color: #1F2937 !important;
        margin-bottom: 8px !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] > label {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        margin-bottom: 8px !important;
        transition: all 0.15s ease !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        background-color: #F8FAFF !important;
        border-color: #C7D2FE !important;
    }

    /* 区切り線 */
    hr {
        border: none !important;
        border-top: 1px solid #E2E8F0 !important;
        margin: 28px 0 !important;
    }

    /* アラート・インフォボックスの調整 */
    div[data-testid="stAlert"] {
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        padding: 12px 16px !important;
    }

    /* リンクのデフォルト色 */
    a {
        color: #4F46E5 !important;
        text-decoration: none !important;
    }

    a:hover {
        color: #3730A3 !important;
        text-decoration: underline !important;
    }
    </style>
    """
    st.markdown(css_content, unsafe_allow_html=True)


# 共通ヘッダーとステップインジケーターを描画する関数
def render_common_header(title: str, subtitle: str, current_step: int = 1):
    """
    両ページ共通のヘッダーを表示する。
    - 左側：アイコン + ページタイトル + 説明文
    - 右側：3段階ステップインジケーター（① ニュース選択 → ② 意見の予測 → ③ 確認・訂正）
    - PC画面で高さ100〜120px程度のコンパクトな横長カード

    Args:
        title: ページタイトル
        subtitle: 1行説明文
        current_step: 現在のステップ番号 (1, 2, 3)
    """
    steps = [
        {"num": 1, "name": "ニュース選択"},
        {"num": 2, "name": "意見の予測"},
        {"num": 3, "name": "確認・訂正"},
    ]

    step_pills = []
    for s in steps:
        is_active = (s["num"] == current_step)
        is_done = (s["num"] < current_step)

        if is_active:
            pill = (
                f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; '
                f'border-radius: 20px; background: #EEF2FF; border: 1px solid #C7D2FE; '
                f'font-size: 13px; font-weight: 700; color: #3730A3; white-space: nowrap;">'
                f'<span style="display: inline-flex; align-items: center; justify-content: center; '
                f'width: 18px; height: 18px; border-radius: 50%; background: #4F46E5; color: #FFFFFF; font-size: 11px;">{s["num"]}</span>'
                f'{s["name"]}</span>'
            )
        elif is_done:
            pill = (
                f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; '
                f'border-radius: 20px; background: #ECFDF5; border: 1px solid #A7F3D0; '
                f'font-size: 13px; font-weight: 600; color: #065F46; white-space: nowrap;">'
                f'<span style="display: inline-flex; align-items: center; justify-content: center; '
                f'width: 18px; height: 18px; border-radius: 50%; background: #059669; color: #FFFFFF; font-size: 11px;">✓</span>'
                f'{s["name"]}</span>'
            )
        else:
            pill = (
                f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; '
                f'border-radius: 20px; background: #FFFFFF; border: 1px solid #E2E8F0; '
                f'font-size: 13px; font-weight: 500; color: #64748B; white-space: nowrap;">'
                f'<span style="display: inline-flex; align-items: center; justify-content: center; '
                f'width: 18px; height: 18px; border-radius: 50%; background: #E2E8F0; color: #475569; font-size: 11px;">{s["num"]}</span>'
                f'{s["name"]}</span>'
            )
        step_pills.append(pill)

    arrow_html = '<span style="color: #94A3B8; font-size: 12px; margin: 0 2px;">→</span>'
    steps_html = arrow_html.join(step_pills)

    # 改行やインデント空白によるMarkdownコードブロック化を完全に防ぐインラインHTML
    header_html = (
        '<div style="'
        'background: #FFFFFF;'
        'border: 1px solid #E2E8F0;'
        'border-radius: 14px;'
        'padding: 16px 22px;'
        'margin-bottom: 24px;'
        'box-shadow: 0 2px 8px rgba(31, 41, 55, 0.04);'
        'display: flex;'
        'flex-wrap: wrap;'
        'align-items: center;'
        'justify-content: space-between;'
        'gap: 14px;'
        '">'
        '<div style="display: flex; align-items: center; gap: 12px;">'
        '<div style="'
        'width: 40px;'
        'height: 40px;'
        'border-radius: 10px;'
        'background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);'
        'border: 1px solid #C7D2FE;'
        'display: flex;'
        'align-items: center;'
        'justify-content: center;'
        'font-size: 20px;'
        'flex-shrink: 0;'
        '">🤖</div>'
        '<div>'
        f'<h1 style="margin: 0; padding: 0; font-size: 19px; font-weight: 700; color: #1F2937; letter-spacing: -0.01em; line-height: 1.3;">{title}</h1>'
        f'<p style="margin: 3px 0 0 0; padding: 0; font-size: 13px; color: #475569; line-height: 1.4;">{subtitle}</p>'
        '</div>'
        '</div>'
        f'<div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">{steps_html}</div>'
        '</div>'
    )

    st.markdown(header_html, unsafe_allow_html=True)


# カテゴリバッジのHTML文字列を生成する関数
def get_category_badge_html(category: str) -> str:
    """
    カテゴリに応じた淡く上品なカラーバッジHTMLを返す。
    高コントラストで視認性を確保する。
    """
    color_map = {
        "国内": {"bg": "#EFF6FF", "color": "#1D4ED8", "border": "#BFDBFE"},
        "国際": {"bg": "#EEF2FF", "color": "#4338CA", "border": "#C7D2FE"},
        "経済": {"bg": "#ECFDF5", "color": "#047857", "border": "#A7F3D0"},
        "エンタメ": {"bg": "#FDF2F8", "color": "#BE185D", "border": "#FBCFE8"},
        "スポーツ": {"bg": "#FFF7ED", "color": "#C2410C", "border": "#FED7AA"},
        "IT": {"bg": "#F0F9FF", "color": "#0369A1", "border": "#BAE6FD"},
        "科学": {"bg": "#FAF5FF", "color": "#6D28D9", "border": "#DDD6FE"},
        "ライフ": {"bg": "#F0FDF4", "color": "#15803D", "border": "#BBF7D0"},
        "地域": {"bg": "#F7FEE7", "color": "#4D7C0F", "border": "#D9F99D"},
    }

    style = color_map.get(
        category,
        {"bg": "#F1F5F9", "color": "#334155", "border": "#CBD5E1"},
    )

    badge_html = (
        f'<span style="display: inline-block; background-color: {style["bg"]}; color: {style["color"]}; '
        f'border: 1px solid {style["border"]}; padding: 3px 10px; border-radius: 6px; font-size: 12px; '
        f'font-weight: 600; letter-spacing: 0.02em;">{category or "ニュース"}</span>'
    )

    return badge_html
