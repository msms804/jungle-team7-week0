from flask import Flask, render_template, request, redirect, url_for, session
from datetime import timedelta
from bson import ObjectId  # ObjectId를 사용하기 위해 추가

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

    restaurants = list(restaurants_collection.find(query, {"_id": 0}))  # ObjectId 제거

    return render_template("main.html", restaurants=restaurants, selected_category=category, categories=categories)

##################################################
# 4) 로그아웃
##################################################
@app.route("/logout")
def logout():
    """
    수동 로그아웃. (30분 후 자동으로도 세션은 만료됨)
    """
    session.clear()
    return redirect(url_for("login"))


# MOCKDATA 삽입
test_data = [
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d11"),
        "name": "김밥천국",
        "address": "서울특별시 강남구 테헤란로 123",
        "category": "한식",
        "naver_url": "https://map.naver.com/v5/entry/place/123456",
        "likes": 120,
        "description": "저렴하고 다양한 한식 메뉴를 제공하는 분식집",
        "image_url": "https://example.com/images/kimbap.jpg"
    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d12"),
        "name": "짜장명가",
        "address": "서울특별시 마포구 양화로 456",
        "category": "중식",
        "naver_url": "https://map.naver.com/v5/entry/place/654321",
        "likes": 200,
        "description": "정통 짜장면과 탕수육이 인기 있는 중식당",
        "image_url": "https://example.com/images/jajangmyeon.jpg"
    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d13"),
        "name": "스시야",
        "address": "부산광역시 해운대구 해운대로 789",
        "category": "일식",
        "naver_url": "https://map.naver.com/v5/entry/place/789123",
        "likes": 300,
        "description": "싱싱한 회와 스시를 제공하는 일본식 초밥 전문점",
        "image_url": "https://example.com/images/sushi.jpg"
    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d14"),
        "name": "미스터 피자",
        "address": "대구광역시 중구 중앙대로 321",
        "category": "양식",
        "naver_url": "https://map.naver.com/v5/entry/place/321789",
        "likes": 150,
        "description": "다양한 토핑과 수제 도우가 특징인 피자 전문점",
        "image_url": "https://example.com/images/pizza.jpg"
    },
    {
        "restaurant_id": ObjectId("650f0c1e8a3b4a2d4c8e7d15"),
        "name": "육쌈냉면",
        "address": "서울특별시 종로구 종로3가 12",
        "category": "한식",
        "naver_url": "https://map.naver.com/v5/entry/place/987654",
        "likes": 180,
        "description": "숯불 고기와 함께 먹는 냉면 전문점",
        "image_url": "https://example.com/images/naengmyeon.jpg"
    }
]

# MongoDB에 데이터 삽입 (중복 방지: 같은 restaurant_id가 있는 경우 삽입 안 함)
for data in test_data:
    if not restaurants_collection.find_one({"restaurant_id": data["restaurant_id"]}):
        restaurants_collection.insert_one(data)



##################################################
# Flask 실행
##################################################
if __name__ == "__main__":
    app.run(debug=True)

                                                                                                                                                                                                                                                                                                                                                                   