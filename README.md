# SwitchBot Logging

SwitchBot API v1.1 を使って温湿度計・Hub 2 などのセンサーデータ(温度・湿度・CO2・照度・電池残量)を定期的に取得し、DBに保存するロガーです。保存したデータをグラフで確認できるWebダッシュボード付きです。

## 対応デバイス

デフォルトで以下のデバイスタイプを自動検出して記録します:

- Meter / MeterPlus / MeterPro / MeterPro(CO2)(温湿度計シリーズ)
- WoIOSensor(防水温湿度計)
- Hub 2(温度・湿度・照度)

`TARGET_DEVICE_TYPES` で対象タイプを変更できます。上記以外のタイプでも、ステータスAPIが返す値はすべて `raw_status` カラムにJSONで保存されます。

## セットアップ

1. SwitchBotアプリでトークンとシークレットを取得
   - プロフィール → 設定 → 基本データ → アプリバージョンを10回タップ → 「開発者向けオプション」
2. `.env` を作成:

   ```sh
   cp .env.example .env
   # SWITCHBOT_TOKEN と SWITCHBOT_SECRET を記入
   ```

3. 起動:

   ```sh
   docker compose up -d --build
   ```

4. ログ確認:

   ```sh
   docker compose logs -f
   ```

## Webダッシュボード

`docker compose up -d` で起動後、ブラウザで **http://localhost:8080** を開くとダッシュボードが表示されます。

- デバイスごとの最新値カード(温度・湿度・CO2・電池残量・最終更新時刻)
- 温度/湿度/CO2/照度/電池残量の時系列グラフ(データのある項目のみ表示)
- 表示期間の切替(6時間/24時間/7日/30日)
- 60秒ごとに自動更新

公開ポートは `docker-compose.yml` の `ports`(デフォルト `8080:8080`)で変更できます。

### API

ダッシュボードが使うJSON APIは直接呼ぶこともできます:

- `GET /api/devices` — 記録済みデバイス一覧
- `GET /api/latest` — デバイスごとの最新値
- `GET /api/measurements?hours=24&device_id=XXX` — 時系列データ(`device_id`は省略可。1デバイスあたり最大500点に間引き)

## 外気温を重ねて表示する

[Open-Meteo](https://open-meteo.com/)(無料・APIキー不要)から外気温・外気湿度を取得して、センサーと同じテーブルに「外気」という擬似デバイスとして記録できます。ダッシュボードでは破線で表示され、室内との比較ができます。

`.env` に自宅の緯度・経度を設定するだけで有効になります(Googleマップで場所を右クリックすると座標を確認できます):

```
WEATHER_LATITUDE=35.6812
WEATHER_LONGITUDE=139.7671
```

表示名を変えたい場合は `WEATHER_DEVICE_NAME`(デフォルト: 外気)を設定してください。

## データの確認(SQLite)

デフォルトでは名前付きボリューム `switchbot-data` 内の SQLite (`/data/switchbot.db`) に保存されます。

```sh
docker compose exec switchbot-logger python -c "
import sqlite3
con = sqlite3.connect('/data/switchbot.db')
for row in con.execute('SELECT recorded_at, device_name, temperature, humidity FROM measurements ORDER BY id DESC LIMIT 10'):
    print(row)
"
```

## PostgreSQL を使う場合

`docker-compose.yml` には PostgreSQL(`db` サービス)が含まれています。`.env` の `DATABASE_URL` を変更して再起動するだけで切り替わります:

```
DATABASE_URL=postgresql+psycopg2://switchbot:switchbot@db:5432/switchbot
```

```sh
docker compose up -d --build
```

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `SWITCHBOT_TOKEN` | (必須) | APIトークン |
| `SWITCHBOT_SECRET` | (必須) | APIシークレット |
| `POLL_INTERVAL_SECONDS` | `300` | 取得間隔(秒) |
| `DATABASE_URL` | `sqlite:////data/switchbot.db` | DB接続URL(SQLAlchemy形式) |
| `TARGET_DEVICE_TYPES` | 温湿度計系+Hub 2 | 記録対象デバイスタイプ(カンマ区切り) |
| `TARGET_DEVICE_IDS` | (全デバイス) | 記録対象デバイスID(カンマ区切り) |
| `WEATHER_LATITUDE` / `WEATHER_LONGITUDE` | (無効) | 両方設定すると外気温・外気湿度を記録(Open-Meteo) |
| `WEATHER_DEVICE_NAME` | `外気` | 外気データの表示名 |

APIのレート制限は 10,000 リクエスト/日です。1サイクルで「デバイス一覧1回+デバイスごとに1回」リクエストするため、例えばデバイス3台・5分間隔なら約1,152リクエスト/日です。

## テーブル構造(measurements)

| カラム | 型 | 説明 |
|---|---|---|
| `id` | INTEGER | 主キー |
| `recorded_at` | DATETIME | 記録時刻(UTC) |
| `device_id` | VARCHAR | デバイスID |
| `device_name` | VARCHAR | デバイス名 |
| `device_type` | VARCHAR | デバイスタイプ |
| `temperature` | FLOAT | 温度(℃) |
| `humidity` | FLOAT | 湿度(%) |
| `battery` | INTEGER | 電池残量(%) |
| `co2` | INTEGER | CO2濃度(ppm、MeterPro(CO2)のみ) |
| `light_level` | INTEGER | 照度レベル(Hub 2のみ) |
| `raw_status` | TEXT | APIレスポンス全体(JSON) |
