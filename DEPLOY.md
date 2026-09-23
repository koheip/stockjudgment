# 公開手順

## 1. GitHub

対象: https://github.com/koheip/stockjudgment （ブランチ master）
`.env` と `.streamlit/secrets.toml` はアップロードしません。
過去に共有したJevキーは再発行し、公開環境には新しいキーを設定してください。

## 2. Render

https://dashboard.render.com/ で New > Blueprint を選び、このリポジトリの `master` を接続します。
`render.yaml` を読み込ませ、`TYPESAFE_API_KEY` に発行済みキーを入力して作成します。
プランはfree、API起動は1ワーカーです。WebサービスのURLを控えてください。
Environmentに自動生成される `STOCK_API_TOKEN` を、次のStreamlit Secretsへコピーします。
このトークンはJevキーとは別の、画面サーバーからAPIサーバーへの接続用です。
`/` が200で応答すること、トークンなしの `/predict/AAPL` が401になることを確認します。

## 3. Streamlit Community Cloud

https://share.streamlit.io/ で Create app を選びます。

- Repository: `koheip/stockjudgment`
- Branch: `master`
- Main file path: `front.py`
- Advanced settings: Python 3.12
- Secrets: 下記（実際のURLとトークンに置き換え）

```toml
STOCK_API_URL = "https://YOUR-API.onrender.com"
STOCK_API_TOKEN = "Renderで自動生成された値"
```

JevキーをStreamlitへ設定する必要はありません。
Deploy後、1銘柄を判定し、同じ年数で再判定すると保存済み結果が表示されることを確認してください。
発行された `.streamlit.app` URLが利用者に共有するURLです。

## 制限と運用

- 全利用者合計30リクエスト/分。新規の判定処理は200回/日（UTC）を既定値とします。失敗も回数に含みます。
- 同時に1件処理し、混雑時は503を返します。画面は401/429/503で残りの処理を停止します。
- 成功したJev判定だけを銘柄・期間・モデル別に1時間保存（最大256件）。取得日時は保持します。
- 制限とキャッシュは単一プロセスのメモリ上です。再起動・再デプロイ時にリセットされます。**課金額の厳密な上限ではありません。** 必要に応じて提供元の利用上限も設定してください。
- 利用者別の制限ではなくアプリ全体の上限です。公開画面の連打は全体枠を消費します。
- 台数・ワーカーを増やす場合は共有ストレージによるカウンター・キャッシュへの変更が必要です。
- 無料サービスは起動待ちが発生する場合があります。タイムアウト時は少し待って再試行してください。
- Renderでは環境変数を使用し、ローカルの `.env` を読み込みません。
- 証券データを一般公開する用途がデータ提供元の利用条件に合うかを確認してください。

## 公式ドキュメント

- https://render.com/docs/blueprint-spec
- https://render.com/docs/deploy-fastapi
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
