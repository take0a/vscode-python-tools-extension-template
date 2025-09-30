# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Runner to use when running under a different interpreter.
"""

import os
import pathlib
import sys
import traceback


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


# pylint: disable=wrong-import-position,import-error
import lsp_jsonrpc as jsonrpc
import lsp_utils as utils

RPC = jsonrpc.create_json_rpc(sys.stdin.buffer, sys.stdout.buffer)

EXIT_NOW = False
while not EXIT_NOW:
    msg = RPC.receive_data()

    method = msg["method"]
    if method == "exit":
        EXIT_NOW = True
        continue

    if method == "run":
        is_exception = False
        # これは sys.path を保持するために必要です。
        # pylint は sys.path を変更するため、次回のシナリオでは機能しない可能性があります。
        with utils.substitute_attr(sys, "path", sys.path[:]):
            try:
                # `utils.run_module` は `python -m <pytool-module>` の実行と同等です。
                # ツールがプログラムAPIをサポートしている場合は、
                # 以下の関数をツールのコードに置き換えてください。
                # 作業ディレクトリの変更やIOストリームの管理などを処理する 
                # `utils.run_api` ヘルパーも使用できます。
                # また、`lsp_server.py` の `_run_tool_on_document` 関数と 
                # `_run_tool` 関数も更新してください。
                result = utils.run_module(
                    module=msg["module"],
                    argv=msg["argv"],
                    use_stdin=msg["useStdin"],
                    cwd=msg["cwd"],
                    source=msg["source"] if "source" in msg else None,
                )
            except Exception:  # pylint: disable=broad-except
                result = utils.RunResult("", traceback.format_exc(chain=True))
                is_exception = True

        response = {"id": msg["id"]}
        if result.stderr:
            response["error"] = result.stderr
            response["exception"] = is_exception
        elif result.stdout:
            response["result"] = result.stdout

        RPC.send_data(response)
