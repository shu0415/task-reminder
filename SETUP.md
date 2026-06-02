# セットアップガイド

## 全体の流れ

1. Google Sheets API の設定
2. Slack App の作成
3. Railway へのデプロイ
4. 環境変数の設定
5. スプレッドシートの初期化

---

## 1. Google Sheets API の設定

### サービスアカウントの作成

1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. 新しいプロジェクトを作成（例: `task-reminder`）
3. 「APIとサービス」→「ライブラリ」から以下を有効化
   - **Google Sheets API**
   - **Google Drive API**
4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」
5. サービスアカウント名を入力して作成
6. 作成したサービスアカウントをクリック →「キー」タブ →「鍵を追加」→「JSON」
7. ダウンロードしたJSONファイルを `config/google_credentials.json` として保存

### スプレッドシートの準備

1. Googleスプレッドシートで新規シートを作成
2. URLから `spreadsheet_id` をコピー
   - `https://docs.google.com/spreadsheets/d/【ここがID】/edit`
3. サービスアカウントのメールアドレス（`xxxx@xxx.iam.gserviceaccount.com`）に**編集権限**を共有

---

## 2. Slack App の作成

1. [Slack API](https://api.slack.com/apps) → 「Create New App」→「From scratch」
2. App名（例: `TaskReminder`）とワークスペースを選択

### Bot Token Scopes の設定

「OAuth & Permissions」→「Bot Token Scopes」に以下を追加:
- `chat:write`
- `chat:write.public`

### Event Subscriptions

「Event Subscriptions」→ Enable → Request URL に:
```
https://あなたのサーバーURL/slack/events
```

### Interactivity

「Interactivity & Shortcuts」→ Enable → Request URL に:
```
https://あなたのサーバーURL/slack/interactions
```

### インストール

「Install to Workspace」→ 承認
→ 「Bot User OAuth Token」（`xoxb-...`）をコピー

### チャンネルIDの取得

各チャンネルを右クリック →「チャンネル詳細を表示」→ 一番下にチャンネルIDあり

---

## 3. Railway へのデプロイ

1. [Railway](https://railway.app/) でアカウント作成
2. 「New Project」→「Deploy from GitHub repo」
3. このリポジトリを接続
4. Startコマンドを設定:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

---

## 4. 環境変数の設定

`.env.example` を参考に Railway の環境変数に以下を設定:

| 変数名 | 値 |
|---|---|
| `SLACK_BOT_TOKEN` | `xoxb-...` |
| `SLACK_SIGNING_SECRET` | Slack App の署名シークレット |
| `SLACK_CHANNEL_INSTAGRAM` | `#instagram` チャンネルのID |
| `SLACK_CHANNEL_TIKTOK` | `#tiktok` チャンネルのID |
| `SLACK_CHANNEL_X` | `#x` チャンネルのID |
| `SLACK_CHANNEL_GUMROAD` | `#gumroad` チャンネルのID |
| `GOOGLE_CREDENTIALS_FILE` | `config/google_credentials.json` |
| `SPREADSHEET_ID` | スプレッドシートのID |
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `MEMBER_1_NAME` | `Shu` |
| `MEMBER_2_NAME` | `Partner` |
| `REMINDER_TIME_1` | `09:00` |
| `REMINDER_TIME_2` | `13:00` |

---

## 5. スプレッドシートの初期化

デプロイ後、以下のエンドポイントを叩いてシートを初期化:

```bash
curl -X POST https://あなたのサーバーURL/remind/now
```

または Pythonで直接実行:

```bash
python -c "from src.sheets import init_sheets; init_sheets()"
```

---

## テスト送信

```bash
curl -X POST https://あなたのサーバーURL/remind/now
```

全チャンネルに即時送信されます。

---

## タスクの記入方法

スプレッドシートを開き、各プラットフォームのシートに直接入力してください。

**必須入力**（手入力）:
- タスク名
- 期限
- 担当者（プルダウン）
- カテゴリ（プルダウン）
- 優先度（プルダウン）

**自動入力**:
- タスクID（自動採番）
- 作成日（入力日）
- 完了日（完了時自動）
- AIスコア（リマインド時に自動更新）
