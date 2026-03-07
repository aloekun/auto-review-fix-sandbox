# Auto Review Fix: 知見まとめ

## 1. Claude Code Actions を Claude Code サブスクリプション（OAuth）で使う

### メリット

Claude Code MAX プラン（月額定額）で利用でき、API 従量課金が不要。
個人開発者であれば、コストを気にせず Claude Code Actions を活用できる。

### 設定方法

- `anthropic_api_key` の代わりに `claude_code_oauth_token` を使用
- GitHub リポジトリの Settings > Secrets に `CLAUDE_CODE_OAUTH_TOKEN` を設定
- ワークフローの permissions に `id-token: write` と `actions: read` が必要（OIDC 認証のため）

### 制約

- **ワークフロー一致要件**: PR ブランチのワークフローファイルがデフォルトブランチ（main）と完全一致している必要がある。不一致だと `Workflow validation failed` エラー
- **個人開発者向け**: サブスクリプションは個人に紐づくため、チーム利用には向かない
- 初回は main にワークフローを先にプッシュしてから PR を作る必要がある

### ワークフロー例

```yaml
permissions:
  contents: write
  pull-requests: write
  actions: read
  id-token: write

steps:
  - uses: actions/checkout@v4
  - uses: anthropics/claude-code-action@v1
    with:
      claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
      allowed_bots: "coderabbitai[bot]"
      claude_args: |
        --allowed-tools "Read,Edit,Glob,Grep,LS,Bash(git:*),Bash(gh pr:*)"
```

---

## 2. Claude Code Actions の Agent モード

### Tag モード vs Agent モード

| 項目 | Tag モード | Agent モード |
|------|-----------|-------------|
| トリガー | `@claude` メンション | `prompt:` を指定 |
| 基本ツール | 自動で含まれる | 明示的に `allowedTools` で指定が必要 |
| プロンプト | 740行以上の詳細テンプレート（レビュー内容含む） | ユーザー指定のプロンプトのみ |
| MCP ツール | 自動設定 | `allowedTools` に含めた場合のみ |

### Agent モードの必須ツール

コード修正に最低限必要:

```
Read,Edit,Glob,Grep,LS
```

git 操作用（コロン区切り。スペース区切りは不正）:

```
Bash(git:*)
```

GitHub CLI 操作用:

```
Bash(gh pr:*)
```

### コスト実績（API 従量課金時の参考）

| 実行 | ターン | 拒否 | コスト | 結果 |
|------|--------|------|--------|------|
| #1 allowedTools なし | 39 | 32 | $1.03 | 失敗 |
| #2 Bash のみ | 31 | 48 | $1.41 | 失敗 |
| #3 全ツール（API） | 21 | 17 | $0.46 | max_turns |
| #4 Bash のみ（OAuth） | 15 | 5 | $0.37 | 成功（修正なし） |
| #5 全ツール（OAuth） | 40 | 9 | $0.92 | **成功（修正あり）** |

---

## 3. CodeRabbit のレビュー仕組み

### レビュー状態（state）

- `CHANGES_REQUESTED`: 問題を検出した場合（通常の自動レビュー時）
- `COMMENTED`: `@coderabbitai review` で手動トリガーした場合に多い

### トリガー方法

| 方法 | レビュー状態 | 備考 |
|------|-------------|------|
| 新コード push | `CHANGES_REQUESTED` | 問題がある場合 |
| `@coderabbitai review` コメント | `COMMENTED` | 手動トリガー |
| `@coderabbitai resume` コメント | - | 一時停止解除 |

### 増分レビュー（Incremental Review）

- 同じコードは再レビューしない
- 新しい diff がないと `@coderabbitai review` しても前回のレビューを返すだけ
- 新しいコードを push して初めて新しいレビューが走る

### Auto Pause 機能

- 「Auto Pause After Reviewed Commits」設定が有効だと、短時間に複数 push するとレビューが自動で一時停止される
- CodeRabbit の設定画面で無効化可能
- PR コメントに `@coderabbitai resume` で解除

### .coderabbit.yaml の重要設定

```yaml
reviews:
  auto_review:
    enabled: true
    base_branches: ["main"]
  request_changes_workflow: true  # CHANGES_REQUESTED を使用
```

---

## 4. GitHub Actions のイベント仕様

### `pull_request_review` イベント

- `types: [submitted]` でレビュー投稿時に発火
- **main ブランチのワークフロー定義が使われる**（PR ブランチのものではない）
- `paths` フィルタが効かない（GitHub の仕様制限）
- `github.event.review.state` で状態を判定可能

### Bot チェック

- Claude Code Action は非人間アクター（Bot）からのトリガーをデフォルトで拒否
- `allowed_bots: "coderabbitai[bot]"` で明示的に許可が必要
- `*` で全 Bot を許可可能

---

## 5. トラブルシューティングで得た教訓

### 試行錯誤は高コスト

Claude Code Action の 1 回の実行は $0.5〜$1.5（API 従量課金時）。ソースコードを事前に読み、設定を正確にしてからデプロイすべき。

### ソースコード調査が最も有効

公式ドキュメントだけでなく、`anthropics/claude-code-action` のソースを読むことで Agent モードと Tag モードの違い、ツール許可の仕組みを正確に理解できた。

重要なソースファイル:

| ファイル | 内容 |
|---------|------|
| `src/create-prompt/index.ts` | Tag モードの基本ツール定義、Bash パターンのコロン区切り |
| `src/modes/agent/index.ts` | Agent モードの処理。ユーザー指定ツールのみ使用 |
| `src/modes/agent/parse-tools.ts` | `--allowedTools` のパース処理 |
| `src/github/validation/actor.ts` | Bot チェック、`allowed_bots` の処理 |
| `src/mcp/install-mcp-server.ts` | MCP サーバーの設定 |

### ワークフローの変更は main 先行

`pull_request_review` イベントは main のワークフローを使うため、PR ブランチだけ変更しても反映されない。OAuth の OIDC 検証でもワークフロー一致が必要。

---

## 6. `workflow_run` イベントと `claude-ci-fix.yml` の知見

### `github.actor` vs `workflow_run.actor.login`

`workflow_run` トリガーでは 2 種類のアクター情報が取れる:

| コンテキスト変数 | 人間 push 時の値 | 意味 |
|----------------|----------------|------|
| `github.actor` | `aloekun`（pushした人） | workflow_run の場合はCIを発火させたpush者 |
| `github.event.workflow_run.actor.login` | `aloekun`（同上） | CI を発火させたcommitのpush者 |

> 実測: 両方とも同じ値になった（PR #7 テスト結果）

### `allowed_bots` の要否（未解決・部分検証）

- **人間 push → CI fail → claude-ci-fix.yml 発火**: `allowed_bots` なしで Claude が動作 ✓
- **claude[bot] push → CI fail → claude-ci-fix.yml 発火**: **未検証**
  - Claude の fix が CI を PASS させたため、failure ケースが自然発生しなかった
  - `claude-ci-fix.yml` は `conclusion == 'failure'` の場合のみ実行するため、Claude の修正後は SKIPPED になった（正常動作）

### `workflow_run` でのチェックアウト注意点

```yaml
# NG: detached HEAD になり git push が失敗しやすい
- uses: actions/checkout@v4
  with:
    ref: ${{ github.event.workflow_run.head_sha }}

# OK: ブランチとして checkout、git push が正常に動作
- uses: actions/checkout@v4
  with:
    ref: ${{ github.event.workflow_run.head_branch }}
```

### `claude-ci-fix.yml` の推奨ツール設定

```yaml
claude_args: |
  --allowed-tools "Read,Edit,Glob,Grep,LS,Bash(git:*),Bash(gh run:*),Bash(npx:*),Bash(npm:*)"
```

- `Bash(npx:*)`: `npx tsc --noEmit` で修正検証に必要
- `Bash(npm:*)`: パッケージインストールに必要（CI環境でnode_modules未キャッシュの場合）

### permission_denials_count について

- Claude Code Action が内部的にブロックしたツール呼び出しのカウント
- `git push` の認証失敗などは含まれない（別の bash 実行失敗として扱われる）
- 7回の permission_denials でも Claude は実際に fix を push できた
  - 許可されていないツール（例: `gh pr`、`WebFetch`等）は単純にスキップされ、コア機能（Read/Edit/git）は正常動作
