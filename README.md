# ViRAD

ROSアプリケーションのTopic通信を可視化するためのツールです。
- 個々のファイルをノードとみなします。
- 正規表現で "advertise" と "subscribe" を探索しています。
- 上記関数呼び出しの括弧内に現れる文字列リテラルをトピック名と認識します。

## Dependencies 依存関係

実行に必要なもの

- Python (3.8 で開発しています)
- Graphviz
- システムにインストールされた Graphviz を利用するための Python モジュール graphviz 
  -  `pip install graphviz` でインストールできます．

## Usage

ソースコードからグラフを抽出する visualization.py と，
2バージョンのグラフを比較する differences.py からなります．

### visualization.py 

ソースコードからグラフを可視化するツールです．

起動に必用なコマンドライン引数

`python visualization.py input_path output_path [filter]`

- input_path: 解析対象のファイルパス．この中の cpp ファイルが解析対象となります．
- output_path: 出力先ディレクトリ．存在しなければ自動で作られます．
- filter: 省略可能．出力に含めたくないノードの名前をカンマ区切りで指定します．

出力されるファイル:
- `connection.csv`: ノードとトピックの接続関係．
  - publish しているノード名, topic名, subscribe しているノード名（複数ある場合はカンマ区切りの列）
- `connect_graph`: 上記の関係の Graphviz DOT ファイルとしての表現．
- `connect_graph.svg`: 上記の関係の図での表現．
- `non_connected_pub.csv`: publish されているが subscribe されていないトピックの一覧．
- `remap.csv`: remap情報をの一覧．
- 

### differences.py

差分表示ツールです．

`python differences.py new.csv old.csv output_path`

- new.csv: 新しいバージョンの接続関係を記録したcsvのファイルパス
- old.csv: 古いバージョンの接続関係を記録したcsvのファイルパス
- output_path: 出力先のファイルパス