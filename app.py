from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import timedelta, datetime
from bson import ObjectId  # ObjectId를 사용하기 위해 추가
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pymongo
from flask import redirect, url_for, flash

##################################################
# Flask 애플리케이션 생성 및 기본 설정
##################################################
app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY"  # 세션 암호화용 키 (실서비스에서는 안전한 값으로 교체)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
# session.permanent = True 로 설정 시 30분 후 자동 만료

##################################################
# MongoDB 연결 (예: 로컬 또는 Atlas)
##################################################
# 여기서는 로컬 MongoDB를 예시로 사용
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["sundaydb"]          # 데이터베이스 이름
users_collection = db["users"]      # 유저 정보를 저장할 컬렉션
restaurants_collection = db["restaurants"]  # 식당 정보 저장할 컬렉션
menus_collection = db["menus"] # 추천메뉴 저장할 컬렉션


##################################################
# Selenium 설정
##################################################
# driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
# options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # GUI 없이 실행


##################################################
# 1) 첫 페이지(로그인 페이지) - GET/POST
##################################################
@app.route("/", methods=["GET", "POST"])
def login():
    """
    - GET: 로그인 화면 렌더링
    - POST: ID/PW 확인
      1) DB에 ID가 없으면 => alert("ID가 없습니다. 회원가입 해주세요.");
         확인 후 로그인 화면(빈칸)
      2) PW가 틀리면 => alert("PW가 틀립니다.");
         확인 후 로그인화면(ID 유지, PW만 비움)
      3) 로그인 성공 => session 저장 후 main 페이지로 이동
    """
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        # DB에서 해당 email 찾기
        user_data = users_collection.find_one({"email": email})

        if not user_data:
            # ID가 존재하지 않을 때
            return """
            <script>
              alert("이메일이 존재하지 않습니다. 회원가입 해주세요.");
              window.location.href = "/";
            </script>
            """
        else:
            # ID가 존재 → PW 비교
            if user_data.get("password") != password:
                # PW 틀림
                return f"""
                <script>
                  alert("비밀번호가 틀립니다.");
                  window.location.href = "/?retain_email={email}";
                </script>
                """
            else:
                # 로그인 성공
                session.clear()
                session.permanent = True  
                session["_id"] = str(user_data.get("_id"))  
                session["email"] = email
                session["campnum"] = user_data.get("campnum")  # 교번 세션 저장
                return redirect(url_for("main"))

    else:
        # GET 요청 → 로그인 페이지 렌더링
        retain_email = request.args.get("retain_email", "")
        return render_template("login.html", retain_email=retain_email)

##################################################
# 2) 회원가입 페이지 - GET/POST
##################################################
@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    - GET: 회원가입 화면 렌더링
    - POST: 입력받은 ID/PW 체크
      1) 이미 존재하는 ID => alert("이미 존재하는 ID입니다.");
         입력값 유지 후 회원가입 화면 다시
      2) 비밀번호 / 비밀번호 확인 불일치 => alert("비밀번호가 동일하지 않습니다.");
         비밀번호만 지우고 다시 회원가입 화면
      3) 성공 => DB에 저장 후 => alert("회원가입이 완료되었습니다!") => 로그인 페이지로
    """
    if request.method == "POST":
        email = request.form.get("email", "")
        campnum = request.form.get("campnum", "")
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # 1) ID 중복 확인
        existing_user = users_collection.find_one({"email": email})
        if existing_user:
            return f"""
            <script>
              alert("이미 존재하는 이메일입니다.");
              window.location.href = "/signup?retain_email={email}";
            </script>
            """

        # ✅ 교번 중복 체크 (고유한 번호이므로 중복 불가)
        existing_campnum = users_collection.find_one({"campnum": campnum})
        if existing_campnum:
            return f"""
            <script>
              alert("이미 존재하는 교번입니다.");
              window.location.href = "/signup?retain_email={email}&retain_campnum={campnum}";
            </script>
            """

        # 2) 비밀번호/확인 불일치
        if password != password_confirm:
            return f"""
            <script>
              alert("비밀번호가 동일하지 않습니다.");
              // ID는 유지하고, PW만 빈칸으로
              window.location.href = "/signup?retain_email={email}&retain_campnum={campnum}";

            </script>
            """

        # 위 조건을 통과하면 DB에 새 유저 정보 저장
        new_user = {
            "email": email,
            "campnum": campnum,
            "password": password
        }
        users_collection.insert_one(new_user)

        # 가입 완료 → 로그인 페이지로 리다이렉트
        # return """
        # <script>
        #   alert("회원가입이 완료되었습니다! 로그인 화면으로 이동합니다.");
        #   window.location.replace("/");
        # </script>
        # """
        flash("회원가입이 완료되었습니다! 로그인하세요.")  # 로그인 페이지에서 알림 띄우기
        return redirect(url_for("login"))

    else:
        # GET 요청 → 회원가입 페이지 렌더링
        retain_email = request.args.get("retain_email", "")
        retain_campnum = request.args.get("retain_campnum", "")
        return render_template("signup.html", retain_email=retain_email, retain_campnum=retain_campnum)

##################################################
# 3) 메인 페이지 (로그인 성공 후)
##################################################
@app.route("/list")
def main():
    """
    로그인 성공 시 이동하는 메인 페이지
    - session["_id"] = MongoDB의 _id 문자열 (user 식별자)
    - session["user_id"] = 사용자가 입력한 ID
    - 30분 세션 만료 설정
    """
    if "_id" not in session:
        # 세션 만료 혹은 로그인 안 된 경우 → 로그인 화면으로
        return redirect(url_for("login"))
    
    category = request.args.get("category", "전체")  # 기본값 "전체"
    categories = ["전체", "치킨", "한식", "카페/디저트", "중식", "버거/샌드위치", "분식", "회/초밥", "일식/돈가스", "기타"]
    query = {} if category == "전체" else {"category": category}

    restaurants = list(restaurants_collection.find(query, {"_id": 0}).limit(6))  # ObjectId 제거

    return render_template("main.html", restaurants=restaurants, selected_category=category, categories=categories)
##################################################
# 3 - 1 무한스크롤!!
##################################################
@app.route("/list/infinite")
def get_restaurants():
    """
    음식점 목록을 JSON으로 반환하는 API
    """

    if "_id" not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401  # 401 Unauthorized 응답

    try:
        category = request.args.get("category", "전체")  # 기본값 "전체"
        query = {} if category == "전체" else {"category": category}

        offset = int(request.args.get('offset'))
        limit = int(request.args.get('limit'))

        restaurants = list(restaurants_collection.find(query, {"_id": 0}).skip(offset).limit(limit))
        for restaurant in restaurants:
            restaurant["restaurant_id"] = str(restaurant["restaurant_id"])  # 변환 처리
        print(restaurants)
        return jsonify({"restaurants": restaurants})  # JSON 응답

        # print("식당", len(restaurants))
        # return jsonify({"restaurants": restaurants})  # 정상 JSON 반환

    except Exception as e:
        print(f"서버 오류: {str(e)}")  # 터미널에서 오류 로그 확인
        return jsonify({"error": "서버 내부 오류"}), 500

##################################################
# 4) 로그아웃
##################################################
@app.route("/logout")
def logout():
    """
    - 세션을 비우고 로그인 페이지로 이동
    - 30분 자동 로그아웃도 적용됨 (세션 유지 시간 설정)
    """
    session.clear()  # 세션 삭제
    
    # 로그아웃 메시지를 Flash 메시지로 추가할 수도 있음 (선택 사항)
    flash("로그아웃 되었습니다. 다시 로그인 해주세요.", "info")

    return redirect(url_for("login"))  # 로그인 페이지로 이동

##################################################
# 5) 레스토랑 좋아요 기능
##################################################
@app.route("/like/<restaurant_id>", methods=["POST"])
def like_restaurant(restaurant_id):
    if "_id" not in session:
        return redirect(url_for("login"))
    
    restaurant = restaurants_collection.find_one({"restaurant_id": ObjectId(restaurant_id)})
    
    if not restaurant:
        return redirect(url_for("login"))
    
    # 좋아요 수만 증가
    restaurants_collection.update_one(
        {"restaurant_id": ObjectId(restaurant_id)},
        {"$inc": {"likes": 1}}
    )
    
    return redirect(url_for("main"))

##################################################
# 6) 추천메뉴 삽입 기능
##################################################

@app.route('/add_menu', methods=['POST'])
def add_menu():
    restaurant_name = request.form.get('restaurant_name')
    menu_name = request.form.get('menu_name')
    print("Restaurant Name:", restaurant_name)  # restaurant_name 값
    print("Menu Name:", menu_name)  # 입력된 메뉴 이름 값

    # restaurants_collection 에서 restaurant_name 와 같은 것에 menu 를 푸시
     # restaurant_name으로 해당 식당 찾기
    restaurant = restaurants_collection.find_one({"name": restaurant_name})

    if restaurant:
        # menus 배열의 0번째 위치에 새로운 메뉴 추가 (앞에 추가)
        restaurants_collection.update_one(
            {"name": restaurant_name},
            {"$push": {"menus": {"$each": [menu_name], "$position": 0, "$slice": 3}}}
        )
        print(f"'{menu_name}'을(를) '{restaurant_name}'의 첫 번째 메뉴로 추가했습니다.")
    else:
        print("해당 식당을 찾을 수 없습니다.")

    return redirect(url_for('main'))


##################################################
# 6) 네이버 지도 링크 받고 Parsing
##################################################
@app.route('/register', methods=['POST'])
def get_naver_url():
    naver_url = request.form.get('naver_url')
    category = request.form.get('category') # 사용자 지정 카테고리

    print(f"Received category: {category}")
    print(f"Received naver_url: {naver_url}")
    parse_url(naver_url, category)

    
    return redirect(url_for('main'))  # 다른 페이지로 리디렉션하거나 결과를 처리


# WebDriver 인스턴스 생성 함수
def initialize_driver():
    # 새로운 WebDriver 세션 시작
    driver = webdriver.Chrome()
    return driver

#  실제 parsing 함수
def parse_url(url, category):
    driver = initialize_driver()  # 새로운 driver 인스턴스를 생성

    start_time = time.time()  # 크롤링 시작 시간 기록
    
    driver.get(url)
    time.sleep(1)

    # iframe 요소 찾기
    try:
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "entryIframe"))  # iframe ID로 찾기
        )
        driver.switch_to.frame(iframe)  # iframe으로 전환
        print("iframe 내부로 이동 완료")
    except Exception as e:
        print("iframe을 찾을 수 없습니다:", e)

    ## 가게이름
    try:
        shop_name = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "GHAhO"))
        )
        print("가게 이름:", shop_name.text)  # 가게 이름 출력
    except Exception as e:
        print("가게 이름 찾을 수 없음", e)
        
    ## 주소
    try:
        address = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "LDgIH"))
        )
        print("주소 : ", address.text)
    except Exception as e:
        print("주소 찾을 수 없음")


    ## 해시태그
    try:
        hashtag = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "lnJFt"))
        )
        print("해시태그 : ", hashtag.text)
    except Exception as e:
        print("해시태그 찾을 수 없음")

    # 이미지 url
    try:
        # 'fNygA' 클래스의 div 요소 찾기
        div_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fNygA"))
        )
        
        # 해당 div 안에서 img 태그 찾기
        img_element = div_element.find_element(By.TAG_NAME, "img")
        
        # 이미지 src 속성 추출
        img_src = img_element.get_attribute("src")
        print("이미지 src: ", img_src)
        
    except Exception as e:
        print("이미지 찾을 수 없음:", e)

    restaurant_data = {
        "restaurant_id": ObjectId(),
        "name": shop_name.text,
        "address": address.text,
        "category": category,  # 카테고리는 수집된 카테고리 값으로 설정
        "naver_url": url,  # 입력된 네이버 URL
        "likes": 0,  # 좋아요 수는 크롤링 시점에서 수집할 수 없다면 0으로 기본값 설정
        "description": "설명 없음",  # 설명도 크롤링하거나 입력된 값으로 설정
        "image_url": img_src,  # 크롤링된 이미지 URL
        "menus": []  # 메뉴 정보는 수집되지 않으므로 기본 빈 리스트
    }
        
    restaurants_collection.insert_one(restaurant_data)

    # WebDriver 종료
    driver.quit()
    
    end_time = time.time()  # 크롤링 종료 시간 기록
    crawling_time = end_time - start_time  # 소요 시간 계산
    print(f"크롤링 소요 시간: {crawling_time:.2f} 초")

##################################################
# MOCKDATA 삽입
##################################################

# restaurants_collection.drop()  # 기존 컬렉션 삭제
#menus_collection.drop() # 기존 메뉴 컬렉션 삭제 

test_data = [
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d11"),
        "name": "김밥천국",
        "address": "서울특별시 강남구 테헤란로 123",
        "category": "한식",
        "naver_url": "https://map.naver.com/v5/entry/place/123456",
        "likes": 120,
        "description": "저렴하고 다양한 한식 메뉴를 제공하는 분식집",
        "image_url": "https://example.com/images/kimbap.jpg",
        "menus": ["김밥", "어묵", "떡볶이"]
    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d12"),
        "name": "짜장명가",
        "address": "서울특별시 마포구 양화로 456",
        "category": "중식",
        "naver_url": "https://map.naver.com/v5/entry/place/654321",
        "likes": 200,
        "description": "정통 짜장면과 탕수육이 인기 있는 중식당",
        "image_url": "https://example.com/images/jajangmyeon.jpg",
        "menus": ["짜장", "짬뽕"]

    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d13"),
        "name": "스시야",
        "address": "부산광역시 해운대구 해운대로 789",
        "category": "일식/돈가스",
        "naver_url": "https://map.naver.com/v5/entry/place/789123",
        "likes": 300,
        "description": "싱싱한 회와 스시를 제공하는 일본식 초밥 전문점",
        "image_url": "https://example.com/images/sushi.jpg",
        "menus": ["고등어", "참치"]

    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d14"),
        "name": "미스터 피자",
        "address": "대구광역시 중구 중앙대로 321",
        "category": "기타",
        "naver_url": "https://map.naver.com/v5/entry/place/321789",
        "likes": 150,
        "description": "다양한 토핑과 수제 도우가 특징인 피자 전문점",
        "image_url": "https://example.com/images/pizza.jpg",
        "menus": []

    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d15"),
        "name": "육쌈냉면",
        "address": "서울특별시 종로구 종로3가 12",
        "category": "한식",
        "naver_url": "https://map.naver.com/v5/entry/place/987654",
        "likes": 180,
        "description": "숯불 고기와 함께 먹는 냉면 전문점",
        "image_url": "https://example.com/images/naengmyeon.jpg",
        "menus": ["냉면"]

    }
]

test_menu_data = [
    {
        "menu_id": 1,
        "restaurant_id" : ObjectId("650f0c1e8a3b4a2d4c8e7d15"),
        "user_id": 'test1',
        "name": "육쌈냉면",
        "menu_name": '냉면',
        "datetime": datetime.utcnow()
    },
    {
        "menu_id": 2,
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d15"),
        "user_id": 'test2',
        "name": "육쌈냉면",
        "menu_name": '갈비',
        "datetime": datetime.utcnow() + timedelta(minutes=1)
    },
    {
        "menu_id": 3,
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d15"),
        "user_id": 'test3',
        "name": "육쌈냉면",
        "menu_name": '냉면2',
        "datetime": datetime.utcnow() + timedelta(minutes=2)
    },
    {
        "menu_id": 4,
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d12"),
        "user_id": 'test3',
        "name": "짜장명가",
        "menu_name": '짜장면',
        "datetime": datetime.utcnow() + timedelta(minutes=3)
    },
    {
        "menu_id": 5,
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d12"),
        "user_id": 'test3',
        "name": "짜장명가",
        "menu_name": '짬뽕',
        "datetime": datetime.utcnow() + timedelta(minutes=4)
    },
]


# MongoDB에 데이터 삽입 (중복 방지: 같은 restaurant_id가 있는 경우 삽입 안 함)
for data in test_data:
    if not restaurants_collection.find_one({"restaurant_id": data["restaurant_id"]}):
        restaurants_collection.insert_one(data)

# 메뉴데이터 db에 삽입
for data in test_menu_data:
    if not menus_collection.find_one({"menu_id": data["menu_id"]}):
        menus_collection.insert_one(data)
# mongodb에 메뉴 삽입

##################################################
# Flask 실행
##################################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

                                                                                                                                                                                                                                                                                                                                                                   