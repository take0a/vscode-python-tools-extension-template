# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Debugging support for LSP."""

import os
import pathlib
import runpy
import sys


def update_sys_path(path_to_add: str) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        sys.path.append(path_to_add)


# 初期化をデバッグするために、他のものをロードする前にデバッガーがロードされていることを確認します。
debugger_path = os.getenv("DEBUGPY_PATH", None)
if debugger_path:
    if debugger_path.endswith("debugpy"):
        debugger_path = os.fspath(pathlib.Path(debugger_path).parent)

    update_sys_path(debugger_path)

    # pylint: disable=wrong-import-position,import-error
    import debugpy

    # 5678 はデフォルトのポートです。
    # 変更する必要がある場合は、ここと launch.json で更新してください。
    debugpy.connect(5678)

    # これにより、デバッガーが VS Code に接続するとすぐに実行が一時停止されます。
    # ここで一時停止したくない場合は、この行をコメントアウトし、
    # 適切なブレークポイントを設定してください。
    debugpy.breakpoint()

SERVER_PATH = os.fspath(pathlib.Path(__file__).parent / "lsp_server.py")
# 注意: 続行する前に、`lsp_server.py` にブレークポイントを設定してください。
runpy.run_path(SERVER_PATH, run_name="__main__")
