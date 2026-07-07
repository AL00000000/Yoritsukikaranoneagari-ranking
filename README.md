# 寄付からの値上がり率ランキング (東証プライム・スタンダード・グロース)

[ストックウェザー](https://finance.stockweather.co.jp/contents/ranking.aspx?mkt=1&cat=0000&type=2) の「寄付からの値上がり率」ランキング(東証プライム / スタンダード / グロース 各100位)を平日ごとに取得したデータです。

**📊 閲覧用サイト: https://al00000000.github.io/Yoritsukikaranoneagari-ranking/**
(市場切替・日付切替・列ソート・銘柄検索ができます)

## データ

- [docs/data/](docs/data/) … 閲覧用サイトが読み込む日次JSON(3市場まとめ)
- [output/](output/) … 日次のランキングCSV (`ranking_YYYY-MM-DD.csv`, UTF-8, 3市場で300行)
  - 市場 / 順位 / 順位変動(前営業日比) / 前日順位 / コード / 銘柄名 / 現在値 / 前日比 / 前日比% / 寄付からの値上がり率
- [history/](history/) … 比較計算用の生データ (JSON)

順位変動の表記: `↑n`(n位上昇) / `↓n`(n位下降) / `→`(変わらず) / `NEW`(前営業日圏外から登場)。
順位変動は市場ごとに前営業日の同市場ランキングと比較しています。

## 取得スクリプト

[fetch_ranking.py](fetch_ranking.py) — Python標準ライブラリのみで動作します。

```
py fetch_ranking.py
```

## 注意

- データの取得元は finance.stockweather.co.jp です。データの正確性は保証しません。投資判断は自己責任でお願いします。
- 市場休場日は更新されません。
