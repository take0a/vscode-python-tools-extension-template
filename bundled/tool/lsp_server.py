# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
import sys
import sysconfig
import traceback
from typing import Any, Optional, Sequence


# **********************************************************
# バンドルされたライブラリをインポートする前に、sys.path を更新します。
# **********************************************************
def update_sys_path(path_to_add: str, strategy: str) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        if strategy == "useBundled":
            sys.path.insert(0, path_to_add)
        elif strategy == "fromEnvironment":
            sys.path.append(path_to_add)


# LSP ライブラリやその他のバンドル ライブラリをインポートできることを確認します。
update_sys_path(
    os.fspath(pathlib.Path(__file__).parent.parent / "libs"),
    os.getenv("LS_IMPORT_STRATEGY", "useBundled"),
)

# **********************************************************
# 言語サーバーに必要なインポートはこれより下になります。
# **********************************************************
# pylint: disable=wrong-import-position,import-error
import lsp_jsonrpc as jsonrpc
import lsp_utils as utils
import lsprotocol.types as lsp
from pygls import server, uris, workspace

WORKSPACE_SETTINGS = {}
GLOBAL_SETTINGS = {}
RUNNER = pathlib.Path(__file__).parent / "lsp_runner.py"

MAX_WORKERS = 5

LSP_SERVER = server.LanguageServer(
    name="VSCode Python Extension", version="2022.0.0-dev", max_workers=MAX_WORKERS
)


# **********************************************************
# ツール固有のコードはこれ以下に記述します。
# **********************************************************

# Reference:
#  LS Protocol:
#  https://microsoft.github.io/language-server-protocol/specifications/specification-3-16/
#
#  Sample implementations:
#  Pylint: https://github.com/microsoft/vscode-pylint/blob/main/bundled/tool
#  Black: https://github.com/microsoft/vscode-black-formatter/blob/main/bundled/tool
#  isort: https://github.com/microsoft/vscode-isort/blob/main/bundled/tool

TOOL_MODULE = "pyext"

TOOL_DISPLAY = "VSCode Python Extension"

TOOL_ARGS = []  # default arguments always passed to your tool.


# **********************************************************
# リンティング機能はここから始まります
# **********************************************************

# フル機能のリンター拡張機能については `pylint` 実装を参照してください。
#  Pylint: https://github.com/microsoft/vscode-pylint/blob/main/bundled/tool


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    """textDocument/didOpen リクエストの LSP ハンドラー。"""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """textDocument/didSave リクエストの LSP ハンドラー。"""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.publish_diagnostics(document.uri, diagnostics)


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """textDocument/didClose リクエストの LSP ハンドラー。"""
    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    # このファイルのエントリをクリアするために空の診断を公開します。
    LSP_SERVER.publish_diagnostics(document.uri, [])


def _linting_helper(document: workspace.Document) -> list[lsp.Diagnostic]:
    # ツールが標準入力経由でのファイル内容の受け渡しをサポートしているかどうかを確認してください。
    # 変更時のリンティングをサポートする場合、ツールが効果的に機能するには、
    # 標準入力経由のリンティングをサポートしている必要があります。
    # プロジェクトの必要に応じて、_run_tool_on_document 関数と _run_tool 関数を読み、
    # 更新してください。
    result = _run_tool_on_document(document)
    return _parse_output_using_regex(result.stdout) if result.stdout else []


# リンターの出力がJSONなどの既知の形式である場合は、それに応じて解析してください。
# ただし、正規表現を使用して出力を解析する必要がある場合は、以下のヘルパーをご利用ください。
# flake8の例:
# flake8で以下のフォーマット引数を使用すると、以下の正規表現を使用して解析できます。
# TOOL_ARGS += ["--format='%(row)d,%(col)d,%(code).1s,%(code)s:%(text)s'"]
# DIAGNOSTIC_RE =
#    r"(?P<line>\d+),(?P<column>-?\d+),(?P<type>\w+),(?P<code>\w+\d+):(?P<message>[^\r\n]*)"
DIAGNOSTIC_RE = re.compile(r"")


def _parse_output_using_regex(content: str) -> list[lsp.Diagnostic]:
    lines: list[str] = content.splitlines()
    diagnostics: list[lsp.Diagnostic] = []

    line_at_1 = True
    column_at_1 = True

    line_offset = 1 if line_at_1 else 0
    col_offset = 1 if column_at_1 else 0
    for line in lines:
        if line.startswith("'") and line.endswith("'"):
            line = line[1:-1]
        match = DIAGNOSTIC_RE.match(line)
        if match:
            data = match.groupdict()
            position = lsp.Position(
                line=max([int(data["line"]) - line_offset, 0]),
                character=int(data["column"]) - col_offset,
            )
            diagnostic = lsp.Diagnostic(
                range=lsp.Range(
                    start=position,
                    end=position,
                ),
                message=data.get("message"),
                severity=_get_severity(data["code"], data["type"]),
                code=data["code"],
                source=TOOL_MODULE,
            )
            diagnostics.append(diagnostic)

    return diagnostics


# ユーザーが設定可能な方法でリンターの特定の重大度を設定したい場合は、
# 私たちのチームが実装した `pylint` 拡張機能をご覧ください。
# Pylint: https://github.com/microsoft/vscode-pylint
# package.json の設定からサーバーへの重大度フローに従ってください。
def _get_severity(*_codes: list[str]) -> lsp.DiagnosticSeverity:
    return lsp.DiagnosticSeverity.Warning


# **********************************************************
# リンティング機能はここで終了です
# **********************************************************

# **********************************************************
# 書式設定機能はここから始まります
# **********************************************************
#  Sample implementations:
#  Black: https://github.com/microsoft/vscode-black-formatter/blob/main/bundled/tool


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_FORMATTING)
def formatting(params: lsp.DocumentFormattingParams) -> list[lsp.TextEdit] | None:
    """textDocument/formatting 要求の LSP ハンドラー。"""
    # ツールがフォーマッタである場合、このハンドラを使用して保存時にフォーマット処理をサポートできます。
    # フォーマットされた結果を返すには、lsp.TextEditオブジェクトの配列を返す必要があります。

    document = LSP_SERVER.workspace.get_document(params.text_document.uri)
    edits = _formatting_helper(document)
    if edits:
        return edits

    # 注意: [] 配列を指定すると、VS Code はファイルのすべての内容をクリアします。
    # ファイルに変更がないことを示すには、None を返します。
    return None


def _formatting_helper(document: workspace.Document) -> list[lsp.TextEdit] | None:
    # 保存時のフォーマットをサポートするには、使用するフォーマッタが
    # 標準入力経由のフォーマットをサポートしている必要があります。
    # フォーマッタの必要に応じて、読み取り、update_run_tool_on_document 
    # および _run_tool 関数を実行してください。
    result = _run_tool_on_document(document, use_stdin=True)
    if result.stdout:
        new_source = _match_line_endings(document, result.stdout)
        return [
            lsp.TextEdit(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=len(document.lines), character=0),
                ),
                new_text=new_source,
            )
        ]
    return None


def _get_line_endings(lines: list[str]) -> str:
    """テキストで使用されている行末文字列を返します。"""
    try:
        if lines[0][-2:] == "\r\n":
            return "\r\n"
        return "\n"
    except Exception:  # pylint: disable=broad-except
        return None


def _match_line_endings(document: workspace.Document, text: str) -> str:
    """編集されたテキストの行末がドキュメントの行末と一致することを確認します。"""
    expected = _get_line_endings(document.source.splitlines(keepends=True))
    actual = _get_line_endings(text.splitlines(keepends=True))
    if actual == expected or actual is None or expected is None:
        return text
    return text.replace(actual, expected)


# **********************************************************
# 書式設定機能はここで終了です
# **********************************************************


# **********************************************************
# 必要な言語サーバーの初期化および終了ハンドラー。
# **********************************************************
@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams) -> None:
    """初期化要求の LSP ハンドラー。"""
    log_to_output(f"CWD Server: {os.getcwd()}")

    paths = "\r\n   ".join(sys.path)
    log_to_output(f"sys.path used to run Server:\r\n   {paths}")

    GLOBAL_SETTINGS.update(**params.initialization_options.get("globalSettings", {}))

    settings = params.initialization_options["settings"]
    _update_workspace_settings(settings)
    log_to_output(
        f"Settings used to run Server:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )
    log_to_output(
        f"Global settings:\r\n{json.dumps(GLOBAL_SETTINGS, indent=4, ensure_ascii=False)}\r\n"
    )


@LSP_SERVER.feature(lsp.EXIT)
def on_exit(_params: Optional[Any] = None) -> None:
    """終了時にクリーンアップを処理します。"""
    jsonrpc.shutdown_json_rpc()


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None) -> None:
    """シャットダウン時にクリーンアップを処理します。"""
    jsonrpc.shutdown_json_rpc()


def _get_global_defaults():
    return {
        "path": GLOBAL_SETTINGS.get("path", []),
        "interpreter": GLOBAL_SETTINGS.get("interpreter", [sys.executable]),
        "args": GLOBAL_SETTINGS.get("args", []),
        "importStrategy": GLOBAL_SETTINGS.get("importStrategy", "useBundled"),
        "showNotifications": GLOBAL_SETTINGS.get("showNotifications", "off"),
    }


def _update_workspace_settings(settings):
    if not settings:
        key = os.getcwd()
        WORKSPACE_SETTINGS[key] = {
            "cwd": key,
            "workspaceFS": key,
            "workspace": uris.from_fs_path(key),
            **_get_global_defaults(),
        }
        return

    for setting in settings:
        key = uris.to_fs_path(setting["workspace"])
        WORKSPACE_SETTINGS[key] = {
            "cwd": key,
            **setting,
            "workspaceFS": key,
        }


def _get_settings_by_path(file_path: pathlib.Path):
    workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

    while file_path != file_path.parent:
        str_file_path = str(file_path)
        if str_file_path in workspaces:
            return WORKSPACE_SETTINGS[str_file_path]
        file_path = file_path.parent

    setting_values = list(WORKSPACE_SETTINGS.values())
    return setting_values[0]


def _get_document_key(document: workspace.Document):
    if WORKSPACE_SETTINGS:
        document_workspace = pathlib.Path(document.path)
        workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

        # 指定されたファイルのワークスペース設定を見つけます。
        while document_workspace != document_workspace.parent:
            if str(document_workspace) in workspaces:
                return str(document_workspace)
            document_workspace = document_workspace.parent

    return None


def _get_settings_by_document(document: workspace.Document | None):
    if document is None or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]

    key = _get_document_key(document)
    if key is None:
        # これはワークスペース以外のファイルであるか、ワークスペースがありません。
        key = os.fspath(pathlib.Path(document.path).parent)
        return {
            "cwd": key,
            "workspaceFS": key,
            "workspace": uris.from_fs_path(key),
            **_get_global_defaults(),
        }

    return WORKSPACE_SETTINGS[str(key)]


# *****************************************************
# 内部実行 API
# *****************************************************
def _run_tool_on_document(
    document: workspace.Document,
    use_stdin: bool = False,
    extra_args: Optional[Sequence[str]] = None,
) -> utils.RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    if extra_args is None:
        extra_args = []
    if str(document.uri).startswith("vscode-notebook-cell"):
        # ノートブックのセルをスキップするかどうかを決定します。
        # ノートブックのセルをスキップ
        return None

    if utils.is_stdlib_file(document.path):
        # 標準ライブラリファイルをスキップするかどうかを決定します。
        # 標準ライブラリの Python ファイルをスキップします。
        return None

    # 誤ってグローバル設定を更新しないように、ここでディープコピーを実行します。
    settings = copy.deepcopy(_get_settings_by_document(document))

    code_workspace = settings["workspaceFS"]
    cwd = settings["cwd"]

    use_path = False
    use_rpc = False
    if settings["path"]:
        # 「path」設定が何よりも優先されます。
        use_path = True
        argv = settings["path"]
    elif settings["interpreter"] and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # 異なるインタープリターが設定されている場合は、そのインタープリターで
        # 実行されているサブプロセスに対して JSON-RPC を使用します。
        argv = [TOOL_MODULE]
        use_rpc = True
    else:
        # インタープリターがこのプロセスを実行しているインタープリターと同じ場合は、
        # モジュールとして実行されます。
        argv = [TOOL_MODULE]

    argv += TOOL_ARGS + settings["args"] + extra_args

    if use_stdin:
        # ドキュメントの内容をツールに標準入力経由で提供するために、
        # 適切な引数を渡すようにこれらを更新してください。
        # 例えば、pylint の場合、標準入力への引数は以下のようになります。
        #   pylint --from-stdin <path>
        # ここで、`--from-stdin` パスは、pylint が処理対象のファイルの内容を
        # 判断するために使用されます。例えば、除外ルールを適用するなどです。
        # 引数は以下のようになります。
        #   argv += ["--from-stdin", document.path]
        # お使いのツールが標準入力経由でコンテンツをどのように処理するかを確認してください。
        # 標準入力がサポートされていない場合は、use_stdin を False に設定するか、
        # パスを指定するなど、ツールに適した方法を使用してください。
        argv += []
    else:
        argv += [document.path]

    if use_path:
        # このモードは実行可能ファイルを実行するときに使用されます。
        log_to_output(" ".join(argv))
        log_to_output(f"CWD Server: {cwd}")
        result = utils.run_path(
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=document.source.replace("\r\n", "\n"),
        )
        if result.stderr:
            log_to_output(result.stderr)
    elif use_rpc:
        # このモードは、このサーバーを実行しているインタープリターが、
        # このサーバーの実行に使用されているインタープリターと異なる場合に使用されます。
        log_to_output(" ".join(settings["interpreter"] + ["-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")

        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=document.source,
        )
        if result.exception:
            log_error(result.exception)
            result = utils.RunResult(result.stdout, result.stderr)
        elif result.stderr:
            log_to_output(result.stderr)
    else:
        # このモードでは、ツールは言語サーバーと同じプロセス内のモジュールとして実行されます。
        log_to_output(" ".join([sys.executable, "-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")
        # これは、ツールが sys.path を変更し、次回このシナリオでは機能しない可能性がある場合に、
        # sys.path を保持するために必要です。
        with utils.substitute_attr(sys, "path", sys.path[:]):
            try:
                # `utils.run_module` は `python -m pyext` の実行と同等です。
                # ツールがプログラムAPIをサポートしている場合は、以下の関数を
                # ツールのコードに置き換えてください。
                # 作業ディレクトリの変更やIOストリームの管理などを処理する 
                # `utils.run_api` ヘルパーも使用できます。
                # また、`lsp_runner.py` の `_run_tool` 関数と 
                # `utils.run_module` も更新してください。
                result = utils.run_module(
                    module=TOOL_MODULE,
                    argv=argv,
                    use_stdin=use_stdin,
                    cwd=cwd,
                    source=document.source,
                )
            except Exception:
                log_error(traceback.format_exc(chain=True))
                raise
        if result.stderr:
            log_to_output(result.stderr)

    log_to_output(f"{document.uri} :\r\n{result.stdout}")
    return result


def _run_tool(extra_args: Sequence[str]) -> utils.RunResult:
    """Runs tool."""
    # 誤ってグローバル設定を更新しないように、ここでディープコピーを実行します。
    settings = copy.deepcopy(_get_settings_by_document(None))

    code_workspace = settings["workspaceFS"]
    cwd = settings["workspaceFS"]

    use_path = False
    use_rpc = False
    if len(settings["path"]) > 0:
        # 「path」設定が何よりも優先されます。
        use_path = True
        argv = settings["path"]
    elif len(settings["interpreter"]) > 0 and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # 異なるインタープリターが設定されている場合は、そのインタープリターで
        # 実行されているサブプロセスに対して JSON-RPC を使用します。
        argv = [TOOL_MODULE]
        use_rpc = True
    else:
        # インタープリターがこのプロセスを実行しているインタープリターと同じ場合は、
        # モジュールとして実行されます。
        argv = [TOOL_MODULE]

    argv += extra_args

    if use_path:
        # このモードは実行可能ファイルを実行するときに使用されます。
        log_to_output(" ".join(argv))
        log_to_output(f"CWD Server: {cwd}")
        result = utils.run_path(argv=argv, use_stdin=True, cwd=cwd)
        if result.stderr:
            log_to_output(result.stderr)
    elif use_rpc:
        # このモードは、このサーバーを実行しているインタープリターが、
        # このサーバーの実行に使用されているインタープリターと異なる場合に使用されます。
        log_to_output(" ".join(settings["interpreter"] + ["-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")
        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=True,
            cwd=cwd,
        )
        if result.exception:
            log_error(result.exception)
            result = utils.RunResult(result.stdout, result.stderr)
        elif result.stderr:
            log_to_output(result.stderr)
    else:
        # このモードでは、ツールは言語サーバーと同じプロセス内のモジュールとして実行されます。
        log_to_output(" ".join([sys.executable, "-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")
        # これは、ツールが sys.path を変更し、次回このシナリオでは機能しない
        # 可能性がある場合に、sys.path を保持するために必要です。
        with utils.substitute_attr(sys, "path", sys.path[:]):
            try:
                # `utils.run_module` は `python -m pyext` の実行と同等です。
                # ツールがプログラム API をサポートしている場合は、
                # 以下の関数をツールのコードに置き換えてください。
                # 作業ディレクトリの変更や IO ストリームの管理などを処理する 
                # `utils.run_api` ヘルパーも使用できます。
                # また、`lsp_runner.py` の `_run_tool_on_document` 関数と 
                # `utils.run_module` も更新してください。
                result = utils.run_module(
                    module=TOOL_MODULE, argv=argv, use_stdin=True, cwd=cwd
                )
            except Exception:
                log_error(traceback.format_exc(chain=True))
                raise
        if result.stderr:
            log_to_output(result.stderr)

    log_to_output(f"\r\n{result.stdout}\r\n")
    return result


# *****************************************************
# ログ記録と通知。
# *****************************************************
def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    LSP_SERVER.show_message_log(message, msg_type)


def log_error(message: str) -> None:
    LSP_SERVER.show_message_log(message, lsp.MessageType.Error)
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["onError", "onWarning", "always"]:
        LSP_SERVER.show_message(message, lsp.MessageType.Error)


def log_warning(message: str) -> None:
    LSP_SERVER.show_message_log(message, lsp.MessageType.Warning)
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["onWarning", "always"]:
        LSP_SERVER.show_message(message, lsp.MessageType.Warning)


def log_always(message: str) -> None:
    LSP_SERVER.show_message_log(message, lsp.MessageType.Info)
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["always"]:
        LSP_SERVER.show_message(message, lsp.MessageType.Info)


# *****************************************************
# サーバーを起動します。
# *****************************************************
if __name__ == "__main__":
    LSP_SERVER.start_io()
