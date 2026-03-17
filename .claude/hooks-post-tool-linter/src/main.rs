//! PostToolUse リンターフック
//!
//! Write/Edit ツール使用後に Python ファイルに対して
//! Ruff (lint --fix → format → lint) を実行し、
//! 残りの診断結果を additionalContext として Claude にフィードバックします。

use serde::{Deserialize, Serialize};
use std::io::{self, Read};
use std::path::Path;
use std::process::Command;

// --- 入力 ---

#[derive(Deserialize)]
struct HookInput {
    tool_input: Option<ToolInput>,
}

#[derive(Deserialize)]
struct ToolInput {
    file_path: Option<String>,
    path: Option<String>,
}

// --- 出力 ---

#[derive(Serialize)]
struct HookOutput {
    #[serde(rename = "hookSpecificOutput")]
    hook_specific_output: HookSpecificOutput,
}

#[derive(Serialize)]
struct HookSpecificOutput {
    #[serde(rename = "hookEventName")]
    hook_event_name: String,
    #[serde(rename = "additionalContext")]
    additional_context: String,
}

/// 対象の拡張子か判定
fn is_target_extension(file: &str) -> bool {
    matches!(
        Path::new(file)
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| e.to_lowercase())
            .as_deref(),
        Some("py")
    )
}

/// コマンドを直接実行し、(stdout, stderr) を返す
/// シェル（cmd /c）を経由しないため、ファイルパス中のメタ文字によるインジェクションを防止する
fn run_command(program: &str, args: &[&str]) -> (String, String) {
    match Command::new(program).args(args).output() {
        Ok(o) => (
            String::from_utf8_lossy(&o.stdout).to_string(),
            String::from_utf8_lossy(&o.stderr).to_string(),
        ),
        Err(e) => (String::new(), format!("Failed to run {}: {}", program, e)),
    }
}

/// フィードバック JSON を stdout に出力
fn emit_feedback(message: &str) {
    let output = HookOutput {
        hook_specific_output: HookSpecificOutput {
            hook_event_name: "PostToolUse".to_string(),
            additional_context: message.to_string(),
        },
    };
    if let Ok(json) = serde_json::to_string(&output) {
        println!("{}", json);
    }
}

fn main() {
    // stdin を消費（フックの仕様上必須）
    let mut input = String::new();
    let _ = io::stdin().read_to_string(&mut input);

    // JSON からファイルパスを取得
    let hook_input: HookInput = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(_) => return, // パース失敗 → 何もせず終了
    };

    let file = hook_input
        .tool_input
        .and_then(|t| t.file_path.filter(|s| !s.is_empty()).or(t.path))
        .unwrap_or_default();

    if file.is_empty() {
        return;
    }

    // 対象拡張子でなければスキップ
    if !is_target_extension(&file) {
        return;
    }

    // 1. ruff check --fix で自動修正 (失敗しても続行)
    let _ = run_command("ruff", &["check", "--fix", &file]);

    // 2. ruff format でフォーマット (失敗しても続行)
    let _ = run_command("ruff", &["format", &file]);

    // 3. ruff check で残りの診断を取得（stdout + stderr を結合）
    let (stdout, stderr) = run_command("ruff", &["check", &file]);
    let combined = if stdout.ends_with('\n') || stdout.is_empty() {
        format!("{}{}", stdout, stderr)
    } else {
        format!("{}\n{}", stdout, stderr)
    };

    // 診断結果があればフィードバック (先頭20行に制限)
    let trimmed: String = combined.lines().take(20).collect::<Vec<_>>().join("\n");
    if !trimmed.trim().is_empty() {
        emit_feedback(&trimmed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn py_is_target() {
        assert!(is_target_extension("ai-review-fixer/main.py"));
    }

    #[test]
    fn py_windows_path_is_target() {
        assert!(is_target_extension(r"e:\work\project\src\app.py"));
    }

    #[test]
    fn py_case_insensitive() {
        assert!(is_target_extension("file.PY"));
        assert!(is_target_extension("file.Py"));
    }

    #[test]
    fn ts_is_not_target() {
        assert!(!is_target_extension("src/app.ts"));
    }

    #[test]
    fn js_is_not_target() {
        assert!(!is_target_extension("index.js"));
    }

    #[test]
    fn rs_is_not_target() {
        assert!(!is_target_extension("main.rs"));
    }

    #[test]
    fn json_is_not_target() {
        assert!(!is_target_extension("package.json"));
    }

    #[test]
    fn no_extension_is_not_target() {
        assert!(!is_target_extension("Makefile"));
    }

    #[test]
    fn empty_is_not_target() {
        assert!(!is_target_extension(""));
    }

    #[test]
    fn feedback_json_has_correct_structure() {
        let output = HookOutput {
            hook_specific_output: HookSpecificOutput {
                hook_event_name: "PostToolUse".to_string(),
                additional_context: "test diagnostic".to_string(),
            },
        };
        let json = serde_json::to_string(&output).unwrap();
        assert!(json.contains(r#""hookEventName":"PostToolUse""#));
        assert!(json.contains(r#""additionalContext":"test diagnostic""#));
    }
}
