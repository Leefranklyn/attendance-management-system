from service import login, logout
from domains.auth import auth_bp

auth_bp.route("/login", methods=["GET", "POST"])(login)
auth_bp.route("/logout")(logout)
