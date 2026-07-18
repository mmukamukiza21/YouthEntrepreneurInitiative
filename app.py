from flask import Flask, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

db_user = os.getenv("DB_USER")
db_password = quote_plus(os.getenv("DB_PASSWORD"))
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---- Database Models ----

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class BusinessIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    lessons = db.relationship("Lesson", backref="course", cascade="all, delete-orphan", lazy=True)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content_type = db.Column(db.String(50), nullable=False)  # 'article' or 'video'
    body = db.Column(db.Text, nullable=True)                 # content for articles
    video_url = db.Column(db.String(500), nullable=True)     # embed link for videos


# ---- Routes ----

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        raw_password = request.form.get("password")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "<h2>That email is already registered. Try logging in instead.</h2>"

        hashed = generate_password_hash(raw_password)
        new_user = User(name=name, email=email, password_hash=hashed)
        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        raw_password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, raw_password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        else:
            return "<h2>Invalid email or password.</h2>"
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    return render_template("dashboard.html", user=user)


@app.route("/ideas")
def list_ideas():
    if "user_id" not in session:
        return redirect(url_for("login"))

    all_ideas = BusinessIdea.query.all()
    return render_template("business_ideas.html", ideas=all_ideas)


@app.route("/ideas/new", methods=["GET", "POST"])
def new_idea():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        idea = BusinessIdea(title=title, description=description, user_id=session["user_id"])
        db.session.add(idea)
        db.session.commit()

        return redirect(url_for("list_ideas"))

    return render_template("new_idea.html")


@app.route("/courses")
def list_courses():
    if "user_id" not in session:
        return redirect(url_for("login"))

    all_courses = Course.query.all()
    return render_template("courses.html", courses=all_courses)


@app.route("/courses/<int:course_id>", methods=["GET", "POST"])
def course_detail(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    course = Course.query.get_or_404(course_id)

    if request.method == "POST":
        title = request.form.get("title")
        content_type = request.form.get("content_type")
        body = request.form.get("body")
        video_url = request.form.get("video_url")

        new_lesson = Lesson(
            course_id=course.id,
            title=title,
            content_type=content_type,
            body=body if content_type == "article" else None,
            video_url=video_url if content_type == "video" else None
        )
        db.session.add(new_lesson)
        db.session.commit()
        return redirect(url_for("course_detail", course_id=course.id))

    active_lesson_id = request.args.get("lesson_id", type=int)
    active_lesson = None
    if active_lesson_id:
        active_lesson = Lesson.query.filter_by(id=active_lesson_id, course_id=course.id).first()
    if not active_lesson and course.lessons:
        active_lesson = course.lessons[0]

    return render_template("course_detail.html", course=course, active_lesson=active_lesson)


@app.route("/courses/new", methods=["GET", "POST"])
def new_course():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")

        course = Course(title=title, description=description, category=category)
        db.session.add(course)
        db.session.commit()

        return redirect(url_for("list_courses"))

    return render_template("new_course.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=3000)