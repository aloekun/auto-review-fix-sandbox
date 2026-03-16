# ADR 002: ブランチ起点をリモートブランチ（@origin）に統一

## ステータス

採択済み (2026-03-15)

## コンテキスト

### 旧規約（GIT_WORKFLOW.md）

従来は以下の運用を行っていた。

- `develop` ブランチを日常開発のベースとし、feature ブランチは `develop` から切る
- PR は `develop` に向けて作成する（リリース時に `develop` → `main` をマージ）
- ブランチ作成時は `git checkout develop && git pull origin develop` でローカルを最新化

### 発生した問題

ローカルブランチをベースにする運用で、以下の問題が繰り返し発生した。

#### 1. 先祖返り（regression）

ローカルの `main` や `develop` がリモートより古い状態のまま新しいブランチを切ると、
既にマージ済みの変更が含まれないブランチが作られる。
このブランチから PR を出すと、マージ時にリモートの最新変更が巻き戻される（先祖返り）。

#### 2. コンフリクトの多発

ローカルブランチが古い状態で作業を続けると、リモートとの差分が大きくなり、
PR 作成時やマージ時に不必要なコンフリクトが発生する。

#### 3. マージフローの複雑化

`develop` → `main` の 2 段階マージにより、以下の混乱が生じた。

- `develop` と `main` の同期忘れ
- hotfix を `main` に入れた後 `develop` への反映漏れ
- どのブランチが「正」なのか不明確になる場面

### `develop` ブランチの不要性

本プロジェクトは個人開発のサンドボックスであり、
リリースブランチを分離する必要性が低い。
`main` 一本で十分にワークフローが回る。

## 決定

**ブランチの作成元・PR の作成先をリモートブランチ（`@origin`）に統一する。
`develop` ブランチは廃止する。**

### 新しいブランチ規約

| 項目 | 旧規約 | 新規約 |
|------|--------|--------|
| ベースブランチ | `develop`（ローカル） | `main@origin`（リモート） |
| ブランチ作成 | `git checkout develop && git pull` | `jj new main@origin`（`pnpm jj-start-change`） |
| PR の向き先 | `develop` | `main` |
| Stacked PR のベース | - | `[branch-name]@origin`（push 済みブランチ） |
| `develop` ブランチ | 必須 | 廃止 |

### ブランチ命名規則

| type | 用途 |
|------|------|
| `feat/説明` | 新機能・ワークフロー変更 |
| `fix/説明` | バグ修正 |
| `refactor/説明` | リファクタリング |
| `docs/説明` | ドキュメント変更 |
| `test/説明` | テスト・レビュー動作テスト |
| `chore/説明` | ビルド・CI・依存関係 |

**簡略化した点:**
- Issue 番号はブランチ名に必須としない（個人開発のため）
- `hotfix/*` は廃止（`main` 直接ベースのため `fix/*` で統一）

### コミットメッセージ

[Conventional Commits](https://www.conventionalcommits.org/) に準拠する（変更なし）。

```
<type>(<scope>): <subject>
```

使用可能な type: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `revert`

### ガード機構による強制

ローカルブランチベースの操作を防ぐため、以下のガード層を設けている。

| ガード | 内容 |
|--------|------|
| `validate-command.exe` | `git` コマンド直接実行をブロック |
| `validate-command.exe` | `jj new main`（ローカル main）をブロック |
| `validate-command.exe` | `jj edit main`（ローカル main 編集）をブロック |
| `jj-push-safe.sh` | push 前にリモートブランチが祖先かチェック |
| `jj-start-change.sh` | 作業開始前に working copy が clean かチェック |

これらのガードにより、「ローカルの古い main から誤ってブランチを切る」操作が
構造的に不可能になっている。

## トレードオフ

### メリット

- **先祖返りの防止**: 常にリモート最新をベースにするため、古い状態からの分岐が起きない
- **コンフリクトの削減**: リモート最新との差分が最小化される
- **ワークフローの簡素化**: `develop` 廃止により分岐・マージの経路が単純になる
- **ガード機構との親和性**: `jj-start-change` が fetch → `jj new main@origin` を一括実行するため、手順の漏れが起きない

### デメリット

- ネットワーク接続が必須（`jj git fetch` が必要）
- ローカルのみでの実験的ブランチ作成ができない（ガードをバイパスする必要がある）
- チーム開発に移行する場合、`develop` ブランチの再導入を検討する可能性がある

## 影響範囲

| ファイル | 変更内容 |
|---------|---------|
| `README.md` | ブランチ規約を `main@origin` ベースに更新済み |
| `CLAUDE.md` | 同上 |
| `ai/rules/VCS_JUJUTSU.md` | `pnpm jj-start-change` ワークフローを記載済み |
| `ai/rules/GIT_WORKFLOW.md` | 本 ADR に合わせて更新（`develop` 廃止を反映） |
