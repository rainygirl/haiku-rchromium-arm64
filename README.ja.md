# R Chromium -- arm64 (AArch64)

[English](README.md) | **日本語** | [한국어](README.ko.md)

Chromium の `content_shell` を Haiku/AArch64 向けにネイティブビルドし、手書きの
BeAPI ツールバーで包んだブラウザです。x86 をエミュレートせず、Apple Silicon
(および arm64 ハードウェア) 上でネイティブ速度で動作します。本書はエンドユーザー
向けのインストールと実行のガイドです。

ビルド、アーキテクチャ、移植の内部事情は [`AGENTS.md`](AGENTS.md) にあります。

![Haiku arm64 デスクトップで news.naver.com を描画する R Chromium](docs/images/screenshot-naver.png)

*RENKU (Haiku arm64) デスクトップ上で、ネイティブ BeAPI ツールバーとともに描画
された news.naver.com。Apple Silicon Mac の QEMU/HVF VM で撮影。*

## 要件

- **AArch64 版 Haiku** -- 実際の renku-arm64 デスクトップ (Apple Silicon 上の
  QEMU/HVF で起動、または arm64 ハードウェア)。
- **イメージに `A0001` runtime_loader TLSDESC パッチが適用されていること。**
  clang が生成する `R_AARCH64_TLSDESC` 再配置を素の Haiku ローダーは解決できない
  ため、このパッチがないとバイナリはロードされません。パッチは
  `haiku_kernel_patches/A0001-arm64-runtime-loader-tlsdesc.patch` で、既存
  イメージの `haiku.hpkg` に組み込む手順は [`AGENTS.md`](AGENTS.md) にあります。
- **Haiku 標準フォント。** テキストはシステムフォントでシェイピングとラスタライズ
  を行います。標準の RENKU/Haiku フォントセットで十分です (news.naver.com の
  韓国語も描画されます)。

## デバイスへのインストールと実行

### 配置

バイナリ、リソース、BeAPI シム (`libchromium_haiku.so`) を一か所にまとめます。
例えば書き込み可能な BFS ボリューム上の `cs/` ディレクトリ:

```
cs/content_shell                 # バイナリ
cs/content_shell.pak             # リソース ...
cs/icudtl.dat
cs/snapshot_blob.bin
cs/v8_context_snapshot.bin
cs/locales/
cs/lib/libchromium_haiku.so      # ネイティブ BeAPI ツールバーのシム
```

### 実行

`content_shell` はシムを必要とする (`DT_NEEDED: libchromium_haiku`) ので、
ローダーに `cs/lib` を指定します。起動フラグは不要です。Haiku ではビルド自体が
ソフトウェアコンポジットを有効にします:

```sh
cd cs
LIBRARY_PATH=$(pwd)/lib:/boot/system/lib ./content_shell https://news.naver.com
```

ツールバー付きのネイティブ Haiku ウィンドウが開き、その下にページが描画されます。

### ブラウザの使い方

ウィンドウ上部のツールバーは BeAPI コントロールで描かれています:

- **戻る / 進む / 再読み込み** -- 左側のアイコンボタン。ページ読み込み中は
  再読み込みが停止ボタンに変わります。
- **アドレス欄** -- URL を入力して Enter で移動します。`example.com` のように
  スキームがない場合は `https://example.com` として扱われます。現在のページの
  URL に追従します。
- **ブックマークに追加 (星)** -- 現在のページを日付グループ ("Today", ...) の
  下にあるブックマークストアへ登録します。
- **ブックマークを表示** -- 検索可能なブックマークウィンドウを開きます。
  項目をダブルクリックすると開きます。

### 既知の制限とトラブルシューティング

- **起動時に `libchromium_haiku.so: Troubles handling dynamic section`** --
  シムが 4 KB ページでリンクされていません。正しいビルドのシムを使ってください
  (再リンクのフラグと理由は [`AGENTS.md`](AGENTS.md) にあります)。
- **`Bad data relocating` / バイナリがロードされない** -- イメージのローダーに
  `A0001` TLSDESC パッチがありません (要件を参照)。
- news.naver.com などのページは、ネイティブツールバー、アドレス欄からの移動、
  ブックマークとともに完全に描画されます。検証履歴の全容と既知の粗い部分は
  [`AGENTS.md`](AGENTS.md) にあります。

## AI 利用について

このプログラムは Claude と一緒に作成しました。
