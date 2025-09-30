# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""標準 IO 経由の軽量 JSON-RPC"""


import atexit
import contextlib
import io
import json
import pathlib
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO, Dict, Optional, Sequence, Union

CONTENT_LENGTH = "Content-Length: "
RUNNER_SCRIPT = str(pathlib.Path(__file__).parent / "lsp_runner.py")


def to_str(text) -> str:
    """必要に応じてバイトを文字列に変換します。"""
    return text.decode("utf-8") if isinstance(text, bytes) else text


class StreamClosedException(Exception):
    """JSON RPC ストリームが閉じられています。"""

    pass  # pylint: disable=unnecessary-pass


class JsonWriter:
    """ライター ストリームへの JSON-RPC メッセージの書き込みを管理します。"""

    def __init__(self, writer: io.TextIOWrapper):
        self._writer = writer
        self._lock = threading.Lock()

    def close(self):
        """基礎となるライター ストリームを閉じます。"""
        with self._lock:
            if not self._writer.closed:
                self._writer.close()

    def write(self, data):
        """指定されたデータを JSON-RPC 形式でストリームに書き込みます。"""
        if self._writer.closed:
            raise StreamClosedException()

        with self._lock:
            content = json.dumps(data)
            length = len(content.encode("utf-8"))
            self._writer.write(
                f"{CONTENT_LENGTH}{length}\r\n\r\n{content}".encode("utf-8")
            )
            self._writer.flush()


class JsonReader:
    """ストリームからの JSON-RPC メッセージの読み取りを管理します。"""

    def __init__(self, reader: io.TextIOWrapper):
        self._reader = reader

    def close(self):
        """基になるリーダー ストリームを閉じます。"""
        if not self._reader.closed:
            self._reader.close()

    def read(self):
        """ストリームから JSON-RPC 形式でデータを読み取ります。"""
        if self._reader.closed:
            raise StreamClosedException
        length = None
        while not length:
            line = to_str(self._readline())
            if line.startswith(CONTENT_LENGTH):
                length = int(line[len(CONTENT_LENGTH) :])

        line = to_str(self._readline()).strip()
        while line:
            line = to_str(self._readline()).strip()

        content = to_str(self._reader.read(length))
        return json.loads(content)

    def _readline(self):
        line = self._reader.readline()
        if not line:
            raise EOFError
        return line


class JsonRpc:
    """JSON-RPC 経由のデータの送受信を管理します。"""

    def __init__(self, reader: io.TextIOWrapper, writer: io.TextIOWrapper):
        self._reader = JsonReader(reader)
        self._writer = JsonWriter(writer)

    def close(self):
        """基になるストリームを閉じます。"""
        with contextlib.suppress(Exception):
            self._reader.close()
        with contextlib.suppress(Exception):
            self._writer.close()

    def send_data(self, data):
        """指定されたデータを JSON-RPC 形式で送信します。"""
        self._writer.write(data)

    def receive_data(self):
        """JSON-RPC 形式でデータを受信します。"""
        return self._reader.read()


def create_json_rpc(readable: BinaryIO, writable: BinaryIO) -> JsonRpc:
    """読み取り可能および書き込み可能なストリーム用の JSON-RPC ラッパーを作成します。"""
    return JsonRpc(readable, writable)


class ProcessManager:
    """ツールを実行するために起動されたサブプロセスを管理します。"""

    def __init__(self):
        self._args: Dict[str, Sequence[str]] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._rpc: Dict[str, JsonRpc] = {}
        self._lock = threading.Lock()
        self._thread_pool = ThreadPoolExecutor(10)

    def stop_all_processes(self):
        """すべてのプロセスに終了コマンドを送信し、トランスポートをシャットダウンします。"""
        for i in self._rpc.values():
            with contextlib.suppress(Exception):
                i.send_data({"id": str(uuid.uuid4()), "method": "exit"})
        self._thread_pool.shutdown(wait=False)

    def start_process(self, workspace: str, args: Sequence[str], cwd: str) -> None:
        """プロセスを開始し、stdio 経由で JSON-RPC 通信を確立します。"""
        # pylint: disable=consider-using-with
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
        self._processes[workspace] = proc
        self._rpc[workspace] = create_json_rpc(proc.stdout, proc.stdin)

        def _monitor_process():
            proc.wait()
            with self._lock:
                try:
                    del self._processes[workspace]
                    rpc = self._rpc.pop(workspace)
                    rpc.close()
                except:  # pylint: disable=bare-except
                    pass

        self._thread_pool.submit(_monitor_process)

    def get_json_rpc(self, workspace: str) -> JsonRpc:
        """指定された ID の JSON-RPC ラッパーを取得します。"""
        with self._lock:
            if workspace in self._rpc:
                return self._rpc[workspace]
        raise StreamClosedException()


_process_manager = ProcessManager()
atexit.register(_process_manager.stop_all_processes)


def _get_json_rpc(workspace: str) -> Union[JsonRpc, None]:
    try:
        return _process_manager.get_json_rpc(workspace)
    except StreamClosedException:
        return None
    except KeyError:
        return None


def get_or_start_json_rpc(
    workspace: str, interpreter: Sequence[str], cwd: str
) -> Union[JsonRpc, None]:
    """既存の JSON-RPC 接続を取得するか、接続を開始して返します。"""
    res = _get_json_rpc(workspace)
    if not res:
        args = [*interpreter, RUNNER_SCRIPT]
        _process_manager.start_process(workspace, args, cwd)
        res = _get_json_rpc(workspace)
    return res


class RpcRunResult:
    """RPC 経由でツールを実行した結果を保持するオブジェクト。"""

    def __init__(self, stdout: str, stderr: str, exception: Optional[str] = None):
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.exception: Optional[str] = exception


# pylint: disable=too-many-arguments
def run_over_json_rpc(
    workspace: str,
    interpreter: Sequence[str],
    module: str,
    argv: Sequence[str],
    use_stdin: bool,
    cwd: str,
    source: str = None,
) -> RpcRunResult:
    """JSON-RPC を使用してコマンドを実行します。"""
    rpc: Union[JsonRpc, None] = get_or_start_json_rpc(workspace, interpreter, cwd)
    if not rpc:
        raise Exception("Failed to run over JSON-RPC.")

    msg_id = str(uuid.uuid4())
    msg = {
        "id": msg_id,
        "method": "run",
        "module": module,
        "argv": argv,
        "useStdin": use_stdin,
        "cwd": cwd,
    }
    if source:
        msg["source"] = source

    rpc.send_data(msg)

    data = rpc.receive_data()

    if data["id"] != msg_id:
        return RpcRunResult(
            "", f"Invalid result for request: {json.dumps(msg, indent=4)}"
        )

    result = data["result"] if "result" in data else ""
    if "error" in data:
        error = data["error"]

        if data.get("exception", False):
            return RpcRunResult(result, "", error)
        return RpcRunResult(result, error)

    return RpcRunResult(result, "")


def shutdown_json_rpc():
    """すべての JSON-RPC プロセスをシャットダウンします。"""
    _process_manager.stop_all_processes()
