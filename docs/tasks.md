# Auto Review Fix MVP: タスクリスト

設計書: [design.md](design.md)

## Phase 1: ファイル作成 (ローカル)

- [x] 1.1 `.gitignore` を作成
- [x] 1.2 `package.json` を作成
- [x] 1.3 `tsconfig.json` を作成
- [x] 1.4 `src/sample.ts` を作成 (空ファイル: `// sample module` のみ)
- [x] 1.5 `.coderabbit.yaml` を作成
- [x] 1.6 `.github/workflows/fix-review.yml` を作成
  - techbook-ledger のワークフローを参照し、ドラフトと照合・調整
  - レビュアーフィルタ (`coderabbitai[bot]`)
  - concurrency group (PR 番号ごと、cancel-in-progress: true)
  - 権限定義 (contents:write, pull-requests:write, issues:write)
  - カウント追跡 (PR body HTML コメント)
  - リトライ上限チェック (3回)

## Phase 2: GitHub リポジトリセットアップ

- [x] 2.1 リポジトリ作成 (`gh repo create aloekun/auto-review-fix-sandbox --private --clone`)
- [x] 2.2 jj colocated 初期化 (`jj git init --colocate`)
- [x] 2.3 Phase 1 のファイルを main にプッシュ
- [x] 2.4 GitHub Secret 設定 (`ANTHROPIC_API_KEY`)
- [x] 2.5 Label 作成 (`needs-human-review`)
- [x] 2.6 Code Rabbit インストール (GitHub App)

## Phase 3: 基本動作検証

- [x] 3.1 テスト用ブランチ作成 (`jj new main`)
- [x] 3.2 `src/sample.ts` に問題コードを追加
- [x] 3.3 ブランチをプッシュしてPR作成
- [x] 3.4 Code Rabbit のレビューが発火することを確認
- [x] 3.5 レビュー状態が `CHANGES_REQUESTED` であることを確認
- [x] 3.6 Auto Fix Review ワークフローが発火することを確認
- [ ] 3.7 Claude Code Action が修正コミットをプッシュすることを確認 (**未達: パーミッション拒否**)
- [x] 3.8 PR body に `<!-- claude-autofix-count:1 -->` が記録されることを確認

## Phase 4: ループ上限検証

- [ ] 4.1 PR body の `claude-autofix-count` を `2` に手動設定
- [ ] 4.2 次の修正サイクルでカウントが 3 に到達することを確認
- [ ] 4.3 `needs-human-review` ラベルが付与されることを確認
- [ ] 4.4 上限到達コメントが投稿されることを確認

## Phase 5: クリーンアップ・振り返り

- [ ] 5.1 テスト PR をクローズ
- [ ] 5.2 検証結果を記録 (成功/失敗、問題点、改善案)
- [ ] 5.3 横展開に向けた知見を整理

## Phase 6: AI自動修正品質改善

### 背景

PR #20・#21でCodeRabbitとのやり取りが6往復以上に膨らんだ。根本原因は3つ:
- context不足（diffのみ、ファイル全体・呼び出し元なし）
- `Fix ONLY` 制約による副作用チェックなし
- verification step なし（修正後に自己検証しない）

### Phase 6.1: プロンプト改善（`prompt_builder.py`）

- [x] 6.1.1 変更対象ファイルの**全体内容**をプロンプトに追加
  - diffだけでなく、レビューで言及されたファイルを丸ごと渡す
  - `context_builder.py`: `extract_changed_files()` / `get_file_contents()`
- [x] 6.1.2 **Call graph context** を追加
  - 修正対象の関数を呼び出しているコードを grep して渡す
  - `context_builder.py`: `extract_function_names_from_diff()` / `get_call_graph_context()`
- [x] 6.1.3 **Previous fix context** を追加
  - 前回の自動修正diffがあればプロンプトに含める
  - `context_builder.py`: `get_previous_fix_diff()`
- [x] 6.1.4 `Fix ONLY` 制約を緩和し **Fix plan + Self-verification** に変更
  - Step 1: 修正計画を説明させる
  - Step 2: 実装する
  - Step 3: 修正後にファイル全体を再読し「フォールバック値が後続ロジックを壊さないか」「新たなエッジケースを導入していないか」を検証させてからcommitさせる
  - Step 4: 全項目クリア後に commit & push

### Phase 6.2: Patch Proposal Mode（`orchestrator.py` 構造変更）

*Phase 6.1 の効果測定後に `config.yaml` の `patch_proposal_mode: true` で有効化する。*

- [x] 6.2.1 Run 1: パッチ生成のみ（commitしない）
  - `prompt_builder.py`: `build_patch_proposal_prompt()` — 変更後に `git diff > proposed.patch` して停止
- [x] 6.2.2 Run 2: パッチ検証 → 問題があれば修正 → commit
  - `prompt_builder.py`: `build_patch_verification_prompt()` — `git diff` 再読 → 検証チェックリスト → commit
- [x] 6.2.3 orchestrator.py・claude_runner.py の対応する変更
  - `orchestrator.py`: `_process_pr_patch_mode()` で2段階実行、`_finalize_run()` で共通後処理
  - `config.yaml`: `patch_proposal_mode: false`（デフォルト off）

### Phase 6.3: E2Eテスト整備（PR #27）

- [x] 6.3.1 テスト用 GitHub リポジトリ作成（`aloekun/test-review-fix-sandbox`）と `sample.py` 初期プッシュ
- [x] 6.3.2 `conftest.py` を拡張（`.env.e2e` 自動読み込み、`e2e_workspace` / `e2e_test_pr` / `e2e_gh_client` フィクスチャ）
  - `_GHClientWithSyntheticReviews`: GitHub の自己レビュー制限を回避する synthetic review 注入
  - `_rmtree_robust()`: Windows の read-only `.git` ファイル対応の安全削除
  - クローン先を `tmp/e2e/workspace-<uuid>/` に変更（プロジェクトローカル）
- [x] 6.3.3 `test_full_flow.py` 実装（実 Orchestrator + real claude CLI によるフルフロー）
  - PR HEAD SHA の変化 + "AI Auto Fix Report" コメントを検証
- [x] 6.3.4 `package.json` に `py-test:e2e` スクリプト追加
- [x] 6.3.5 `.gitignore` に `ai-review-fixer/.env.e2e` 追加
- [x] 6.3.6 `docs/e2e-setup.md` 作成（セットアップ手順・トラブルシューティング）

## Phase 7: jj-start-change dirty tree guard

**前提条件: Phase 6 (テスト整備 PR #25) のマージ後に着手**

### 背景

Phase 6 のテスト整備作業中に、旧セッションの作業コピー（編集途中ファイルを含む）の上に
そのまま新しい作業を重ねてしまった。その結果、push 時に第4層 guard（`jj-push-safe.sh`）に
弾かれた後、`jj rebase -d main@origin` で事後リベースして回避する経路が使われた。

### 問題の構造（dirty working tree problem）

```text
旧 change（前セッション残留ファイルあり）
    │
    └── 新セッション: そのまま編集
              ↓
         push → 第4層 guard に弾かれる
              ↓
         jj rebase で履歴だけ修正 ← 抜け穴
              ↓
         push 通過（履歴だけ新しい、内容は汚染済み）
```

### なぜ jj rebase 禁止は不採用か

Jujutsu の核心機能は「履歴を後から自由に書き換える」こと。
rebase 禁止は jj の強みを潰す上に、将来の PR 修正・stack 修正・review fix で
rebase が必須になる場面がある。

### 修正方針: 入口でのチェック（Layer 5）

問題の根本は「作業開始時に working tree が汚れている」こと。
**`jj-start-change` スクリプトに dirty tree guard を追加する。**

```text
Layer 1: git 直接実行ブロック           (validate-command.exe)
Layer 2: jj new main ブロック           (validate-command.exe)
Layer 3: jj edit main ブロック          (validate-command.exe)
Layer 4: push 前 ancestor guard        (jj-push-safe.sh)
Layer 5: start-change dirty tree guard  (jj-start-change.sh) ← 追加
```

`jj-start-change` 改良版の骨子:

```bash
#!/usr/bin/env bash
set -e

# Working copy に未記録の変更があれば中断する（description の有無に関係なくチェック）
changes=$(jj diff --stat 2>/dev/null || true)
if [ -n "$changes" ]; then
  echo "ERROR: Working copy is dirty (uncommitted changes remain)."
  echo "前セッションのファイルが残っています。"
  echo ""
  echo "解決方法:"
  echo "  jj abandon @      # 変更を破棄して前の change に戻る"
  echo "  jj restore        # ファイルを元に戻す"
  exit 1
fi

jj git fetch
jj new main@origin
```

### 将来の発展: jj workspace

より根本的な解決策として `jj workspace add` による完全分離がある。
1タスク = 1 workspace にすることで旧ファイルの物理的混入が起きなくなる。
現行 workflow との統合変更が必要なため、別タスクとして検討する。

### 実装タスク

- [x] 7.1 `jj-start-change` スクリプトを新規作成（`.claude/scripts/jj-start-change.sh`）
- [x] 7.2 dirty tree 検出ロジックの実装とエラーメッセージ整備
- [x] 7.3 `package.json` の `jj-start-change` スクリプトを新ファイルに向ける
- [ ] 7.4 動作確認（dirty ケース: `pnpm jj-start-change` がエラーで停止することを確認。clean ケース: 次タスク開始時に検証）
- [x] 7.5 `ai/rules/VCS_JUJUTSU.md` の作業開始手順を更新（ガード層構成表・エラー時の対処法を追加）
