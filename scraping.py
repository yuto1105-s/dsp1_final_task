import requests
from bs4 import BeautifulSoup
import time
import sqlite3
from pathlib import Path

# Googleのプロフィールに掲載されているリポジトリ一覧を取得する（全件ではない）
url = "https://github.com/google?tab=repositories"

res = requests.get(url, timeout=30)
time.sleep(1)  # サーバーに負荷をかけないための遅延（課題の指定）

print(f"ステータスコード：{res.status_code}")
print(f"ステータスメッセージ：{res.reason}")
res.raise_for_status()  # 通信に失敗した場合は処理を止める

# HTMLのソースコードをBeautifulSoupオブジェクトに変換する処理
html_soup = BeautifulSoup(res.content, 'html.parser')
print(f"html_soupの型：{type(html_soup)}")

# ----- 指定したタグ・属性で要素を検索する ------- #
# ページ全体ではなく、Googleのリポジトリ一覧の中だけを検索する
repo_list = html_soup.find(id='org-repositories')
if repo_list is None:
    raise ValueError('リポジトリ一覧が見つかりません。GitHubのHTMLを確認してください。')

repositories = []
for repo in repo_list.find_all('li', class_='Box-row'):
    # 1件ずつ検索すると、名前・言語・スター数の対応がずれない
    name_tag = repo.find('a', attrs={'itemprop': 'name codeRepository'})
    language_tag = repo.find('span', attrs={'itemprop': 'programmingLanguage'})
    if name_tag is None:
        raise ValueError('リポジトリ名が見つかりません。HTMLを確認してください。')

    name = name_tag.get_text(strip=True)
    language = language_tag.get_text(strip=True) if language_tag else '未設定'
    stars_tag = repo.find('a', attrs={'href': name_tag['href'] + '/stargazers'})
    if stars_tag is None:
        raise ValueError(f'{name}のスター数が見つかりません。HTMLを確認してください。')
    # 例：'7,268' → '7268' → 整数7268
    stars = int(stars_tag.get_text(strip=True).replace(',', ''))
    repositories.append((name, language, stars))

if not repositories:
    raise ValueError('取得件数が0件です。GitHubのHTMLを確認してください。')

# ----- DBを作成し、取得したデータを保存する ------- #
# VSCodeでどのフォルダから実行しても、このコードと同じ場所に保存する
db_path = Path(__file__).with_name('google_repositories.db')
# 1. DBに接続する（ファイルが存在しなければ新しく作られる）
con = sqlite3.connect(db_path)
try:
    # 2. SQLを実行するためのカーソルを取得する
    cur = con.cursor()

    # 3. SQLを変数に用意する
    sql_create_table = """
        CREATE TABLE IF NOT EXISTS repositories (
            name TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            stars INTEGER NOT NULL CHECK (stars >= 0)
        )
    """
    sql_insert_many = """
        INSERT INTO repositories (name, language, stars) VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            language = excluded.language,
            stars = excluded.stars
    """
    sql_select = 'SELECT name, language, stars FROM repositories ORDER BY stars DESC, name'

    # 4. SQLを実行する
    cur.execute(sql_create_table)
    # 授業のcars_listの代わりに、スクレイピング結果のrepositoriesを渡す
    # 同じ名前があれば言語とスター数を更新する（再実行しても重複させない）
    cur.executemany(sql_insert_many, repositories)

    # 5. コミットして保存を確定する
    con.commit()

    # ----- 保存したデータをSELECT文で表示する ------- #
    cur.execute(sql_select)
    print('\nリポジトリ名 / 主要な言語 / スター数')
    for name, language, stars in cur:
        print(f'{name} / {language} / {stars}')

except sqlite3.Error as e:
    con.rollback()  # 保存が確定していない変更を取り消す
    print('データベース処理でエラーが発生しました。')
    print(e)
    raise  # エラーがあった場合は成功表示に進まず終了する

finally:
    # 6. エラーの有無にかかわらずDBへの接続を閉じる
    con.close()

print(f'\n今回の取得件数：{len(repositories)}件（プロフィールの一覧掲載分）')
print(f'保存先：{db_path}')
