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

## Cloudflare Workers（GitHub 経由）

Python 版はローカル研究用。公開は Workers + D1 です。リポジトリは `https://github.com/yusuke-mizu/horse`。

### 1. 一度だけ D1 を作る

```powershell
npm install
npx wrangler login
npx wrangler d1 create horse-sim
```

表示された `database_id` を `wrangler.jsonc` の `REPLACE_WITH_D1_ID` に入れる。

### 2. GitHub に載せる

変更を `main` に push する。

**方法 A（推奨）Cloudflare ダッシュボードの Git 連携**

1. [Workers & Pages](https://dash.cloudflare.com/?to=/:account/workers-and-pages) → Import a repository
2. `yusuke-mizu/horse` を選ぶ
3. Worker 名を `horse-sim`（`wrangler.jsonc` の `name` と一致必須）
4. Deploy command: `npm run deploy`

**方法 B GitHub Actions**

リポジトリ Secrets:

- `CLOUDFLARE_API_TOKEN`（Workers / D1 編集権限）
- `CLOUDFLARE_ACCOUNT_ID`

`main` への push で `.github/workflows/deploy.yml` が `npm run deploy` を実行する。

初回アクセスで合成データを D1 に投入する。

