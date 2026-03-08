# ADR 001: GitHub Actions から Local AI Agent Daemon への移行

## ステータス

採択済み (2026-03-08)

## コンテキスト

当初、GitHub Actions + Claude Code Action を使った自動レビュー修正フローを構築していた。
具体的には `fix-review.yml` と `claude-ci-fix.yml` を用いて以下を実現しようとした。

- CodeRabbit がレビュー → `pull_request_review` イベント → Claude Code Action が修正 → push

### 試行した構成

| フェーズ | 認証方式 | 結果 |
|---------|---------|------|
| Phase 3 | `anthropic_api_key`（API従量課金） | パーミッション拒否 32回、修正コミット失敗 |
| Phase 4 | `claude_code_oauth_token`（OAuthサブスク） | 動作確認できたが制約あり |

### GitHub Actions (OAuth) 方式の限界

#### 1. Anthropic 非公認のサードパーティ利用

Anthropic は Claude Code の OAuth 認証を **個人の対話的利用** に向けて設計しており、
サードパーティによる自動化利用（GitHub Actions など）を公式に許可していない。

> Claude Code OAuth is designed for personal, interactive use. Third-party automation using OAuth is not officially permitted.

この制約により、将来的にトークンが失効・無効化されるリスクがある。

#### 2. GitHub のセキュリティ制約（ワークフロー一致要件）

`pull_request_review` イベントは **main ブランチのワークフロー定義** を参照する。
PR ブランチのワークフローファイルが main と一致していないと、OIDC 検証で失敗する。

これにより以下の制約が生じる。

- ワークフロー変更 → main へのマージ → テスト用ブランチ作成、という順序が必須
- ワークフローのイテレーションが遅くなる

#### 3. 実行時間とコスト

API 従量課金の場合、Claude Code Action の 1 実行で $0.5〜$1.5 かかる。
試行錯誤のコストが高い。

#### 4. デバッグの困難さ

GitHub Actions ログだけでは Claude の実行内容を追いにくい。
アーティファクトのダウンロードや JSON 解析が必要。

## 決定

**GitHub Actions を廃止し、Local AI Agent Daemon に移行する。**

### 新アーキテクチャ

```
GitHub PR
   │
   ▼
CodeRabbit review → PR comments
   │
   ▼
Local Daemon (orchestrator.py) ← 60秒ポーリング
   ├── gh api: レビュー取得
   ├── gh pr diff: 差分取得
   ├── プロンプト構築
   │
   ▼
Claude Code CLI (--dangerously-skip-permissions)
   ├── ファイル編集
   └── git commit + push (tmp/daemon-workspace/ 内)
```

### 役割分担

| 役割 | ツール |
|------|------|
| レビュー | CodeRabbit |
| 修正 | Claude Code CLI |
| リポジトリ操作 | GitHub CLI (gh) |
| 自動化主体 | Local Python Daemon |

### 主な利点

| 項目 | 内容 |
|------|------|
| Anthropic API 不要 | Claude Code サブスク（OAuth）を対話的に利用 |
| GitHub Actions 不要 | ローカルで完結。CI への依存なし |
| 長時間処理可能 | Actions の 6 時間上限なし |
| デバッグ容易 | ローカル実行のためログを直接確認可能 |
| イテレーション速度 | コード変更後すぐに再起動できる |

## 廃止するファイル

| ファイル | 廃止理由 |
|---------|---------|
| `.github/workflows/fix-review.yml` | GitHub Actions 方式を廃止 |
| `.github/workflows/claude-ci-fix.yml` | 同上 |

## 維持するファイル

| ファイル | 理由 |
|---------|------|
| `.github/workflows/ci.yml` | TypeScript CI（Claude Code とは無関係） |
| `.github/workflow_samples/` | 参考実装として保持 |

## トレードオフ

### デメリット

- ローカルマシンが起動・インターネット接続している必要がある
- cloud-native な自動化ではない（サーバーレス実行不可）
- デーモンプロセスの管理が必要

### 将来の拡張可能性

- Codex など他の AI レビューを追加可能（PR コメントを読むだけでよい）
- 将来的に Claude API が安定的に利用可能になれば API 方式に戻すことも検討
- AWS Lambda / Cloud Run などでホスティングする場合は API 方式が必要
