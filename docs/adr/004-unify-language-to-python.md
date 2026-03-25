# ADR 004: プログラミング言語を Python に統一

## ステータス

採択済み (2026-03-25)

## コンテキスト

### 言語混在の経緯

プロジェクト初期（Phase 1〜4）では、Code Rabbit のレビュー対象として TypeScript のサンプルコード（`src/sample.ts`）を使用していた。CI にも TypeScript 用の typecheck ジョブ（`tsc --noEmit`）を設けていた。

その後 Phase 5 以降で AI エージェント（orchestrator）を Python で実装し、lint（ruff）・型チェック（mypy）・テスト（pytest）のパイプラインを Python 向けに整備した。

結果として、以下の構成が混在していた。

| 言語 | 用途 | ファイル |
|------|------|---------|
| TypeScript | レビューテスト用サンプルコード | `src/sample.ts`, `tsconfig.json` |
| Python | AI エージェント本体、スクリプト | `ai-review-fixer/`, `scripts/` |

### 発生した問題

1. **CI の typecheck ジョブが常時失敗**: `src/sample.ts` は意図的にエラーを含むテスト素材だったが、テスト完了後も残存し CI を壊し続けた
2. **hooks が TypeScript を未カバー**: `hooks-config.toml` の PostToolUse / Stop フックは Python のみを対象としており、TypeScript の型エラーはローカルで検知できなかった
3. **ツールチェーンの二重管理**: `tsc` と `mypy`、`npm` と `pip` が共存し、保守コストが増大

### テスト素材の役割終了

`src/sample.ts` は「Code Rabbit がレビュー → Claude が自動修正」のシナリオテスト用に作成された。テストは Phase 4 で完了しており、サンプルコード自体は不要になっていた。

## 決定

**プロジェクトのプログラミング言語を Python に統一する。TypeScript 関連のファイル・設定・CI ジョブを削除する。**

### 変更内容

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| サンプルコード | `src/sample.ts` (TypeScript) | 削除（テスト完了済み） |
| TypeScript 設定 | `tsconfig.json` | 削除 |
| `pnpm typecheck` | `tsc --noEmit` | `mypy --config-file ai-review-fixer/pyproject.toml ai-review-fixer/` |
| `pnpm py-lint` | `ruff check ... && mypy ...` | `ruff check ...`（mypy を分離） |
| CI typecheck ジョブ | TypeScript 用 (`tsc`) | 削除（Python 用 mypy は `python-lint-and-test` ジョブ内に存在） |
| Stop フック | `py-lint`, `py-test`, `py-test:e2e` | `py-lint`, `typecheck`, `py-test`, `py-test:e2e` |
| エージェント定義 | `type-check-fixer.md` (TypeScript 前提) | Python (mypy) 向けに書き換え |

### lint と typecheck の責務分離

従来 `py-lint` は `ruff check && mypy` のチェーンだったが、以下の理由で分離した。

- **ruff**: linter（スタイル、未使用 import、コード品質）
- **mypy**: 静的型チェック（型注釈の整合性検証のみ）

mypy は linter の役割を持たないため、`typecheck` として独立させることで責務が明確になる。

## トレードオフ

### メリット

- **CI の安定化**: TypeScript 起因の失敗がなくなる
- **ツールチェーンの単純化**: Python 系ツール（ruff, mypy, pytest）に一本化
- **hooks の完全カバー**: Stop フックで lint・型チェック・テストが漏れなく実行される
- **責務の明確化**: lint（ruff）と型チェック（mypy）の分離

### デメリット

- 将来 TypeScript が必要になった場合、設定の再構築が必要
- 既存ドキュメント（`docs/design.md` 等）に TypeScript 前提の記述が歴史的記録として残る

## 既存ドキュメントの扱い

`docs/design.md`、`docs/tasks-completed.md`、`tasks/todo.md` に含まれる TypeScript 前提の記述は、Phase 1〜4 の歴史的記録として変更しない。本 ADR が方針転換の根拠となる。
