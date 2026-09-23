# MIRAI STOCK

一般公開の設定と手順は [DEPLOY.md](DEPLOY.md) を参照してください。

StreamlitとFastAPIで企業の財務指標を取得し、TypeSafeのJevで長期株価成長の候補を分類します。

## 設定と起動

`.env` の `TYPESAFE_API_KEY` にTypeSafeから発行されたAPIキーを設定してください。
キーは共有・コミットしないでください。任意の `TYPESAFE_MODEL` でモデルを変更できます（既定値 `jev-1.13.0`）。
設定変更後はバックエンドを再起動してください。

別々のターミナルで起動します。

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
.\.venv\Scripts\python.exe -m streamlit run front.py
```

## 判定の意味

- 画面で判定期間を1〜30年（初期値10年）から指定します。期間の変更後は再分類してください。
- APIは `/predict/AAPL?horizon_years=5` のように指定できます。省略時は10年です。
- 指定年数はJevの指示・入力と結果・CSVに反映します。過去データの取得期間と固定基準は変えません。

- Jevへ銘柄・企業名・業種・株価と7つの財務指標、取得可能な最大5期の年次決算と月次株価の過去成長率を送信します。年次データは提供元の収録範囲に依存します。
- 最終分類はAIの選択結果です。参考の固定基準達成率とは独立しています。
- AIの確信度はモデル内部の分類確信度で、実際の株価上昇確率ではありません。
- 直近指標と年次決算を合わせ、成長・収益性・キャッシュフロー・財務・割高感の2分野以上が利用可能ならAIを呼びます。売上・利益成長率は必須ではありません。株価推移だけではAIを呼びません。
- AIは優勢な方向を選び、根本的な情報不足・重大な矛盾・拮抗の場合に保留します。保留率を減らす設計変更は、予測精度の向上を意味しません。
- キー未設定・通信失敗・不正応答は判定保留とし、AI判定成功として扱いません。
- 条件達成／未達成の一覧は固定基準の評価であり、AIが生成した理由ではありません。
- 10年後の株価で検証済みの予測モデルではありません。

## 確認

```powershell
.\.venv\Scripts\python.exe -m unittest test_classification -v
.\.venv\Scripts\python.exe check_jev.py
```

自動テストはAPIをモックします。`check_jev.py` は実際のTypeSafe APIを呼び出します。
