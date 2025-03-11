from flask import Flask, render_template, request, redirect, url_for, session
from datetime import timedelta
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
        user_id = request.form.get("user_id", "")
        user_pw = request.form.get("user_pw", "")

        # DB에서 해당 user_id 찾기
        user_data = users_collection.find_one({"user_id": user_id})

        if not user_data:
            # ID가 존재하지 않을 때
            return """
            <script>
              alert("ID가 없습니다. 회원가입 해주세요.");
              window.location.href = "/";
            </script>
            """
        else:
            # ID가 존재 → PW 비교
            if user_data.get("password") != user_pw:
                # PW 틀림
                return f"""
                <script>
                  alert("PW가 틀립니다.");
                  // ID는 유지하고 PW만 비워서 다시 로그인 페이지로
                  window.location.href = "/?retain_id={user_id}";
                </script>
                """
            else:
                # 로그인 성공
                session.clear()
                session.permanent = True  # 30분 타이머 적용
                session["_id"] = str(user_data.get("_id"))  # MongoDB _id(ObjectId)
                session["user_id"] = user_id
                return redirect(url_for("main"))

    else:
        # GET 요청 → 로그인 페이지 렌더링
        retain_id = request.args.get("retain_id", "")
        return render_template("login.html", retain_id=retain_id)

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
        user_id = request.form.get("user_id", "")
        user_pw = request.form.get("user_pw", "")
        user_pw_confirm = request.form.get("user_pw_confirm", "")

        # 1) ID 중복 확인
        existing_user = users_collection.find_one({"user_id": user_id})
        if existing_user:
            return f"""
            <script>
              alert("이미 존재하는 ID입니다.");
              window.location.href = "/signup?retain_id={user_id}";
            </script>
            """

        # 2) 비밀번호/확인 불일치
        if user_pw != user_pw_confirm:
            return f"""
            <script>
              alert("비밀번호가 동일하지 않습니다.");
              // ID는 유지하고, PW만 빈칸으로
              window.location.href = "/signup?retain_id={user_id}";
            </script>
            """

        # 위 조건을 통과하면 DB에 새 유저 정보 저장
        new_user = {
            "user_id": user_id,
            "password": user_pw
            # 필요하다면 추가 정보(이메일, 닉네임 등)도 저장 가능
        }
        inserted_id = users_collection.insert_one(new_user).inserted_id

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
        retain_id = request.args.get("retain_id", "")
        return render_template("signup.html", retain_id=retain_id)

##################################################
# 3) 메인 페이지 (로그인 성공 후)
##################################################
@app.route("/main")
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

    return render_template("main.html")

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

##################################################
# Flask 실행
##################################################
if __name__ == "__main__":
    app.run(debug=True)
                                                                                                                                                                                                                                                                                                                                                                   