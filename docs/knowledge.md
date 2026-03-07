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

## 5. workflow_run イベントと claude-ci-fix.yml の実験結果

### github.actor の挙動（実測値）

| シナリオ | github.actor | workflow_run.actor.login |
|---------|-------------|--------------------------|
| 人間が push → CI 失敗 → claude-ci-fix 発火 | `aloekun`（人間） | `aloekun` |
| Claude が push → CI 成功 → claude-ci-fix SKIPPED | `claude[bot]` | `claude[bot]` |

**確認方法:** SKIPPED ランは Debug ステップが実行されないため、GitHub API で確認:
```
gh api "repos/OWNER/REPO/actions/runs/RUN_ID" --jq "{actor: .actor.login, triggering_actor: .triggering_actor.login}"
```

### claude-ci-fix.yml の再帰実行リスク

- Claude の修正で CI が**成功**する場合 → claude-ci-fix.yml は `conclusion != 'failure'` で SKIPPED → 無限ループなし
- Claude の修正で CI が**失敗**する場合 → claude-ci-fix.yml が発火、`github.actor = claude[bot]`
  - `allowed_bots` の設定がないと Claude Code Action はBot をデフォルト拒否
  - `allowed_bots: "claude[bot]"` を追加すれば再実行を許可できる（ただし無限ループリスクあり）

### show_full_output: true の重要性

`--debug` フラグを `claude_args` に追加しても、GitHub Actions の出力は制限される。
詳細なツール呼び出しログ（どのツールが何回呼ばれたか、拒否されたか）を見るには:

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    show_full_output: "true"  # これがないと debug ログが GitHub Actions に出力されない
```

**`--debug` フラグと `show_full_output` の違い:**
| 設定 | 効果 |
|-----|------|
| `claude_args: --debug` | Claude CLI のデバッグモード（内部ログ）。`show_full_output` なしでは GitHub Actions に出力されない |
| `show_full_output: "true"` | Claude Code Action の実行ログを GitHub Actions に全文出力。これがないと `permission_denials_count` だけが見える |

### コスト実績（claude-ci-fix.yml シナリオ B）

| 実行 | ターン | 拒否 | コスト | 結果 |
|------|--------|------|--------|------|
| Run #1（22803499050） | 24 | 7 | $0.42 | 成功（修正コミットあり） |
| Run #2（22803505035） | 20 | 6 | $0.34 | 成功（修正不要と判断） |

拒否されたツールの詳細は `show_full_output: false` のため不明。

---

## 6. トラブルシューティングで得た教訓

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
