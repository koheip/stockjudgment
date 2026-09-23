import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import pandas as pd
import requests
import streamlit as st
from result_ui import company_card, screening_chips, financial_cards, loading_card, annual_evidence_card, comparison_table


def read_secrets():
    """Return (flattened secret items, parse error). Keys placed under a [section] are still found."""
    try:
        items = list(st.secrets.items())
    except Exception as error:
        # An invalid TOML (e.g. full-width quotes) hides every secret; report it instead of "missing".
        return [], None if "parsing" not in str(error) else str(error)
    flat = []
    for key, value in items:
        if hasattr(value, "items"):
            flat.extend((str(k), v) for k, v in value.items() if not hasattr(v, "items"))
        else:
            flat.append((str(key), value))
    return flat, None


def setting(name, default=""):
    # Tolerate common Secrets mistakes: lowercase keys, keys inside a [section], stray quotes/spaces.
    # Also accept the name without the STOCK_ prefix (e.g. API_TOKEN), a frequent typo.
    names = (name, name.removeprefix("STOCK_"))
    matches = [v for n in names for k, v in read_secrets()[0] if k.strip().upper() == n]
    value = str(matches[0]) if matches else os.getenv(name, default)
    return value.strip().strip("'\"“”‘’　").strip()


SECRETS_EXAMPLE = """```toml
STOCK_API_URL = "https://mirai-stock-api.onrender.com"
STOCK_API_TOKEN = "Renderでコピーした値"
```"""


def token_help():
    items, parse_error = read_secrets()
    if parse_error:
        return f"""**Secretsの書き方に誤りがあり、Streamlitが設定を1つも読み込めていません。**

よくある原因：全角の `”` `＝` や全角スペース、値を `"` で囲んでいない、行の途中で改行されている。
**⋮ → Settings → Secrets** の中身をすべて消し、半角英数字で次の2行だけにして **Save** してください（日本語入力をオフにして編集）。

{SECRETS_EXAMPLE}

エラー内容：`{parse_error.split(":", 1)[-1].strip()[:200]}`"""
    keys = sorted({k for k, _ in items})
    found = "、".join(keys) if keys else "なし（Secretsが空か、保存が反映されていません）"
    return f"""**Streamlitに `STOCK_API_TOKEN` が設定されていないため、APIへ接続できません。**（JevのAPIキーとは別の値です）

1. https://dashboard.render.com/ → `mirai-stock-api` → **Environment** を開き、`STOCK_API_TOKEN` の値をコピー
2. https://share.streamlit.io/ → このアプリの **⋮ → Settings → Secrets** に次の2行を貼り付けて **Save**

{SECRETS_EXAMPLE}

3. 1分ほど待っても変わらない場合は **⋮ → Reboot app** を実行

現在Secretsで見つかったキー名：{found}""" + ("\n\n`STOCK_API_TOKEN` はありますが値が空です。`\"` と `\"` の間にRenderの値を貼り付けてください。" if any(k.strip().upper() == "STOCK_API_TOKEN" for k in keys) else "")

st.set_page_config(page_title="MIRAI STOCK ✦ 未来の成長をみつけよう", page_icon="🪐", layout="wide")
st.markdown(f"<style>{Path(__file__).with_name('style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.markdown('''
<div class="brand-bar"><span class="brand">✳ MIRAI STOCK</span><span class="brand-tag">YOUR LITTLE FUTURE LAB</span></div>
<section class="hero">
  <div class="hero-copy">
    <div class="eyebrow">✦ FIND YOUR NEXT POSSIBILITY</div>
    <h1>あなたが選ぶ未来の可能性を、<br><span>いっしょに見つけよう。</span></h1>
    <p>気になる企業の「これから」を、7つの指標でチェック。<br>未来の成長候補を探す、小さなリサーチラボ。</p>
    <div class="hero-tags"><span>↗ 長期成長</span><span>✦ Jev AI判定</span><span>◎ 7つの指標</span></div>
  </div>
  <div class="future-art" aria-hidden="true">
    <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
    <span class="spark spark-one">✦</span><span class="spark spark-two">✧</span>
    <div class="planet"><div class="planet-face">• ᴗ •</div><div class="planet-blush"></div></div>
    <div class="floating-label">HELLO, FUTURE! ↗</div>
    <span class="little-star">✳</span>
  </div>
</section>
''', unsafe_allow_html=True)
st.info("Jevが指定した年数での成長候補を分類します。将来の株価上昇を保証するものではありません。AIの確信度と固定基準の達成率は、株価の上昇確率ではありません。")
with st.expander("判定基準とデータの限界"):
    st.markdown("""
**最終分類はJevによるAI判定です。** 銘柄・企業名・業種・株価・財務指標をTypeSafeのAPIに送信します。
直近の7指標に加え、取得可能な最大5期の年次決算と過去の株価推移を参照します。
成長・収益性・キャッシュフロー・財務・割高感のうち2分野以上にデータがあればAI判定を実行します。
売上・利益成長率の欠損だけでは停止しません。AIは強弱を比較して優勢な方向を選び、判断不能や拮抗の場合に保留します。
AIが判断できない場合や接続に失敗した場合は **判定保留** とし、実行状況を表示します。

以下はAI判定とは独立した**参考用の固定基準**です。
取得できた指標の **60%以上** が条件を満たす企業を参考分類で **伸びる候補**、それ未満を **伸びにくい候補** とします。
参考分類には売上・利益成長率の両方と、全7項目中5項目以上が必要です。この条件はAIの実行条件とは別です。

| 指標 | 条件 |
| --- | --- |
| 売上成長率・利益成長率 | それぞれ5%以上 |
| 営業利益率・ROE | それぞれ10%以上 |
| フリーキャッシュフロー | プラス |
| 負債／自己資本比率 | 100%以下 |
| 実績PER | 0倍超、25倍以下 |

各項目は同じ重みです。固定基準は期間によらず共通で、指定年数はAI判定に反映します。
データはYahoo! Finance（yfinance経由）の指標です。判定期間を変えても過去データの取得期間は変わりません。
項目ごとに対象期間・更新時点が異なり、取得日時は決算日ではありません。
独自基準であり、将来の株価で検証した予測モデルではありません。
業種差、競争力、将来の事業変化、配当込みの収益を反映しません。
金融業や赤字成長企業などでは特に基準が適さない場合があります。
""")

with st.form("classification_form"):
    st.markdown('<div class="section-kicker">01 / LET’S EXPLORE</div><h2 class="section-title">気になる企業を教えてね ✧</h2>', unsafe_allow_html=True)
    raw = st.text_area("銘柄コード（カンマ・空白・改行区切り、最大20件）", "7203.T, AAPL, MSFT")
    horizon_years = st.number_input("何年後の成長を判定しますか？", min_value=1, max_value=30, value=10, step=1, help="1〜30年で指定できます。変更後は分類ボタンを押して再判定してください。")
    st.caption("日本株は 7203.T のように入力。米国株は AAPL などのティッカーで検索できます。")
    submitted = st.form_submit_button("未来の成長候補をチェック  ↗", type="primary", width="stretch")

if submitted:
    tickers = list(dict.fromkeys(t.upper() for t in re.split(r"[,、\s]+", raw.strip()) if t))
    if not tickers or len(tickers) > 20:
        st.error("銘柄コードは1〜20件で入力してください。")
    else:
        results, errors = [], []
        progress = st.empty()
        page_host = urlsplit(st.context.url or "").hostname or ""
        cloud = page_host.endswith(".streamlit.app")
        api_url = setting("STOCK_API_URL", "https://mirai-stock-api.onrender.com" if cloud else "http://localhost:8001").rstrip("/")
        api_token = setting("STOCK_API_TOKEN")
        parsed_api = urlsplit(api_url)
        if parsed_api.scheme not in ("http", "https") or not parsed_api.hostname or parsed_api.username or parsed_api.password:
            st.error("STOCK_API_URLに有効なAPI URLを設定してください。")
            st.stop()
        if cloud and (parsed_api.scheme != "https" or parsed_api.hostname in ("localhost", "127.0.0.1", "::1")):
            st.error("公開画面の接続先がローカル用です。StreamlitのSettings → Secretsで STOCK_API_URL を https://mirai-stock-api.onrender.com に変更してください。")
            st.stop()
        if cloud and not api_token:
            st.error("API接続用トークンが未設定です。\n\n" + token_help())
            st.stop()
        with st.container():
            for index, ticker in enumerate(tickers):
                progress.markdown(loading_card(index, len(tickers), ticker, len(errors)), unsafe_allow_html=True)
                try:
                    response = requests.get(f"{api_url}/predict/{quote(ticker, safe='')}", params={"horizon_years": horizon_years}, headers={"X-API-Key": api_token} if api_token else {}, timeout=(5, 120))
                    data = response.json()
                    if response.ok and isinstance(data, dict) and "classification" in data:
                        results.append(data)
                    else:
                        detail = data.get("detail", "分類できませんでした。") if isinstance(data, dict) else "応答形式が不正です。"
                        if response.status_code == 401:
                            detail = "APIには接続できていますが、認証に失敗しました。StreamlitとRenderの STOCK_API_TOKEN を同じ値に設定してください。"
                        errors.append(f"{ticker}: {detail}")
                        if response.status_code in (401, 429, 503):
                            errors.append("残りの銘柄の処理を停止しました。時間をおくか、接続設定を確認してください。")
                            progress.empty()
                            break
                except requests.exceptions.Timeout:
                    errors.append(f"{ticker}: 取得がタイムアウトしました。")
                except requests.exceptions.ConnectionError:
                    errors.append(f"{ticker}: 接続先 {parsed_api.hostname} に到達できません。STOCK_API_URLとRenderのサービス状態を確認してください。")
                    progress.empty()
                    break
                except (requests.exceptions.RequestException, ValueError):
                    errors.append(f"{ticker}: 有効な応答を取得できませんでした。")
                progress.markdown(loading_card(index + 1, len(tickers), tickers[index + 1] if index + 1 < len(tickers) else None, len(errors)), unsafe_allow_html=True)
        st.session_state["results"] = results
        st.session_state["errors"] = errors

for error in st.session_state.get("errors", []):
    st.error(error)
results = st.session_state.get("results", [])
if results:
    st.markdown('<div class="section-kicker results-kicker">02 / YOUR DISCOVERIES</div><h2 class="section-title">未来の候補、見つかった？</h2>', unsafe_allow_html=True)
    columns = st.columns(3)
    for column, category, label in zip(columns, ["GROW", "LOW_GROWTH", "HOLD"], ["伸びる候補", "伸びにくい候補", "判定保留"]):
        column.metric(label, f"{sum(r['classification']['category'] == category for r in results)}社")
    rows = []
    for result in results:
        c = result["classification"]
        rows.append({"銘柄": result["ticker"], "企業名": result["company_name"], "分類": c["label"],
                     "判定期間（年）": result.get("prediction_horizon_years", 10),
                     "判定方式": "Jev AI" if c.get("mode") == "jev" else "AI未実行・失敗",
                     "AI確信度（%）": round(c["confidence"] * 100, 1) if c.get("confidence") is not None else None,
                     "固定基準の達成率（%）": c["score"], "取得指標数": f"{c['available_metrics']}/7",
                     "株価": result["latest_price"], "通貨": result["currency"]})
    frame = pd.DataFrame(rows)
    st.caption(f"{len(results)}社のリサーチ結果 ／ カードでAI判定を、詳細で財務指標を確認できます。")
    for result in results:
        c = result["classification"]
        st.markdown(company_card(result), unsafe_allow_html=True)
        if result.get("cache_hit"):
            st.caption("保存済みの判定結果を表示しています（最大1時間）。取得日時は詳細をご確認ください。")
        with st.expander(f"◎ {result['ticker']} の財務指標をくわしく見る"):
            st.caption("以下は固定基準の参考評価です。AIが生成した判定理由ではありません。")
            st.markdown(screening_chips(c), unsafe_allow_html=True)
            if c.get("mode") == "insufficient_data":
                st.warning("直近指標と年次決算を合わせても、評価できる分野が2つ未満のため判定保留です。")
            st.markdown(financial_cards(result), unsafe_allow_html=True)
            evidence = c.get("evidence", {})
            if c.get("evidence_groups"):
                names = {"growth": "成長", "profitability": "収益性", "cashflow": "キャッシュフロー", "balance": "財務", "valuation": "割高感"}
                st.caption("AIが参照できる分野：" + "・".join(names[g] for g in c["evidence_groups"]))
            for source, label in [("income", "年次業績"), ("cashflow", "年次キャッシュフロー"), ("balance", "年次財務状態")]:
                records = evidence.get(source, [])
                if records:
                    st.markdown(annual_evidence_card(label, records, result["financial_currency"]), unsafe_allow_html=True)
            prices = evidence.get("price_history", {})
            if prices:
                st.caption(f"株価の参照期間：{prices['start']} 〜 {prices['end']}（{prices['years']}年）。過去の価格推移は補助情報として使用しています。")
            if evidence.get("warnings"):
                st.caption("一部の年次データは取得できませんでした。利用可能なデータで判定しています。")
            st.caption(f"業種：{result['sector']} ／ 取得日時（UTC）：{result['retrieved_at']}")
    with st.expander("≡ すべての企業を一覧で比較"):
        st.markdown(comparison_table(results), unsafe_allow_html=True)
    st.download_button("↓ リサーチ結果をCSVで保存", frame.to_csv(index=False).encode("utf-8-sig"), "stock_classification.csv", "text/csv")
else:
    st.markdown('''<div class="empty-state"><span class="empty-icon">✧</span><div><strong>あなたの未来リストは、ここから。</strong><p>銘柄を入力してチェックすると、分類結果とその理由がここに並びます。</p></div></div>''', unsafe_allow_html=True)

st.markdown('<footer class="app-footer">✳ MIRAI STOCK <span>小さな発見から、未来を考えよう。</span></footer>', unsafe_allow_html=True)
