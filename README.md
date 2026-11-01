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
    characters: [gray, tabby]      # 出場角色（cast.yaml 裡的代號）
    scene: Gray Cat and Tabby Cat building a sandcastle at the beach.
    age: "6-9"                     # 選填，覆寫整本書的年齡
    provider: openai               # 選填，這頁改用別家
    notes: make the sandcastle bigger   # 選填，額外指示
    use: 2                         # 選填，指定使用第幾版
```

## 規格檢查（report.txt）

- `✗` 錯誤：上傳 KDP 會被退件（頁數不足 24、尺寸不對、字型未內嵌等），必須修正。
- `!` 警告：品質風險（線條太細或太粗、太小的塗色區、內容碰到邊緣、疑似灰階）。請看 preview.png 自行判斷。

## 上架前提醒

- KDP 上架時，AI 生成的內頁與封面圖片必須勾選 AI 生成內容揭露。
- cover.pdf 是黑白校樣用的簡易封面，尺寸已依頁數算好；正式彩色封面可依 report.txt 的尺寸另外設計。
- 正式出版前先訂一本實體校樣書。
