# Coloring Book Studio

兒童著色本工具：角色設定 → 逐頁生圖（API 或手動）→ 清理成純黑白 → 轉向量 → 排成 Amazon KDP 規格的內頁與封面 → 自動規格檢查。

## 資料夾

```
characters/<角色組>/cast.yaml      角色外觀描述 + 參考圖（每次生圖都會附上）
books/<書名>/book.yaml             這本書的設定與每一頁的場景
books/<書名>/raw/                  每頁的原圖，多次生成會變成 p01_v1、p01_v2 …
books/<書名>/out/                  產出：interior.pdf、cover.pdf、preview.png、report.txt
cbs/config.py                      KDP 規格、年齡預設、提示詞規則、AI 模型名稱
```

`clean/`、`vector/`、`out/` 都可以隨時重新產生，所以不會上傳到 GitHub。

## 第一次在 Mac 上安裝（只做一次）

打開「終端機」，逐行貼上：

```bash
brew install potrace git python          # 沒有 Homebrew 請先到 https://brew.sh 安裝
cd ~/Documents
git clone https://github.com/LukeHsiao-YC/coloring-book-studio.git
cd coloring-book-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
open -e .env                             # 填入 GEMINI_API_KEY / OPENAI_API_KEY 後存檔
```

- Gemini 金鑰：https://aistudio.google.com/apikey （要開啟 Billing 才能用圖像模型）
- OpenAI 金鑰：https://platform.openai.com/api-keys
- `.env` 只存在你的電腦，不會上傳。

之後每次使用前：`cd ~/Documents/coloring-book-studio && source .venv/bin/activate`

## 指令

| 指令 | 用途 |
|---|---|
| `python3 -m cbs new <書名> --age 3-5` | 建立新書 |
| `python3 -m cbs gen <書名>` | 用 API 生成所有頁面（加 `--missing` 只補沒圖的頁） |
| `python3 -m cbs gen <書名> p05 --provider openai` | 只重畫第 5 頁，改用 OpenAI |
| `python3 -m cbs prompt <書名> p05` | 印出完整提示詞，貼到 Gemini / ChatGPT 網頁手動生圖 |
| `python3 -m cbs import <書名> p05 ~/Downloads/xxx.png` | 匯入手動生成的圖 |
| `python3 -m cbs status <書名>` | 每頁有哪些版本、目前用哪一版 |
| `python3 -m cbs build <書名>` | 清理、向量化、排版、封面、規格檢查 |

## 兩種生圖流程

**A. 自動（在 Mac 上）**：`gen` 直接呼叫 API，圖存進 `raw/`。
**B. 手動（任何地方）**：用 `prompt` 取得提示詞，連同 `characters/cats/` 的兩張參考圖貼到 Gemini 或 ChatGPT 網頁版，下載後用 `import` 匯入（或直接上傳給 Claude）。

不滿意某頁：再生一次就會多一個版本。想用舊版，在 book.yaml 那一頁加 `use: 1`。

## book.yaml 每頁可設定的欄位

```yaml
  - id: p05
    characters: [小黑, 小黃]      # 出場角色（cast.yaml 裡的代號）
    scene: Xiao Hei and Xiao Huang building a sandcastle at the beach.
    age: "6-9"                     # 選填，覆寫整本書的年齡
    provider: openai               # 選填，這頁改用別家
    notes: make the sandcastle bigger   # 選填，額外指示
    use: 2                         # 選填，指定使用第幾版
```

## 活動頁（程式產生，不用生圖）

在 book.yaml 的頁面加上 `type:` 就會變成活動頁：

| type | 內容 | 常用設定 |
|---|---|---|
| `maze` | 迷宮，起點放角色、終點放圖案 | `start: 小黃`、`goal: tree / tent / house / flower / ball`、`rows`、`cols`、`seed` |
| `tracing` | 描寫英文字，下方有書寫線 | `words: [DRAW, READ]`（最多 5 個） |
| `dot_to_dot` | 連連看 | `shape: star / heart / tent / house / fish`、`icon: 小白` |
| `spot_difference` | 找不同：從一張著色頁拿掉幾個小物件。每次 build 會產生 `out/<頁碼>_candidates.png`，把可拿掉的物件編號標出來 | `source: p07`、`remove: [5, 20, 22]`（照編號人工挑選，建議用這個）；不寫 remove 時自動挑：`count`、`scene_max`（背景物件最多幾個，預設 1）、`seed` |
| `plan` | 週末計畫表＋想嘗試的活動勾選清單 | `days`、`slots`、`ideas` |
| `draw` | 自由畫框＋書寫句 | `lines: ["My favorite activity is"]` |
| `challenge` | 一週挑戰表，每天塗一顆星 | `text`、`days` |

每頁都可以設 `title:`。迷宮和找不同的解答會自動放在書末（`answers: false` 可關閉）。
背面空白頁預設印一行防透色提示（`back_page: blank` 可改成純白）。

`report.txt` 最後有定價試算。印刷成本在 `cbs/config.py` 的 `PRINT_FIXED_USD`，上傳 KDP 後請用官方計算機核對並更新。

## 雙版本：英文版與雙語注音版

book.yaml 的 `editions:` 決定要輸出哪些版本，`build` 會分別輸出到 `out/en/` 和 `out/zh/`：

```yaml
editions:
  en:
    title: "What Shall We Do This Weekend?"
  zh:
    title_zh: "週末做什麼？"
    title: "What Shall We Do This Weekend?"
```

- 著色頁的文字：`text_en: [第一行, 第二行]`、`text_zh: [第一行, 第二行]`
- 活動頁：`title` / `title_zh`、`text` / `text_zh`、`ideas` / `ideas_zh`、`lines` / `lines_zh`
- 注音由程式自動標在每個字右邊（台灣課本格式），字型是可商用的 jf 粉圓體（`fonts/`，SIL OFL）。
- 「一」「不」統一標本調。
- 自動標錯的字詞寫進 `zhuyin:`，例如 `音樂: "ㄧㄣ ㄩㄝˋ"`（每個字一組，用空白分開）。
- 每次 build 會產生 `out/zh/zhuyin_check.md` 校對表：⚠ 是要特別確認的字，✎ 是已人工修正的字。

注意：KDP 平裝本不支援把書的語言設成繁體中文，雙語版上架時語言選英文。

## 規格檢查（report.txt）

- `✗` 錯誤：上傳 KDP 會被退件（頁數不足 24、尺寸不對、字型未內嵌等），必須修正。
- `!` 警告：品質風險（線條太細或太粗、太小的塗色區、內容碰到邊緣、疑似灰階）。請看 preview.png 自行判斷。

## 上架前提醒

- KDP 上架時，AI 生成的內頁與封面圖片必須勾選 AI 生成內容揭露。
- cover.pdf 是黑白校樣用的簡易封面，尺寸已依頁數算好；正式彩色封面可依 report.txt 的尺寸另外設計。
- 正式出版前先訂一本實體校樣書。
