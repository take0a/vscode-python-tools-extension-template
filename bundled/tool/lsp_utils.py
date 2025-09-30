# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""LSP 上でツールを実行するときに使用するユーティリティ関数とクラス。"""
from __future__ import annotations

import contextlib
import io
import os
import os.path
import runpy
import site
import subprocess
import sys
import threading
from typing import Any, Callable, List, Sequence, Tuple, Union

# このモジュールをロードするときに使用する作業ディレクトリを保存します
SERVER_CWD = os.getcwd()
CWD_LOCK = threading.Lock()


def as_list(content: Union[Any, List[Any], Tuple[Any]]) -> Union[List[Any], Tuple[Any]]:
    """常にリストを取得することを保証する"""
    if isinstance(content, (list, tuple)):
        return content
    return [content]


# pylint: disable-next=consider-using-generator
_site_paths = tuple(
    [
        os.path.normcase(os.path.normpath(p))
        for p in (as_list(site.getsitepackages()) + as_list(site.getusersitepackages()))
    ]
)


def is_same_path(file_path1, file_path2) -> bool:
    """2 つのパスが同じ場合は true を返します。"""
    return os.path.normcase(os.path.normpath(file_path1)) == os.path.normcase(
        os.path.normpath(file_path2)
    )


def is_current_interpreter(executable) -> bool:
    """実行可能パスが現在のインタープリターと同じ場合は true を返します。"""
    return is_same_path(executable, sys.executable)


def is_stdlib_file(file_path) -> bool:
    """ファイルが標準ライブラリに属している場合は True を返します。"""
    return os.path.normcase(os.path.normpath(file_path)).startswith(_site_paths)


# pylint: disable-next=too-few-public-methods
class RunResult:
    """実行中のツールの結果を保持するオブジェクト。"""

    def __init__(self, stdout: str, stderr: str):
        self.stdout: str = stdout
        self.stderr: str = stderr


class CustomIO(io.TextIOWrapper):
    """stdio を置き換えるカスタム ストリーム オブジェクト。"""

    name = None

    def __init__(self, name, encoding="utf-8", newline=None):
        self._buffer = io.BytesIO()
        self._buffer.name = name
        super().__init__(self._buffer, encoding=encoding, newline=newline)

    def close(self):
        """いくつかのツールで使用されるこの close メソッドを提供します。"""
        # This is intentionally empty.

    def get_value(self) -> str:
        """バッファからの値を文字列として返します。"""
        self.seek(0)
        return self.read()


@contextlib.contextmanager
def substitute_attr(obj: Any, attribute: str, new_value: Any):
    """runpy.run_module() を使用するときにオブジェクト属性のコンテキストを管理します。"""
    old_value = getattr(obj, attribute)
    setattr(obj, attribute, new_value)
    yield
    setattr(obj, attribute, old_value)


@contextlib.contextmanager
def redirect_io(stream: str, new_stream):
    """stdio ストリームをカスタム ストリームにリダイレクトします。"""
    old_stream = getattr(sys, stream)
    setattr(sys, stream, new_stream)
    yield
    setattr(sys, stream, old_stream)


@contextlib.contextmanager
def change_cwd(new_cwd):
    """コードを実行する前に作業ディレクトリを変更します。"""
    os.chdir(new_cwd)
    yield
    os.chdir(SERVER_CWD)


def _run_module(
    module: str, argv: Sequence[str], use_stdin: bool, source: str = None
) -> RunResult:
    """モジュールとして実行されます。"""
    str_output = CustomIO("<stdout>", encoding="utf-8")
    str_error = CustomIO("<stderr>", encoding="utf-8")

    with contextlib.suppress(SystemExit):
        with substitute_attr(sys, "argv", argv):
            with redirect_io("stdout", str_output):
                with redirect_io("stderr", str_error):
                    if use_stdin and source is not None:
                        str_input = CustomIO("<stdin>", encoding="utf-8", newline="\n")
                        with redirect_io("stdin", str_input):
                            str_input.write(source)
                            str_input.seek(0)
                            runpy.run_module(module, run_name="__main__")
                    else:
                        runpy.run_module(module, run_name="__main__")

    return RunResult(str_output.get_value(), str_error.get_value())


def run_module(
    module: str, argv: Sequence[str], use_stdin: bool, cwd: str, source: str = None
) -> RunResult:
    """モジュールとして実行されます。"""
    with CWD_LOCK:
        if is_same_path(os.getcwd(), cwd):
            return _run_module(module, argv, use_stdin, source)
        with change_cwd(cwd):
            return _run_module(module, argv, use_stdin, source)


def run_path(
    argv: Sequence[str], use_stdin: bool, cwd: str, source: str = None
) -> RunResult:
    """実行可能ファイルとして実行されます。"""
    if use_stdin:
        with subprocess.Popen(
            argv,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=cwd,
        ) as process:
            return RunResult(*process.communicate(input=source))
    else:
        result = subprocess.run(
            argv,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            cwd=cwd,
        )
        return RunResult(result.stdout, result.stderr)


def run_api(
    callback: Callable[[Sequence[str], CustomIO, CustomIO, CustomIO | None], None],
    argv: Sequence[str],
    use_stdin: bool,
    cwd: str,
    source: str = None,
) -> RunResult:
    """API を実行します。"""
    with CWD_LOCK:
        if is_same_path(os.getcwd(), cwd):
            return _run_api(callback, argv, use_stdin, source)
        with change_cwd(cwd):
            return _run_api(callback, argv, use_stdin, source)


def _run_api(
    callback: Callable[[Sequence[str], CustomIO, CustomIO, CustomIO | None], None],
    argv: Sequence[str],
    use_stdin: bool,
    source: str = None,
) -> RunResult:
    str_output = CustomIO("<stdout>", encoding="utf-8")
    str_error = CustomIO("<stderr>", encoding="utf-8")

    with contextlib.suppress(SystemExit):
        with substitute_attr(sys, "argv", argv):
            with redirect_io("stdout", str_output):
                with redirect_io("stderr", str_error):
                    if use_stdin and source is not None:
                        str_input = CustomIO("<stdin>", encoding="utf-8", newline="\n")
                        with redirect_io("stdin", str_input):
                            str_input.write(source)
                            str_input.seek(0)
                            callback(argv, str_output, str_error, str_input)
                    else:
                        callback(argv, str_output, str_error)

    return RunResult(str_output.get_value(), str_error.get_value())
