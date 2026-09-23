"""Presentation helpers for the results; escape all provider-supplied text."""
from html import escape


def text(value):
    return escape(str(value), quote=True)


def comparison_table(results):
    rows = []
    for result in results:
        c = result["classification"]
        tone, icon = {"GROW": ("mint", "↗"), "LOW_GROWTH": ("rose", "◇"), "HOLD": ("lavender", "✧")}.get(c["category"], ("lavender", "✧"))
        ai = c.get("mode") == "jev"
        mode = "✦ Jev AI" if ai else "データ不足" if c.get("mode") == "insufficient_data" else "AI未実行・失敗"
        confidence = f"{c['confidence']:.1%}" if ai and c.get("confidence") is not None else "—"
        score = f"{c['score']:.1f}%" if c.get("score") is not None else "—"
        price = f"{result['latest_price']:,.2f}" if result.get("latest_price") is not None else "—"
        rows.append(f'<tr><th scope="row"><strong>{text(result["ticker"])}</strong><span class="compare-name">{text(result["company_name"])}</span></th><td><span class="screening-chip {tone}">{icon} {text(c["label"])}</span></td><td>{text(result.get("prediction_horizon_years", 10))}年後</td><td><span class="compare-mode">{mode}</span></td><td class="compare-number">{confidence}</td><td class="compare-number">{score}</td><td>{text(c["available_metrics"])} / 7</td><td class="compare-number">{price}<span class="compare-currency">{text(result.get("currency", "通貨不明"))}</span></td></tr>')
    columns = ["銘柄 / 企業名", "判定結果", "判定期間", "判定方式", "AI確信度", "固定基準の達成率", "取得指標数", "株価 / 通貨"]
    headings = ''.join(f'<th scope="col">{label}</th>' for label in columns)
    return f'<section class="evidence-card comparison-card"><div class="evidence-header"><div><span class="section-kicker">✧ COMPARE YOUR DISCOVERIES</span><h4>気になる企業を、並べてチェック。</h4></div><span class="evidence-count">{len(results)}社</span></div><div class="evidence-meta"><span>確信度・達成率は株価の上昇確率ではありません。</span></div><div class="evidence-scroll" tabindex="0" role="region" aria-label="すべての企業の比較表"><table class="evidence-table comparison-table"><caption>今回の判定結果一覧</caption><thead><tr>{headings}</tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="evidence-footnote">横にスクロールして比較できます。— は取得不可またはAI判定なし。通貨・判定期間の違いにご注意ください。</div></section>'


def loading_card(completed, total, ticker=None, errors=0):
    done = completed == total
    percent = round(completed / total * 100)
    title = "リサーチが完了しました" if done else "未来の可能性をリサーチ中…"
    detail = (f"取得成功 {total - errors}社 ・ 取得失敗 {errors}社" if done else
              f"{text(ticker)} の企業データ・判定結果を待っています")
    return f'''<section class="loading-card {'is-complete' if done else 'is-loading'}">
<div class="loading-top"><div class="loading-mascot" aria-hidden="true">{'✓' if done else '✦'}</div><div class="loading-copy"><div class="section-kicker">{'RESEARCH COMPLETE' if done else 'EXPLORING YOUR FUTURE'}</div><h3>{title}</h3><p role="status" aria-live="polite">{detail}</p></div><span class="loading-percent">{percent}<small>%</small></span></div>
<div class="loading-track" role="progressbar" aria-label="銘柄の処理完了率" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{percent}"><div class="loading-fill" style="width:{percent}%"></div></div>
<div class="loading-bottom"><span>{completed} / {total} 社の処理完了</span><span>{'結果を下に表示しています' if done else '銘柄ごとの処理完了に合わせて進みます'}</span></div>
</section>'''


def company_card(result):
    c = result["classification"]
    tone, icon = {"GROW": ("mint", "↗"), "LOW_GROWTH": ("rose", "◇"),
                  "HOLD": ("lavender", "✧")}.get(c["category"], ("lavender", "✧"))
    ai = c.get("mode") == "jev"
    status = "✦ Jev AI 判定済み" if ai else "○ AI未実行・失敗"
    if c.get("mode") == "insufficient_data":
        status = "○ データ不足"
    confidence = c.get("confidence") if ai else None
    confidence_text = f"{confidence:.1%}" if confidence is not None else "—"
    width = max(0, min(100, confidence * 100)) if confidence is not None else 0
    score = f"{c['score']:.1f}%" if c.get("score") is not None else "—"
    price = f"{result['latest_price']:,.2f}" if result.get("latest_price") is not None else "取得不可"
    message = c.get("status_message", "AI判定結果がありません。再分類してください。")
    return f'''<article class="company-card {tone}">
<div class="company-top"><div class="company-identity"><span class="company-symbol" aria-hidden="true">{icon}</span><div><div class="ticker-label">{text(result['ticker'])}</div><h3>{text(result['company_name'])}</h3></div></div><span class="ai-status">{status}</span></div>
<div class="company-verdict"><span class="verdict-badge">{icon} {text(c['label'])}</span><span class="ai-status">{text(result.get('prediction_horizon_years', 10))}年後の見通し</span><span class="company-sector">{text(result.get('sector', '不明'))}</span></div>
<p class="verdict-message">{text(message)}</p>
<div class="result-facts"><div class="result-fact confidence-fact"><span>AI分類の確信度</span><strong>{confidence_text}</strong><div class="confidence-track" aria-hidden="true"><div style="width:{width:.1f}%"></div></div></div><div class="result-fact"><span>固定基準の達成率</span><strong>{score}</strong><small>取得指標 {c['available_metrics']} / 7</small></div><div class="result-fact"><span>現在の株価</span><strong>{price}</strong><small>{text(result.get('currency', '通貨不明'))}</small></div></div>
<div class="company-bottom"><span>{text(c.get('model', 'Jev')) if ai else 'AI判定なし'}</span><span>確信度・達成率は株価上昇確率ではありません</span></div>
</article>'''


def screening_chips(classification):
    groups = []
    for key, title, tone, icon in [("strengths", "条件達成", "mint", "✓"),
                                   ("concerns", "条件未達成", "rose", "◇"),
                                   ("missing", "データ不足", "lavender", "○")]:
        chips = ''.join(f'<span class="screening-chip {tone}">{icon} {text(item)}</span>' for item in classification[key])
        groups.append(f'<div class="screening-group"><span class="screening-label">{title}</span><div class="screening-chips">{chips or "<span class=chip-empty>なし</span>"}</div></div>')
    return '<div class="screening-panel">' + ''.join(groups) + '</div>'


def financial_cards(result):
    cards = []
    for metric in result["classification"]["metrics"]:
        value, unit = metric["value"], metric["unit"]
        display = "—" if value is None else (
            f"{value * 100:.1f}%" if unit == "%" else
            f"{value:.1f}%" if unit == "ratio_pct" else
            f"{value:.1f}倍" if unit == "multiple" else f"{value:,.0f}")
        tone, icon, status = ("lavender", "○", "取得不可") if metric["passed"] is None else (
            ("mint", "✓", "達成") if metric["passed"] else ("rose", "◇", "未達成"))
        currency = text(result.get("financial_currency", "通貨不明")) if unit == "currency" and value is not None else ""
        cards.append(f'<article class="financial-card {tone}"><div class="financial-card-top"><h4>{text(metric["label"])}</h4><span class="financial-status">{icon} {status}</span></div><div class="financial-value">{display}</div><div class="financial-unit">{currency}</div></article>')
    return '<div class="financial-heading"><span>◎ FINANCIAL SNAPSHOT</span><small>固定基準による参考評価</small></div><div class="financial-grid">' + ''.join(cards) + '</div>'


def annual_evidence_card(label, records, currency):
    labels = {"Total Revenue": "売上高", "Operating Income": "営業利益", "Net Income": "純利益",
              "Diluted EPS": "希薄化後EPS", "Operating Cash Flow": "営業CF", "Free Cash Flow": "フリーCF",
              "Capital Expenditure": "設備投資", "Total Debt": "有利子負債", "Stockholders Equity": "株主資本",
              "Cash And Cash Equivalents": "現金・現金同等物"}
    fields = [key for key in labels if any(key in record for record in records)]
    headings = ''.join(f'<th scope="col">{text(r["period_end"])}</th>' for r in records)
    rows = []
    for key in fields:
        cells = []
        for record in records:
            value = record.get(key)
            display = "—" if value is None else f"{value:,.2f}" if key == "Diluted EPS" else f"{value:,.0f}"
            cells.append(f'<td>{display}</td>')
        rows.append(f'<tr><th scope="row">{labels[key]}</th>{"".join(cells)}</tr>')
    return f'<section class="evidence-card"><div class="evidence-header"><div><span class="section-kicker">✦ AI INPUT DATA</span><h4>{text(label)}</h4></div><span class="evidence-count">{len(records)}期分</span></div><div class="evidence-meta"><span>決算通貨：{text(currency)}</span><span>EPSは1株あたり ／ — はデータなし</span></div><div class="evidence-scroll" tabindex="0" role="region" aria-label="{text(label)}の年次データ"><table class="evidence-table"><caption>{text(label)}・決算期末ごとの数値</caption><thead><tr><th scope="col">指標 / 決算期末</th>{headings}</tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="evidence-footnote">数値は取得元の決算データです。横にスクロールして各期を比較できます。</div></section>'
