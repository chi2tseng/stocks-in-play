from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        print("正在連接到本地的 Chrome...")
        try:
            # 連接本地已開啟除錯模式的 Chrome
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print("連線失敗！請確認您已完全關閉 Chrome，並使用 --remote-debugging-port=9222 參數重新啟動。")
            print(f"詳細錯誤: {e}")
            return

        # 獲取預設的瀏覽器上下文 (Context) 並開新分頁
        context = browser.contexts[0]
        page = context.new_page()

        print("正在前往活動頁面...")
        page.goto("https://pickapropfirm.com/giveaways/")
        
        # 等待網頁載入
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        print("開始自動填寫表單資料...")
        try:
            # 填寫姓名 (Name)
            name_input = page.locator("input[name*='name' i], input[placeholder*='name' i]").first
            if name_input.is_visible():
                name_input.fill("Keith Tseng")
                print(" -> 姓名已填寫")

            # 填寫信箱 (Email)
            email_input = page.locator("input[type='email'], input[name*='email' i]").first
            if email_input.is_visible():
                email_input.fill("chi4tseng@gmail.com")
                print(" -> Email已填寫")

            # 填寫國家 (Country)
            country_input = page.locator("input[name*='country' i], select[name*='country' i]").first
            if country_input.is_visible():
                is_select = country_input.evaluate("el => el.tagName === 'SELECT'")
                if is_select:
                    country_input.select_option(label="Japan")
                else:
                    country_input.fill("Japan")
                print(" -> 國家已填寫")

            print("\n✅ 基本資料填寫完畢！正在嘗試點擊送出按鈕...")
            
            # 嘗試點擊送出按鈕 (Enter Giveaway 或 Submit)
            submit_btn = page.locator("button[type='submit'], input[type='submit'], button:has-text('Enter Giveaway'), button:has-text('Submit'), a:has-text('Enter Giveaway')").first
            if submit_btn.is_visible():
                submit_btn.click()
                print(" -> 已點擊送出按鈕！等待網頁跳轉或成功提示...")
                page.wait_for_timeout(5000)
            else:
                print(" -> ⚠️ 畫面上找不到明顯的送出按鈕，可能需要您手動點選。")

        except Exception as e:
            print(f"\n⚠️ 填寫或送出過程中發生例外狀況: {e}")

        # 關閉這個分頁，不關閉整個瀏覽器
        page.close()
        print("\n[任務完成] 腳本執行結束。")

if __name__ == "__main__":
    run()
