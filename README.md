# 競馬予想シミュレーション

過去データから馬の基礎能力を推定し、今回の条件での能力発揮率を掛け、Monte Carlo で着順確率を出す。人気は能力の入力に使わない。

現在は **Phase 1**（データ投入 → 基礎能力 → 予測タイム → 順位確率）。馬場・血統・騎手などの補正は `factor_effects` に推定結果が入るまで係数 1.0。

## セットアップ

```powershell
python -m pip install -e ".[dev]"
```

## 使い方

```powershell
python -m horse_sim ingest-synthetic
python -m horse_sim rate
python -m horse_sim races
python -m horse_sim predict --race-id 100
python -m horse_sim serve
```

実データは `data/samples/` の CSV 形式で投入する。

```powershell
python -m horse_sim ingest-csv --races data/samples/races.csv --entries data/samples/entries.csv
```

UI: http://127.0.0.1:8000

## 層

取得 / 正規化 / 能力評価 / 条件補正 / 展開 / Monte Carlo / 確率 / オッズ比較 / バックテスト / UI

根拠は計算結果から生成する。経験則の固定加点はコードに置かない。
