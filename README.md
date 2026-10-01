# Vue + Docker 個人作業版：從下載到啟動

這是基於 [falltwo/AI-Risk-Based-Inventory-ERP](https://github.com/falltwo/AI-Risk-Based-Inventory-ERP)（MIT 授權）的獨立作業版。原本的 Streamlit 程式仍在 `app.py`；這一版另外提供 Vue 畫面、FastAPI API 與 Docker Compose。Docker 使用自己的 SQLite volume，不會連接原本 `data/erp.db`。原專案與個人作業版的開發、啟動方式互不影響。

> **公開程式碼 ≠ 已部署的公開網站。** 以下 Compose 以固定示範帳密建立測試資料，僅供自己電腦或受信任區網使用，**不可將 8514／8515 埠直接轉發至網際網路**。想讓任何人透過網址完整操作與使用 AI，仍須先完成 HTTPS、正式帳號與權限、每位訪客的資料隔離、資料庫持久化，以及 AI 金鑰和費用控管。GitHub Pages 無法執行這個 Python API。

## 架構

```
瀏覽器 → Vue/Nginx（一般模式 localhost:8514；LAN 模式本機完整入口 localhost:8515）→ FastAPI（容器內）→ 獨立 SQLite volume
```

- `web/`：Vue 3 風險總覽、各模組資料頁、常用操作表單及 AI 問答入口。
- `api/`：FastAPI，沿用現有 `backend/` 的資料與角色能力規則。每次請求重新查驗帳號及組織權限；只接受明確列出的操作，不提供任意 SQL。
- `compose.yaml`：啟動 `web` 和 `api` 兩個容器，並保存作業版專用資料庫。

## 第一次使用：Docker 啟動流程

先安裝 Git 與 Docker Desktop，開啟 Docker Desktop，確認它顯示執行中。在 **PowerShell** 依序執行：

```powershell
git clone https://github.com/evaeva12021202-sys/ai-risk-vue-docker.git
cd ai-risk-vue-docker
docker compose version
docker compose up --build -d
```

如果已經下載專案，直接在含 `compose.yaml` 的資料夾執行 `docker compose up --build -d` 即可，不需要再次 clone。

等候約數十秒，再檢查服務：

```powershell
docker compose ps
docker compose logs --tail=80 api
```

`api` 應顯示健康狀態；`web` 應持續運行。然後用**同一台電腦**的瀏覽器開啟 [http://127.0.0.1:8514/](http://127.0.0.1:8514/)。可用 `viewer / viewer` 看資料，或以 `admin / admin` 測試完整操作。這兩組是**虛構示範帳號，不是你個人 GitHub 的密碼**，請勿填入真實 ERP 資料。`8513` 保留給本機 Vite 預覽，與 Docker 版分開。

### 再次啟動、停止與更新

```powershell
docker compose up -d             # 下次開機後啟動
docker compose ps                # 看容器狀態
docker compose logs --tail=80 web # 看前端錯誤
docker compose logs --tail=80 api # 看後端錯誤
docker compose down              # 停止；保留作業資料庫
```

程式更新後，在此資料夾執行 `git pull` 和 `docker compose up --build -d`。`docker compose down` **不會**刪除 volume，既有資料仍在；不要加 `-v`，那會刪掉作業版資料庫。未設定 `API_SESSION_SECRET` 時，API 在啟動時產生隨機金鑰，重啟後需重新登入；要讓登入跨重啟維持有效，可在啟動前設定自己的長隨機字串。不要把金鑰提交到 Git。

如果 `8514` 打不開：先確認 Docker Desktop 正在執行、`docker compose ps` 的 `api` 是否 healthy、`8514` 是否已被其他程式占用，再看上面的 `logs`。在手機或別台電腦輸入 `127.0.0.1` 會連到**那台裝置自己**，不會連到你的電腦；同區網展示請看下一節。

## 限同一區網展示（可選）

一般啟動仍只開放本機。需要讓同一 Wi-Fi 的其他電腦觀看時，先用 `ipconfig` 找到這台電腦目前連線中的 Wi-Fi/乙太網路 IPv4 位址（不要用 WSL、VMware 的虛擬網卡），再於 PowerShell 啟動：

```powershell
$env:LAN_BIND_IP = "172.20.10.3"  # 範例；每次依 ipconfig 的實際位址更換
docker compose -f compose.yaml -f compose.lan.yaml up -d
```

同一區網的其他人開 `http://該IPv4位址:8514/`，使用 `viewer / viewer` 查看示範風險畫面。LAN 設定的 Nginx 只轉送登入、風險總覽與據點查詢 API；`/api/data`、`/api/actions`、`/api/ai` 一律回 403。本機完整測試入口是 `http://127.0.0.1:8515/`，可用 `admin / admin` 測試獨立作業版資料庫。這是 HTTP 區網展示，不適合公開上網或傳送真實資料。電腦和 Docker 必須持續開啟；若同網路仍連不上，先確認 Windows 防火牆、網路設定與 Wi-Fi 是否阻擋裝置間互連。不要為了測試而全面停用防火牆。

展示結束後回到僅本機模式：

```powershell
Remove-Item Env:LAN_BIND_IP -ErrorAction SilentlyContinue
docker compose up -d
```

這會重新建立 web 容器，但保留作業版專用資料庫 volume。

採購單依供應商主檔的國家與地區精確對應據點；這代表「可能需要檢查」，不代表已確認受到事件影響。資料庫沒有原預計交期欄位，因此畫面僅顯示下單日期及已有紀錄的預估延遲，不能推算承諾交期。

## 各模組資料查詢與操作

`GET /api/data` 列出目前登入角色可讀取的資料項目，`GET /api/data/{模組}/{項目}?limit=50&offset=0` 取得資料。每次最多 100 筆；只能讀取程式明確列出的欄位和查詢，不能由請求自行組 SQL。API 涵蓋營運指標、商品／庫存／倉庫、採購、銷售、財務、人資、碳排、供應鏈事件，以及管理員的 AI/LINE 紀錄。營運指標使用與原看板相同的統計條件；其他資料以結構化欄位傳回，供後續 Vue 畫面串接。

例如 `inventory/products`、`procurement/purchase-orders`、`sales/orders`、`finance/ledger`、`hr/payroll`、`carbon/emissions`。資料項目完整清單以登入後的 `/api/data` 為準。沿用原本角色範圍：財務僅 admin；薪資僅 admin/hr；銷售僅 admin/sales；倉儲與採購一般查詢僅 admin/warehouse；風險資料仍需有效的 L1 capability。每次請求都重新解析身分，角色或 L1 授權撤銷後立即失效。

`GET /api/actions` 列出可用表單，`POST /api/actions/{操作}` 執行本機作業版的明確操作；寫入需要同源登入 Cookie 與 `X-ERP-Action: vue-local` 標頭。現有操作包含新增商品、倉庫、供應商、報價、銷售單、收款、總帳、員工、薪資、出勤、碳係數、減碳目標、風險事件，以及庫存出入與訂單狀態更新。複合寫入使用單一交易，庫存不足或無權限時拒絕。這些操作只會修改 Docker 作業版的獨立資料庫。

`POST /api/ai/chat` 接原版 Agent 協調器與治理工具；`POST /api/ai/what-if` 接原版供應鏈情境分析。需要在啟動 Compose 前設定模型金鑰，例如 PowerShell 的 `$env:GEMINI_API_KEY = '你的金鑰'`；不要把金鑰提交到 Git。沒有金鑰時 API 回 503，畫面明確標示 AI 未啟用，不會輸出假分析。AI 工具的寫入仍經過原版 Tool Gateway 審批。

待審批項目現在可在 Vue 檢視；具有決策權限的角色可經原版 Gateway 核准或拒絕，提案人不能核准自己的提案。這仍是**分階段移植中**，不能稱為完整取代 Streamlit：採購提案建立與完整證據畫面、ERP 交換、AI 風險建議更新、CSV 匯入、圖表／報表下載與部分模組的進階編修尚未在 Vue 實作。原版仍保留在獨立的主專案工作目錄。

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

---

[原版 Streamlit 英文說明](README.streamlit.md) · [原版 Streamlit 繁體中文說明](README.zh.md)
