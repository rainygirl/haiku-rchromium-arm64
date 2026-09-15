# R Chromium -- arm64 (AArch64)

[English](README.md) | **日本語** | [한국어](README.ko.md)

Haiku/AArch64 (Apple Silicon やその他の arm64 マシン) でネイティブに動作する
Chromium です。戻る/進む/再読み込み、アドレス欄、ブックマークからなる BeAPI
ツールバー付きです。Noto Sans CJK を同梱しているので、日本語・韓国語・中国語の
ページが追加フォントなしで表示されます。RENKU arm64 イメージ (TLSDESC ローダーパッチを適用した
Haiku arm64) で動作し、素の Haiku arm64 イメージではロードできません。

![Haiku arm64 デスクトップで news.naver.com を描画する R Chromium](docs/images/screenshot-naver.png)

## インストール

デバイスで Terminal を開き、次の 1 行を貼り付けます:

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())"
```

最新リリース (約 140 MB) をダウンロードして `~/config/non-packaged/apps/RChromium/`
にインストールし、**Deskbar -> Applications** とデスクトップに **R Chromium** を
追加し、`rchromium` コマンドを作成します。`/boot` に約 400 MB の空きが必要です。

このリポジトリをチェックアウトしている場合は `./install.sh` でも同じことができます。

## 実行

デスクトップの **R Chromium** をダブルクリックするか、**Deskbar -> Applications**
から選びます。Terminal からは:

```sh
rchromium https://news.naver.com
```

- **戻る / 進む / 再読み込み** -- 左側のアイコンボタン。ページ読み込み中は
  再読み込みが停止ボタンに変わります。
- **アドレス欄** -- URL を入力して Enter。`example.com` のように入力すると
  `https://example.com` を開きます。
- **星** -- 現在のページを日付グループ ("Today", ...) の下にブックマークします。
- **メニュー** -- 検索可能なブックマークウィンドウを開きます。項目を
  ダブルクリックすると開きます。

## アンインストール

```sh
python3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/rainygirl/haiku-rchromium-arm64/main/install.py').read())" --uninstall
```

チェックアウトからは `./install.sh --uninstall`。

## AI 利用について

このプログラムは Claude と一緒に作成しました。
