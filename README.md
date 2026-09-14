# 競馬予想シミュレーション

過去データから馬の基礎能力を推定し、今回の条件での能力発揮率を掛け、Monte Carlo で着順確率を出す。人気は能力の入力に使わない。

現在は **Phase 2**（基礎能力 ＋ 馬場・距離・コース・枠・脚質×展開の推定）。固定加点は使わず、当該走より前の残差だけを見る。

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
python -m horse_sim estimate-factors
python -m horse_sim compare-models
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
