# Vue + Docker 個人作業版

這份作業版從 `main` 建立於獨立 Git 工作目錄 `vue-docker-assignment`。原本的 Streamlit 程式仍在 `app.py`，這份作業新增 Vue 畫面、FastAPI API 與 Docker Compose。Compose 使用自己的 SQLite volume，不會連接原本 `data/erp.db`。

## 架構

```
瀏覽器 → Vue/Nginx（localhost:8514）→ FastAPI（容器內）→ 獨立 SQLite volume
```

- `web/`：Vue 3 風險總覽，登入後顯示 KPI、據點、事件與供應商；點選據點可篩選資料，再點供應商查看其未結案採購單。
- `api/`：FastAPI，沿用現有 `backend/` 的資料與角色能力規則。每次讀取時重新查驗帳號及組織權限；另提供尚未連到 Vue 畫面的各模組唯讀資料 API。
- `compose.yaml`：啟動 `web` 和 `api` 兩個容器，並保存作業版專用資料庫。

## 用 Docker 啟動

先啟動 Docker Desktop，然後在本目錄執行：

```powershell
docker compose up --build -d
```

開啟 `http://127.0.0.1:8514/`，使用 `viewer / viewer` 登入。`8513` 保留給本機 Vite 預覽，與 Docker 版分開。此帳密只在新建的作業版示範資料庫啟用。查看容器：`docker compose ps`；停止：`docker compose down`。停止不會刪除 volume。若要重設作業資料庫，需另外手動刪除專用 volume；不要對原專案資料庫操作。未設定 `API_SESSION_SECRET` 時，API 會在啟動時產生隨機金鑰，重啟後需要重新登入；若要讓登入跨重啟維持有效，可在 Compose 啟動前設定自己的長隨機字串。

## 限同一區網展示（可選）

一般啟動仍只開放本機。需要讓同一 Wi-Fi 的其他電腦觀看時，先用 `ipconfig` 找到這台電腦目前連線中的 Wi-Fi/乙太網路 IPv4 位址（不要用 WSL、VMware 的虛擬網卡），再於 PowerShell 啟動：

```powershell
$env:LAN_BIND_IP = "172.20.10.3"  # 範例；每次依 ipconfig 的實際位址更換
docker compose -f compose.yaml -f compose.lan.yaml up -d
```

同一區網的其他人開 `http://該IPv4位址:8514/`，使用 `viewer / viewer` 查看示範風險畫面。LAN 設定的 Nginx 只轉送 Vue 實際使用的登入、風險總覽與據點查詢 API；`/api/data` 等其他模組資料 API 一律回 403，避免示範帳密暴露薪資、總帳等資料。這是 HTTP 區網展示，不適合公開上網或傳送真實資料。電腦和 Docker 必須持續開啟；若同網路仍連不上，先確認 Windows 防火牆、網路設定與 Wi-Fi 是否阻擋裝置間互連。不要為了測試而全面停用防火牆。

展示結束後回到僅本機模式：

```powershell
Remove-Item Env:LAN_BIND_IP -ErrorAction SilentlyContinue
docker compose up -d
```

這會重新建立 web 容器，但保留作業版專用資料庫 volume。

Vue 畫面目前只展示供應鏈風險的唯讀總覽。採購單依供應商主檔的國家與地區精確對應據點；這代表「可能需要檢查」，不代表已確認受到事件影響。資料庫沒有原預計交期欄位，因此畫面僅顯示下單日期及已有紀錄的預估延遲，不能推算承諾交期。AI 分析、What-if 寫入、採購核准等仍由既有 Streamlit 版處理，尚未搬到 Vue。

## 其他模組的資料查詢 API（尚未顯示在 Vue）

`GET /api/data` 列出目前登入角色可讀取的資料項目，`GET /api/data/{模組}/{項目}?limit=50&offset=0` 取得資料。每次最多 100 筆；只能讀取程式明確列出的欄位和查詢，不能由請求自行組 SQL。API 涵蓋營運指標、商品／庫存／倉庫、採購、銷售、財務、人資、碳排、供應鏈事件，以及管理員的 AI/LINE 紀錄。營運指標使用與原看板相同的統計條件；其他資料以結構化欄位傳回，供後續 Vue 畫面串接。

例如 `inventory/products`、`procurement/purchase-orders`、`sales/orders`、`finance/ledger`、`hr/payroll`、`carbon/emissions`。資料項目完整清單以登入後的 `/api/data` 為準。沿用原本角色範圍：財務僅 admin；薪資僅 admin/hr；銷售僅 admin/sales；倉儲與採購一般查詢僅 admin/warehouse；風險資料仍需有效的 L1 capability。每次請求都重新解析身分，角色或 L1 授權撤銷後立即失效。這批 API 只有 GET，沒有新增、修改、刪除、核准或 AI 生成端點；Vue 也沒有新增選單或頁面。

在 `ERP_DEMO_MODE=true` 的獨立資料庫中，API 會替每個地圖據點建立一筆 `VUE-DEMO-` 開頭的未結虛構採購單，並加入一筆示範事件；各地區風險分數刻意拉開，方便比較與操作。畫面會標示這些是作業版虛構資料，不是 AI 即時判斷，也不代表採購單真的受影響。重啟不會重複新增，既有的熱圖更新紀錄不會被示範分數覆寫。關閉示範模式就不會建立這些資料，原專案資料庫也不會受影響。

## 不使用 Docker 的開發方式

先在獨立的 Python 虛擬環境安裝 `api/requirements.txt`，再設定獨立資料庫路徑及示範模式：

```powershell
$env:ERP_DB_PATH = "C:\path\to\vue-assignment.db"
$env:ERP_DEMO_MODE = "true"
python -m uvicorn api.main:app --reload --port 8001
```

第二個終端機執行：

```powershell
cd web
npm ci
npm run dev
```

Vite 開發伺服器會將 `/api` 轉送到 `127.0.0.1:8001`。正式容器由 Nginx 轉送到內部 API 服務。

## 驗證

```powershell
python -m pytest tests/test_vue_api.py -q
cd web
npm ci
npm run build
```

測試會檢查未登入拒絕、錯誤密碼拒絕、正確登入、取得 ERP 資料、每個據點都有示範採購單、示範風險分數有足夠差距、權限撤銷後立即拒絕，以及登出。手動測試時，在 `8514` 登入，用地圖上方的地區清單切換據點；每個地區都應顯示對應的未結採購單。點選供應商後，採購單還能依供應商篩選。此資料僅供展示，不要作為實際採購決策依據。
