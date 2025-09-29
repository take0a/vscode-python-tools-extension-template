# VS Code Pythonツール拡張機能用テンプレート

これは、お気に入りのPythonツール向けのVS Code拡張機能の構築を開始するためのテンプレートリポジトリです。リンター、フォーマッタ、コード解析ツールなど、あるいはそれらすべてを組み合わせたものでも構いません。このテンプレートは、これらのツール向けのVS Code拡張機能を構築するために必要な基本的な構成要素を提供します。

## プログラミング言語とフレームワーク

拡張機能テンプレートは、拡張機能部分と言語サーバー部分の2つの部分で構成されています。拡張機能部分はTypeScriptで記述され、言語サーバー部分は[_pygls_][pygls]（Python言語サーバー）ライブラリを介してPythonで記述されています。

このテンプレートを使用する場合、ほとんどの部分はPython部分のコードで作業することになります。ツールと拡張機能部分を統合するには、[言語サーバープロトコル](https://microsoft.github.io/language-server-protocol)を使用します。[_pygls_][pygls]は現在、[LSPバージョン3.16](https://microsoft.github.io/language-server-protocol/specifications/specification-3-16/)で動作します。

TypeScript部分は、VS CodeとそのUIの操作を処理します。拡張機能テンプレートには、ツールで使用できるいくつかの設定が事前に構成されています。ツールをサポートするために新しい設定を追加する必要がある場合は、TypeScriptを少し使用する必要があります。拡張機能には、いくつかの設定例が用意されているので、参考にしてください。また、当チームが開発した人気ツール向けの拡張機能も参考としてご覧ください。

## 要件

1. VS Code 1.64.0 以上
1. Python 3.9 以上
1. node >= 18.17.0
1. npm >= 8.19.0 (`npm` は node と一緒にインストールされます。npm のバージョンを確認し、`npm install -g npm@8.3.0` でアップデートしてください)
1. VS Code 用 Python 拡張機能

Python 仮想環境の作成と操作方法を理解している必要があります。

## はじめに

1. この[テンプレートを使用してリポジトリを作成](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)します。
1. 開発マシンでリポジトリをローカルにチェックアウトします。
1. ターミナルで、このプロジェクト用のPython仮想環境を作成し、アクティブ化します。使用するツールの最小バージョンであるPythonを使用してください。このテンプレートはPython 3.9以上で動作するように作成されています。
1. アクティブ化した環境に`nox`をインストールします: `python -m pip install nox`
1. `requirements.in`にお好みのツールを追加します。
1. `nox --session setup`を実行します。
1. **オプション** テスト依存関係をインストールします: `python -m pip install -r src/test/python_tests/requirements.txt`テストエクスプローラーからテストを実行するには、これらをインストールする必要があります。
1. `package.json` を開き、以下の項目を探して更新します。
    1. `<pytool-module>` をツールのモジュール名に置き換えます。これは、設定の名前空間の作成やコマンドの登録などに内部的に使用されます。名前は小文字で表記し、スペースや `-` は使用しないでください。例えば、`<pytool-module>` を `pylint` に置き換えると、設定は `pylint.args` のようになります。また、`<pytool-module>` を `black-formatter` に置き換えると、設定は `black-formatter.args` のようになります。
    1. `<pytool-display-name>` をツールの表示名に置き換えます。これは、マーケットプレイス、拡張機能ビュー、出力ログなどで拡張機能のタイトルとして使用されます。例えば、`black` 拡張機能の場合は `Black Formatter` です。
1. `npm install` を使用して Node.js パッケージをインストールします。
1. https://marketplace.visualstudio.com/vscode にアクセスし、パブリッシャー アカウントをまだお持ちでない場合は作成します。
    1. `package.json` 内の `<my-publisher>` をマーケットプレイスに登録した名前に置き換えて、公開された名前を使用します。

## このテンプレートの機能

導入部分が完了すると、このテンプレートには以下の内容が追加されます。`<pytool-module>` が `mytool` に、`<pytool-display-name>` が `My Tool` に置き換えられていると仮定します。

1. コマンド `My Tool: Restart Server` (コマンド ID: `mytool.restart`)。
1. 以下の設定:
    - `mytool.args`
    - `mytool.path`
    - `mytool.importStrategy`
    - `mytool.interpreter`
    - `mytool.showNotification`
1. 拡張機能の有効化トリガー:
    - 言語が `python` の場合。
    - 開いているワークスペースで拡張子 `.py` のファイルが見つかった場合。
1. 以下のコマンドが登録されています:
    - `mytool.restart`: 言語サーバーを再起動します。
1. ログ出力用の出力チャンネル `Output` > `My Tool`

## ツールから機能を追加する

`bundled/tool/lsp_server.py` を開いてください。ここでほとんどの変更を行います。詳細は、`TODO` コメントを参照してください。

テンプレート全体の他の場所でも `TODO` を確認してください。

- `bundled/tool/lsp_runner.py` : 特殊なケースでは、このファイルを更新する必要がある場合があります。
- `src/test/python_tests/test_server.py` : テストを記述する場所です。ここでは、開始するための不完全な例が2つ提供されています。
- このテンプレートのすべての Markdown ファイルには、`TODO` 項目があります。必ず確認してください。これには、MIT ライセンスを維持する場合でも、LICENSE ファイルの更新が含まれます。

このテンプレートを使用してチームが作成した他の拡張機能への参照:

- プロトコルリファレンス: <https://microsoft.github.io/language-server-protocol/specifications/specification-3-16/>
- ファイルの `open`、`save`、`close` 時の Lint 処理方法を示す実装。[Pylint](https://github.com/microsoft/vscode-pylint/tree/main/bundled/tool)
- フォーマット処理方法を示す実装。[Black Formatter](https://github.com/microsoft/vscode-black-formatter/tree/main/bundled/tool)
- コードアクションの処理方法を示す実装。[isort](https://github.com/microsoft/vscode-isort/blob/main/bundled/tool)

## 拡張機能のビルドと実行

VS Code から `Debug Extension and Python` 設定を実行します。これにより、ホストウィンドウで拡張機能がビルドされ、デバッグされます。

注: ビルドだけを実行したい場合は、VS Code でビルドタスクを実行できます (`ctrl`+`shift`+`B`)

## デバッグ

TypeScript と Python コードの両方をデバッグするには、`Debug Extension and Python` デバッグ構成を使用します。これが推奨される方法です。また、停止する際は、TypeScript と Python の両方のデバッグセッションを停止してください。そうしないと、Python セッションに再接続されない可能性があります。

TypeScript コードのみをデバッグするには、`Debug Extension` デバッグ構成を使用します。

すでに実行中のサーバーまたは本番サーバーをデバッグするには、`Python Attach` を使用し、`lsp_server.py` を実行しているプロセスを選択します。

## ログ出力とログ

テンプレートは、`Output` > `mytool` パネルにログ出力チャネルを作成します。ログレベルは、コマンドパレットから `Developer: Set Log Level...` コマンドを実行し、リストから拡張機能を選択することで制御できます。拡張機能は、ツールの表示名でリストされているはずです。また、グローバルログレベルを設定することもできます。これは、すべての拡張機能とエディターに適用されます。

言語クライアントと言語サーバー間のメッセージに関するログが必要な場合は、`"mytool.server.trace": "verbose"` と設定してメッセージログを取得できます。これらのログは、`Output` > `mytool` パネルでも確認できます。

## 新しい設定またはコマンドの追加

`package.json` ファイルに設定の詳細を追加することで、新しい設定を追加できます。この設定を Python ツールサーバー (`lsp_server.py`) に渡すには、必要に応じて `settings.ts` を更新してください。このファイルには、新しい設定のベースとなる様々な種類の設定例が含まれています。

コマンドの追加方法については、`package.json` と `extension.ts` で `restart` コマンドがどのように実装されているかを参照してください。また、Language Server Protocol を介して Python からコマンドを提供することもできます。

## テスト

出発点として `src/test/python_tests/test_server.py` を参照してください。LSP 経由でツールを実行する際の様々な側面をテストするには、ここに記載されている他のプロジェクトを参照してください。

テスト要件をインストール済みであれば、テストエクスプローラーでテストを確認できます。

`nox --session tests` コマンドを使用して、すべてのテストを実行することもできます。

## リンティング

Python コードと TypeScript コードの両方でリンティングを実行するには、`nox --session lint` を実行してください。別のリンターとフォーマッタを使用する場合は、nox ファイルを更新してください。

## パッケージ化と公開

1. `package.json` 内の各種フィールドを更新します。少なくとも、以下のフィールドを確認し、必要に応じて更新してください。フィールドを追加するには、[拡張機能マニフェスト リファレンス](https://code.visualstudio.com/api/references/extension-manifest) を参照してください。
    - `"publisher"`: <https://marketplace.visualstudio.com/> から取得したパブリッシャー ID に更新します。
    - `"version"`: このフィールドの要件と制限事項の詳細については、<https://semver.org/> を参照してください。
    - `"license"`: プロジェクトに応じてライセンスを更新します。デフォルトは `MIT` です。
    - `"keywords"`: プロジェクトのキーワードを更新します。これらは VS Code マーケットプレイスで検索する際に使用されます。
    - `"categories"`: プロジェクトのカテゴリを更新します。VS Code マーケットプレイスでのフィルタリングが容易になります。
    - `"homepage"`、`"repository"`、`"bugs"` : これらのフィールドの URL を更新し、プロジェクトを参照するようにします。
    - **オプション** このプロジェクトのアイコンとして使用する画像ファイルへの相対パスを指定した `"icon"` フィールドを追加します。
1. 以下の Markdown ファイルを確認してください。
    - **必須** 初回のみ: `CODE_OF_CONDUCT.md`、`LICENSE`、`SUPPORT.md`、`SECURITY.md`
    - すべてのリリース: `CHANGELOG.md`
1. `nox --session build_package` を使用してパッケージをビルドします。
1. 生成された `.vsix` ファイルを拡張機能管理ページ <https://marketplace.visualstudio.com/manage> にアップロードします。

コマンドラインからこれを行うには、こちら <https://code.visualstudio.com/api/working-with-extensions/publishing-extension> を参照してください。

## 依存関係のアップグレード

Dependabot yml は、この拡張機能の依存関係のアップグレードを簡単に設定できるように提供されています。dependabot で使用されているラベルをリポジトリに追加してください。

ローカルプロジェクトを手動でアップグレードするには：

1. 新しいブランチを作成します。
1. `npm update` を実行して Node.js モジュールを更新します。
1. `nox --session setup` を実行して Python パッケージをアップグレードします。

## トラブルシューティング

### `lsp_server.py` のパスまたは名前を変更する

`lsp_server.py` の名前を別の名前に変更したい場合は、変更可能です。`constants.ts` と `src/test/python_tests/lsp_test_client/session.py` を必ず更新してください。

また、`lsp_server.py` に挿入されたパスが、依存パッケージを取得するために正しいフォルダを指していることを確認してください。

### モジュールが見つからないエラー

これは、`bundled/libs` が空の場合に発生する可能性があります。これは、ツールやその他の依存関係を配置するフォルダです。必要なライブラリの作成とバンドルに必要なビルド手順に従ってください。

よくあるエラーは、[_pygls_][pygls] モジュールが見つかりません。

[pygls]: https://github.com/openlawlibrary/pygls
