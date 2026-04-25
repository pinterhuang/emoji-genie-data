# emoji-genie-data

> 表情精靈 Android App 的雲端顏文字資料庫。透過 jsDelivr CDN 即時派送到所有用戶。

## 這個 repo 在做什麼

App 內建約 400+ 顏文字（包在 APK 裡，永久不變）。這份 repo 是「**追加包**」：

- 你在這裡新增的顏文字 / 分類，App 透過 OTA 拉取後會自動合併進輸入法面板
- 不需要更新 App、不需要送審 Google Play
- 修改 `kaomoji-bundle.json` → push 到 main → 全世界用戶下次開 App 就看得到（最快 24 小時內）

## CDN URL

```
https://cdn.jsdelivr.net/gh/pinterhuang/emoji-genie-data@main/kaomoji-bundle.json
```

App 端 `RemoteUpdater.REMOTE_URL` 已指向此網址。

## 如何新增顏文字

### 方式 A：直接在 GitHub 編輯（推薦給非工程師）

1. 點 [kaomoji-bundle.json](./kaomoji-bundle.json) → 鉛筆圖示
2. 在 `kaomojis` 陣列尾端加一筆：
   ```json
   { "id": "h200", "t": "(´｡• ᵕ •｡`)", "c": "happy", "k": ["可愛", "微笑"] }
   ```
3. **id 規則**：分類首字母 + 三位數遞增（如 `h200`、`c150`、`fest010`）。**永遠不要重用 id**，否則用戶的釘選 / 使用統計會錯亂。
4. Commit → 開 PR
5. CI 跑過 → 合併 → 機器人會自動 bump version 並 purge CDN 快取

### 方式 B：本機編輯

```bash
git clone git@github.com:pinterhuang/emoji-genie-data.git
cd emoji-genie-data
# 編輯 kaomoji-bundle.json
node scripts/validate.js     # 本機驗證
git commit -m "feat: 新增春節顏文字 5 筆"
git push origin main
```

## 資料格式

完整 schema 見 [schema.json](./schema.json)。簡述：

```jsonc
{
  "version": 2,                    // 整數，每次發布遞增（CI 自動處理）
  "publishedAt": "2026-04-25",     // 人類可讀日期
  "categories": [
    { "id": "happy", "name": "開心", "icon": "😊", "order": 1 }
  ],
  "kaomojis": [
    {
      "id": "h001",                // 穩定 ID，跨版本不變
      "t": "(╹◡╹)",                 // 顏文字本體
      "c": "happy",                 // 必須對應到 categories 內的 id
      "k": ["開心", "微笑"]          // 中文搜尋標籤（可省略）
    }
  ]
}
```

### 新增分類

如果現有 25 個分類涵蓋不到，可以新增：

```json
{ "id": "weather", "name": "天氣", "icon": "☀️", "order": 27 }
```

App 端會自動把新分類加到 Settings → 分類顯示，使用者可以選擇要不要顯示。

## 版本機制

- 每次 push 到 `main` 且 `kaomoji-bundle.json` 有變動 → GitHub Actions 自動把 `version` +1，commit + 打 tag（`v3`、`v4`、…）
- App 端比對：只有「遠端版本 > 本機已快取版本」才下載並合併
- 需要立刻看到新內容？clean install / 清除 App 資料即可

## CDN 快取行為

jsDelivr 對 `@main` 分支預設快取 12–24 小時。若要立刻刷新：

- Actions 已在每次 release 自動 call `https://purge.jsdelivr.net/gh/pinterhuang/emoji-genie-data@main/kaomoji-bundle.json`（best effort）
- 要更穩可改用 tag 版本：把 App 端 URL 改成 `@v3` 之類的固定 tag，每次 release 同步推 App 端常數（較重，視需求採用）

## 本機開發

```bash
node scripts/validate.js                  # 驗證 bundle
node scripts/bump-version.js              # 手動 bump（一般 CI 自動）
python3 scripts/build-mega-bundle.py      # 從 GitHub 資料源重建（首次/大刷新用）
```

JS scripts 零依賴；`build-mega-bundle.py` 需要 Python 3 + 預先下載 `/tmp/emoticon_dict.json` 與 `/tmp/kao-utf8.json`（見 script 內註解）。

## 自動週更機制

整個 `kaomoji-bundle.json` 包含 **62,430 筆**：

- **9,375 筆**：`availableFrom` 未設置 → App 啟動就看得到
- **53,055 筆**：每筆都標記了 `availableFrom: YYYY-MM-DD` → App 端比對「今天 ≥ availableFrom」才顯示

排程細節：
- 起始日：產出 bundle 後的下一個週一
- 週期：每週週一解鎖一批
- 數量：平均每週約 102 筆，跨類別均衡分佈
- 跨度：520 週（10 年）

**你不需要做月度釋出 / 週度釋出 / 任何手動操作**。一次性產生這份 bundle、push 到 GitHub，App 用戶就會自動看到內容隨時間滴入。

要重新洗牌排程（例如改變起始日、改回月更、加入節日定向）只要重新跑 `build-mega-bundle.py` 並 commit 即可。

## 授權

- **資料內容**（顏文字本身）：[CC0 1.0 Universal](./LICENSE)（公眾領域貢獻）
- **scripts、schema、文件**：MIT

顏文字本質上是短表達創作，多數已進入公眾領域；CC0 確保任何人都可以無顧慮地使用、混合、再發布這份資料。

## 相關連結

- 主要 App repo：（Banscheng 內部）
- 開發者：阪誠網通有限公司 · pinter.tw@gmail.com
