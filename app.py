from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
from datetime import timedelta, datetime
from bson import ObjectId  # ObjectId를 사용하기 위해 추가
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options 
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pymongo
import urllib.parse
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
    page = int(request.args.get('page', 1))  # 첫 번째 페이지
    per_card = 6  # 한 번에 보여줄 데이터 개수



    categories = ["전체", "치킨", "한식", "카페/디저트", "중식", "버거/샌드위치", "분식", "회/초밥", "일식/돈가스", "기타"]
    query = {} if category == "전체" else {"category": category}

    # restaurants = list(restaurants_collection.find(query).skip((page - 1) * per_card).limit(per_card).sort("likes", -1))

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
    
    # 중복된 url 등록시
    existing_restaurant = restaurants_collection.find_one({"naver_url": naver_url})

    # 중복처리시 Parsing 없이 메인페이지로 리턴
    if existing_restaurant:
        return """
        <script>
          alert("이미 식당이 존재합니다.");
          window.location.href = "/list"  
        </script>
            """

    category = request.form.get('category') # 사용자 지정 카테고리

    print(f"Received category: {category}")
    print(f"Received naver_url: {naver_url}")
    parse_url(naver_url, category)

    
    return redirect(url_for('main'))  # 다른 페이지로 리디렉션하거나 결과를 처리


# 네이버 지도 API 활용 -> 경도, 위도 가져오기
def get_geoCode(address):
    # 네이버 클라우드 Maps Geocoding API를 사용하여 주소를 좌표로 변환
    client_id = "iund2fuwi7"  # 네이버 클라우드 API Access Key
    client_secret = "DwzFixhDkyWQF7XxO0dJ0eEaltG4cJuBdHOLMXKu"  # 네이버 클라우드 API Secret Key
    
    url = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    
    params = {
        "query": address  # 변환할 주소
    }
    
    headers = {
        "x-ncp-apigw-api-key-id": client_id,
        "x-ncp-apigw-api-key": client_secret,
        "Accept": "application/json"  # 응답 형식
    }
    
    # API 요청
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data['addresses']:
            # 첫 번째 결과의 좌표 반환
            lat = data['addresses'][0]['y']
            lon = data['addresses'][0]['x']
            return lat, lon
        else:
            print("주소를 찾을 수 없습니다.")
            return None
    else:
        print(f"API 호출 오류: {response.status_code}")
        return None

def create_directions_url(start_lat, start_lon, start_name, shop_name, address):
    """
    주소를 받아서 해당 주소에 대한 위도, 경도를 구하고
    네이버 길찾기 URL을 생성하는 함수
    """
    # 주소로부터 위도, 경도를 구하기
    end_coordinates = get_geoCode(address)
    
    if end_coordinates:
        end_lat, end_lon = end_coordinates
        
        # 네이버 길찾기 URL 형식 (주소와 이름을 URL 인코딩)
        start_name_encoded = urllib.parse.quote(start_name)  # 출발지 이름 URL 인코딩
        finish_name_encoded = urllib.parse.quote(shop_name)  # 도착지 이름 URL 인코딩

        directions_url = f"https://map.naver.com/p/directions/{start_lat},{start_lon},{start_name_encoded}/{end_lon},{end_lat},{finish_name_encoded}/-/walk"
        
        # 생성된 URL 출력
        print(f"생성된 네이버 길찾기 링크: {directions_url}")
        
        return directions_url
    else:
        # 좌표를 가져오지 못한 경우
        print("좌표를 가져올 수 없습니다.")
        return None


# WebDriver 인스턴스 생성 함수
def initialize_driver():
    # 새로운 WebDriver 세션 시작
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 창을 띄우지 않음
    chrome_options.add_argument("--disable-gpu")  # GPU 가속 비활성화
    chrome_options.add_argument("--no-sandbox")  # 보안 샌드박스 비활성화
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
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

    
    lat, lon = get_geoCode(address.text)
    map_url = create_directions_url(14160700.429881, 4476757.1008275, "크래프톤 정글캠퍼스", shop_name.text, address.text)

    restaurant_data = {
        "restaurant_id": ObjectId(),
        "name": shop_name.text,
        "address": address.text,
        "category": category,  # 카테고리는 수집된 카테고리 값으로 설정
        "naver_url": url,  # 입력된 네이버 URL
        "likes": 0,  # 좋아요 수는 크롤링 시점에서 수집할 수 없다면 0으로 기본값 설정
        "description": "설명 없음",  # 설명도 크롤링하거나 입력된 값으로 설정
        "image_url": img_src,  # 크롤링된 이미지 URL
        "map_url" : map_url, # 길찾기 링크
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



# mongodb에 메뉴 삽입

##################################################
# Flask 실행
##################################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

                                                                                                                                                                                                                                                                                                                                                                   