import json
import re
import time
import traceback
import uuid

from PIL import Image
from res import fetcher
from playwright.sync_api import sync_playwright, TimeoutError, Error


def auto_login(page, _user, _pwd):
    print("[Tip] 图形验证码需手动输入.")
    login_url = "https://u.unipus.cn/user/student"
    page.goto(login_url)

    page.locator('[name="username"]').fill(_user)
    page.locator('[name="password"]').fill(_pwd)
    page.locator('[type="checkbox"]').all()[1].click()
    page.locator(".btn.btn-login.btn-fill").click()

    print("[Tip] 出现安全验证不必担心, 手动认证即可.")
    page.wait_for_timeout(1000)

    try:
        page.wait_for_selector('#pw-captchaCode', timeout=800)
        page.eval_on_selector(
            '#pw-captchaCode',
            'el => el.placeholder = "PS:请手动输入图形验证码"'
        )
    except TimeoutError:
        return


def get_exercise(page):
    must_exe = []
    page.wait_for_selector(".icon-lianxi.iconfont")
    exercise = page.locator(".icon-lianxi.iconfont").all()
    for each in exercise:
        if each.locator(".iconfont").count():
            must_exe.append(each)
    return must_exe


def auto_answer(page, auto_mode):
    flag = False
    qids = fetcher.fetch_qid(page)
    if not qids:
        return not flag

    single_choice = ".questions--questionDefault-2XLzl.undefined"

    for qid in qids:
        page.wait_for_timeout(800)
        total_ques = page.query_selector_all(single_choice)
        answer = fetcher.fetch_ans(page, total=len(total_ques), qid=qid)
        rank = 0

        for ques in total_ques:
            if answer[rank]["isRight"] and ques.is_visible():
                choice = answer[rank]["choice"]
                try:
                    ques.wait_for_selector(f'input[value="{choice}"]').click(timeout=1500)
                except TimeoutError:
                    return "selected"
                rank += 1
            else:
                flag = True
                break

        if not auto_mode and qids.index(qid) == len(qids) - 1:
            break

        page.locator(".submit-bar-pc--btn-1_Xvo").all()[-1].click()

    if flag:
        if auto_mode:
            page.eval_on_selector(
                '.dialog-header-pc--dialog-header-2qsXD',
                'el => el.style.fontSize = "20px"'
            )
            page.eval_on_selector(
                '.dialog-header-pc--dialog-header-2qsXD',
                'el => el.innerHTML = "PS:&nbsp;&nbsp;&nbsp;存在不支持题型，本次答题不会提交"'
            )
            page.wait_for_timeout(1500)
        else:
            return flag

    return flag


def init_page():
    print("[Info] 正在启动浏览器 (Playwright Chromium)...")
    browser = p.chromium.launch(headless=False)

    context = browser.new_context()
    context.grant_permissions(['microphone', 'camera'])
    page = context.new_page()
    page.set_default_timeout(300000)

    print("[Info] 等待登录完成...")
    auto_login(page, user, pwd)

    page.wait_for_selector(".my_course_box")

    page.locator(".layui-layer-btn0").click()
    page.wait_for_event("popup").close()

    viewsize = page.evaluate(
        "() => ({ width: window.screen.availWidth, height: window.screen.availHeight })"
    )
    viewsize["height"] -= 50
    page.set_viewport_size(viewsize)

    return page


def auto_func():
    page = init_page()
    title_pattern = re.compile(r"[0-9]+?\.[0-9]+?.+")

    class_urls = [url for url in account["class_url"] if "unipus" in url]

    for class_url in class_urls:
        page.goto(class_url)

        course = page.wait_for_selector(
            ".cc_course_intro_text"
        ).text_content().strip()

        print(f"[Info] 当前课程: {course.splitlines()[0]}")

        page.wait_for_selector(".icon-bixiu.iconCustumStyle.iconfont")
        must_exe = get_exercise(page)

        for exe in must_exe:
            page.reload()
            page.wait_for_selector(".icon-bixiu.iconCustumStyle.iconfont")
            exe.click()

            if must_exe.index(exe) == 0:
                page.wait_for_selector(".iKnow").click()

            page.locator(".dialog-header-pc--close-yD7oN").click()

            flag = auto_answer(page, automode)

            try:
                if not flag:
                    head = page.wait_for_selector(
                        ".layoutHeaderStyle--menuList-Ef90e", timeout=1000
                    ).text_content()
                    title = re.findall(title_pattern, head)[0]
                    print(f"[Info] 获取 <<{title}>> 答案成功!")
            finally:
                      continue


if __name__ == '__main__':
    try:
        with open("account.json", "r", encoding="utf-8") as f:
            account = json.loads(f.read())
            user = account["username"].strip()
            pwd = account["password"].strip()
            automode = account["Automode"]
            key = account["Key"].strip()
            verified = fetcher.verify_key(key)

        print("[Tip] 目前只支持单选题作答!")
        print("===== Runtime Log =====")

        with sync_playwright() as p:
            if automode:
                print("[System] Automode active.")
                auto_func()
                print("所有课程已完成!!")
                input("按 Enter 退出程序...")
            else:
                print("[System] Assistmode active.")
                assist_func()

    except TimeoutError:
        print("[Error] 程序长时间无响应, 自动退出...")
    except Error:
        print("[Error] 浏览器已关闭!")
    except FileNotFoundError:
        print("[Error] 缺失依赖文件!")
    except Exception as e:
        print(f"[Error] {e}")
        if isinstance(e, KeyError):
            print("[Tip] account.json 配置可能有误")

        log = traceback.format_exc()
        with open("log.txt", "w", encoding="utf-8") as doc:
            doc.write(log)

        print("[Info] 错误日志已保存至 log.txt")
    finally:
        time.sleep(1.5)
