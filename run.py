from app import create_app, db
from app.models.models import User

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db, User=User)

if __name__ == "__main__":
    with app.app_context():
        from app.models.database import init_db, get_session, seed_sample_data
        init_db()
        session = get_session()
        seed_sample_data(session)
        session.close()
    app.run(debug=True, host="127.0.0.1", port=5000)
